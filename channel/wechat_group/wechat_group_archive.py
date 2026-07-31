"""SQLite archive for WeChat group messages."""

import ast
import json
import os
import re
import sqlite3
import threading
import time
from contextlib import closing
from typing import Any, Dict, Iterable, List, Optional
from uuid import uuid4

from config import get_appdata_dir


def _default_archive_path() -> str:
    data_root = os.environ.get("LIGHTAGENT_DATA_DIR") or os.path.join(os.path.expanduser("~"), ".lightagent")
    return os.path.join(os.path.expanduser(data_root), "wechat_group", "wechat_group_archive.db")


class WechatGroupArchive:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or _default_archive_path()
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_schema()

    def record_message(
        self,
        message_id: str,
        room_id: str,
        room_name: str = "",
        sender_id: str = "",
        sender_nickname: str = "",
        message_type: str = "text",
        text: str = "",
        media_path: str = "",
        is_at: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
        created_at: Optional[int] = None,
        stable_room_id: str = "",
        runtime_room_id: str = "",
        stable_member_id: str = "",
        runtime_sender_id: str = "",
    ) -> int:
        if not room_id or not message_id:
            return 0
        ts = _coerce_timestamp(created_at)
        runtime_room = str(runtime_room_id or room_id)
        runtime_sender = str(runtime_sender_id or sender_id or "")
        with self._lock, closing(self._connect()) as conn:
            with conn:
                cursor = conn.execute(
                    """
                    INSERT OR IGNORE INTO wechat_group_messages (
                        message_id, room_id, room_name, sender_id, sender_nickname,
                        message_type, text, media_path, is_at, metadata, created_at,
                        stable_room_id, runtime_room_id, stable_member_id, runtime_sender_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(message_id),
                        str(room_id),
                        str(room_name or ""),
                        str(sender_id or ""),
                        str(sender_nickname or ""),
                        str(message_type or "text"),
                        str(text or ""),
                        str(media_path or ""),
                        1 if is_at else 0,
                        json.dumps(metadata or {}, ensure_ascii=False),
                        ts,
                        str(stable_room_id or ""),
                        runtime_room,
                        str(stable_member_id or ""),
                        runtime_sender,
                    ),
                )
                if cursor.rowcount:
                    return int(cursor.lastrowid or 0)
                row = conn.execute(
                    "SELECT id FROM wechat_group_messages WHERE message_id = ? LIMIT 1",
                    (str(message_id),),
                ).fetchone()
                return int(row[0] or 0) if row else 0

    def record_assistant_reply(
        self,
        room_id: str,
        room_name: str = "",
        reply_type: str = "text",
        content: str = "",
        mention_ids: Optional[List[str]] = None,
        created_at: Optional[int] = None,
        stable_room_id: str = "",
        runtime_room_id: str = "",
        thread_id: str = "",
        request_id: str = "",
    ) -> int:
        if not room_id or not content:
            return 0
        ts = _coerce_timestamp(created_at)
        with self._lock, closing(self._connect()) as conn:
            with conn:
                cursor = conn.execute(
                    """
                    INSERT INTO wechat_group_assistant_replies (
                        room_id, room_name, reply_type, content, mention_ids, created_at,
                        stable_room_id, runtime_room_id, thread_id, request_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(room_id),
                        str(room_name or ""),
                        str(reply_type or "text"),
                        str(content or ""),
                        ",".join(mention_ids or []),
                        ts,
                        str(stable_room_id or ""),
                        str(runtime_room_id or room_id),
                        str(thread_id or ""),
                        str(request_id or ""),
                    ),
                )
                return int(cursor.lastrowid or 0)

    def get_room_revision(self, room_id: str) -> Dict[str, int]:
        """Return stable-room inbound/assistant high-water marks."""
        scope = str(room_id or "").strip()
        if not scope:
            return {"inbound_cursor": 0, "assistant_cursor": 0}
        with self._lock, closing(self._connect()) as conn:
            inbound = conn.execute(
                """
                SELECT COALESCE(MAX(id), 0) FROM wechat_group_messages
                WHERE stable_room_id = ?
                   OR (COALESCE(stable_room_id, '') = '' AND room_id = ?)
                """,
                (scope, scope),
            ).fetchone()
            assistant = conn.execute(
                """
                SELECT COALESCE(MAX(id), 0) FROM wechat_group_assistant_replies
                WHERE stable_room_id = ?
                   OR (COALESCE(stable_room_id, '') = '' AND room_id = ?)
                """,
                (scope, scope),
            ).fetchone()
        return {
            "inbound_cursor": int((inbound or [0])[0] or 0),
            "assistant_cursor": int((assistant or [0])[0] or 0),
        }

    def count_room_inbound_after_cursor(self, room_id: str, inbound_cursor: int = 0) -> int:
        """Count stable-room inbound rows newer than the supplied cursor."""
        scope = str(room_id or "").strip()
        if not scope:
            return 0
        cursor_value = max(int(inbound_cursor or 0), 0)
        with self._lock, closing(self._connect()) as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) FROM wechat_group_messages
                WHERE (
                    stable_room_id = ?
                    OR (COALESCE(stable_room_id, '') = '' AND room_id = ?)
                ) AND id > ?
                """,
                (scope, scope, cursor_value),
            ).fetchone()
        return int((row or [0])[0] or 0)

    def record_image_create_usage(
        self,
        room_id: str,
        sender_id: str = "",
        prompt: str = "",
        status: str = "accepted",
        created_at: Optional[int] = None,
        stable_room_id: str = "",
        runtime_room_id: str = "",
        stable_member_id: str = "",
        runtime_sender_id: str = "",
    ) -> None:
        if not room_id:
            return
        ts = _coerce_timestamp(created_at)
        with self._lock, closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO wechat_group_image_create_usage (
                        room_id, sender_id, prompt, status, created_at,
                        stable_room_id, runtime_room_id, stable_member_id, runtime_sender_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(room_id),
                        str(sender_id or ""),
                        str(prompt or "")[:2000],
                        str(status or "accepted"),
                        ts,
                        str(stable_room_id or ""),
                        str(runtime_room_id or room_id),
                        str(stable_member_id or ""),
                        str(runtime_sender_id or sender_id or ""),
                    ),
                )

    def count_image_create_usage(
        self,
        room_id: str,
        window_seconds: int = 3600,
        now: Optional[int] = None,
    ) -> int:
        if not room_id:
            return 0
        cutoff = _coerce_timestamp(now) - max(int(window_seconds or 3600), 1)
        with self._lock, closing(self._connect()) as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM wechat_group_image_create_usage
                WHERE (
                    stable_room_id = ?
                    OR (COALESCE(stable_room_id, '') = '' AND room_id = ?)
                )
                  AND status = 'accepted'
                  AND created_at >= ?
                """,
                (str(room_id), str(room_id), cutoff),
            ).fetchone()
        return int(row[0] or 0) if row else 0

    def get_recent_messages(
        self,
        room_id: str,
        limit: int = 20,
        minutes: int = 60,
        now: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        if not room_id:
            return []
        max_limit = min(max(int(limit or 20), 1), 300)
        window_minutes = max(int(minutes or 60), 1)
        cutoff = _coerce_timestamp(now) - window_minutes * 60
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT id, message_id, room_id, room_name, sender_id, sender_nickname,
                       message_type, text, media_path, is_at, metadata, created_at,
                       stable_room_id, runtime_room_id, stable_member_id, runtime_sender_id
                FROM wechat_group_messages
                WHERE (
                    stable_room_id = ?
                    OR (COALESCE(stable_room_id, '') = '' AND room_id = ?)
                ) AND created_at >= ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (str(room_id), str(room_id), cutoff, max_limit),
            ).fetchall()
        return [self._message_row_to_dict(row) for row in reversed(rows)]

    def get_recent_conversation_messages(
        self,
        room_id: str,
        limit: int = 20,
        minutes: int = 60,
        now: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Return a chronological inbound/outbound timeline for LLM routing."""
        if not room_id:
            return []
        max_limit = min(max(int(limit or 20), 1), 501)
        window_minutes = max(int(minutes or 60), 1)
        until = _coerce_timestamp(now)
        cutoff = until - window_minutes * 60
        scope = str(room_id)
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            inbound_rows = conn.execute(
                """
                SELECT id, message_id, room_id, room_name, sender_id, sender_nickname,
                       message_type, text, media_path, is_at, metadata, created_at,
                       stable_room_id, runtime_room_id, stable_member_id, runtime_sender_id
                FROM wechat_group_messages
                WHERE (
                    stable_room_id = ?
                    OR (COALESCE(stable_room_id, '') = '' AND room_id = ?)
                )
                  AND created_at >= ?
                  AND created_at <= ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (scope, scope, cutoff, until, max_limit),
            ).fetchall()
            assistant_rows = conn.execute(
                """
                SELECT id, room_id, room_name, reply_type, content, created_at,
                       stable_room_id, runtime_room_id, thread_id, request_id,
                       mention_ids
                FROM wechat_group_assistant_replies
                WHERE (
                    stable_room_id = ?
                    OR (COALESCE(stable_room_id, '') = '' AND room_id = ?)
                )
                  AND created_at >= ?
                  AND created_at <= ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (scope, scope, cutoff, until, max_limit),
            ).fetchall()

        timeline = []
        for row in inbound_rows:
            item = self._message_row_to_dict(row)
            item["is_bot"] = False
            item["_timeline_source_order"] = 0
            timeline.append(item)
        for row in assistant_rows:
            data = dict(row)
            reply_id = int(data.get("id") or 0)
            timeline.append(
                {
                    "id": reply_id,
                    "message_id": "assistant-reply:{}".format(reply_id),
                    "room_id": str(data.get("room_id") or ""),
                    "room_name": str(data.get("room_name") or ""),
                    "sender_id": "__lightagent_bot__",
                    "sender_nickname": "LightAgent",
                    "message_type": str(data.get("reply_type") or "text"),
                    "text": str(data.get("content") or ""),
                    "media_path": "",
                    "is_at": False,
                    "metadata": {"source": "assistant_reply"},
                    "at_list": [],
                    "created_at": int(data.get("created_at") or 0),
                    "stable_room_id": str(data.get("stable_room_id") or ""),
                    "runtime_room_id": str(data.get("runtime_room_id") or ""),
                    "stable_member_id": "",
                    "runtime_sender_id": "",
                    "is_bot": True,
                    "thread_id": str(data.get("thread_id") or ""),
                    "request_id": str(data.get("request_id") or ""),
                    "mention_ids": [
                        value for value in str(data.get("mention_ids") or "").split(",")
                        if value
                    ],
                    "source_event_id": "assistant:{}".format(reply_id),
                    "_timeline_source_order": 1,
                }
            )
        timeline.sort(
            key=lambda item: (
                int(item.get("created_at") or 0),
                int(item.get("_timeline_source_order") or 0),
                int(item.get("id") or 0),
            )
        )
        timeline = timeline[-max_limit:]
        for item in timeline:
            item.pop("_timeline_source_order", None)
            if not item.get("source_event_id"):
                item["source_event_id"] = "inbound:{}".format(int(item.get("id") or 0))
        return timeline

    def get_conversation_messages_after_revision(
        self,
        room_id: str,
        inbound_cursor: int = 0,
        assistant_cursor: int = 0,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """Return chronological room events newer than the supplied cursors."""
        scope = str(room_id or "").strip()
        if not scope:
            return []
        max_limit = min(max(int(limit or 200), 1), 500)
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            inbound_rows = conn.execute(
                """
                SELECT id, message_id, room_id, room_name, sender_id,
                       sender_nickname, message_type, text, media_path, is_at,
                       metadata, created_at, stable_room_id, runtime_room_id,
                       stable_member_id, runtime_sender_id
                FROM wechat_group_messages
                WHERE (
                    stable_room_id = ?
                    OR (COALESCE(stable_room_id, '') = '' AND room_id = ?)
                ) AND id > ?
                ORDER BY id ASC LIMIT ?
                """,
                (scope, scope, max(int(inbound_cursor or 0), 0), max_limit),
            ).fetchall()
            assistant_rows = conn.execute(
                """
                SELECT id, room_id, room_name, reply_type, content, created_at,
                       stable_room_id, runtime_room_id, thread_id, request_id,
                       mention_ids
                FROM wechat_group_assistant_replies
                WHERE (
                    stable_room_id = ?
                    OR (COALESCE(stable_room_id, '') = '' AND room_id = ?)
                ) AND id > ?
                ORDER BY id ASC LIMIT ?
                """,
                (scope, scope, max(int(assistant_cursor or 0), 0), max_limit),
            ).fetchall()
        timeline = []
        for row in inbound_rows:
            item = self._message_row_to_dict(row)
            item.update({
                "is_bot": False,
                "source_event_id": "inbound:{}".format(int(item.get("id") or 0)),
                "_timeline_source_order": 0,
            })
            timeline.append(item)
        for row in assistant_rows:
            data = dict(row)
            reply_id = int(data.get("id") or 0)
            timeline.append({
                "id": reply_id,
                "message_id": "assistant-reply:{}".format(reply_id),
                "room_id": str(data.get("room_id") or ""),
                "room_name": str(data.get("room_name") or ""),
                "sender_id": "__lightagent_bot__",
                "sender_nickname": "LightAgent",
                "message_type": str(data.get("reply_type") or "text"),
                "text": str(data.get("content") or ""),
                "metadata": {"source": "assistant_reply"},
                "created_at": int(data.get("created_at") or 0),
                "stable_room_id": str(data.get("stable_room_id") or ""),
                "runtime_room_id": str(data.get("runtime_room_id") or ""),
                "is_bot": True,
                "thread_id": str(data.get("thread_id") or ""),
                "request_id": str(data.get("request_id") or ""),
                "source_event_id": "assistant:{}".format(reply_id),
                "_timeline_source_order": 1,
            })
        timeline.sort(key=lambda item: (
            int(item.get("created_at") or 0),
            int(item.get("_timeline_source_order") or 0),
            int(item.get("id") or 0),
        ))
        for item in timeline:
            item.pop("_timeline_source_order", None)
        return timeline[:max_limit]

    def search_messages(
        self,
        room_id: str,
        query: str = "",
        since_ts: int = 0,
        until_ts: Optional[int] = None,
        limit: int = 48,
        exclude_message_id: str = "",
    ) -> List[Dict[str, Any]]:
        if not room_id:
            return []
        max_limit = min(max(int(limit or 48), 1), 100)
        since = int(since_ts or 0)
        until = _coerce_timestamp(until_ts)
        excluded = str(exclude_message_id or "").strip()
        keywords = _extract_search_keywords(query)
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT id, message_id, room_id, room_name, sender_id, sender_nickname,
                       message_type, text, media_path, is_at, metadata, created_at,
                       stable_room_id, runtime_room_id, stable_member_id, runtime_sender_id
                FROM wechat_group_messages
                WHERE (
                    stable_room_id = ?
                    OR (COALESCE(stable_room_id, '') = '' AND room_id = ?)
                )
                  AND created_at >= ?
                  AND created_at <= ?
                ORDER BY created_at ASC, id ASC
                LIMIT 500
                """,
                (str(room_id), str(room_id), since, until),
            ).fetchall()
        results = []
        for row in rows:
            item = self._message_row_to_dict(row)
            if excluded and str(item.get("message_id") or "") == excluded:
                continue
            if keywords:
                haystack = " ".join(
                    [
                        str(item.get("text") or ""),
                        str(item.get("sender_nickname") or ""),
                        str(item.get("sender_id") or ""),
                    ]
                ).lower()
                if not any(keyword in haystack for keyword in keywords):
                    continue
            results.append(item)
            if len(results) >= max_limit:
                break
        return results

    def get_message_by_id(self, room_id: str, message_id: str) -> Optional[Dict[str, Any]]:
        if not room_id or not message_id:
            return None
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT id, message_id, room_id, room_name, sender_id, sender_nickname,
                       message_type, text, media_path, is_at, metadata, created_at,
                       stable_room_id, runtime_room_id, stable_member_id, runtime_sender_id
                FROM wechat_group_messages
                WHERE (
                    stable_room_id = ?
                    OR (COALESCE(stable_room_id, '') = '' AND room_id = ?)
                ) AND message_id = ?
                LIMIT 1
                """,
                (str(room_id), str(room_id), str(message_id)),
            ).fetchone()
        return self._message_row_to_dict(row) if row else None

    def get_messages_for_distill(
        self,
        room_id: str,
        since_ts: int,
        until_ts: Optional[int] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        if not room_id:
            return []
        max_limit = min(max(int(limit or 200), 1), 500)
        until = _coerce_timestamp(until_ts)
        since = int(since_ts or 0)
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT id, message_id, room_id, room_name, sender_id, sender_nickname,
                       message_type, text, media_path, is_at, metadata, created_at,
                       stable_room_id, runtime_room_id, stable_member_id, runtime_sender_id
                FROM wechat_group_messages
                WHERE (
                    stable_room_id = ?
                    OR (COALESCE(stable_room_id, '') = '' AND room_id = ?)
                )
                  AND created_at >= ?
                  AND created_at <= ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (str(room_id), str(room_id), since, until, max_limit),
            ).fetchall()
        return [self._message_row_to_dict(row) for row in reversed(rows)]

    def get_messages_after_row_id(
        self,
        room_id: str,
        last_row_id: int,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        if not room_id:
            return []
        max_limit = min(max(int(limit or 200), 1), 500)
        try:
            row_id = int(last_row_id or 0)
        except Exception:
            row_id = 0
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT id, message_id, room_id, room_name, sender_id, sender_nickname,
                       message_type, text, media_path, is_at, metadata, created_at,
                       stable_room_id, runtime_room_id, stable_member_id, runtime_sender_id
                FROM wechat_group_messages
                WHERE (
                    stable_room_id = ?
                    OR (COALESCE(stable_room_id, '') = '' AND room_id = ?)
                )
                  AND id > ?
                ORDER BY id ASC
                LIMIT ?
                """,
                (str(room_id), str(room_id), row_id, max_limit),
            ).fetchall()
        return [self._message_row_to_dict(row) for row in rows]

    def count_text_messages_after_row_id(
        self,
        room_id: str,
        last_row_id: int,
        through_row_id: int = 0,
    ) -> int:
        if not room_id:
            return 0
        end_row_id = max(int(through_row_id or 0), 0)
        end_clause = " AND id <= ?" if end_row_id else ""
        params = [str(room_id), str(room_id), int(last_row_id or 0)]
        if end_row_id:
            params.append(end_row_id)
        with self._lock, closing(self._connect()) as conn:
            row = conn.execute(
                f"""
                SELECT COUNT(*)
                FROM wechat_group_messages
                WHERE (
                    stable_room_id = ?
                    OR (COALESCE(stable_room_id, '') = '' AND room_id = ?)
                )
                  AND id > ?
                  AND LOWER(message_type) = 'text'
                  {end_clause}
                """,
                params,
            ).fetchone()
        return int(row[0] or 0) if row else 0

    def get_oldest_text_message_after_row_id(
        self,
        room_id: str,
        last_row_id: int,
        through_row_id: int = 0,
    ) -> Dict[str, Any]:
        if not room_id:
            return {}
        end_row_id = max(int(through_row_id or 0), 0)
        end_clause = " AND id <= ?" if end_row_id else ""
        params = [str(room_id), str(room_id), int(last_row_id or 0)]
        if end_row_id:
            params.append(end_row_id)
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                f"""
                SELECT id, created_at
                FROM wechat_group_messages
                WHERE (
                    stable_room_id = ?
                    OR (COALESCE(stable_room_id, '') = '' AND room_id = ?)
                )
                  AND id > ?
                  AND LOWER(message_type) = 'text'
                  {end_clause}
                ORDER BY id ASC
                LIMIT 1
                """,
                params,
            ).fetchone()
        return dict(row) if row else {}

    def get_text_messages_after_row_id(
        self,
        room_id: str,
        last_row_id: int,
        limit: int = 200,
        window_minutes: int = 120,
        through_row_id: int = 0,
    ) -> List[Dict[str, Any]]:
        if not room_id:
            return []
        max_limit = min(max(int(limit or 200), 1), 500)
        row_id = max(int(last_row_id or 0), 0)
        minutes = max(int(window_minutes or 120), 1)
        end_row_id = max(int(through_row_id or 0), 0)
        end_clause = " AND id <= ?" if end_row_id else ""
        scope_params = (str(room_id), str(room_id), row_id)
        first_params = list(scope_params)
        if end_row_id:
            first_params.append(end_row_id)
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            first = conn.execute(
                f"""
                SELECT created_at
                FROM wechat_group_messages
                WHERE (
                    stable_room_id = ?
                    OR (COALESCE(stable_room_id, '') = '' AND room_id = ?)
                )
                  AND id > ?
                  AND LOWER(message_type) = 'text'
                  {end_clause}
                ORDER BY id ASC
                LIMIT 1
                """,
                first_params,
            ).fetchone()
            if not first:
                return []
            window_end = int(first[0] or 0) + minutes * 60
            row_params = list(scope_params)
            if end_row_id:
                row_params.append(end_row_id)
            row_params.extend([window_end, max_limit])
            rows = conn.execute(
                f"""
                SELECT id, message_id, room_id, room_name, sender_id, sender_nickname,
                       message_type, text, media_path, is_at, metadata, created_at,
                       stable_room_id, runtime_room_id, stable_member_id, runtime_sender_id
                FROM wechat_group_messages
                WHERE (
                    stable_room_id = ?
                    OR (COALESCE(stable_room_id, '') = '' AND room_id = ?)
                )
                  AND id > ?
                  AND LOWER(message_type) = 'text'
                  {end_clause}
                  AND created_at <= ?
                ORDER BY id ASC
                LIMIT ?
                """,
                row_params,
            ).fetchall()
        return [self._message_row_to_dict(row) for row in rows]

    def get_max_row_id(self, room_id: str) -> int:
        room_text = str(room_id or "").strip()
        if not room_text:
            return 0
        with self._lock, closing(self._connect()) as conn:
            row = conn.execute(
                """
                SELECT COALESCE(MAX(id), 0) FROM wechat_group_messages
                WHERE stable_room_id = ?
                   OR (COALESCE(stable_room_id, '') = '' AND room_id = ?)
                """,
                (room_text, room_text),
            ).fetchone()
        return int(row[0] or 0) if row else 0

    def get_report_messages_page(
        self,
        stable_room_id: str,
        start_at: int,
        end_at: int,
        after_id: int = 0,
        limit: int = 200,
        legacy_room_ids: Optional[Iterable[str]] = None,
        message_types: Optional[Iterable[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Return one strictly scoped, half-open report evidence page.

        ``stable_room_id`` is always the primary scope. Historical rows that
        predate stable identity support are included only when the caller has
        supplied an explicitly confirmed runtime-room alias. This avoids the
        broad ``stable_room_id OR room_id`` pattern that can mix reports from
        unrelated accounts after a runtime id is reused.
        """
        room_id = str(stable_room_id or "").strip()
        if not room_id:
            return []
        max_limit = min(max(int(limit or 200), 1), 500)
        try:
            cursor_id = max(int(after_id or 0), 0)
        except (TypeError, ValueError):
            cursor_id = 0
        try:
            start = int(start_at)
            end = int(end_at)
        except (TypeError, ValueError):
            raise ValueError("start_at and end_at must be timestamps")
        if end <= start:
            return []

        aliases = []
        for value in legacy_room_ids or []:
            alias = str(value or "").strip()
            if alias and alias != room_id and alias not in aliases:
                aliases.append(alias)
        scope_clause = "stable_room_id = ?"
        scope_params: List[Any] = [room_id]
        if aliases:
            placeholders = ", ".join("?" for _ in aliases)
            scope_clause = (
                "(stable_room_id = ? OR "
                "(COALESCE(stable_room_id, '') = '' AND room_id IN ({placeholders})))"
            ).format(placeholders=placeholders)
            scope_params.extend(aliases)

        type_values = []
        for value in message_types or []:
            normalized = str(value or "").strip().lower()
            if normalized and normalized not in type_values:
                type_values.append(normalized)
        type_clause = ""
        if type_values:
            type_clause = " AND LOWER(message_type) IN ({})".format(
                ", ".join("?" for _ in type_values)
            )

        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT id, message_id, room_id, room_name, sender_id, sender_nickname,
                       message_type, text, media_path, is_at, metadata, created_at,
                       stable_room_id, runtime_room_id, stable_member_id, runtime_sender_id
                FROM wechat_group_messages
                WHERE {scope_clause}
                  AND created_at >= ? AND created_at < ?
                  AND id > ?
                  {type_clause}
                ORDER BY id ASC
                LIMIT ?
                """.format(scope_clause=scope_clause, type_clause=type_clause),
                [*scope_params, start, end, cursor_id, *type_values, max_limit],
            ).fetchall()
        return [self._message_row_to_dict(row) for row in rows]

    def get_report_source_watermark(
        self,
        stable_room_id: str,
        start_at: int,
        end_at: int,
        legacy_room_ids: Optional[Iterable[str]] = None,
    ) -> int:
        """Return the highest archive row id contributing to a report range."""
        # Keep the query separate from evidence pagination while sharing the
        # same strict stable-room scope rule.
        room_id = str(stable_room_id or "").strip()
        if not room_id:
            return 0
        aliases = []
        for value in legacy_room_ids or []:
            alias = str(value or "").strip()
            if alias and alias != room_id and alias not in aliases:
                aliases.append(alias)
        scope_clause = "stable_room_id = ?"
        params: List[Any] = [room_id]
        if aliases:
            placeholders = ", ".join("?" for _ in aliases)
            scope_clause = (
                "(stable_room_id = ? OR "
                "(COALESCE(stable_room_id, '') = '' AND room_id IN ({placeholders})))"
            ).format(placeholders=placeholders)
            params.extend(aliases)
        with self._lock, closing(self._connect()) as conn:
            row = conn.execute(
                """
                SELECT COALESCE(MAX(id), 0)
                FROM wechat_group_messages
                WHERE {scope_clause} AND created_at >= ? AND created_at < ?
                """.format(scope_clause=scope_clause),
                [*params, int(start_at), int(end_at)],
            ).fetchone()
        return int(row[0] or 0) if row else 0

    def get_report_archive_bounds(
        self,
        stable_room_id: str,
        legacy_room_ids: Optional[Iterable[str]] = None,
    ) -> Dict[str, int]:
        """Return the earliest and latest timestamp available in report scope."""
        room_id = str(stable_room_id or "").strip()
        if not room_id:
            return {"first_created_at": 0, "last_created_at": 0, "message_count": 0}
        aliases = []
        for value in legacy_room_ids or []:
            alias = str(value or "").strip()
            if alias and alias != room_id and alias not in aliases:
                aliases.append(alias)
        scope_clause = "stable_room_id = ?"
        params: List[Any] = [room_id]
        if aliases:
            placeholders = ", ".join("?" for _ in aliases)
            scope_clause = (
                "(stable_room_id = ? OR "
                "(COALESCE(stable_room_id, '') = '' AND room_id IN ({placeholders})))"
            ).format(placeholders=placeholders)
            params.extend(aliases)
        with self._lock, closing(self._connect()) as conn:
            row = conn.execute(
                """
                SELECT COALESCE(MIN(created_at), 0), COALESCE(MAX(created_at), 0), COUNT(*)
                FROM wechat_group_messages
                WHERE {scope_clause}
                """.format(scope_clause=scope_clause),
                params,
            ).fetchone()
        return {
            "first_created_at": int(row[0] or 0) if row else 0,
            "last_created_at": int(row[1] or 0) if row else 0,
            "message_count": int(row[2] or 0) if row else 0,
        }

    def list_members(
        self,
        room_id: str,
        query: str = "",
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        if not room_id:
            return []
        max_limit = min(max(int(limit or 20), 1), 100)
        q = str(query or "").strip().lower()
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT sender_id, sender_nickname, metadata, created_at, stable_member_id, runtime_sender_id
                FROM wechat_group_messages
                WHERE (
                    stable_room_id = ?
                    OR (COALESCE(stable_room_id, '') = '' AND room_id = ?)
                )
                  AND COALESCE(sender_id, '') != ''
                ORDER BY created_at DESC, id DESC
                """,
                (str(room_id), str(room_id)),
            ).fetchall()

        members: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            sender_id = str(row["sender_id"] or "").strip()
            if not sender_id:
                continue
            nickname = str(row["sender_nickname"] or "").strip()
            metadata = _parse_metadata(row["metadata"])
            wechat_id = str(metadata.get("wechat_id") or metadata.get("wechatId") or "").strip()
            haystack = " ".join([sender_id, nickname, wechat_id]).lower()
            if q and q not in haystack:
                continue
            if sender_id not in members:
                members[sender_id] = {
                    "sender_id": sender_id,
                    "stable_member_id": str(row["stable_member_id"] or ""),
                    "runtime_sender_id": str(row["runtime_sender_id"] or sender_id),
                    "sender_nickname": nickname or sender_id,
                    "wechat_id": wechat_id,
                    "last_seen_at": int(row["created_at"] or 0),
                    "message_count": 0,
                }
            elif _looks_like_raw_sender_name(members[sender_id].get("sender_nickname"), sender_id) and not _looks_like_raw_sender_name(nickname, sender_id):
                members[sender_id]["sender_nickname"] = nickname
            members[sender_id]["message_count"] += 1

        return list(members.values())[:max_limit]

    def find_latest_sender_name(self, sender_id: str, limit: int = 100) -> Optional[Dict[str, Any]]:
        sender_text = str(sender_id or "").strip()
        if not sender_text:
            return None
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT room_id, room_name, sender_nickname, created_at
                FROM wechat_group_messages
                WHERE sender_id = ?
                  AND COALESCE(sender_nickname, '') != ''
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (sender_text, min(max(int(limit or 100), 1), 500)),
            ).fetchall()
        for row in rows:
            nickname = str(row["sender_nickname"] or "").strip()
            if _looks_like_raw_sender_name(nickname, sender_text):
                continue
            return {
                "room_id": str(row["room_id"] or "").strip(),
                "room_name": str(row["room_name"] or "").strip(),
                "sender_nickname": nickname,
                "created_at": int(row["created_at"] or 0),
            }
        return None

    def find_room_name(self, room_id: str) -> str:
        room_text = str(room_id or "").strip()
        if not room_text:
            return ""
        for table in ("wechat_group_messages", "wechat_group_assistant_replies"):
            with self._lock, closing(self._connect()) as conn:
                room_clause = (
                    "(stable_room_id = ? OR "
                    "(COALESCE(stable_room_id, '') = '' AND room_id = ?))"
                )
                row = conn.execute(
                    f"""
                    SELECT room_name
                    FROM {table}
                    WHERE {room_clause}
                      AND COALESCE(room_name, '') != ''
                    ORDER BY created_at DESC, id DESC
                    LIMIT 1
                    """,
                    (room_text, room_text),
                ).fetchone()
            if row and str(row[0] or "").strip():
                return str(row[0] or "").strip()
        return ""

    def create_distill_run(
        self,
        room_id: str,
        since_ts: int,
        until_ts: int,
        message_count: int,
    ) -> str:
        run_id = uuid4().hex
        now = int(time.time())
        with self._lock, closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO wechat_group_memory_distill_runs (
                        run_id, room_id, since_ts, until_ts, message_count,
                        status, auto_applied_count, candidate_count, started_at
                    ) VALUES (?, ?, ?, ?, ?, 'running', 0, 0, ?)
                    """,
                    (run_id, room_id, since_ts, until_ts, message_count, now),
                )
        return run_id

    def finish_distill_run(
        self,
        run_id: str,
        status: str,
        auto_applied_count: int = 0,
        candidate_count: int = 0,
        failed_reason: str = "",
        raw_output_summary: str = "",
    ) -> None:
        with self._lock, closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    """
                    UPDATE wechat_group_memory_distill_runs
                    SET status = ?,
                        auto_applied_count = ?,
                        candidate_count = ?,
                        failed_reason = ?,
                        raw_output_summary = ?,
                        finished_at = ?
                    WHERE run_id = ?
                    """,
                    (
                        status,
                        int(auto_applied_count or 0),
                        int(candidate_count or 0),
                        failed_reason,
                        raw_output_summary[:2000],
                        int(time.time()),
                        run_id,
                    ),
                )

    def list_distill_runs(
        self,
        room_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT *
                FROM wechat_group_memory_distill_runs
                WHERE room_id = ?
                ORDER BY started_at DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                (room_id, min(max(int(limit or 20), 1), 100), max(int(offset or 0), 0)),
            ).fetchall()
        return [dict(row) for row in rows]

    def insert_memory_candidate(
        self,
        run_id: str,
        room_id: str,
        candidate_type: str,
        content: Dict[str, Any],
        confidence: float,
        evidence_message_ids: List[str],
        evidence_text: str = "",
        status: str = "pending",
        target_sender_id: str = "",
        target_sender_nickname: str = "",
        applied_memory_id: str = "",
    ) -> Dict[str, Any]:
        candidate_id = uuid4().hex
        now = int(time.time())
        with self._lock, closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO wechat_group_memory_candidates (
                        candidate_id, run_id, room_id, candidate_type,
                        target_sender_id, target_sender_nickname, content_json,
                        confidence, evidence_message_ids, evidence_text,
                        status, applied_memory_id, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        candidate_id,
                        run_id,
                        room_id,
                        candidate_type,
                        target_sender_id,
                        target_sender_nickname,
                        json.dumps(content or {}, ensure_ascii=False),
                        float(confidence or 0.0),
                        json.dumps(evidence_message_ids or [], ensure_ascii=False),
                        evidence_text,
                        status,
                        applied_memory_id,
                        now,
                    ),
                )
        return self.get_memory_candidate(room_id, candidate_id) or {}

    def list_memory_candidates(
        self,
        room_id: str,
        status: Optional[str] = None,
        candidate_type: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        params: List[Any] = [room_id]
        clauses = ["room_id = ?"]
        if status:
            clauses.append("status = ?")
            params.append(status)
        if candidate_type:
            clauses.append("candidate_type = ?")
            params.append(candidate_type)
        params.extend([min(max(int(limit or 20), 1), 100), max(int(offset or 0), 0)])
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"""
                SELECT *
                FROM wechat_group_memory_candidates
                WHERE {' AND '.join(clauses)}
                ORDER BY created_at DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                params,
            ).fetchall()
        return [self._candidate_row_to_dict(row) for row in rows]

    def get_memory_candidate(self, room_id: str, candidate_id: str) -> Optional[Dict[str, Any]]:
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT *
                FROM wechat_group_memory_candidates
                WHERE room_id = ? AND candidate_id = ?
                """,
                (room_id, candidate_id),
            ).fetchone()
        return self._candidate_row_to_dict(row) if row else None

    def update_memory_candidate_status(
        self,
        room_id: str,
        candidate_id: str,
        status: str,
        applied_memory_id: str = "",
        review_note: str = "",
    ) -> Dict[str, Any]:
        with self._lock, closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    """
                    UPDATE wechat_group_memory_candidates
                    SET status = ?,
                        applied_memory_id = COALESCE(NULLIF(?, ''), applied_memory_id),
                        review_note = ?,
                        reviewed_at = ?
                    WHERE room_id = ? AND candidate_id = ?
                    """,
                    (status, applied_memory_id, review_note, int(time.time()), room_id, candidate_id),
                )
        row = self.get_memory_candidate(room_id, candidate_id)
        if not row:
            raise ValueError("candidate_id is not found in this room")
        return row

    def _init_schema(self) -> None:
        with closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS wechat_group_messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        message_id TEXT NOT NULL UNIQUE,
                        room_id TEXT NOT NULL,
                        room_name TEXT,
                        sender_id TEXT,
                        sender_nickname TEXT,
                        message_type TEXT NOT NULL DEFAULT 'text',
                        text TEXT,
                        media_path TEXT,
                        is_at INTEGER NOT NULL DEFAULT 0,
                        metadata TEXT,
                        created_at INTEGER NOT NULL,
                        stable_room_id TEXT NOT NULL DEFAULT '',
                        runtime_room_id TEXT NOT NULL DEFAULT '',
                        stable_member_id TEXT NOT NULL DEFAULT '',
                        runtime_sender_id TEXT NOT NULL DEFAULT ''
                    )
                    """
                )
                _ensure_column(conn, "wechat_group_messages", "stable_room_id", "TEXT NOT NULL DEFAULT ''")
                _ensure_column(conn, "wechat_group_messages", "runtime_room_id", "TEXT NOT NULL DEFAULT ''")
                _ensure_column(conn, "wechat_group_messages", "stable_member_id", "TEXT NOT NULL DEFAULT ''")
                _ensure_column(conn, "wechat_group_messages", "runtime_sender_id", "TEXT NOT NULL DEFAULT ''")
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_wechat_group_messages_room_time
                    ON wechat_group_messages(room_id, created_at, id)
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_wechat_group_messages_stable_room_time
                    ON wechat_group_messages(stable_room_id, created_at, id)
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_wechat_group_messages_stable_room_member_time
                    ON wechat_group_messages(stable_room_id, stable_member_id, created_at, id)
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS wechat_group_assistant_replies (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        room_id TEXT NOT NULL,
                        room_name TEXT,
                        reply_type TEXT NOT NULL DEFAULT 'text',
                        content TEXT,
                        mention_ids TEXT,
                        created_at INTEGER NOT NULL,
                        stable_room_id TEXT NOT NULL DEFAULT '',
                        runtime_room_id TEXT NOT NULL DEFAULT '',
                        thread_id TEXT NOT NULL DEFAULT '',
                        request_id TEXT NOT NULL DEFAULT ''
                    )
                    """
                )
                _ensure_column(conn, "wechat_group_assistant_replies", "stable_room_id", "TEXT NOT NULL DEFAULT ''")
                _ensure_column(conn, "wechat_group_assistant_replies", "runtime_room_id", "TEXT NOT NULL DEFAULT ''")
                _ensure_column(conn, "wechat_group_assistant_replies", "thread_id", "TEXT NOT NULL DEFAULT ''")
                _ensure_column(conn, "wechat_group_assistant_replies", "request_id", "TEXT NOT NULL DEFAULT ''")
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_wechat_group_replies_stable_room_time
                    ON wechat_group_assistant_replies(stable_room_id, created_at, id)
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_wechat_group_replies_room_time
                    ON wechat_group_assistant_replies(room_id, created_at, id)
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS wechat_group_image_create_usage (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        room_id TEXT NOT NULL,
                        sender_id TEXT,
                        prompt TEXT,
                        status TEXT NOT NULL,
                        created_at INTEGER NOT NULL,
                        stable_room_id TEXT NOT NULL DEFAULT '',
                        runtime_room_id TEXT NOT NULL DEFAULT '',
                        stable_member_id TEXT NOT NULL DEFAULT '',
                        runtime_sender_id TEXT NOT NULL DEFAULT ''
                    )
                    """
                )
                _ensure_column(conn, "wechat_group_image_create_usage", "stable_room_id", "TEXT NOT NULL DEFAULT ''")
                _ensure_column(conn, "wechat_group_image_create_usage", "runtime_room_id", "TEXT NOT NULL DEFAULT ''")
                _ensure_column(conn, "wechat_group_image_create_usage", "stable_member_id", "TEXT NOT NULL DEFAULT ''")
                _ensure_column(conn, "wechat_group_image_create_usage", "runtime_sender_id", "TEXT NOT NULL DEFAULT ''")
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_wechat_group_image_usage_stable_room_time
                    ON wechat_group_image_create_usage(stable_room_id, created_at, id)
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_wechat_group_image_create_usage_room_time
                    ON wechat_group_image_create_usage(room_id, status, created_at)
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS wechat_group_memory_distill_runs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        run_id TEXT NOT NULL UNIQUE,
                        room_id TEXT NOT NULL,
                        since_ts INTEGER NOT NULL,
                        until_ts INTEGER NOT NULL,
                        message_count INTEGER NOT NULL DEFAULT 0,
                        status TEXT NOT NULL,
                        auto_applied_count INTEGER NOT NULL DEFAULT 0,
                        candidate_count INTEGER NOT NULL DEFAULT 0,
                        failed_reason TEXT,
                        raw_output_summary TEXT,
                        started_at INTEGER NOT NULL,
                        finished_at INTEGER
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_wechat_group_distill_runs_room_time
                    ON wechat_group_memory_distill_runs(room_id, started_at, id)
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS wechat_group_memory_candidates (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        candidate_id TEXT NOT NULL UNIQUE,
                        run_id TEXT NOT NULL,
                        room_id TEXT NOT NULL,
                        candidate_type TEXT NOT NULL,
                        target_sender_id TEXT,
                        target_sender_nickname TEXT,
                        content_json TEXT NOT NULL,
                        confidence REAL NOT NULL,
                        evidence_message_ids TEXT,
                        evidence_text TEXT,
                        status TEXT NOT NULL,
                        applied_memory_id TEXT,
                        review_note TEXT,
                        created_at INTEGER NOT NULL,
                        reviewed_at INTEGER
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_wechat_group_memory_candidates_room_status
                    ON wechat_group_memory_candidates(room_id, status, candidate_type, created_at)
                    """
                )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path, timeout=10)

    @staticmethod
    def _message_row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        data = dict(row)
        metadata = _parse_metadata(data.get("metadata"))
        data["metadata"] = metadata
        at_list = metadata.get("at_list") if isinstance(metadata, dict) else []
        data["at_list"] = [str(item) for item in at_list or [] if str(item or "").strip()]
        return data

    @staticmethod
    def _candidate_row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        data = dict(row)
        data["content"] = _loads_json(data.pop("content_json", "{}"), {})
        data["evidence_message_ids"] = _loads_json(data.get("evidence_message_ids"), [])
        return data


