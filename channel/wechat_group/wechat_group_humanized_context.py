"""Humanized prompt context builder for the WeChat group channel."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

from channel.wechat_group.wechat_group_archive_context import (
    build_archive_evidence_block,
    build_local_extractive_summary_block,
)
from channel.wechat_group.wechat_group_context import build_safe_wechat_group_recent_context_block_from_rows
from channel.wechat_group.wechat_group_permissions import (
    build_wechat_group_admin_policy_block,
    is_wechat_group_admin,
)
from channel.wechat_group.wechat_group_persona import (
    build_wechat_group_persona_block,
    get_wechat_group_persona_config,
    should_skip_persona_for_message,
)
from channel.wechat_group.wechat_group_reference_policy import build_wechat_group_reference_policy_block
from channel.wechat_group.wechat_group_reply_policy import (
    build_wechat_group_addressee_policy_block,
    build_wechat_group_mention_verification_block,
    build_wechat_group_reply_policy_block,
)
from config import conf


def _scope_text(value) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def _stable_room_scope(msg) -> str:
    return (
        _scope_text(getattr(msg, "wechat_group_stable_room_id", ""))
        or _scope_text(getattr(msg, "stable_room_id", ""))
        or _scope_text(getattr(msg, "other_user_id", ""))
    )


def _stable_member_scope(msg) -> str:
    return (
        _scope_text(getattr(msg, "wechat_group_stable_member_id", ""))
        or _scope_text(getattr(msg, "stable_member_id", ""))
        or _scope_text(getattr(msg, "actual_user_id", ""))
    )


@dataclass
class WechatGroupHumanizedContextResult:
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class WechatGroupHumanizedContextBuilder:
    def __init__(self, channel):
        self.channel = channel

    def build(
        self,
        msg,
        user_content: str,
        trigger_source: str = "",
        include_quote: bool = True,
    ) -> WechatGroupHumanizedContextResult:
        text = str(user_content or "").strip()
        source = trigger_source or self.channel._infer_multimodal_trigger_source(msg)
        include_history = should_include_contextual_history(text, source)
        room_scope = _stable_room_scope(msg)
        member_scope = _stable_member_scope(msg)
        metadata: Dict[str, Any] = {
            "wechat_group_trigger_source": source,
            "wechat_group_contextual_history": include_history,
        }
        blocks = []

        identity_confirmed = getattr(msg, "wechat_group_identity_requires_confirmation", False) is not True
        admin_policy_block = build_wechat_group_admin_policy_block(
            room_scope,
            member_scope,
            identity_confirmed=identity_confirmed,
        )
        if admin_policy_block:
            metadata["wechat_group_is_admin"] = identity_confirmed and is_wechat_group_admin(room_scope, member_scope)
            blocks.append(admin_policy_block)

        if conf().get("wechat_group_reply_policy_enabled", True):
            blocks.append(build_wechat_group_mention_verification_block(msg, source))
            blocks.append(build_wechat_group_addressee_policy_block(msg, source))
            blocks.append(build_wechat_group_reply_policy_block(source))

        if should_skip_persona_for_message(msg):
            metadata["wechat_group_persona_skipped"] = True
        else:
            persona = get_wechat_group_persona_config()
            block = build_wechat_group_persona_block(persona["prompt"])
            if block:
                metadata["wechat_group_persona_preset_id"] = persona["preset_id"]
                blocks.append(block)

        if include_history and conf().get("wechat_group_archive_evidence_enabled", True):
            evidence_block = build_archive_evidence_block(
                self.channel.archive,
                room_id=room_scope,
                query=text,
                now=msg.create_time,
                days=conf().get("wechat_group_archive_evidence_days", 90),
                limit=conf().get("wechat_group_archive_evidence_limit", 48),
                recent_limit=conf().get("wechat_group_archive_evidence_recent_limit", 16),
                exclude_message_id=msg.msg_id,
            )
            if evidence_block:
                metadata["wechat_group_archive_evidence_injected"] = True
                blocks.append(evidence_block)

        if include_history and conf().get("wechat_group_local_summary_enabled", True):
            summary_block = build_local_extractive_summary_block(
                self.channel.archive,
                room_id=room_scope,
                now=msg.create_time,
                hours=conf().get("wechat_group_local_summary_hours", 24),
                limit=conf().get("wechat_group_local_summary_limit", 100),
                exclude_message_id=msg.msg_id,
            )
            if summary_block:
                metadata["wechat_group_local_summary_injected"] = True
                blocks.append(summary_block)

        focus = self.channel._resolve_focus_context(msg, text)
        if focus:
            metadata["wechat_group_focus"] = focus

        recent_block = self._build_recent_context_block(msg, focus, include_history)
        if recent_block:
            metadata["wechat_group_recent_context_injected"] = True
            blocks.append(recent_block)

        focus_block = self.channel._build_focus_context_block(focus)
        if focus_block:
            metadata["wechat_group_focus_injected"] = True
            blocks.append(focus_block)

        memory_block = self._normalize_memory_block(self.channel._build_memory_context_block(msg, text))
        if memory_block:
            metadata["wechat_group_memory_injected"] = True
            blocks.append(memory_block)

        style_block = self.channel._build_style_context_block(msg)
        if style_block:
            metadata["wechat_group_style_injected"] = True
            blocks.append(style_block)

        emotion_block = self.channel._build_emotion_context_block(msg)
        if emotion_block:
            metadata["wechat_group_emotion_injected"] = True
            blocks.append(emotion_block)

        if conf().get("wechat_group_reference_policy_enabled", True) or conf().get("wechat_group_link_policy_enabled", True):
            reference_block = build_wechat_group_reference_policy_block(
                msg,
                text,
                reference_enabled=conf().get("wechat_group_reference_policy_enabled", True),
                link_enabled=conf().get("wechat_group_link_policy_enabled", True),
            )
            if reference_block:
                metadata["wechat_group_reference_policy_injected"] = True
                blocks.append(reference_block)

        multimodal = self.channel._build_multimodal_context(
            msg,
            query=text,
            trigger_source=source,
            include_quote=include_quote,
        )
        metadata["wechat_group_multimodal_diagnostics"] = multimodal.get("diagnostics") or {}
        matched_images = multimodal.get("matched_images") or []
        if matched_images:
            metadata["wechat_group_multimodal_matched_images"] = matched_images
        multimodal_block = multimodal.get("block") or ""
        if multimodal_block:
            metadata["wechat_group_multimodal_injected"] = True
            blocks.append(multimodal_block)

        content = "{}\n\n{}".format("\n\n".join([block for block in blocks if block]), text).strip() if blocks else text
        return WechatGroupHumanizedContextResult(content=content, metadata=metadata)

    def _build_recent_context_block(self, msg, focus: Dict[str, Any], include_history: bool) -> str:
        if not conf().get("wechat_group_recent_context_enabled", True):
            return ""
        if not include_history and not (focus and focus.get("messages")):
            return ""
        rows = []
        used_focus_rows = False
        if focus and focus.get("messages"):
            rows = list(focus.get("messages") or [])
            used_focus_rows = True
        elif include_history:
            rows = self.channel.archive.get_recent_messages(
                _stable_room_scope(msg),
                limit=conf().get("wechat_group_recent_context_limit", 100),
                minutes=conf().get("wechat_group_recent_context_minutes", 1440),
                now=msg.create_time,
            )
        rows = [
            row for row in rows
            if row and str(row.get("message_id") or "") != str(getattr(msg, "msg_id", "") or "")
        ]
        if not rows and include_history and used_focus_rows:
            rows = self.channel.archive.get_recent_messages(
                _stable_room_scope(msg),
                limit=conf().get("wechat_group_recent_context_limit", 100),
                minutes=conf().get("wechat_group_recent_context_minutes", 1440),
                now=msg.create_time,
            )
            rows = [
                row for row in rows
                if row and str(row.get("message_id") or "") != str(getattr(msg, "msg_id", "") or "")
            ]
        return build_safe_wechat_group_recent_context_block_from_rows(rows)

    @staticmethod
    def _normalize_memory_block(block: str) -> str:
        text = str(block or "").strip()
        if not text:
            return ""
        text = text.replace("<wechat-group-knowledge>", "<wechat-group-memory>")
        text = text.replace("</wechat-group-knowledge>", "</wechat-group-memory>")
        return text


def should_include_contextual_history(user_content: str, trigger_source: str = "") -> bool:
    source = str(trigger_source or "").strip()
    if source in {"free_reply", "quote_self", "image_message"}:
        return True
    text = str(user_content or "").lower()
    markers = (
        "above", "earlier", "previous", "before", "just now", "summarize",
        "summary", "continue", "quote", "image", "picture", "photo", "link",
        "刚才", "上面", "前面", "之前", "谁说", "总结", "继续", "引用",
        "图片", "照片", "这张", "链接", "啥意思", "什么意思",
    )
    return any(marker in text for marker in markers)
