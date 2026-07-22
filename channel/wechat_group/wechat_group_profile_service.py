"""Service layer for room-scoped WeChat group member profiles."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from channel.wechat_group.wechat_group_archive import WechatGroupArchive
from channel.wechat_group.wechat_group_profile_store import WechatGroupProfileStore
from channel.wechat_group.wechat_group_transport import is_wechat_transport_metadata_term


class WechatGroupProfileService:
    def __init__(
        self,
        store: Optional[WechatGroupProfileStore] = None,
        archive: Optional[WechatGroupArchive] = None,
        identity_service: Any = None,
    ):
        self.store = store or WechatGroupProfileStore()
        self.archive = archive or WechatGroupArchive()
        if identity_service is None:
            from channel.wechat_group.wechat_group_identity_service import WechatGroupIdentityService

            identity_service = WechatGroupIdentityService()
        self.identity_service = identity_service

    def get_profile(self, sender_id: str, room_id: str = "") -> Optional[Dict[str, Any]]:
        room_text = str(room_id or "").strip()
        member_id = self.resolve_canonical_member_id(room_text, sender_id)
        if not room_text or not member_id:
            return None
        profile = self.store.get_profile(room_text, member_id)
        return self._attach_names_and_content(profile) if profile else None

    def list_profiles(
        self,
        query: str = "",
        limit: int = 20,
        room_id: str = "",
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        room_text = str(room_id or "").strip()
        if not room_text:
            return []
        return [
            self._attach_names_and_content(row)
            for row in self.store.list_profiles(room_text, query=query, limit=limit, offset=offset)
        ]

    def count_profiles(self, room_id: str, query: str = "") -> int:
        room_text = str(room_id or "").strip()
        return self.store.count_profiles(room_text, query=query) if room_text else 0

    def upsert_manual_profile(
        self,
        sender_id: str,
        primary_nickname: str,
        speak_style: str,
        interests: List[str],
        common_words: List[str],
        aliases: List[str],
        room_id: str = "",
        room_name: str = "",
    ) -> Dict[str, Any]:
        room_text = _require_stable_room_id(room_id)
        member_id = self._require_canonical_member(room_text, sender_id)
        normalized_primary = _normalize_display_name(primary_nickname, member_id)
        normalized_aliases = _normalize_aliases(aliases, member_id, normalized_primary)
        self.store.apply_manual_update(
            room_text,
            member_id,
            fields={
                "primary_nickname": normalized_primary,
                "speak_style": str(speak_style or "").strip(),
                "interests": _normalize_list(interests),
                "common_words": _normalize_list(common_words),
            },
            primary_nickname=normalized_primary,
            aliases=normalized_aliases,
        )
        return self.get_profile(member_id, room_id=room_text) or {}

    def merge_learned_profile(
        self,
        sender_id: str,
        primary_nickname: str,
        aliases: List[str],
        speak_style: str,
        interests: List[str],
        common_words: List[str],
        msg_delta: int,
        activity_delta: int,
        intimacy_delta: int,
        room_id: str,
        room_name: str,
        last_seen_at: int,
    ) -> Dict[str, Any]:
        room_text = _require_stable_room_id(room_id)
        member_id = self.resolve_canonical_member_id(room_text, sender_id)
        if not member_id or not self._automatic_subject_allowed(room_text, member_id):
            return {}
        existing = self.store.get_profile(room_text, member_id) or {}
        normalized_primary = _choose_primary_nickname(
            primary_nickname,
            member_id,
            existing.get("primary_nickname"),
            aliases,
        )
        normalized_aliases = _normalize_aliases(aliases, member_id, normalized_primary)
        profile = self.store.upsert_profile(
            stable_room_id=room_text,
            stable_member_id=member_id,
            primary_nickname=normalized_primary,
            speak_style=str(speak_style or "").strip(),
            interests=_normalize_list(interests),
            common_words=_normalize_list(common_words),
            msg_count=int(existing.get("msg_count") or 0) + max(int(msg_delta or 0), 0),
            activity_score=int(existing.get("activity_score") or 0) + max(int(activity_delta or 0), 0),
            intimacy_score=int(existing.get("intimacy_score") or 0) + max(int(intimacy_delta or 0), 0),
            first_observed_at=int(existing.get("first_observed_at") or last_seen_at or 0),
            last_observed_at=max(int(existing.get("last_observed_at") or 0), int(last_seen_at or 0)),
        )
        if normalized_primary:
            self.store.upsert_name_record(
                room_text,
                member_id,
                normalized_primary,
                source_kind="observed",
                confidence=0.8,
                last_seen_at=last_seen_at,
            )
        self._record_aliases(
            room_text,
            member_id,
            normalized_aliases,
            last_seen_at=last_seen_at,
            source_kind="learning",
            confidence=0.8,
        )
        return self.get_profile(member_id, room_id=room_text) or profile

    def merge_learned_aliases(
        self,
        sender_id: str,
        aliases: List[str],
        room_id: str,
        room_name: str,
        last_seen_at: int,
        source_kind: str = "learning",
    ) -> Dict[str, Any]:
        room_text = _require_stable_room_id(room_id)
        member_id = self.resolve_canonical_member_id(room_text, sender_id)
        if not member_id or not self._automatic_subject_allowed(room_text, member_id):
            return {}
        normalized_aliases = _normalize_aliases(aliases, member_id)
        if not normalized_aliases:
            return self.get_profile(member_id, room_id=room_text) or {}
        existing = self.store.get_profile(room_text, member_id) or {}
        profile = self.store.upsert_profile(
            stable_room_id=room_text,
            stable_member_id=member_id,
            primary_nickname=_choose_primary_nickname(
                "",
                member_id,
                existing.get("primary_nickname"),
                normalized_aliases,
            ),
            first_observed_at=int(existing.get("first_observed_at") or last_seen_at or 0),
            last_observed_at=max(int(existing.get("last_observed_at") or 0), int(last_seen_at or 0)),
        )
        self._record_aliases(
            room_text,
            member_id,
            normalized_aliases,
            last_seen_at=last_seen_at,
            source_kind=source_kind or "learning",
            confidence=0.9 if source_kind == "llm_evolution" else 0.8,
        )
        return self.get_profile(member_id, room_id=room_text) or profile

    def apply_evolution_profile(
        self,
        room_id: str,
        stable_member_id: str,
        fields: Dict[str, Any],
        aliases: List[Dict[str, Any]],
        claims: List[Dict[str, Any]],
        run_id: str,
        evidence_message_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        room_text = _require_stable_room_id(room_id)
        member_id = self.resolve_canonical_member_id(room_text, stable_member_id)
        if not member_id or not self._automatic_subject_allowed(room_text, member_id):
            return {}
        current = self.store.get_profile(room_text, member_id) or {}
        update = dict(fields or {})
        update["interests"] = _dedupe(list(current.get("interests") or []) + _normalize_list(update.get("interests")))
        update["common_words"] = _dedupe(list(current.get("common_words") or []) + _normalize_list(update.get("common_words")))
        update["role_hints"] = _dedupe(list(current.get("role_hints") or []) + _normalize_list(update.get("role_hints")))
        update["last_observed_at"] = max(
            int(current.get("last_observed_at") or 0),
            int(update.get("last_observed_at") or 0),
        )
        result = self.store.apply_evolution_update(
            room_text,
            member_id,
            fields=update,
            aliases=aliases,
            claims=claims,
            run_id=run_id,
            evidence_message_ids=evidence_message_ids,
        )
        return self._attach_names_and_content(result) if result else {}

    def confirm_member_redirect(
        self,
        room_id: str,
        old_stable_member_id: str,
        canonical_stable_member_id: str,
        actor: str = "",
        reason: str = "",
    ) -> Dict[str, Any]:
        room_text = _require_stable_room_id(room_id)
        if self.identity_service is None:
            raise ValueError("identity service is required for member redirect")
        canonical = self.identity_service.confirm_member_redirect(
            room_text,
            old_stable_member_id,
            canonical_stable_member_id,
            actor=actor,
            reason=reason,
        )
        self.store.merge_profile_subjects(room_text, old_stable_member_id, canonical)
        return self.get_profile(canonical, room_id=room_text) or {}

    def resolve_profiles_for_prompt(
        self,
        sender_id: str,
        mentioned_sender_ids: List[str],
        query: str,
        bot_sender_id: str = "",
        room_id: str = "",
    ) -> Dict[str, Any]:
        room_text = str(room_id or "").strip()
        speaker_member_id = self.resolve_canonical_member_id(room_text, sender_id)
        speaker_profile = self.get_profile(speaker_member_id, room_id=room_text) if speaker_member_id else None
        mentioned_profiles = []
        seen = set()
        for raw_id in mentioned_sender_ids or []:
            runtime_or_stable = str(raw_id or "").strip()
            if not runtime_or_stable or runtime_or_stable == str(bot_sender_id or "").strip():
                continue
            member_id = self.resolve_canonical_member_id(room_text, runtime_or_stable)
            if not member_id or member_id == speaker_member_id or member_id in seen:
                continue
            profile = self.get_profile(member_id, room_id=room_text)
            if profile:
                mentioned_profiles.append(profile)
                seen.add(member_id)

        return {
            "speaker_profile": speaker_profile,
            "mentioned_profiles": mentioned_profiles,
        }

    def resolve_canonical_member_id(self, room_id: str, sender_id: str) -> str:
        room_text = str(room_id or "").strip()
        sender_text = str(sender_id or "").strip()
        if not room_text or not sender_text:
            return ""
        member_id = sender_text
        if self.identity_service is not None:
            try:
                if not sender_text.startswith("wgm_"):
                    member_id = self.identity_service.resolve_runtime_member_in_stable_room(room_text, sender_text)
                if not member_id:
                    return ""
                member_id = self.identity_service.resolve_canonical_member_id(room_text, member_id)
                member = self.identity_service.store.get_member(member_id)
                if not member or str(member.get("stable_room_id") or "") != room_text:
                    return ""
            except Exception:
                return ""
        elif not sender_text.startswith("wgm_"):
            return ""
        return str(member_id or "").strip()

    def resolve_automatic_member_id(self, room_id: str, sender_id: str) -> str:
        room_text = str(room_id or "").strip()
        member_id = self.resolve_canonical_member_id(room_text, sender_id)
        if not member_id or not self._automatic_subject_allowed(room_text, member_id):
            return ""
        return member_id

    def _require_canonical_member(self, room_id: str, sender_id: str) -> str:
        member_id = self.resolve_canonical_member_id(room_id, sender_id)
        if not member_id:
            raise ValueError("stable_member_id is required and must belong to stable_room_id")
        return member_id

    def _automatic_subject_allowed(self, room_id: str, member_id: str) -> bool:
        if self.store.get_profile(room_id, member_id):
            return True
        if self.identity_service is None:
            return member_id.startswith("wgm_")
        try:
            member = self.identity_service.store.get_member(member_id)
        except Exception:
            return False
        if not member or str(member.get("stable_room_id") or "") != room_id:
            return False
        confidence = str(member.get("confidence") or "").strip()
        metadata = _metadata_dict(member.get("metadata"))
        if confidence in {"manual", "wechat_id"}:
            return True
        if str(metadata.get("wechat_id") or "").strip():
            return True
        return False

    def _record_aliases(
        self,
        room_id: str,
        member_id: str,
        aliases: List[str],
        last_seen_at: int,
        source_kind: str,
        confidence: float,
    ) -> None:
        for alias in _normalize_list(aliases):
            self.store.upsert_name_record(
                room_id,
                member_id,
                alias,
                source_kind=source_kind,
                confidence=confidence,
                last_seen_at=last_seen_at,
            )

    def _attach_names_and_content(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        result = dict(profile or {})
        room_id = str(result.get("stable_room_id") or "").strip()
        member_id = str(result.get("stable_member_id") or "").strip()
        records = self.store.list_name_records(room_id, member_id, limit=200)
        live_name = self._current_room_member_name(room_id, member_id)
        stored_primary = _normalize_display_name(result.get("primary_nickname"), member_id)
        manual_primary = _first_record_name([
            item for item in records
            if str(item.get("source_kind") or "") == "manual_primary"
        ])
        primary = manual_primary or stored_primary or live_name or _first_record_name(records)
        aliases = []
        for record in records:
            name = _normalize_display_name(record.get("display_name"), member_id)
            if name and name != primary and name not in aliases:
                aliases.append(name)
        result["sender_id"] = member_id
        result["room_id"] = room_id
        result["primary_nickname"] = primary
        result["aliases"] = aliases
        result["name_records"] = records
        result["room_summaries"] = [{
            "room_id": room_id,
            "room_name": self._resolve_room_name(room_id),
            "display_names": _dedupe(([primary] if primary else []) + aliases),
            "last_seen_at": int(result.get("last_observed_at") or 0),
            "name_count": len(records),
        }]
        result["last_seen_at"] = int(result.get("last_observed_at") or 0)
        result["content"] = self._format_profile_content(result)
        return result

    def _current_room_member_name(self, room_id: str, member_id: str) -> str:
        try:
            for row in self.archive.list_members(room_id, limit=500):
                stable_member_id = str(row.get("stable_member_id") or "").strip()
                if stable_member_id != member_id:
                    continue
                runtime_sender_id = str(row.get("runtime_sender_id") or row.get("sender_id") or "").strip()
                name = _normalize_display_name(row.get("sender_nickname"), runtime_sender_id or member_id)
                if name:
                    return name
        except Exception:
            return ""
        return ""

    def _resolve_room_name(self, room_id: str) -> str:
        try:
            return self.archive.find_room_name(room_id)
        except Exception:
            return ""

    @staticmethod
    def _format_profile_content(profile: Dict[str, Any]) -> str:
        reply_name = WechatGroupProfileService._choose_reply_name(profile)
        stored_common_words = list(profile.get("common_words") or [])
        common_words = [] if any(
            is_wechat_transport_metadata_term(item) for item in stored_common_words
        ) else [str(item) for item in stored_common_words]
        lines = [
            f"stable_member_id: {profile.get('stable_member_id', '')}",
            f"primary_nickname: {profile.get('primary_nickname', '')}",
            f"aliases: {', '.join(profile.get('aliases') or [])}",
            f"reply_name: {reply_name}",
            f"role_hints: {', '.join(profile.get('role_hints') or [])}",
            f"speak_style: {profile.get('speak_style', '')}",
            f"interests: {', '.join(profile.get('interests') or [])}",
            f"common_words: {', '.join(common_words)}",
            f"msg_count: {profile.get('msg_count', 0)}",
            f"activity_score: {profile.get('activity_score', 0)}",
            f"intimacy_score: {profile.get('intimacy_score', 0)}",
        ]
        return "\n".join(line for line in lines if not line.endswith(": "))

    @staticmethod
    def _choose_reply_name(profile: Dict[str, Any]) -> str:
        manual_primary_names = [
            str(item.get("display_name") or "").strip()
            for item in profile.get("name_records") or []
            if str(item.get("source_kind") or "") == "manual_primary"
        ]
        manual_aliases = [
            str(item.get("display_name") or "").strip()
            for item in profile.get("name_records") or []
            if str(item.get("source_kind") or "") == "manual"
        ]
        primary = str(profile.get("primary_nickname") or "").strip()
        for name in manual_primary_names + manual_aliases + [primary] + list(profile.get("aliases") or []):
            text = str(name or "").strip()
            if text:
                return text
        return ""


def _require_stable_room_id(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("stable_room_id is required")
    return text


def _normalize_list(value: Any) -> List[str]:
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


def _normalize_aliases(value: Any, sender_id: str, primary_nickname: str = "") -> List[str]:
    result = []
    primary = str(primary_nickname or "").strip()
    for item in _normalize_list(value):
        alias = _normalize_display_name(item, sender_id)
        if alias and alias != primary and alias not in result:
            result.append(alias)
    return result


def _choose_primary_nickname(primary_nickname: Any, sender_id: str, existing_primary: Any, aliases: Any) -> str:
    incoming = _normalize_display_name(primary_nickname, sender_id)
    if incoming:
        return incoming
    existing = _normalize_display_name(existing_primary, sender_id)
    if existing:
        return existing
    alias_list = _normalize_aliases(aliases, sender_id)
    return alias_list[0] if alias_list else ""


def _normalize_display_name(value: Any, sender_id: str = "") -> str:
    text = str(value or "").replace("\u2005", " ").replace("\xa0", " ").strip()
    text = re.sub(r"\s+", " ", text)
    if not text:
        return ""
    if text.startswith("@") and not _looks_like_raw_sender_name(text, sender_id):
        text = text[1:].strip()
    if _looks_like_raw_sender_name(text, sender_id):
        return ""
    return text


def _looks_like_raw_sender_name(value: Any, sender_id: str = "") -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    normalized = text.lstrip("@")
    sender_text = str(sender_id or "").strip()
    sender_normalized = sender_text.lstrip("@")
    if sender_text and text == sender_text:
        return True
    if sender_normalized and normalized == sender_normalized:
        return True
    if normalized.startswith(("wxid_", "wgm_")):
        return True
    if text.startswith("@") and re.fullmatch(r"[0-9A-Za-z_-]{12,}", normalized):
        return True
    return False


def _first_record_name(records: List[Dict[str, Any]]) -> str:
    for record in records or []:
        value = str(record.get("display_name") or "").strip()
        if value:
            return value
    return ""


def _metadata_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}
