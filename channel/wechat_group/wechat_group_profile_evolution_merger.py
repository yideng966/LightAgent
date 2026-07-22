"""Validated merger for LLM-derived room-scoped member profiles."""

from __future__ import annotations

import re
import time
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from channel.wechat_group.wechat_group_profile_service import WechatGroupProfileService


_AMBIGUOUS_ALIASES = {
    "all",
    "everyone",
    "here",
    "所有人",
    "全体成员",
    "全员",
    "大家",
    "各位",
    "群友",
}


class WechatGroupProfileEvolutionMerger:
    def __init__(
        self,
        profile_service: Optional[WechatGroupProfileService] = None,
        evolution_store=None,
        min_confidence: float = 0.72,
        alias_min_confidence: float = 0.85,
    ):
        self.profile_service = profile_service or WechatGroupProfileService()
        self.evolution_store = evolution_store
        self.min_confidence = float(min_confidence or 0.72)
        self.alias_min_confidence = float(alias_min_confidence or 0.85)

    def merge(
        self,
        room_id: str,
        run_id: str,
        payload: Dict[str, Any],
        room_name: str = "",
        member_by_token: Optional[Dict[str, str]] = None,
        evidence_by_token: Optional[Dict[str, List[str]]] = None,
    ) -> Dict[str, int]:
        room_text = str(room_id or "").strip()
        run_text = str(run_id or "").strip()
        if not room_text:
            raise ValueError("stable_room_id is required")
        if not run_text:
            raise ValueError("run_id is required")

        allowed_members = self._canonical_member_allowlist(room_text, member_by_token or {})
        allowed_evidence = {
            token: set(_normalize_string_list(values))
            for token, values in (evidence_by_token or {}).items()
            if token in allowed_members
        }
        profiles = [item for item in (payload or {}).get("profiles") or [] if isinstance(item, dict)]
        token_counts = Counter(str(item.get("member_token") or "").strip() for item in profiles)
        counters = {
            "profile_update_count": 0,
            "alias_update_count": 0,
            "role_hint_update_count": 0,
            "rejected_profile_count": 0,
            "rejected_claim_count": 0,
        }

        for item in profiles:
            token = str(item.get("member_token") or "").strip()
            if (
                not token
                or token_counts[token] != 1
                or token not in allowed_members
                or item.get("sender_id")
                or item.get("stable_member_id")
                or (item.get("room_id") and str(item.get("room_id")) != room_text)
            ):
                counters["rejected_profile_count"] += 1
                continue

            evidence_allowlist = allowed_evidence.get(token, set())
            aliases, rejected_aliases = self._accepted_items(
                item.get("aliases"),
                "alias",
                self.alias_min_confidence,
                evidence_allowlist,
            )
            role_hints, rejected_roles = self._accepted_items(
                item.get("role_hints"),
                "role_hint",
                self.min_confidence,
                evidence_allowlist,
            )
            interests, rejected_interests = self._accepted_items(
                item.get("interests"),
                "interest",
                self.min_confidence,
                evidence_allowlist,
            )
            common_terms, rejected_terms = self._accepted_items(
                item.get("common_terms"),
                "common_term",
                self.min_confidence,
                evidence_allowlist,
            )
            catchphrases, rejected_catchphrases = self._accepted_items(
                item.get("catchphrases"),
                "catchphrase",
                self.min_confidence,
                evidence_allowlist,
            )
            speak_styles, rejected_styles = self._accepted_items(
                [item.get("speak_style")] if item.get("speak_style") else [],
                "speak_style",
                self.min_confidence,
                evidence_allowlist,
            )
            counters["rejected_claim_count"] += sum((
                rejected_aliases,
                rejected_roles,
                rejected_interests,
                rejected_terms,
                rejected_catchphrases,
                rejected_styles,
            ))

            accepted_claims = aliases + role_hints + interests + common_terms + catchphrases + speak_styles
            if not accepted_claims:
                continue

            member_id = allowed_members[token]
            existing = self.profile_service.get_profile(member_id, room_id=room_text) or {}
            fields: Dict[str, Any] = {
                "last_observed_at": int(time.time()),
            }
            if aliases and not existing.get("primary_nickname"):
                fields["primary_nickname"] = aliases[0]["value"]
            if role_hints:
                fields["role_hints"] = [claim["value"] for claim in role_hints]
            if interests:
                fields["interests"] = [claim["value"] for claim in interests]
            common_words = [claim["value"] for claim in common_terms + catchphrases]
            if common_words:
                fields["common_words"] = common_words
            if speak_styles:
                fields["speak_style"] = max(speak_styles, key=lambda claim: claim["confidence"])["value"]

            alias_rows = [
                {
                    "value": claim["value"],
                    "confidence": claim["confidence"],
                    "evidence_message_ids": claim["evidence_message_ids"],
                    "source_kind": "llm_evolution",
                }
                for claim in aliases
            ]
            evidence_ids = _dedupe([
                evidence_id
                for claim in accepted_claims
                for evidence_id in claim["evidence_message_ids"]
            ])
            result = self.profile_service.apply_evolution_profile(
                room_id=room_text,
                stable_member_id=member_id,
                fields=fields,
                aliases=alias_rows,
                claims=accepted_claims,
                run_id=run_text,
                evidence_message_ids=evidence_ids,
            )
            if not result:
                counters["rejected_profile_count"] += 1
                continue
            counters["profile_update_count"] += 1
            counters["alias_update_count"] += len(aliases)
            counters["role_hint_update_count"] += len(role_hints)

        return counters

    def _canonical_member_allowlist(self, room_id: str, member_by_token: Dict[str, str]) -> Dict[str, str]:
        result = {}
        for token, raw_member_id in member_by_token.items():
            token_text = str(token or "").strip()
            if not re.fullmatch(r"member_[0-9]{3,6}", token_text):
                continue
            member_id = self.profile_service.resolve_automatic_member_id(room_id, raw_member_id)
            if member_id:
                result[token_text] = member_id
        return result

    @staticmethod
    def _accepted_items(
        value: Any,
        dimension: str,
        threshold: float,
        evidence_allowlist: set,
    ) -> Tuple[List[Dict[str, Any]], int]:
        accepted = []
        rejected = 0
        seen = set()
        for raw in value or []:
            if not isinstance(raw, dict):
                rejected += 1
                continue
            text = _normalize_claim_value(raw.get("value"), dimension)
            confidence = _to_float(raw.get("confidence"), 0)
            evidence_ids = _normalize_string_list(raw.get("evidence_message_ids"))
            if (
                not text
                or confidence < threshold
                or not evidence_ids
                or any(evidence_id not in evidence_allowlist for evidence_id in evidence_ids)
                or (dimension == "alias" and _is_ambiguous_alias(text))
            ):
                rejected += 1
                continue
            key = text.casefold()
            if key in seen:
                continue
            seen.add(key)
            accepted.append({
                "dimension": dimension,
                "value": text,
                "confidence": min(confidence, 1.0),
                "evidence_message_ids": evidence_ids,
                "source_kind": "llm_evolution",
            })
        return accepted, rejected


def _is_ambiguous_alias(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return not text or text in _AMBIGUOUS_ALIASES


def _normalize_claim_value(value: Any, dimension: str) -> str:
    text = re.sub(r"<[^>]{0,200}>", " ", str(value or "").strip())
    text = re.sub(r"\s+", " ", text)
    limit = 300 if dimension == "speak_style" else 120
    if dimension in {"alias", "common_term", "catchphrase"}:
        limit = 80
    return text[:limit]


def _normalize_string_list(value: Any) -> List[str]:
    if value is None:
        items = []
    elif isinstance(value, list):
        items = value
    else:
        items = str(value).replace("\n", ",").split(",")
    return _dedupe([str(item or "").strip() for item in items])


def _dedupe(values: List[str]) -> List[str]:
    result = []
    for value in values or []:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def _to_float(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except Exception:
        return fallback
