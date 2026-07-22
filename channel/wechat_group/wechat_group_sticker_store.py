"""SQLite store for WeChat group stickers."""

from __future__ import annotations

import hashlib
import os
import sqlite3
import threading
import time
from contextlib import closing
from typing import Dict, List, Optional


def _default_sticker_store_path() -> str:
    data_root = os.environ.get("LIGHTAGENT_DATA_DIR") or os.path.join(os.path.expanduser("~"), ".lightagent")
    return os.path.join(os.path.expanduser(data_root), "wechat_group", "wechat_group_sticker.db")


class WechatGroupStickerStore:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or _default_sticker_store_path()
        self._lock = threading.Lock()
        parent = os.path.dirname(self.db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._init_schema()

    def upsert_sticker(
        self,
        room_id: str,
        file_hash: str,
        media_path: str,
        description: str,
        source_message_id: str = "",
        status: str = "active",
        sticker_id: str = "",
        created_at: Optional[int] = None,
        updated_at: Optional[int] = None,
    ) -> Dict:
        room_text = str(room_id or "").strip()
        hash_text = str(file_hash or "").strip()
        path_text = str(media_path or "").strip()
        if not room_text or not hash_text or not path_text:
            raise ValueError("room_id, file_hash and media_path are required")
        sticker_text = str(sticker_id or "").strip() or _build_sticker_id(room_text, hash_text)
        now = _coerce_timestamp(updated_at)
        created_ts = _coerce_timestamp(created_at) if created_at is not None else now
        with self._lock, closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO wechat_group_stickers (
                        sticker_id, room_id, file_hash, media_path, description,
                        source_message_id, use_count, status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?)
                    ON CONFLICT(room_id, file_hash) DO UPDATE SET
                        media_path = excluded.media_path,
                        description = CASE
                            WHEN excluded.description != '' THEN excluded.description
                            ELSE wechat_group_stickers.description
                        END,
                        source_message_id = CASE
                            WHEN excluded.source_message_id != '' THEN excluded.source_message_id
                            ELSE wechat_group_stickers.source_message_id
                        END,
                        status = excluded.status,
                        updated_at = excluded.updated_at
                    """,
                    (
                        sticker_text,
                        room_text,
                        hash_text,
                        path_text,
                        str(description or "").strip(),
                        str(source_message_id or "").strip(),
                        str(status or "active").strip() or "active",
                        created_ts,
                        now,
                    ),
                )
        return self.get_sticker_by_hash(room_text, hash_text) or {}

    def get_sticker(self, room_id: str, sticker_id: str) -> Optional[Dict]:
        room_text = str(room_id or "").strip()
        sticker_text = str(sticker_id or "").strip()
        if not room_text or not sticker_text:
            return None
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT *
                FROM wechat_group_stickers
                WHERE room_id = ? AND sticker_id = ?
                LIMIT 1
                """,
                (room_text, sticker_text),
            ).fetchone()
        return dict(row) if row else None

    def get_sticker_by_hash(self, room_id: str, file_hash: str) -> Optional[Dict]:
        room_text = str(room_id or "").strip()
        hash_text = str(file_hash or "").strip()
        if not room_text or not hash_text:
            return None
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT *
                FROM wechat_group_stickers
                WHERE room_id = ? AND file_hash = ?
                LIMIT 1
                """,
                (room_text, hash_text),
            ).fetchone()
        return dict(row) if row else None

    def list_stickers(
        self,
        room_id: str,
        query: str = "",
        status: str = "active",
        limit: int = 20,
    ) -> List[Dict]:
        room_text = str(room_id or "").strip()
        if not room_text:
            return []
        clauses = ["room_id = ?"]
        params = [room_text]
        status_text = str(status or "").strip()
        if status_text:
            clauses.append("status = ?")
            params.append(status_text)
        query_text = str(query or "").strip().lower()
        if query_text:
            clauses.append("(LOWER(description) LIKE ? OR LOWER(media_path) LIKE ?)")
            like = f"%{query_text}%"
            params.extend([like, like])
        params.append(min(max(int(limit or 20), 1), 100))
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"""
                SELECT *
                FROM wechat_group_stickers
                WHERE {' AND '.join(clauses)}
                ORDER BY use_count DESC, updated_at DESC, sticker_id DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def update_status(self, room_id: str, sticker_id: str, status: str) -> Dict:
        room_text = str(room_id or "").strip()
        sticker_text = str(sticker_id or "").strip()
        if not room_text or not sticker_text:
            raise ValueError("room_id and sticker_id are required")
        with self._lock, closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    """
                    UPDATE wechat_group_stickers
                    SET status = ?, updated_at = ?
                    WHERE room_id = ? AND sticker_id = ?
                    """,
                    (str(status or "active").strip() or "active", int(time.time()), room_text, sticker_text),
                )
        return self.get_sticker(room_text, sticker_text) or {}

    def update_description(
        self,
        room_id: str,
        sticker_id: str,
        description: str,
        expected_description: Optional[str] = None,
    ) -> Dict:
        room_text = str(room_id or "").strip()
        sticker_text = str(sticker_id or "").strip()
        description_text = str(description or "").strip()
        if not room_text or not sticker_text:
            raise ValueError("room_id and sticker_id are required")
        clauses = ["room_id = ?", "sticker_id = ?"]
        params = [description_text, int(time.time()), room_text, sticker_text]
        if expected_description is not None:
            clauses.append("description = ?")
            params.append(str(expected_description))
        with self._lock, closing(self._connect()) as conn:
            with conn:
                cursor = conn.execute(
                    """
                    UPDATE wechat_group_stickers
                    SET description = ?, updated_at = ?
                    WHERE {}
                    """.format(" AND ".join(clauses)),
                    params,
                )
        if int(cursor.rowcount or 0) <= 0:
            return {}
        return self.get_sticker(room_text, sticker_text) or {}

    def record_usage(self, room_id: str, sticker_id: str, created_at: Optional[int] = None) -> Dict:
        room_text = str(room_id or "").strip()
        sticker_text = str(sticker_id or "").strip()
        if not room_text or not sticker_text:
            raise ValueError("room_id and sticker_id are required")
        ts = _coerce_timestamp(created_at)
        with self._lock, closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO wechat_group_sticker_usage (
                        room_id, sticker_id, created_at
                    ) VALUES (?, ?, ?)
                    """,
                    (room_text, sticker_text, ts),
                )
                conn.execute(
                    """
                    UPDATE wechat_group_stickers
                    SET use_count = use_count + 1,
                        updated_at = ?
                    WHERE room_id = ? AND sticker_id = ?
                    """,
                    (ts, room_text, sticker_text),
                )
        return self.get_sticker(room_text, sticker_text) or {}

    def count_usage(self, room_id: str, since_ts: int) -> int:
        room_text = str(room_id or "").strip()
        if not room_text:
            return 0
        with self._lock, closing(self._connect()) as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM wechat_group_sticker_usage
                WHERE room_id = ?
                  AND created_at >= ?
                """,
                (room_text, int(since_ts or 0)),
            ).fetchone()
        return int(row[0] or 0) if row else 0

    def _init_schema(self):
        with closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS wechat_group_stickers (
                        sticker_id TEXT PRIMARY KEY,
                        room_id TEXT NOT NULL,
                        file_hash TEXT NOT NULL,
                        media_path TEXT NOT NULL,
                        description TEXT NOT NULL DEFAULT '',
                        source_message_id TEXT NOT NULL DEFAULT '',
                        use_count INTEGER NOT NULL DEFAULT 0,
                        status TEXT NOT NULL DEFAULT 'active',
                        created_at INTEGER NOT NULL,
                        updated_at INTEGER NOT NULL,
                        UNIQUE(room_id, file_hash)
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_wechat_group_stickers_room_status
                    ON wechat_group_stickers(room_id, status, updated_at)
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS wechat_group_sticker_usage (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        room_id TEXT NOT NULL,
                        sticker_id TEXT NOT NULL,
                        created_at INTEGER NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_wechat_group_sticker_usage_room_time
                    ON wechat_group_sticker_usage(room_id, created_at, id)
                    """
                )

    def _connect(self):
        return sqlite3.connect(self.db_path, timeout=10)


def _coerce_timestamp(value=None) -> int:
    try:
        return int(value)
    except Exception:
        return int(time.time())


def _build_sticker_id(room_id: str, file_hash: str) -> str:
    payload = "|".join([str(room_id or "").strip(), str(file_hash or "").strip()])
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:24]
