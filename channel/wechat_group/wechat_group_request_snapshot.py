"""Immutable request snapshot shared by WeChat group context consumers."""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any, Dict, Optional, Tuple
from uuid import uuid4

from agent.memory import get_conversation_store
from channel.wechat_group.wechat_group_context_policy import (
    WechatGroupContextPolicy,
    WechatGroupContextPolicyDecision,
)
from channel.wechat_group.wechat_group_timeline_service import (
    RoomRevision,
    WechatGroupTimelineService,
    WechatGroupTimelineSnapshot,
)


@dataclass(frozen=True)
class WechatGroupRequestSnapshot:
    request_id: str
    stable_room_id: str
    stable_member_id: str
    current_message_id: str
    current_created_at: int
    context_policy: WechatGroupContextPolicyDecision
    timeline: WechatGroupTimelineSnapshot
    owner_session_id: str = ""
    thread_id: str = ""
    thread_action: str = ""
    included_source_event_ids: Tuple[str, ...] = ()
    excluded_source_event_ids: Tuple[str, ...] = ()
    diagnostics: Dict[str, Any] = field(default_factory=dict)

    def recent_block(self, after_revision: Optional[RoomRevision] = None) -> str:
        return self.timeline.render_recent_block(
            max_chars=self.context_policy.recent_max_chars,
            after_revision=after_revision,
        )


class WechatGroupRequestSnapshotFactory:
    def __init__(self, archive, store=None, context_policy=None):
        self.archive = archive
        self.store = store
        self.context_policy = context_policy or WechatGroupContextPolicy()
        self.timeline_service = WechatGroupTimelineService(archive)

    def build(
        self,
        msg,
        text: str,
        trigger_source: str,
        is_free_reply: bool,
        owner_session_id: str = "",
        thread_id: str = "",
        thread_action: str = "",
        request_id: str = "",
        required_context_mode: str = "",
    ) -> WechatGroupRequestSnapshot:
        try:
            current_created_at = int(getattr(msg, "create_time", 0) or 0)
        except (TypeError, ValueError):
            current_created_at = 0
        stable_room_id = str(
            getattr(msg, "wechat_group_stable_room_id", "")
            or getattr(msg, "stable_room_id", "")
            or getattr(msg, "other_user_id", "")
            or ""
        ).strip()
        stable_member_id = str(
            getattr(msg, "wechat_group_stable_member_id", "")
            or getattr(msg, "stable_member_id", "")
            or getattr(msg, "actual_user_id", "")
            or ""
        ).strip()
        policy = self.context_policy.resolve(
            text,
            trigger_source=trigger_source,
            is_free_reply=is_free_reply,
            is_quote_self=bool(getattr(msg, "is_quote_self", False)),
            message_type=str(getattr(msg, "message_type", "text") or "text"),
            required_context_mode=required_context_mode,
        )
        excluded = []
        if thread_action == "resume_thread" and owner_session_id and thread_id:
            store = self.store or get_conversation_store()
            excluded = store.get_thread_source_event_ids(owner_session_id, thread_id)
        timeline = self.timeline_service.snapshot(
            stable_room_id,
            current_message_id=str(getattr(msg, "msg_id", "") or ""),
            limit=policy.recent_limit,
            minutes=policy.recent_minutes,
            now=current_created_at or int(time.time()),
            excluded_source_event_ids=excluded,
        )
        timeline_event_count = len(timeline.events)
        member_events = [
            event
            for event in timeline.events
            if event.source_type == "inbound" and event.actor_type == "member"
        ]
        timeline = WechatGroupTimelineSnapshot(
            stable_room_id=timeline.stable_room_id,
            revision=timeline.revision,
            events=member_events,
        )
        included = tuple(
            event.source_event_id
            for event in timeline.events
            if event.source_event_id
        )
        excluded_ids = tuple(
            str(item or "").strip()
            for item in excluded
            if str(item or "").strip()
        )
        return WechatGroupRequestSnapshot(
            request_id=str(request_id or uuid4().hex),
            stable_room_id=stable_room_id,
            stable_member_id=stable_member_id,
            current_message_id=str(getattr(msg, "msg_id", "") or ""),
            current_created_at=current_created_at,
            context_policy=policy,
            timeline=timeline,
            owner_session_id=str(owner_session_id or ""),
            thread_id=str(thread_id or ""),
            thread_action=str(thread_action or ""),
            included_source_event_ids=included,
            excluded_source_event_ids=excluded_ids,
            diagnostics={
                "context_mode": policy.mode,
                "policy_reason": policy.reason,
                "timeline_event_count": timeline_event_count,
                "included_source_event_count": len(included),
                "excluded_thread_event_count": len(excluded_ids),
                "room_revision": timeline.revision.to_dict(),
            },
        )
