"""SQLite store for WeChat group focus stacks."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from contextlib import closing
from typing import Any, Dict, List, Optional
from uuid import uuid4


def _default_data_root() -> str:
    return os.environ.get("LIGHTAGENT_DATA_DIR") or os.path.join(os.path.expanduser("~"), ".lightagent")


def _default_focus_store_path() -> str:
    return os.path.join(os.path.expanduser(_default_data_root()), "wechat_group", "wechat_group_focus.db")


def legacy_topic_db_path(data_root: str = "") -> str:
    root = os.path.expanduser(data_root or _default_data_root())
    direct = os.path.join(root, "wechat_group_topics.db")
    if data_root and os.path.exists(direct):
        return direct
    return os.path.join(root, "wechat_group", "wechat_group_topics.db")


def discard_legacy_topic_data(data_root: str = "") -> bool:
    root = os.path.expanduser(data_root or _default_data_root())
    candidates = [
        legacy_topic_db_path(data_root),
        os.path.join(root, "wechat_group_topics.db"),
        os.path.join(root, "wechat_group", "wechat_group_topics.db"),
    ]
    discarded = False
    for path in _unique_texts(candidates):
        if not path or not os.path.exists(path):
            continue
        try:
            os.remove(path)
            discarded = True
            continue
        except OSError:
            pass
        conn = sqlite3.connect(path, timeout=10)
        try:
            with conn:
                conn.execute("DROP TABLE IF EXISTS wechat_group_topic_threads")
                conn.execute("DROP TABLE IF EXISTS wechat_group_topic_message_refs")
                conn.execute("DROP TABLE IF EXISTS wechat_group_topic_summary_history")
            discarded = True
        finally:
            conn.close()
    return discarded


class WechatGroupFocusStore:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or _default_focus_store_path()
        self._lock = threading.Lock()
        parent = os.path.dirname(self.db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        discard_legacy_topic_data()
        self._init_schema()

    def load_stack(self, room_id: str) -> List[Dict[str, Any]]:
        room_text = str(room_id or "").strip()
        if not room_text:
            return []
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT *
                FROM wechat_group_focus_frames
                WHERE room_id = ? AND status = 'active'
                ORDER BY depth ASC, last_seen_at ASC, frame_id ASC
                """,
                (room_text,),
            ).fetchall()
        return [self._frame_row_to_dict(row) for row in rows]

    def save_stack(self, room_id: str, frames: List[Dict[str, Any]]) -> None:
        room_text = _require_text("room_id", room_id)
        now = int(time.time())
        normalized = []
        for index, frame in enumerate(frames or []):
            if not isinstance(frame, dict):
                continue
            item = dict(frame)
            item["room_id"] = room_text
            item["depth"] = int(item.get("depth") if item.get("depth") is not None else index)
            item["frame_id"] = str(item.get("frame_id") or uuid4().hex)
            item["topic"] = _normalize_list(item.get("topic"))
            item["participants"] = _normalize_list(item.get("participants"))
            item["conclusions"] = _normalize_list(item.get("conclusions"))
            item["title"] = str(item.get("title") or _build_title_from_topic(item["topic"])).strip()
            item["summary"] = str(item.get("summary") or "").strip()
            item["started_at"] = int(item.get("started_at") or now)
            item["started_row_id"] = int(item.get("started_row_id") or item.get("last_row_id") or 0)
            item["last_seen_at"] = int(item.get("last_seen_at") or now)
            item["last_row_id"] = int(item.get("last_row_id") or 0)
            item["hit_count"] = max(int(item.get("hit_count") or 1), 1)
            item["status"] = str(item.get("status") or "active").strip() or "active"
            normalized.append(item)
        normalized.sort(key=lambda item: int(item.get("depth") or 0))
        with self._lock, closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    "DELETE FROM wechat_group_focus_frames WHERE room_id = ? AND status = 'active'",
                    (room_text,),
                )
                for depth, item in enumerate(normalized):
                    conn.execute(
                        """
                        INSERT INTO wechat_group_focus_frames (
                            frame_id, room_id, depth, topic_json, title, summary,
                            participants_json, conclusions_json, started_at,
                            started_row_id, last_seen_at, last_row_id, hit_count, status
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            item["frame_id"],
                            room_text,
                            depth,
                            json.dumps(item["topic"], ensure_ascii=False),
                            item["title"],
                            item["summary"],
                            json.dumps(item["participants"], ensure_ascii=False),
                            json.dumps(item["conclusions"], ensure_ascii=False),
                            item["started_at"],
                            item["started_row_id"],
                            item["last_seen_at"],
                            item["last_row_id"],
                            item["hit_count"],
                            item["status"],
                        ),
                    )

    def clear_room(self, room_id: str) -> int:
        room_text = str(room_id or "").strip()
        if not room_text:
            return 0
        with self._lock, closing(self._connect()) as conn:
            with conn:
                cur_refs = conn.execute(
                    "DELETE FROM wechat_group_focus_message_refs WHERE room_id = ?",
                    (room_text,),
                )
                cur_frames = conn.execute(
                    "DELETE FROM wechat_group_focus_frames WHERE room_id = ?",
                    (room_text,),
                )
        return int((cur_refs.rowcount or 0) + (cur_frames.rowcount or 0))

    def append_message_ref(
        self,
        room_id: str,
        frame_id: str,
        message_id: str = "",
        row_id: int = 0,
        created_at: Optional[int] = None,
    ) -> Dict[str, Any]:
        room_text = _require_text("room_id", room_id)
        frame_text = _require_text("frame_id", frame_id)
        message_text = str(message_id or "").strip()
        row_value = int(row_id or 0)
        if not message_text and row_value <= 0:
            raise ValueError("message_id or row_id is required")
        now = _coerce_timestamp(created_at)
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            with conn:
                cur = conn.execute(
                    """
                    INSERT INTO wechat_group_focus_message_refs (
                        room_id, frame_id, message_id, row_id, created_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (room_text, frame_text, message_text, row_value, now),
                )
                row = conn.execute(
                    """
                    SELECT *
                    FROM wechat_group_focus_message_refs
                    WHERE id = ?
                    """,
                    (cur.lastrowid,),
                ).fetchone()
        return dict(row) if row else {}

    def list_message_refs(self, room_id: str, frame_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        room_text = str(room_id or "").strip()
        frame_text = str(frame_id or "").strip()
        if not room_text or not frame_text:
            return []
        max_limit = min(max(int(limit or 20), 1), 200)
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT *
                FROM wechat_group_focus_message_refs
                WHERE room_id = ? AND frame_id = ?
                ORDER BY row_id DESC, created_at DESC, id DESC
                LIMIT ?
                """,
                (room_text, frame_text, max_limit),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def search_frames(self, room_id: str, query: str = "", limit: int = 20) -> List[Dict[str, Any]]:
        room_text = str(room_id or "").strip()
        if not room_text:
            return []
        max_limit = min(max(int(limit or 20), 1), 100)
        clauses = ["room_id = ?"]
        params: List[Any] = [room_text]
        query_text = str(query or "").strip()
        if query_text:
            like = f"%{query_text}%"
            clauses.append("(title LIKE ? OR summary LIKE ? OR topic_json LIKE ?)")
            params.extend([like, like, like])
        params.append(max_limit)
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"""
                SELECT *
                FROM wechat_group_focus_frames
                WHERE {' AND '.join(clauses)}
                ORDER BY last_seen_at DESC, depth DESC, frame_id DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [self._frame_row_to_dict(row) for row in rows]

    def _init_schema(self) -> None:
        with closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS wechat_group_focus_frames (
                        frame_id TEXT PRIMARY KEY,
                        room_id TEXT NOT NULL,
                        depth INTEGER NOT NULL,
                        topic_json TEXT NOT NULL DEFAULT '[]',
                        title TEXT NOT NULL DEFAULT '',
                        summary TEXT NOT NULL DEFAULT '',
                        participants_json TEXT NOT NULL DEFAULT '[]',
                        conclusions_json TEXT NOT NULL DEFAULT '[]',
                        started_at INTEGER NOT NULL,
                        started_row_id INTEGER NOT NULL DEFAULT 0,
                        last_seen_at INTEGER NOT NULL,
                        last_row_id INTEGER NOT NULL DEFAULT 0,
                        hit_count INTEGER NOT NULL DEFAULT 1,
                        status TEXT NOT NULL DEFAULT 'active'
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_wechat_group_focus_frames_room_depth
                    ON wechat_group_focus_frames(room_id, depth)
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_wechat_group_focus_frames_room_status
                    ON wechat_group_focus_frames(room_id, status, last_seen_at)
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS wechat_group_focus_message_refs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        room_id TEXT NOT NULL,
                        frame_id TEXT NOT NULL,
                        message_id TEXT NOT NULL DEFAULT '',
                        row_id INTEGER NOT NULL DEFAULT 0,
                        created_at INTEGER NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_wechat_group_focus_refs_room_frame
                    ON wechat_group_focus_message_refs(room_id, frame_id, row_id)
                    """
                )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path, timeout=10)

    @staticmethod
    def _frame_row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        data = dict(row)
        data["topic"] = _loads_json(data.pop("topic_json", "[]"), [])
        data["participants"] = _loads_json(data.pop("participants_json", "[]"), [])
        data["conclusions"] = _loads_json(data.pop("conclusions_json", "[]"), [])
        return data


def _require_text(name: str, value: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} is required")
    return text


def _normalize_list(value: Any) -> List[str]:
    if value is None:
        return []
    items = value if isinstance(value, list) else [value]
    result = []
    for item in items:
        text = str(item or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def _unique_texts(values: List[str]) -> List[str]:
    result = []
    for value in values or []:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def _loads_json(value: Any, default: Any) -> Any:
    if not value:
        return default
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, type(default)) else default
    except Exception:
        return default


def _coerce_timestamp(value: Any = None) -> int:
    try:
        return int(value)
    except Exception:
        return int(time.time())


def _build_title_from_topic(topic: List[str]) -> str:
    title = "".join(str(item or "").strip() for item in (topic or [])[:3])
    return title[:24] if title else "recent focus"
