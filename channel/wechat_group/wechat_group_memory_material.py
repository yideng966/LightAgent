"""Build strictly room-scoped, sanitized material for group memory Dream."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List
from urllib.parse import urlsplit, urlunsplit

from channel.wechat_group.wechat_group_archive import WechatGroupArchive
from channel.wechat_group.wechat_group_transport import project_wechat_message_type


_URL_PATTERN = re.compile(r"https?://[^\s<>'\"]+", re.I)
_WINDOWS_PATH_PATTERN = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]+[^\s]+")
_UNIX_PATH_PATTERN = re.compile(r"(?<![A-Za-z0-9])/(?:home|root|Users|etc|var|opt|app)/[^\s]+", re.I)
_SECRET_PATTERN = re.compile(
    r"(?i)(?:api[_-]?key|access[_-]?token|secret|password|passwd|authorization)\s*[:=]"
)
_BASE64_PATTERN = re.compile(r"(?<![A-Za-z0-9+/])[A-Za-z0-9+/]{160,}={0,2}(?![A-Za-z0-9+/])")


@dataclass(frozen=True)
class WechatGroupMemoryMaterialBatch:
    stable_room_id: str
    batch_start_row_id: int
    batch_end_row_id: int
    scanned_count: int
    messages: List[Dict[str, Any]]
    evidence_message_ids: List[str]

    @property
    def eligible_count(self) -> int:
        return len(self.messages)

    @property
    def filtered_count(self) -> int:
        return max(int(self.scanned_count or 0) - len(self.messages), 0)


class WechatGroupMemoryMaterialBuilder:
    def __init__(self, archive: WechatGroupArchive):
        self.archive = archive

    def build(
        self,
        stable_room_id: str,
        *,
        after_row_id: int,
        limit: int,
        window_minutes: int,
        through_row_id: int = 0,
    ) -> WechatGroupMemoryMaterialBatch:
        room_id = str(stable_room_id or "").strip()
        if not room_id:
            raise ValueError("stable_room_id is required")
        rows = self.archive.get_text_messages_after_row_id(
            room_id,
            after_row_id,
            limit=limit,
            window_minutes=window_minutes,
            through_row_id=through_row_id,
        )
        speaker_tokens: Dict[str, str] = {}
        messages: List[Dict[str, Any]] = []
        evidence_ids: List[str] = []
        for row in rows:
            if project_wechat_message_type(
                row.get("message_type") or "text",
                row.get("text"),
            ) != "text":
                continue
            text = sanitize_group_memory_text(row.get("text"))
            message_id = str(row.get("message_id") or "").strip()
            if not text or not message_id:
                continue
            member_key = str(
                row.get("stable_member_id")
                or row.get("sender_id")
                or row.get("runtime_sender_id")
                or f"unknown:{row.get('id', '')}"
            )
            token = speaker_tokens.setdefault(
                member_key,
                f"speaker_{len(speaker_tokens) + 1:03d}",
            )
            messages.append({
                "message_id": message_id,
                "speaker_token": token,
                "created_at": int(row.get("created_at") or 0),
                "text": text,
            })
            evidence_ids.append(message_id)

        batch_end = int(rows[-1].get("id") or after_row_id) if rows else int(after_row_id or 0)
        return WechatGroupMemoryMaterialBatch(
            stable_room_id=room_id,
            batch_start_row_id=int(after_row_id or 0),
            batch_end_row_id=batch_end,
            scanned_count=len(rows),
            messages=messages,
            evidence_message_ids=evidence_ids,
        )


def sanitize_group_memory_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text or len(text) > 4000:
        return ""
    lowered = text.lower()
    if "<msg" in lowered or "<?xml" in lowered or "<appmsg" in lowered:
        return ""
    text = _URL_PATTERN.sub(_strip_url_query, text)
    if _WINDOWS_PATH_PATTERN.search(text) or _UNIX_PATH_PATTERN.search(text):
        return ""
    if _SECRET_PATTERN.search(text) or _BASE64_PATTERN.search(text):
        return ""
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:1000]


def _strip_url_query(match: re.Match) -> str:
    raw = match.group(0)
    try:
        parsed = urlsplit(raw)
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    except Exception:
        return ""
