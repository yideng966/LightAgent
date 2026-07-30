"""Deterministic context-depth policy for WeChat group requests."""

from __future__ import annotations

import re
from dataclasses import dataclass

from channel.wechat_group.wechat_group_free_reply import is_contextual_short_question
from channel.wechat_group.wechat_group_free_reply_context import (
    is_explicit_bot_followup_text,
)


_RECALL_RE = re.compile(
    r"(?:总结|汇总|谁说|说过什么|之前聊|历史记录|聊天记录|昨天|前天|上周|回到之前|约定)"
)
_MINIMAL_COMMAND_RE = re.compile(r"^\s*(?:/|#)(?:cancel|清除|帮助|help|状态|status)\b", re.I)


@dataclass(frozen=True)
class WechatGroupContextPolicyDecision:
    mode: str
    recent_limit: int
    recent_minutes: int
    recent_max_chars: int
    include_archive_evidence: bool = False
    include_focus: bool = False
    include_rolling_summary: bool = False
    reason: str = ""


class WechatGroupContextPolicy:
    def resolve(
        self,
        text: str,
        trigger_source: str = "",
        is_free_reply: bool = False,
        is_quote_self: bool = False,
        message_type: str = "text",
        required_context_mode: str = "",
    ) -> WechatGroupContextPolicyDecision:
        value = str(text or "").strip()
        source = str(trigger_source or "").strip()
        required_mode = str(required_context_mode or "").strip().lower()
        if required_mode in {"minimal", "recent", "contextual", "recall"}:
            return self._decision_for_mode(required_mode, reason="intent_route")
        if _MINIMAL_COMMAND_RE.search(value):
            return self._decision_for_mode("minimal", reason="deterministic_command")
        if _RECALL_RE.search(value):
            return self._decision_for_mode("recall", reason="explicit_recall")
        if (
            is_quote_self
            or source in {"quote_self", "image_message"}
            or str(message_type or "text") != "text"
            or is_explicit_bot_followup_text(value)
            or is_contextual_short_question(value)
        ):
            return self._decision_for_mode(
                "contextual",
                reason="quote_media_or_followup",
            )
        return self._decision_for_mode(
            "recent",
            reason="ambient" if is_free_reply else "default_group_scene",
        )

    @staticmethod
    def _decision_for_mode(
        mode: str,
        reason: str,
    ) -> WechatGroupContextPolicyDecision:
        if mode == "minimal":
            return WechatGroupContextPolicyDecision(
                mode="minimal",
                recent_limit=4,
                recent_minutes=10,
                recent_max_chars=800,
                reason=reason,
            )
        if mode == "recall":
            return WechatGroupContextPolicyDecision(
                mode="recall",
                recent_limit=20,
                recent_minutes=24 * 60,
                recent_max_chars=4800,
                include_archive_evidence=True,
                include_focus=True,
                include_rolling_summary=True,
                reason=reason,
            )
        if mode == "contextual":
            return WechatGroupContextPolicyDecision(
                mode="contextual",
                recent_limit=24,
                recent_minutes=120,
                recent_max_chars=4800,
                include_focus=True,
                include_rolling_summary=True,
                reason=reason,
            )
        return WechatGroupContextPolicyDecision(
            mode="recent",
            recent_limit=12,
            recent_minutes=30,
            recent_max_chars=2400,
            include_rolling_summary=True,
            reason=reason,
        )
