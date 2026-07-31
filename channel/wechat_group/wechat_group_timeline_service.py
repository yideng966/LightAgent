"""Canonical prompt-safe room timeline for the WeChat group channel."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Optional, Set

from channel.wechat_group.wechat_group_context import (
    is_wechat_group_transport_payload,
    sanitize_wechat_group_prompt_text,
)
from channel.wechat_group.wechat_group_transport import (
    project_wechat_media_semantic_text,
    project_wechat_message_type,
)


@dataclass(frozen=True)
class RoomRevision:
    inbound_cursor: int = 0
    assistant_cursor: int = 0

    def to_dict(self) -> Dict[str, int]:
        return asdict(self)


@dataclass(frozen=True)
class WechatGroupTimelineEvent:
    source_event_id: str
    source_type: str
    created_at: int
    actor_type: str
    actor_display_name: str
    safe_text: str
    message_type: str = "text"
    quote_actor_display_name: str = ""
    quote_excerpt: str = ""
    is_reply_to_assistant: bool = False
    is_directed_to_assistant: bool = False
    thread_id: str = ""

    def render(self) -> str:
        timestamp = ""
        try:
            timestamp = time.strftime("%m-%d %H:%M", time.localtime(self.created_at))
        except Exception:
            pass
        actor = self.actor_display_name or (
            "LightAgent" if self.actor_type == "assistant" else "群成员"
        )
        relation = ""
        if self.quote_actor_display_name or self.quote_excerpt:
            quote_actor = self.quote_actor_display_name or "群成员"
            quote_text = self.quote_excerpt or "[消息]"
            relation = "（回复 {}：{}）".format(quote_actor, quote_text)
        return "{} [{}] {}{}: {}".format(
            timestamp,
            self.message_type,
            actor,
            relation,
            self.safe_text,
        ).strip()


@dataclass(frozen=True)
class WechatGroupTimelineSnapshot:
    stable_room_id: str
    revision: RoomRevision
    events: List[WechatGroupTimelineEvent]

    def render_recent_block(
        self,
        max_chars: int = 4800,
        after_revision: Optional[RoomRevision] = None,
    ) -> str:
        limit = max(int(max_chars or 0), 200)
        selected: List[str] = []
        used = 0
        events = self.events
        if after_revision is not None:
            events = [
                event for event in events
                if _event_after_revision(event, after_revision)
            ]
        for event in reversed(events):
            line = event.render()
            if not line:
                continue
            addition = len(line) + (1 if selected else 0)
            if selected and used + addition > limit:
                break
            if not selected and addition > limit:
                line = line[:limit]
                addition = len(line)
            selected.append(line)
            used += addition
        if not selected:
            return ""
        selected.reverse()
        return (
            "<recent-wechat-group-transcript untrusted=\"true\">\n"
            + "\n".join(selected)
            + "\n</recent-wechat-group-transcript>"
        )


class WechatGroupTimelineService:
    def __init__(self, archive):
        self.archive = archive

    def snapshot(
        self,
        stable_room_id: str,
        current_message_id: str = "",
        limit: int = 12,
        minutes: int = 30,
        now: Optional[int] = None,
        excluded_source_event_ids: Optional[Iterable[str]] = None,
    ) -> WechatGroupTimelineSnapshot:
        scope = str(stable_room_id or "").strip()
        revision_data = self.archive.get_room_revision(scope)
        rows = self.archive.get_recent_conversation_messages(
            scope,
            limit=max(int(limit or 12), 1),
            minutes=max(int(minutes or 30), 1),
            now=now,
        )
        excluded: Set[str] = {
            str(item or "").strip()
            for item in (excluded_source_event_ids or [])
            if str(item or "").strip()
        }
        current_id = str(current_message_id or "").strip()
        events = []
        for row in rows or []:
            if current_id and str(row.get("message_id") or "") == current_id:
                continue
            event = self._project_event(row)
            if not event or event.source_event_id in excluded:
                continue
            events.append(event)
        return WechatGroupTimelineSnapshot(
            stable_room_id=scope,
            revision=RoomRevision(
                inbound_cursor=int(revision_data.get("inbound_cursor") or 0),
                assistant_cursor=int(revision_data.get("assistant_cursor") or 0),
            ),
            events=events,
        )

    def events_after_revision(
        self,
        stable_room_id: str,
        revision: Optional[RoomRevision] = None,
        limit: int = 200,
    ) -> List[WechatGroupTimelineEvent]:
        """读取双游标之后的事件，并统一执行 Prompt 安全投影。"""
        cursor = revision or RoomRevision()
        rows = self.archive.get_conversation_messages_after_revision(
            str(stable_room_id or "").strip(),
            inbound_cursor=cursor.inbound_cursor,
            assistant_cursor=cursor.assistant_cursor,
            limit=limit,
        )
        events = []
        for row in rows or []:
            event = self._project_event(row)
            if event is not None:
                events.append(event)
        return events

    @staticmethod
    def _project_event(row: Dict[str, Any]) -> Optional[WechatGroupTimelineEvent]:
        source_id = str(row.get("source_event_id") or "").strip()
        if not source_id:
            source_id = "{}:{}".format(
                "assistant" if row.get("is_bot") is True else "inbound",
                int(row.get("id") or 0),
            )
        is_bot = row.get("is_bot") is True
        raw_text = str(row.get("text") or "")
        msg_type = project_wechat_message_type(
            row.get("message_type") or "text",
            raw_text,
        )
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        semantic_text = project_wechat_media_semantic_text(
            msg_type,
            raw_text,
            metadata,
        )
        if semantic_text:
            safe_text = semantic_text
        elif is_wechat_group_transport_payload(raw_text):
            safe_text = "[media message]"
        elif msg_type != "text":
            safe_text = "[{} message]".format(msg_type)
        else:
            safe_text = sanitize_wechat_group_prompt_text(raw_text, 320)
        if not safe_text:
            return None

        quote = metadata.get("quote") if isinstance(metadata.get("quote"), dict) else {}
        quote_actor = sanitize_wechat_group_prompt_text(
            quote.get("sender_name") or quote.get("display_name") or "",
            80,
        )
        quote_excerpt = sanitize_wechat_group_prompt_text(
            quote.get("content") or quote.get("text") or "",
            120,
        )
        actor = (
            "LightAgent"
            if is_bot
            else sanitize_wechat_group_prompt_text(
                row.get("sender_nickname") or "群成员",
                80,
            )
        )
        is_quote_self = bool(metadata.get("is_quote_self"))
        return WechatGroupTimelineEvent(
            source_event_id=source_id,
            source_type="assistant" if is_bot else "inbound",
            created_at=int(row.get("created_at") or 0),
            actor_type="assistant" if is_bot else "member",
            actor_display_name=actor,
            safe_text=safe_text,
            message_type=msg_type,
            quote_actor_display_name=quote_actor,
            quote_excerpt=quote_excerpt,
            is_reply_to_assistant=is_quote_self,
            is_directed_to_assistant=bool(row.get("is_at") or is_quote_self),
            thread_id=str(row.get("thread_id") or "") if is_bot else "",
        )


def _event_after_revision(
    event: WechatGroupTimelineEvent,
    revision: RoomRevision,
) -> bool:
    try:
        source_type, raw_id = event.source_event_id.split(":", 1)
        row_id = int(raw_id)
    except Exception:
        return True
    if source_type == "assistant":
        return row_id > int(revision.assistant_cursor or 0)
    return row_id > int(revision.inbound_cursor or 0)
