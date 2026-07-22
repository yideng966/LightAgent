"""Runtime helpers for WeChat group focus stacks."""

from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from channel.wechat_group.wechat_group_focus_store import WechatGroupFocusStore
from channel.wechat_group.wechat_group_transport import (
    is_wechat_transport_metadata_term,
    is_wechat_transport_xml,
    project_wechat_message_type,
)
from config import conf


CONTEXTUAL_TOKENS = (
    "刚才", "上面", "前面", "之前", "继续", "接着", "总结",
    "这张", "这个", "这条", "那张", "那个", "那条",
    "图里", "图上", "图片", "照片", "截图", "引用",
    "谁说", "聊天记录", "什么意思", "啥意思", "回到",
    "above", "earlier", "previous", "before", "summarize", "summary",
    "continue", "quote", "image", "picture", "photo",
)

RETURN_TOKENS = ("回到", "之前", "前面", "刚才", "继续", "return", "back", "previous", "earlier", "continue")

STOPWORDS = {
    "一个", "帮忙", "看看", "这个", "那个", "就是", "可以", "是不是",
    "什么", "怎么", "一下", "一下子", "我们", "你们", "他们", "gpt",
    "lightbot",
}


def normalize_query_text(text: str) -> str:
    value = str(text or "").replace("\u2005", " ").replace("\xa0", " ").strip()
    value = re.sub(r"^@\S+\s*", "", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def extract_focus_keywords(text: str, limit: int = 8) -> List[str]:
    value = normalize_query_text(text)
    value = re.sub(r"@?(?:wxid_[0-9A-Za-z_-]+|[0-9A-Za-z_-]{12,})", " ", value)
    tokens = re.findall(r"[0-9A-Za-z_-]{2,}|[\u4e00-\u9fff]{2,}", value)
    result = []
    for token in tokens:
        text = token.strip("@").strip()
        if not text:
            continue
        lowered = text.lower()
        if lowered in STOPWORDS or lowered.startswith("wxid_"):
            continue
        if text not in result:
            result.append(text)
        if len(result) >= max(int(limit or 8), 1):
            break
    return result


def is_contextual_request(msg, query: str) -> Tuple[bool, str]:
    quote = getattr(msg, "quote", {}) or {}
    if isinstance(quote, dict) and quote:
        return True, "quote"
    if getattr(msg, "is_quote_self", False) is True:
        return True, "quote_self"
    message_type = str(getattr(msg, "message_type", "") or "").lower()
    if message_type in ("image", "video", "file", "app"):
        return True, "media"
    value = normalize_query_text(query)
    for token in CONTEXTUAL_TOKENS:
        if token and token in value:
            return True, "contextual_keyword"
    return False, "standalone"


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


class WechatGroupFocusService:
    def __init__(self, store: Optional[WechatGroupFocusStore] = None):
        self.store = store or WechatGroupFocusStore()

    def list_active_focus(self, room_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        stack = self.store.load_stack(room_id)
        if limit is None:
            limit = int(conf().get("wechat_group_focus_stack_depth", 4) or 4)
        return list(reversed(stack))[: max(int(limit or 1), 1)]

    def search_focus(self, room_id: str, query: str = "", limit: int = 20) -> List[Dict[str, Any]]:
        return self.store.search_frames(room_id, query=query, limit=limit)

    def clear_room(self, room_id: str) -> int:
        return self.store.clear_room(room_id)

    def refresh_active_focus_from_archive(self, archive, room_id: str, now=None) -> Optional[Dict[str, Any]]:
        messages = self._recent_messages(archive, room_id, now=now)
        text_rows = [row for row in messages if str(row.get("text") or "").strip()]
        if not text_rows:
            return None
        latest = text_rows[-1]
        frame = self._frame_from_rows(room_id, text_rows, now=_coerce_timestamp(now))
        if not frame:
            return None
        frame["last_row_id"] = int(latest.get("id") or 0)
        self.store.save_stack(room_id, [frame])
        return self.store.load_stack(room_id)[-1] if self.store.load_stack(room_id) else frame

    def resolve_reply_focus(self, archive, msg, query: str, now: Optional[int] = None) -> Dict[str, Any]:
        room_id = _stable_room_scope(msg)
        if not room_id:
            return self._result("noop", "standalone", "missing_room", {}, [], [])
        ts = _coerce_timestamp(now if now is not None else getattr(msg, "create_time", None))
        contextual, reason = is_contextual_request(msg, query)
        mode = "contextual" if contextual else "standalone"
        stack = self.store.load_stack(room_id)
        recent_rows = self._recent_messages(archive, room_id, now=ts)
        current_row = self._find_current_row(archive, msg, recent_rows)
        stack = self._drop_stale_stack(room_id, stack, current_row)
        keywords = extract_focus_keywords(query, limit=8)

        if mode == "standalone":
            frame = {}
            event = "leaf"
            if len(keywords) >= int(conf().get("wechat_group_focus_min_keywords", 2) or 2):
                frame = self._new_frame(room_id, keywords, current_row, ts)
                stack = self._push_frame(stack, frame)
                self.store.save_stack(room_id, stack)
                self._append_current_ref(room_id, frame, current_row, msg, ts)
                event = "created" if len(stack) == 1 else "pushed"
            messages = [current_row] if current_row else []
            return self._result(event, mode, reason, frame, stack, messages)

        if not stack:
            frame = self._frame_from_rows(room_id, recent_rows, now=ts) or self._new_frame(room_id, keywords, current_row, ts)
            stack = [frame] if frame else []
            if stack:
                self.store.save_stack(room_id, stack)
                self._append_current_ref(room_id, frame, current_row, msg, ts)
            messages = self._limit_context_rows(recent_rows)
            return self._result("created" if frame else "noop", mode, reason, frame, stack, messages)

        matched_index = self._find_matching_frame_index(stack, keywords, include_top=True)
        event = "kept"
        if matched_index >= 0 and matched_index == len(stack) - 1:
            frame = dict(stack[-1])
            self._touch_frame(frame, keywords, current_row, ts)
            stack[-1] = frame
        elif matched_index >= 0 and self._has_return_intent(query):
            frame = dict(stack[matched_index])
            self._touch_frame(frame, keywords, current_row, ts)
            stack = stack[: matched_index + 1]
            stack[-1] = frame
            event = "returned"
        else:
            frame = self._new_frame(room_id, keywords, current_row, ts)
            stack = self._push_frame(stack, frame)
            event = "pushed"

        self.store.save_stack(room_id, stack)
        self._append_current_ref(room_id, frame, current_row, msg, ts)
        if event in ("created", "pushed"):
            messages = list(recent_rows or [])
        else:
            messages = self._focus_rows_for_frame(archive, room_id, frame, recent_rows)
        if current_row and not any(int(row.get("id") or 0) == int(current_row.get("id") or 0) for row in messages):
            messages.append(current_row)
        return self._result(event, mode, reason, frame, stack, self._limit_context_rows(messages))

    def build_prompt_block(self, focus: Dict[str, Any]) -> str:
        if not focus:
            return ""
        frame = focus.get("frame") or {}
        if not frame and focus.get("mode") == "standalone":
            return ""
        raw_title = frame.get("title") or _build_title_from_keywords(frame.get("topic") or [])
        raw_summary = frame.get("summary")
        frame_is_transport = is_wechat_transport_xml(raw_title) or is_wechat_transport_xml(raw_summary)
        topic = list(frame.get("topic") or [])
        topic_has_transport_metadata = any(
            is_wechat_transport_metadata_term(item) for item in topic
        )
        topic_has_transport_structure = any(
            str(item or "").strip().lower() in {"xml", "msg", "img", "emoji"}
            for item in topic
        )
        topic_is_transport = topic_has_transport_metadata and topic_has_transport_structure
        title = "[media message]" if topic_is_transport else _safe_focus_prompt_text(raw_title)
        keywords = []
        if not frame_is_transport and not topic_is_transport:
            for item in topic:
                keyword = _safe_focus_prompt_text(item)
                if is_wechat_transport_metadata_term(keyword):
                    continue
                if keyword and keyword not in keywords:
                    keywords.append(keyword)
        lines = [
            '<wechat-group-focus event="{}" mode="{}">'.format(
                _xml_attr(focus.get("event") or ""),
                _xml_attr(focus.get("mode") or ""),
            )
        ]
        if title:
            lines.append(f"current_focus: {title}")
        if keywords:
            lines.append("keywords: {}".format(", ".join(keywords)))
        summary = _safe_focus_prompt_text(raw_summary)
        if summary:
            lines.append(f"summary: {summary}")
        participants = [str(item) for item in (frame.get("participants") or []) if str(item).strip()]
        if participants:
            lines.append("participants: {}".format(", ".join(participants)))
        messages = focus.get("messages") or []
        lines.append("message_count: {}".format(len(messages)))
        lines.append("</wechat-group-focus>")
        return "\n".join(lines)

    def _recent_messages(self, archive, room_id: str, now=None) -> List[Dict[str, Any]]:
        try:
            rows = archive.get_recent_messages(
                room_id,
                limit=int(conf().get("wechat_group_focus_recent_message_limit", 30) or 30),
                minutes=max(int(conf().get("wechat_group_recent_context_minutes", 60) or 60), 1),
                now=now,
            )
            return [dict(row) for row in rows or []]
        except Exception:
            return []

    @staticmethod
    def _find_current_row(archive, msg, recent_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        message_id = str(getattr(msg, "msg_id", "") or "").strip()
        room_id = _stable_room_scope(msg)
        if message_id and room_id:
            try:
                row = archive.get_message_by_id(room_id, message_id)
                if row:
                    return dict(row)
            except Exception:
                pass
        for row in reversed(recent_rows or []):
            if message_id and str(row.get("message_id") or "") == message_id:
                return dict(row)
        if message_id or str(getattr(msg, "content", "") or getattr(msg, "text", "") or "").strip():
            return {
                "id": 0,
                "message_id": message_id,
                "room_id": room_id,
                "room_name": str(getattr(msg, "other_user_nickname", "") or ""),
                "sender_id": str(getattr(msg, "actual_user_id", "") or ""),
                "sender_nickname": str(getattr(msg, "actual_user_nickname", "") or ""),
                "message_type": str(getattr(msg, "message_type", "") or "text"),
                "text": str(getattr(msg, "text", "") or getattr(msg, "content", "") or ""),
                "media_path": str(getattr(msg, "media_path", "") or ""),
                "created_at": _coerce_timestamp(getattr(msg, "create_time", None)),
            }
        return {}

    def _drop_stale_stack(self, room_id: str, stack: List[Dict[str, Any]], current_row: Dict[str, Any]) -> List[Dict[str, Any]]:
        stale_rounds = int(conf().get("wechat_group_focus_stale_rounds", 20) or 20)
        if stale_rounds <= 0 or not stack:
            return list(stack or [])
        current_row_id = int((current_row or {}).get("id") or 0)
        if current_row_id <= 0:
            return list(stack or [])
        result = list(stack or [])
        while result and current_row_id - int(result[-1].get("last_row_id") or 0) > stale_rounds:
            result.pop()
        if len(result) != len(stack):
            self.store.save_stack(room_id, result)
        return result

    @staticmethod
    def _find_matching_frame_index(stack: List[Dict[str, Any]], keywords: List[str], include_top: bool = True) -> int:
        if not keywords:
            return -1
        end = len(stack) if include_top else max(len(stack) - 1, 0)
        for index in range(end - 1, -1, -1):
            frame = stack[index]
            if _keywords_match(keywords, frame.get("topic") or []):
                return index
        return -1

    @staticmethod
    def _has_return_intent(query: str) -> bool:
        value = normalize_query_text(query)
        return any(token in value for token in RETURN_TOKENS)

    @staticmethod
    def _push_frame(stack: List[Dict[str, Any]], frame: Dict[str, Any]) -> List[Dict[str, Any]]:
        depth = int(conf().get("wechat_group_focus_stack_depth", 4) or 4)
        result = list(stack or []) + [frame]
        if depth > 0 and len(result) > depth:
            result = result[-depth:]
        for index, item in enumerate(result):
            item["depth"] = index
        return result

    @staticmethod
    def _new_frame(room_id: str, keywords: List[str], current_row: Dict[str, Any], now: int) -> Dict[str, Any]:
        safe_text = _safe_row_text(current_row)
        topic = keywords or extract_focus_keywords(safe_text, limit=8)
        title = _build_title_from_keywords(topic) or _clip_text(safe_text, 24) or "recent focus"
        row_id = int((current_row or {}).get("id") or 0)
        return {
            "frame_id": "focus-{}".format(uuid4().hex),
            "room_id": room_id,
            "depth": 0,
            "topic": topic,
            "title": title,
            "summary": _clip_text(safe_text, 160),
            "participants": _participants_from_rows([current_row] if current_row else []),
            "conclusions": [],
            "started_at": now,
            "started_row_id": row_id,
            "last_seen_at": now,
            "last_row_id": row_id,
            "hit_count": 1,
            "status": "active",
        }

    @staticmethod
    def _frame_from_rows(room_id: str, rows: List[Dict[str, Any]], now: int) -> Dict[str, Any]:
        text_rows = [row for row in rows or [] if str(row.get("text") or "").strip()]
        if not text_rows:
            return {}
        keywords = []
        for row in text_rows[-3:]:
            for token in extract_focus_keywords(_safe_row_text(row), limit=4):
                if token not in keywords:
                    keywords.append(token)
        latest = text_rows[-1]
        first = text_rows[0]
        return {
            "frame_id": "focus-{}".format(uuid4().hex),
            "room_id": room_id,
            "depth": 0,
            "topic": keywords[:8],
            "title": _build_title_from_keywords(keywords) or _clip_text(_safe_row_text(latest), 24) or "recent focus",
            "summary": " / ".join(_clip_text(_safe_row_text(row), 40) for row in text_rows[-3:])[:160],
            "participants": _participants_from_rows(text_rows),
            "conclusions": [],
            "started_at": int(first.get("created_at") or now),
            "started_row_id": int(first.get("id") or 0),
            "last_seen_at": int(latest.get("created_at") or now),
            "last_row_id": int(latest.get("id") or 0),
            "hit_count": 1,
            "status": "active",
        }

    @staticmethod
    def _touch_frame(frame: Dict[str, Any], keywords: List[str], current_row: Dict[str, Any], now: int) -> None:
        topic = list(frame.get("topic") or [])
        for token in keywords:
            if token not in topic:
                topic.append(token)
        frame["topic"] = topic[:8]
        frame["last_seen_at"] = now
        frame["last_row_id"] = int((current_row or {}).get("id") or frame.get("last_row_id") or 0)
        frame["hit_count"] = int(frame.get("hit_count") or 0) + 1
        participants = list(frame.get("participants") or [])
        for item in _participants_from_rows([current_row] if current_row else []):
            if item not in participants:
                participants.append(item)
        frame["participants"] = participants

    def _append_current_ref(self, room_id: str, frame: Dict[str, Any], current_row: Dict[str, Any], msg, now: int) -> None:
        if not frame:
            return
        message_id = str((current_row or {}).get("message_id") or getattr(msg, "msg_id", "") or "").strip()
        row_id = int((current_row or {}).get("id") or 0)
        if not message_id and row_id <= 0:
            return
        try:
            self.store.append_message_ref(
                room_id,
                frame_id=str(frame.get("frame_id") or ""),
                message_id=message_id,
                row_id=row_id,
                created_at=int((current_row or {}).get("created_at") or now),
            )
        except Exception:
            return

    def _focus_rows_for_frame(
        self,
        archive,
        room_id: str,
        frame: Dict[str, Any],
        recent_rows: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        refs = self.store.list_message_refs(
            room_id,
            str(frame.get("frame_id") or ""),
            limit=int(conf().get("wechat_group_focus_context_message_limit", 8) or 8),
        )
        ref_row_ids = {int(item.get("row_id") or 0) for item in refs if int(item.get("row_id") or 0) > 0}
        ref_message_ids = {str(item.get("message_id") or "") for item in refs if str(item.get("message_id") or "").strip()}
        if ref_row_ids or ref_message_ids:
            rows = [
                row for row in (recent_rows or [])
                if int(row.get("id") or 0) in ref_row_ids or str(row.get("message_id") or "") in ref_message_ids
            ]
            if rows:
                return rows
        _ = archive
        last_row_id = int(frame.get("last_row_id") or 0)
        if last_row_id:
            rows = [row for row in (recent_rows or []) if int(row.get("id") or 0) <= last_row_id]
            if rows:
                return rows
        return list(recent_rows or [])

    @staticmethod
    def _limit_context_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        limit = int(conf().get("wechat_group_focus_context_message_limit", 8) or 8)
        values = [dict(row) for row in rows or [] if row]
        return values[-max(limit, 1):]

    @staticmethod
    def _result(
        event: str,
        mode: str,
        reason: str,
        frame: Dict[str, Any],
        stack: List[Dict[str, Any]],
        messages: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        return {
            "event": event,
            "mode": mode,
            "reason": reason,
            "frame": frame or {},
            "stack": list(stack or []),
            "messages": list(messages or []),
        }


def _keywords_match(keywords: List[str], topic: List[str]) -> bool:
    for keyword in keywords or []:
        key = str(keyword or "").lower().strip()
        if not key:
            continue
        for item in topic or []:
            value = str(item or "").lower().strip()
            if not value:
                continue
            if key == value or key in value or value in key:
                return True
    return False


def _participants_from_rows(rows: List[Dict[str, Any]]) -> List[str]:
    result = []
    for row in rows or []:
        sender_id = str(row.get("sender_id") or "").strip()
        name = str(row.get("sender_nickname") or sender_id).strip()
        if not name or name.startswith("wxid_"):
            name = sender_id
        if name and name not in result:
            result.append(name)
    return result


def _build_title_from_keywords(keywords: List[str]) -> str:
    values = [str(item or "").strip() for item in keywords or [] if str(item or "").strip()]
    if not values:
        return ""
    return "".join(values[:2])[:24]


def _clip_text(value: Any, limit: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    return text[: max(int(limit or 0) - 1, 0)].rstrip() + "..."


def _safe_row_text(row: Dict[str, Any]) -> str:
    if not row:
        return ""
    msg_type = project_wechat_message_type(row.get("message_type") or "text", row.get("text"))
    if msg_type != "text":
        message_id = str(row.get("message_id") or "").strip()
        return "[{} message{}]".format(
            msg_type,
            " {}".format(message_id) if message_id else "",
        )
    return str(row.get("text") or "")


def _safe_focus_prompt_text(value: Any) -> str:
    text = str(value or "").strip()
    if is_wechat_transport_xml(text):
        return "[media message]"
    return text


def _coerce_timestamp(value: Any = None) -> int:
    try:
        return int(value)
    except Exception:
        return int(time.time())


def _xml_attr(value: Any) -> str:
    return str(value or "").replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")
