"""
Typed memory scopes for long-term memory isolation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class MemoryScope:
    """Normalized memory scope used by scoped memory search and writes."""

    scope_type: str
    scope_id: str = ""
    channel_type: str = ""
    subject_id: str = ""

    @classmethod
    def shared(cls) -> "MemoryScope":
        return cls(scope_type="shared")

    @classmethod
    def user(cls, user_id: str) -> "MemoryScope":
        user_id = _require_text("user_id", user_id)
        return cls(scope_type="user", scope_id=user_id, subject_id=user_id)

    @classmethod
    def session(cls, session_id: str, user_id: Optional[str] = None) -> "MemoryScope":
        session_id = _require_text("session_id", session_id)
        return cls(scope_type="session", scope_id=session_id, subject_id=(user_id or "").strip())

    @classmethod
    def wechat_group(cls, room_id: str) -> "MemoryScope":
        room_id = _require_text("room_id", room_id)
        return cls(scope_type="wechat_group", scope_id=room_id, channel_type="wechat_group")

    @classmethod
    def wechat_group_member_profile(cls, room_id: str, sender_id: str) -> "MemoryScope":
        room_id = _require_text("room_id", room_id)
        sender_id = _require_text("sender_id", sender_id)
        return cls(
            scope_type="wechat_group_member_profile",
            scope_id=room_id,
            channel_type="wechat_group",
            subject_id=sender_id,
        )

    @classmethod
    def wechat_group_member_profiles(cls, room_id: str) -> "MemoryScope":
        room_id = _require_text("room_id", room_id)
        return cls(
            scope_type="wechat_group_member_profile",
            scope_id=room_id,
            channel_type="wechat_group",
            subject_id="*",
        )

    @classmethod
    def from_legacy(
        cls,
        scope: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> "MemoryScope":
        scope = (scope or "shared").strip()
        if scope == "shared":
            return cls.shared()
        if scope == "user":
            return cls.user(user_id or "")
        if scope == "session":
            return cls.session(session_id or "", user_id=user_id)
        return cls(scope_type=scope, scope_id=(user_id or "").strip(), subject_id=(user_id or "").strip())


def _require_text(name: str, value: str) -> str:
    value = (value or "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value