def _coerce_timestamp(value: Any = None) -> int:
    try:
        return int(value)
    except Exception:
        return int(time.time())


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    existing = {
        str(row[1])
        for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    }
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _parse_metadata(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="ignore")
    text = str(value)
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        pass
    try:
        parsed = ast.literal_eval(text)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _loads_json(value: Any, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def _extract_search_keywords(query: Any) -> List[str]:
    text = str(query or "").lower()
    tokens = re.findall(r"[\w\u4e00-\u9fff]+", text)
    stopwords = {
        "a", "an", "and", "are", "did", "for", "is", "of", "or", "the", "to",
        "was", "were", "what", "when", "where", "who", "whom", "why", "how",
        "this", "that", "these", "those", "please", "summarize",
    }
    keywords = []
    for token in tokens:
        token = token.strip("_")
        if len(token) < 2 or token in stopwords:
            continue
        if token not in keywords:
            keywords.append(token)
    return keywords[:8]


def _looks_like_raw_sender_name(value: Any, sender_id: str = "") -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    normalized = text.lstrip("@")
    sender_text = str(sender_id or "").strip()
    sender_normalized = sender_text.lstrip("@")
    if sender_text and text == sender_text:
        return True
    if sender_normalized and normalized == sender_normalized:
        return True
    if normalized.startswith("wxid_"):
        return True
    if text.startswith("@") and re.fullmatch(r"[0-9A-Za-z_-]{12,}", normalized):
        return True
    return False
