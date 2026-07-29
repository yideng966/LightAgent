"""Non-destructive session and thread policy for WeChat group requests."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional
from uuid import uuid4

from agent.memory import get_conversation_store
from channel.wechat_group.wechat_group_free_reply_context import (
    is_explicit_bot_followup_text,
)
from config import conf


ACTION_NEW_THREAD = "new_thread"
ACTION_RESUME_THREAD = "resume_thread"
ACTION_OBSERVE_ONLY = "observe_only"


def wechat_group_context_engine_v2_enabled() -> bool:
    return str(
        conf().get("wechat_group_context_engine_mode", "legacy") or "legacy"
    ).lower() == "v2"


def resolve_wechat_group_session_scope() -> str:
    configured = str(conf().get("wechat_group_session_scope", "") or "").strip().lower()
    if configured in {"member", "room"}:
        return configured
    return "room" if conf().get("group_shared_session", False) is True else "member"


def build_wechat_group_owner_session_id(
    stable_room_id: str,
    stable_member_id: str,
    fallback_member_id: str = "",
) -> str:
    room_id = str(stable_room_id or "").strip()
    member_id = str(stable_member_id or fallback_member_id or "").strip()
    if not room_id:
        return ""
    if resolve_wechat_group_session_scope() == "room":
        return "wechat_group:{}".format(room_id)
    return "wechat_group:{}:{}".format(room_id, member_id)


@dataclass(frozen=True)
class WechatGroupSessionDecision:
    action: str
    owner_session_id: str
    thread_id: str = ""
    reason: str = ""
    history_mode: str = ""
    ttl_seconds: int = 900

    def to_context(self) -> Dict[str, Any]:
        result = asdict(self)
        result["wechat_group_session_action"] = result.pop("action")
        result["wechat_group_owner_session_id"] = result.pop("owner_session_id")
        result["wechat_group_thread_id"] = result.pop("thread_id")
        result["wechat_group_session_reason"] = result.pop("reason")
        result["wechat_group_agent_history_mode"] = result.pop("history_mode")
        result["wechat_group_thread_ttl_seconds"] = result.pop("ttl_seconds")
        return result


class WechatGroupSessionPolicy:
    def __init__(self, store=None):
        self.store = store

    def _store(self):
        if self.store is None:
            self.store = get_conversation_store()
        return self.store

    @staticmethod
    def _ttl_seconds() -> int:
        try:
            minutes = int(conf().get("wechat_group_thread_followup_ttl_minutes", 15) or 15)
        except (TypeError, ValueError):
            minutes = 15
        return min(max(minutes, 1), 1440) * 60

    def resolve(
        self,
        stable_room_id: str,
        stable_member_id: str,
        fallback_member_id: str = "",
        trigger_source: str = "",
        text: str = "",
        is_free_reply: bool = False,
        local_decision: Optional[Dict[str, Any]] = None,
        llm_decision: Optional[Dict[str, Any]] = None,
        is_quote_self: bool = False,
    ) -> WechatGroupSessionDecision:
        owner = build_wechat_group_owner_session_id(
            stable_room_id,
            stable_member_id,
            fallback_member_id=fallback_member_id,
        )
        ttl = self._ttl_seconds()
        local = local_decision if isinstance(local_decision, dict) else {}
        llm = llm_decision if isinstance(llm_decision, dict) else {}
        addressee = local.get("addressee") if isinstance(local.get("addressee"), dict) else {}
        target = str(llm.get("target") or addressee.get("target_kind") or "unknown")
        follows_bot = bool(
            llm.get("is_followup_to_bot") is True
            or addressee.get("is_followup_to_bot") is True
            or is_explicit_bot_followup_text(text)
        )

        if is_free_reply and target != "bot":
            return WechatGroupSessionDecision(
                action=ACTION_OBSERVE_ONLY,
                owner_session_id=owner,
                reason="ambient_not_addressed_to_bot",
                history_mode="observe_only",
                ttl_seconds=ttl,
            )

        should_resume = bool(
            is_quote_self
            or str(trigger_source or "").strip() == "quote_self"
            or follows_bot
        )
        active = self._store().get_active_thread(owner, ttl_seconds=ttl) if owner and should_resume else None
        if active and active.get("thread_id"):
            return WechatGroupSessionDecision(
                action=ACTION_RESUME_THREAD,
                owner_session_id=owner,
                thread_id=str(active["thread_id"]),
                reason="quote_or_explicit_followup",
                history_mode="interactive_session",
                ttl_seconds=ttl,
            )

        reason = "followup_without_active_thread" if should_resume else "independent_request"
        return WechatGroupSessionDecision(
            action=ACTION_NEW_THREAD,
            owner_session_id=owner,
            thread_id="wgt_{}".format(uuid4().hex),
            reason=reason,
            history_mode="fresh",
            ttl_seconds=ttl,
        )

    def ensure_thread(
        self,
        decision: WechatGroupSessionDecision,
        stable_room_id: str,
        stable_member_id: str,
        message_id: str = "",
    ) -> None:
        if decision.action == ACTION_OBSERVE_ONLY or not decision.thread_id:
            return
        if decision.action == ACTION_NEW_THREAD:
            self._store().create_thread(
                decision.owner_session_id,
                decision.thread_id,
                channel_type="wechat_group",
                stable_room_id=stable_room_id,
                stable_member_id=stable_member_id,
                root_message_id=message_id,
                ttl_seconds=decision.ttl_seconds,
                metadata={"reason": decision.reason},
            )
            return
        self._store().touch_thread(
            decision.owner_session_id,
            decision.thread_id,
            message_id=message_id,
            ttl_seconds=decision.ttl_seconds,
        )
