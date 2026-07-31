"""Humanized prompt context builder for the WeChat group channel."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

from channel.wechat_group.wechat_group_archive_context import (
    build_archive_evidence_block,
)
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
from channel.wechat_group.wechat_group_request_snapshot import (
    WechatGroupRequestSnapshotFactory,
)
from channel.wechat_group.wechat_group_continuation_store import (
    WechatGroupContinuationStore,
)
from channel.wechat_group.wechat_group_rolling_summary import (
    WechatGroupRollingSummaryService,
)
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
        reply_mode: str = "",
        is_free_reply: bool = False,
        request_context=None,
    ) -> WechatGroupHumanizedContextResult:
        text = str(user_content or "").strip()
        source = trigger_source or self.channel._infer_multimodal_trigger_source(msg)
        route_details = (
            request_context.get("wechat_group_intent_route_details")
            if request_context else {}
        )
        if not isinstance(route_details, dict):
            route_details = {}
        factory = getattr(self.channel, "_wechat_group_snapshot_factory", None)
        if factory is None:
            factory = WechatGroupRequestSnapshotFactory(self.channel.archive)
            self.channel._wechat_group_snapshot_factory = factory
        snapshot = factory.build(
            msg,
            text,
            trigger_source=source,
            is_free_reply=bool(is_free_reply),
            owner_session_id=(
                request_context.get("wechat_group_owner_session_id")
                if request_context else ""
            ) or "",
            thread_id=(
                request_context.get("wechat_group_thread_id")
                if request_context else ""
            ) or "",
            thread_action=(
                request_context.get("wechat_group_session_action")
                if request_context else ""
            ) or "",
            request_id=(request_context.get("request_id") if request_context else "") or "",
            required_context_mode=str(
                route_details.get("required_context_mode") or ""
            ),
        )
        ambient_free_reply = bool(is_free_reply)
        room_scope = _stable_room_scope(msg)
        member_scope = _stable_member_scope(msg)
        metadata: Dict[str, Any] = {
            "wechat_group_trigger_source": source,
            "wechat_group_contextual_history": True,
        }
        metadata.update({
            "request_id": snapshot.request_id,
            "wechat_group_request_snapshot": snapshot,
            "wechat_group_context_mode": snapshot.context_policy.mode,
            "wechat_group_context_diagnostics": snapshot.diagnostics,
            "wechat_group_room_revision_before": snapshot.timeline.revision.to_dict(),
        })
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

        blocks.append(build_wechat_group_mention_verification_block(msg, source))
        blocks.append(build_wechat_group_addressee_policy_block(msg, source))
        blocks.append(build_wechat_group_reply_policy_block(source, reply_mode=reply_mode))

        if should_skip_persona_for_message(msg):
            metadata["wechat_group_persona_skipped"] = True
        else:
            persona = get_wechat_group_persona_config()
            block = build_wechat_group_persona_block(persona["prompt"])
            if block:
                metadata["wechat_group_persona_preset_id"] = persona["preset_id"]
                blocks.append(block)

        summary_revision = None
        summary_source_event_ids = ()
        if (
            snapshot
            and snapshot.context_policy.include_rolling_summary
            and conf().get("wechat_group_rolling_summary_enabled", True)
        ):
            summary_service = getattr(
                self.channel,
                "_wechat_group_rolling_summary_service",
                None,
            )
            if summary_service is None:
                summary_service = WechatGroupRollingSummaryService(self.channel.archive)
                self.channel._wechat_group_rolling_summary_service = summary_service
            get_state = getattr(summary_service, "get_prompt_context_state", None)
            if callable(get_state):
                summary_block, summary_state = get_state(
                    snapshot.stable_room_id,
                    now=msg.create_time,
                )
                summary_revision = summary_state.revision if summary_state else None
                summary_source_event_ids = (
                    summary_state.source_event_ids if summary_state else ()
                )
            else:
                summary_block, summary_revision = summary_service.get_prompt_context(
                    snapshot.stable_room_id,
                    now=msg.create_time,
                )
            if summary_block:
                metadata["wechat_group_rolling_summary_injected"] = True
                metadata["wechat_group_rolling_summary_revision"] = (
                    summary_revision.to_dict() if summary_revision else {}
                )
                blocks.append(summary_block)

        include_focus = snapshot.context_policy.include_focus if snapshot else True
        focus = (
            {}
            if ambient_free_reply or not include_focus
            else self.channel._resolve_focus_context(msg, text)
        )
        if focus:
            metadata["wechat_group_focus"] = focus

        recent_block = snapshot.recent_block(after_revision=summary_revision)
        if recent_block:
            metadata["wechat_group_recent_context_injected"] = True
            blocks.append(recent_block)

        excluded_evidence_sources = set(snapshot.included_source_event_ids)
        excluded_evidence_sources.update(snapshot.excluded_source_event_ids)
        excluded_evidence_sources.update(summary_source_event_ids)
        include_evidence = snapshot.context_policy.include_archive_evidence
        if (
            include_evidence
            and not ambient_free_reply
            and conf().get("wechat_group_archive_evidence_enabled", True)
        ):
            evidence_block = build_archive_evidence_block(
                self.channel.archive,
                room_id=room_scope,
                query=text,
                now=msg.create_time,
                days=conf().get("wechat_group_archive_evidence_days", 90),
                limit=12,
                exclude_message_id=msg.msg_id,
                exclude_source_event_ids=excluded_evidence_sources,
                max_chars=3200,
            )
            if evidence_block:
                metadata["wechat_group_archive_evidence_injected"] = True
                blocks.append(evidence_block)

        focus_block = self.channel._build_focus_context_block(focus)
        if focus_block:
            metadata["wechat_group_focus_injected"] = True
            blocks.append(focus_block)

        memory_block = self._normalize_memory_block(
            self.channel._build_memory_context_block(msg, text)
        )
        if memory_block:
            metadata["wechat_group_memory_injected"] = True
            blocks.append(memory_block)

        metadata["wechat_group_context_source_counts"] = {
            "recent": len(snapshot.included_source_event_ids),
            "summary": len(summary_source_event_ids),
            "thread_excluded": len(snapshot.excluded_source_event_ids),
            "archive_excluded": len(excluded_evidence_sources),
        }

        if (
            snapshot
            and snapshot.thread_action == "resume_thread"
            and conf().get(
                "wechat_group_tool_continuation_enabled",
                False,
            )
        ):
            continuation_store = getattr(
                self.channel,
                "_wechat_group_continuation_store",
                None,
            )
            if continuation_store is None:
                continuation_store = WechatGroupContinuationStore()
                self.channel._wechat_group_continuation_store = continuation_store
            continuation_block = continuation_store.get_prompt_block(
                snapshot.owner_session_id,
                snapshot.thread_id,
                snapshot.stable_room_id,
                snapshot.stable_member_id,
            )
            if continuation_block:
                metadata["wechat_group_continuation_injected"] = True
                blocks.append(continuation_block)

        style_block = self.channel._build_style_context_block(msg)
        if style_block:
            metadata["wechat_group_style_injected"] = True
            blocks.append(style_block)

        reference_block = build_wechat_group_reference_policy_block(
            msg,
            text,
            reference_enabled=True,
            link_enabled=True,
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

    @staticmethod
    def _normalize_memory_block(block: str) -> str:
        text = str(block or "").strip()
        if not text:
            return ""
        text = text.replace("<wechat-group-knowledge>", "<wechat-group-memory>")
        text = text.replace("</wechat-group-knowledge>", "</wechat-group-memory>")
        return text
