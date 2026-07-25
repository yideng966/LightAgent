"""Evidence-bound topic and highlight generation for group reports."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from channel.wechat_group.wechat_group_identity_service import WechatGroupIdentityService
from channel.wechat_group.wechat_group_statistics_service import safe_report_message_text
from common.log import logger


_MODEL_BATCH_SIZE = 80
_MAX_TOPICS = 3
_MAX_HIGHLIGHTS = 3
_COMMENTARY_FALLBACK = "这句话把讨论说得很有画面。"
_SENSITIVE_COMMENTARY_MARKERS = (
    "政治", "宗教", "收入", "疾病", "残疾", "性取向", "色情", "歧视", "滚", "废物",
)
_STOPWORDS = {
    "这个", "那个", "我们", "你们", "他们", "然后", "就是", "可以", "一下", "已经",
    "还是", "因为", "所以", "如果", "但是", "没有", "一个", "今天", "明天", "现在",
    "the", "this", "that", "with", "from", "have", "will", "about", "https", "http",
}


class WechatGroupReportContentService:
    """Generate content only from server-issued, ephemeral evidence tokens."""

    def __init__(
        self,
        identity_service: Optional[WechatGroupIdentityService] = None,
        model_router: Any = None,
    ) -> None:
        self.identity_service = identity_service or WechatGroupIdentityService()
        self.model_router = model_router

    def build_content(
        self,
        base_report: Dict[str, Any],
        messages: Iterable[Dict[str, Any]],
        use_model: bool = True,
    ) -> Dict[str, Any]:
        """Attach up to three verified topics and highlights to report facts."""
        report = dict(base_report or {})
        candidates = self._build_candidates(report, messages)
        model_data = self._model_candidates(candidates) if use_model else {"topics": [], "highlights": []}
        topics = self._validated_topics(model_data.get("topics"), candidates)
        if not topics:
            topics = self._deterministic_topics(candidates)
        highlights = self._validated_highlights(model_data.get("highlights"), candidates)
        if not highlights:
            highlights = self._deterministic_highlights(candidates)
        report["topics"] = topics[:_MAX_TOPICS]
        report["topic_count"] = len(report["topics"])
        report["highlights"] = highlights[:_MAX_HIGHLIGHTS]
        return report

    def _build_candidates(
        self,
        report: Dict[str, Any],
        messages: Iterable[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        room_id = str(report.get("stable_room_id") or "").strip()
        candidates = []
        for message in messages or []:
            text = safe_report_message_text(message)
            if not text or text.startswith("["):
                continue
            row_id = int(message.get("id") or 0)
            if not row_id:
                continue
            member_id = str(message.get("stable_member_id") or "").strip()
            canonical = self._canonical_member_id(room_id, member_id)
            if not canonical:
                continue
            candidates.append({
                "message_token": f"m_{row_id}",
                "speaker_token": f"u_{canonical}",
                "speaker_member_id": canonical,
                "speaker_display_name": self._display_name(canonical, message.get("sender_nickname")),
                "text": text[:600],
                "created_at": int(message.get("created_at") or 0),
                "row_id": row_id,
            })
        return candidates

    def _model_candidates(self, candidates: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        router = self._get_model_router()
        if router is None or not candidates:
            return {"topics": [], "highlights": []}
        topic_rows: List[Dict[str, Any]] = []
        highlight_rows: List[Dict[str, Any]] = []
        for offset in range(0, len(candidates), _MODEL_BATCH_SIZE):
            batch = candidates[offset: offset + _MODEL_BATCH_SIZE]
            response = self._complete_batch(router, batch)
            if not response:
                continue
            topic_rows.extend(response.get("topics") or [])
            highlight_rows.extend(response.get("highlights") or [])
        return {"topics": topic_rows, "highlights": highlight_rows}

    def _get_model_router(self):
        if self.model_router is not None:
            return self.model_router
        try:
            from bridge.agent_bridge import TextModelRouter
            from bridge.bridge import Bridge

            self.model_router = TextModelRouter(Bridge())
            return self.model_router
        except Exception as exc:
            logger.debug("[wechat_group_report] text model router unavailable: %s", exc)
            return None

    def _complete_batch(self, router: Any, batch: List[Dict[str, Any]]) -> Dict[str, Any]:
        evidence = [
            {
                "message_token": row["message_token"],
                "speaker_token": row["speaker_token"],
                "text": row["text"],
                "created_at": row["created_at"],
            }
            for row in batch
        ]
        prompt = (
            "Summarize only the supplied WeChat group evidence. Return one JSON object with "
            "topics (max 3: title, summary, evidence_tokens) and highlights (max 3: "
            "message_token, speaker_token, commentary). Never invent tokens, people, messages, "
            "URLs, or facts. Commentary must be friendly, non-insulting and non-sensitive.\n"
            + json.dumps(evidence, ensure_ascii=False, separators=(",", ":"))
        )
        try:
            result = router.complete(
                [{"role": "user", "content": prompt}],
                purpose="wechat_group_report_content",
                system="Return valid JSON only.",
                max_tokens=1200,
            )
        except Exception as exc:
            logger.debug("[wechat_group_report] report content model failed: %s", exc)
            return {}
        if not isinstance(result, dict) or not result.get("success"):
            return {}
        content = str(result.get("content") or "").strip()
        try:
            parsed = json.loads(_extract_json_object(content))
        except Exception:
            return {}
        if not isinstance(parsed, dict) or _looks_like_model_error_envelope(parsed):
            return {}
        return parsed

    def _validated_topics(self, rows: Any, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not isinstance(rows, list):
            return []
        by_token = {row["message_token"]: row for row in candidates}
        result = []
        seen_sets = set()
        for raw in rows:
            if not isinstance(raw, dict):
                continue
            tokens = _unique_strings(raw.get("evidence_tokens"))
            evidence = [by_token[token] for token in tokens if token in by_token]
            if len(evidence) < 2:
                continue
            key = tuple(sorted(row["message_token"] for row in evidence))
            if key in seen_sets:
                continue
            seen_sets.add(key)
            topic = _topic_from_evidence(
                _clean_title(raw.get("title")), _clean_summary(raw.get("summary")), evidence
            )
            if topic:
                result.append(topic)
            if len(result) >= _MAX_TOPICS:
                break
        return result

    def _deterministic_topics(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        keyword_evidence: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for candidate in candidates:
            for keyword in _extract_keywords(candidate["text"]):
                keyword_evidence[keyword].append(candidate)
        ordered = sorted(
            keyword_evidence.items(),
            key=lambda item: (-len(item[1]), item[0]),
        )
        result = []
        consumed = set()
        for keyword, evidence in ordered:
            unique = _dedupe_evidence(evidence)
            if len(unique) < 2:
                continue
            tokens = {item["message_token"] for item in unique}
            if tokens <= consumed:
                continue
            result.append(_topic_from_evidence(keyword, f"围绕“{keyword}”展开了持续讨论。", unique))
            consumed.update(tokens)
            if len(result) >= _MAX_TOPICS:
                break
        if not result and len(candidates) >= 2:
            result.append(_topic_from_evidence(
                "群内讨论",
                "本周期内出现了多条可回溯的群内讨论。",
                candidates[:min(len(candidates), 20)],
            ))
        return [item for item in result if item]

    def _validated_highlights(self, rows: Any, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not isinstance(rows, list):
            return []
        by_token = {row["message_token"]: row for row in candidates}
        result = []
        used = set()
        for raw in rows:
            if not isinstance(raw, dict):
                continue
            token = str(raw.get("message_token") or "").strip()
            candidate = by_token.get(token)
            if not candidate or token in used:
                continue
            speaker_token = str(raw.get("speaker_token") or "").strip()
            if speaker_token and speaker_token != candidate["speaker_token"]:
                continue
            used.add(token)
            result.append(_highlight_from_candidate(candidate, _safe_commentary(raw.get("commentary"))))
            if len(result) >= _MAX_HIGHLIGHTS:
                break
        return result

    def _deterministic_highlights(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # Prefer substantive messages while spreading choices across members.
        ordered = sorted(
            candidates,
            key=lambda row: (-min(len(row["text"]), 240), row["created_at"], row["row_id"]),
        )
        result = []
        used_speakers = set()
        for candidate in ordered:
            speaker = candidate["speaker_member_id"]
            if speaker in used_speakers and len(used_speakers) < 3:
                continue
            used_speakers.add(speaker)
            result.append(_highlight_from_candidate(candidate, _COMMENTARY_FALLBACK))
            if len(result) >= _MAX_HIGHLIGHTS:
                break
        return result

    def _canonical_member_id(self, room_id: str, member_id: str) -> str:
        if not room_id or not member_id:
            return ""
        try:
            return str(self.identity_service.resolve_canonical_member_id(room_id, member_id) or "")
        except Exception:
            return ""

    def _display_name(self, member_id: str, fallback: Any) -> str:
        try:
            member = self.identity_service.store.get_member(member_id)
            name = str(member.get("display_name") or "").strip()
            if name:
                return name[:80]
        except Exception:
            pass
        name = re.sub(r"\s+", " ", str(fallback or "")).strip()
        return name[:80] or "未命名群友"


def _topic_from_evidence(title: str, summary: str, evidence: List[Dict[str, Any]]) -> Dict[str, Any]:
    evidence = _dedupe_evidence(evidence)
    if len(evidence) < 2:
        return {}
    timestamps = [int(row.get("created_at") or 0) for row in evidence]
    duration_minutes = max(0, (max(timestamps) - min(timestamps)) // 60) if timestamps else 0
    participants = len({row.get("speaker_member_id") for row in evidence if row.get("speaker_member_id")})
    heat = round(
        50 * min(len(evidence) / 20, 1)
        + 30 * min(participants / 10, 1)
        + 20 * min(duration_minutes / 180, 1)
    )
    return {
        "title": title or "群内讨论",
        "heat": int(heat),
        "summary": summary or "本周期内出现了多条相关讨论。",
        "evidence_message_count": len(evidence),
        "participant_count": participants,
        "duration_minutes": int(duration_minutes),
        "_evidence_tokens": [row["message_token"] for row in evidence],
    }


def _highlight_from_candidate(candidate: Dict[str, Any], commentary: str) -> Dict[str, Any]:
    return {
        "speaker_display_name": candidate["speaker_display_name"],
        "quote": candidate["text"][:280],
        "commentary": commentary or _COMMENTARY_FALLBACK,
        "_message_token": candidate["message_token"],
    }


def _dedupe_evidence(values: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result = []
    seen = set()
    for value in values:
        token = str(value.get("message_token") or "")
        if token and token not in seen:
            seen.add(token)
            result.append(value)
    return result


def _extract_keywords(text: str) -> List[str]:
    tokens = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z][A-Za-z0-9_-]{2,}", str(text or "").lower())
    result = []
    for token in tokens:
        if token in _STOPWORDS or token.isdigit() or token in result:
            continue
        result.append(token)
    return result[:8]


def _unique_strings(value: Any) -> List[str]:
    source = value if isinstance(value, list) else []
    result = []
    for item in source:
        text = str(item or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def _clean_title(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:80]


def _clean_summary(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:360]


def _safe_commentary(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not text or any(marker in text for marker in _SENSITIVE_COMMENTARY_MARKERS):
        return _COMMENTARY_FALLBACK
    return text[:160]


def _extract_json_object(value: str) -> str:
    text = str(value or "").strip()
    if text.startswith("{") and text.endswith("}"):
        return text
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start:end + 1]
    return "{}"


def _looks_like_model_error_envelope(value: Dict[str, Any]) -> bool:
    if value.get("error") is True:
        return True
    status = value.get("status_code") or value.get("status")
    try:
        return int(status) in {408, 429, 500, 502, 503, 504}
    except (TypeError, ValueError):
        return False
