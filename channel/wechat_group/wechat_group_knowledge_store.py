"""SQLite store for WeChat group-scoped knowledge."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from contextlib import closing
from typing import Any, Dict, List, Optional
from uuid import uuid4


def _default_knowledge_store_path() -> str:
    data_root = os.environ.get("LIGHTAGENT_DATA_DIR") or os.path.join(os.path.expanduser("~"), ".lightagent")
    return os.path.join(os.path.expanduser(data_root), "wechat_group", "wechat_group_knowledge.db")


class WechatGroupKnowledgeStore:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or _default_knowledge_store_path()
        self._lock = threading.Lock()
        parent = os.path.dirname(self.db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._init_schema()

    def add_group_memory(self, room_id: str, content: str, **extra) -> Dict[str, Any]:
        room_id = _require_text("room_id", room_id)
        content = _require_text("content", content)
        now = int(time.time())
        memory_id = str(extra.get("memory_id") or uuid4().hex)
        evidence_message_ids = _normalize_list(extra.get("evidence_message_ids"))
        with self._lock, closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO wechat_group_group_memories (
                        memory_id, room_id, content, source_kind,
                        evidence_message_ids_json, evidence_text, status,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        memory_id,
                        room_id,
                        content,
                        str(extra.get("source_kind") or "learning"),
                        json.dumps(evidence_message_ids, ensure_ascii=False),
                        str(extra.get("evidence_text") or ""),
                        str(extra.get("status") or "active"),
                        int(extra.get("created_at") or now),
                        int(extra.get("updated_at") or now),
                    ),
                )
        return self.get_group_memory(room_id, memory_id) or {}

    def get_group_memory(self, room_id: str, memory_id: str) -> Optional[Dict[str, Any]]:
        if not room_id or not memory_id:
            return None
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT *
                FROM wechat_group_group_memories
                WHERE room_id = ? AND memory_id = ?
                LIMIT 1
                """,
                (str(room_id), str(memory_id)),
            ).fetchone()
        return self._memory_row_to_dict(row) if row else None

    def list_group_memories(
        self,
        room_id: str,
        query: str = "",
        limit: int = 20,
        status: str = "active",
    ) -> List[Dict[str, Any]]:
        room_id = _require_text("room_id", room_id)
        max_limit = min(max(int(limit or 20), 1), 200)
        params: List[Any] = [room_id, status]
        clauses = ["room_id = ?", "status = ?"]
        q = str(query or "").strip()
        if q:
            clauses.append("(content LIKE ? OR evidence_text LIKE ?)")
            like = f"%{q}%"
            params.extend([like, like])
        params.append(max_limit)
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"""
                SELECT *
                FROM wechat_group_group_memories
                WHERE {' AND '.join(clauses)}
                ORDER BY updated_at DESC, memory_id DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [self._memory_row_to_dict(row) for row in rows]

    def update_group_memory_status(self, room_id: str, memory_id: str, status: str) -> bool:
        room_id = _require_text("room_id", room_id)
        memory_id = _require_text("memory_id", memory_id)
        status = _require_text("status", status)
        with self._lock, closing(self._connect()) as conn:
            with conn:
                cursor = conn.execute(
                    """
                    UPDATE wechat_group_group_memories
                    SET status = ?, updated_at = ?
                    WHERE room_id = ? AND memory_id = ?
                    """,
                    (status, int(time.time()), room_id, memory_id),
                )
        return bool(cursor.rowcount)

    def get_cursor(self, room_id: str) -> Dict[str, Any]:
        room_id = _require_text("room_id", room_id)
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT *
                FROM wechat_group_learning_cursors
                WHERE room_id = ?
                LIMIT 1
                """,
                (room_id,),
            ).fetchone()
        if row:
            return dict(row)
        return {"room_id": room_id, "last_archive_row_id": 0, "updated_at": 0}

    def update_cursor(self, room_id: str, last_archive_row_id: int) -> None:
        room_id = _require_text("room_id", room_id)
        now = int(time.time())
        with self._lock, closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO wechat_group_learning_cursors (
                        room_id, last_archive_row_id, updated_at
                    ) VALUES (?, ?, ?)
                    ON CONFLICT(room_id) DO UPDATE SET
                        last_archive_row_id = excluded.last_archive_row_id,
                        updated_at = excluded.updated_at
                    """,
                    (room_id, int(last_archive_row_id or 0), now),
                )

    def create_learning_run(self, room_id: str, mode: str, batch_start_row_id: int) -> str:
        room_id = _require_text("room_id", room_id)
        mode = _require_text("mode", mode)
        run_id = uuid4().hex
        now = int(time.time())
        with self._lock, closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO wechat_group_learning_runs (
                        run_id, room_id, mode, batch_start_row_id, batch_end_row_id,
                        batch_message_count, profile_update_count, group_memory_upsert_count,
                        status, failed_reason, started_at, finished_at
                    ) VALUES (?, ?, ?, ?, 0, 0, 0, 0, 'running', '', ?, 0)
                    """,
                    (run_id, room_id, mode, int(batch_start_row_id or 0), now),
                )
        return run_id

    def finish_learning_run(
        self,
        run_id: str,
        status: str,
        batch_end_row_id: int,
        batch_message_count: int,
        profile_update_count: int,
        group_memory_upsert_count: int,
        failed_reason: str = "",
    ) -> None:
        with self._lock, closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    """
                    UPDATE wechat_group_learning_runs
                    SET status = ?,
                        batch_end_row_id = ?,
                        batch_message_count = ?,
                        profile_update_count = ?,
                        group_memory_upsert_count = ?,
                        failed_reason = ?,
                        finished_at = ?
                    WHERE run_id = ?
                    """,
                    (
                        str(status or "failed"),
                        int(batch_end_row_id or 0),
                        int(batch_message_count or 0),
                        int(profile_update_count or 0),
                        int(group_memory_upsert_count or 0),
                        str(failed_reason or ""),
                        int(time.time()),
                        str(run_id),
                    ),
                )

    def list_learning_runs(self, room_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        room_id = _require_text("room_id", room_id)
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT *
                FROM wechat_group_learning_runs
                WHERE room_id = ?
                ORDER BY started_at DESC, run_id DESC
                LIMIT ?
                """,
                (room_id, min(max(int(limit or 20), 1), 100)),
            ).fetchall()
        return [dict(row) for row in rows]

    def _init_schema(self) -> None:
        with closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS wechat_group_group_memories (
                        memory_id TEXT PRIMARY KEY,
                        room_id TEXT NOT NULL,
                        content TEXT NOT NULL,
                        source_kind TEXT NOT NULL DEFAULT 'learning',
                        evidence_message_ids_json TEXT NOT NULL DEFAULT '[]',
                        evidence_text TEXT NOT NULL DEFAULT '',
                        status TEXT NOT NULL DEFAULT 'active',
                        created_at INTEGER NOT NULL,
                        updated_at INTEGER NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_wechat_group_group_memories_room_status
                    ON wechat_group_group_memories(room_id, status, updated_at)
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS wechat_group_learning_cursors (
                        room_id TEXT PRIMARY KEY,
                        last_archive_row_id INTEGER NOT NULL DEFAULT 0,
                        updated_at INTEGER NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS wechat_group_learning_runs (
                        run_id TEXT PRIMARY KEY,
                        room_id TEXT NOT NULL,
                        mode TEXT NOT NULL,
                        batch_start_row_id INTEGER NOT NULL DEFAULT 0,
                        batch_end_row_id INTEGER NOT NULL DEFAULT 0,
                        batch_message_count INTEGER NOT NULL DEFAULT 0,
                        profile_update_count INTEGER NOT NULL DEFAULT 0,
                        group_memory_upsert_count INTEGER NOT NULL DEFAULT 0,
                        status TEXT NOT NULL,
                        failed_reason TEXT NOT NULL DEFAULT '',
                        started_at INTEGER NOT NULL,
                        finished_at INTEGER NOT NULL DEFAULT 0
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_wechat_group_learning_runs_room_time
                    ON wechat_group_learning_runs(room_id, started_at, run_id)
                    """
                )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path, timeout=10)

    @staticmethod
    def _memory_row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        data = dict(row)
        data["evidence_message_ids"] = _loads_json(data.pop("evidence_message_ids_json", "[]"), [])
        return data


def _require_text(name: str, value: str) -> str:
    value = str(value or "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


def _normalize_list(value: Any) -> List[str]:
    if value is None:
        items = []
    elif isinstance(value, list):
        items = value
    else:
        items = str(value).replace("\n", ",").split(",")
    result = []
    for item in items:
        text = str(item or "").strip()
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
