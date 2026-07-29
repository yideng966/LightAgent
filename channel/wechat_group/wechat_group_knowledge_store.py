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
                        source_run_id, confidence, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        memory_id,
                        room_id,
                        content,
                        str(extra.get("source_kind") or "learning"),
                        json.dumps(evidence_message_ids, ensure_ascii=False),
                        str(extra.get("evidence_text") or ""),
                        str(extra.get("status") or "active"),
                        str(extra.get("source_run_id") or ""),
                        float(extra.get("confidence") or 0.0),
                        int(extra.get("created_at") or now),
                        int(extra.get("updated_at") or now),
                    ),
                )
        return self.get_group_memory(room_id, memory_id) or {}

    def upsert_group_memory(self, room_id: str, content: str, **extra) -> Dict[str, Any]:
        """Create or replace a deterministic room-scoped memory by memory_id."""
        room_id = _require_text("room_id", room_id)
        content = _require_text("content", content)
        memory_id = _require_text("memory_id", extra.get("memory_id"))
        now = int(time.time())
        evidence_message_ids = _normalize_list(extra.get("evidence_message_ids"))
        with self._lock, closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO wechat_group_group_memories (
                        memory_id, room_id, content, source_kind,
                        evidence_message_ids_json, evidence_text, status,
                        source_run_id, confidence, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(memory_id) DO UPDATE SET
                        room_id = excluded.room_id,
                        content = excluded.content,
                        source_kind = excluded.source_kind,
                        evidence_message_ids_json = excluded.evidence_message_ids_json,
                        evidence_text = excluded.evidence_text,
                        status = excluded.status,
                        source_run_id = excluded.source_run_id,
                        confidence = excluded.confidence,
                        updated_at = excluded.updated_at
                    """,
                    (
                        memory_id,
                        room_id,
                        content,
                        str(extra.get("source_kind") or "learning"),
                        json.dumps(evidence_message_ids, ensure_ascii=False),
                        str(extra.get("evidence_text") or ""),
                        str(extra.get("status") or "active"),
                        str(extra.get("source_run_id") or ""),
                        float(extra.get("confidence") or 0.0),
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
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        room_id = _require_text("room_id", room_id)
        max_limit = min(max(int(limit or 20), 1), 1000)
        safe_offset = max(int(offset or 0), 0)
        params: List[Any] = [room_id, status]
        clauses = ["room_id = ?", "status = ?"]
        q = str(query or "").strip()
        if q:
            clauses.append("(content LIKE ? OR evidence_text LIKE ?)")
            like = f"%{q}%"
            params.extend([like, like])
        params.extend([max_limit, safe_offset])
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"""
                SELECT *
                FROM wechat_group_group_memories
                WHERE {' AND '.join(clauses)}
                ORDER BY updated_at DESC, memory_id DESC
                LIMIT ? OFFSET ?
                """,
                params,
            ).fetchall()
        return [self._memory_row_to_dict(row) for row in rows]

    def count_group_memories(
        self,
        room_id: str,
        query: str = "",
        status: str = "active",
    ) -> int:
        room_id = _require_text("room_id", room_id)
        params: List[Any] = [room_id, status]
        clauses = ["room_id = ?", "status = ?"]
        q = str(query or "").strip()
        if q:
            clauses.append("(content LIKE ? OR evidence_text LIKE ?)")
            like = f"%{q}%"
            params.extend([like, like])
        with self._lock, closing(self._connect()) as conn:
            row = conn.execute(
                f"""
                SELECT COUNT(*)
                FROM wechat_group_group_memories
                WHERE {' AND '.join(clauses)}
                """,
                params,
            ).fetchone()
        return int(row[0] or 0) if row else 0

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

    def get_scheduler_state(self, room_id: str) -> Dict[str, Any]:
        room_id = _require_text("room_id", room_id)
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT * FROM wechat_group_memory_scheduler_state
                WHERE room_id = ?
                LIMIT 1
                """,
                (room_id,),
            ).fetchone()
        if row:
            return dict(row)
        return _empty_scheduler_state(room_id)

    def update_scheduler_state(self, room_id: str, **changes) -> Dict[str, Any]:
        room_id = _require_text("room_id", room_id)
        allowed = {
            "latest_observed_row_id",
            "last_signal_at",
            "last_attempt_at",
            "last_success_at",
            "next_retry_at",
            "consecutive_failures",
            "last_failed_reason_code",
            "initialized_at",
            "initialization_mode",
        }
        unexpected = set(changes) - allowed
        if unexpected:
            raise ValueError(f"unsupported scheduler state fields: {sorted(unexpected)}")
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM wechat_group_memory_scheduler_state WHERE room_id = ?",
                (room_id,),
            ).fetchone()
            state = dict(row) if row else _empty_scheduler_state(room_id)
            state.update(changes)
            state["updated_at"] = int(time.time())
            with conn:
                conn.execute(
                    """
                    INSERT INTO wechat_group_memory_scheduler_state (
                        room_id, latest_observed_row_id, last_signal_at,
                        last_attempt_at, last_success_at, next_retry_at,
                        consecutive_failures, last_failed_reason_code,
                        initialized_at, initialization_mode, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(room_id) DO UPDATE SET
                        latest_observed_row_id = excluded.latest_observed_row_id,
                        last_signal_at = excluded.last_signal_at,
                        last_attempt_at = excluded.last_attempt_at,
                        last_success_at = excluded.last_success_at,
                        next_retry_at = excluded.next_retry_at,
                        consecutive_failures = excluded.consecutive_failures,
                        last_failed_reason_code = excluded.last_failed_reason_code,
                        initialized_at = excluded.initialized_at,
                        initialization_mode = excluded.initialization_mode,
                        updated_at = excluded.updated_at
                    """,
                    (
                        room_id,
                        int(state.get("latest_observed_row_id") or 0),
                        int(state.get("last_signal_at") or 0),
                        int(state.get("last_attempt_at") or 0),
                        int(state.get("last_success_at") or 0),
                        int(state.get("next_retry_at") or 0),
                        int(state.get("consecutive_failures") or 0),
                        str(state.get("last_failed_reason_code") or ""),
                        int(state.get("initialized_at") or 0),
                        str(state.get("initialization_mode") or ""),
                        int(state.get("updated_at") or 0),
                    ),
                )
        return state

    def get_backfill_state(self, room_id: str) -> Dict[str, Any]:
        room_id = _require_text("room_id", room_id)
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT * FROM wechat_group_memory_backfill_state
                WHERE room_id = ?
                LIMIT 1
                """,
                (room_id,),
            ).fetchone()
        if row:
            return dict(row)
        return _empty_backfill_state(room_id)

    def update_backfill_state(self, room_id: str, **changes) -> Dict[str, Any]:
        room_id = _require_text("room_id", room_id)
        allowed = {
            "cursor_row_id",
            "target_row_id",
            "status",
            "completed_batches",
            "last_failed_reason_code",
            "started_at",
            "finished_at",
        }
        unexpected = set(changes) - allowed
        if unexpected:
            raise ValueError(f"unsupported backfill state fields: {sorted(unexpected)}")
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM wechat_group_memory_backfill_state WHERE room_id = ?",
                (room_id,),
            ).fetchone()
            state = dict(row) if row else _empty_backfill_state(room_id)
            state.update(changes)
            state["updated_at"] = int(time.time())
            with conn:
                conn.execute(
                    """
                    INSERT INTO wechat_group_memory_backfill_state (
                        room_id, cursor_row_id, target_row_id, status,
                        completed_batches, last_failed_reason_code,
                        started_at, updated_at, finished_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(room_id) DO UPDATE SET
                        cursor_row_id = excluded.cursor_row_id,
                        target_row_id = excluded.target_row_id,
                        status = excluded.status,
                        completed_batches = excluded.completed_batches,
                        last_failed_reason_code = excluded.last_failed_reason_code,
                        started_at = excluded.started_at,
                        updated_at = excluded.updated_at,
                        finished_at = excluded.finished_at
                    """,
                    (
                        room_id,
                        int(state.get("cursor_row_id") or 0),
                        int(state.get("target_row_id") or 0),
                        str(state.get("status") or "idle"),
                        int(state.get("completed_batches") or 0),
                        str(state.get("last_failed_reason_code") or ""),
                        int(state.get("started_at") or 0),
                        int(state.get("updated_at") or 0),
                        int(state.get("finished_at") or 0),
                    ),
                )
        return state

    def create_learning_run(
        self,
        room_id: str,
        mode: str,
        batch_start_row_id: int,
        trigger_source: str = "manual",
    ) -> str:
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
                        status, failed_reason, trigger_source, summary_status,
                        dream_status, skipped_count, dream_summary, llm_status_code,
                        started_at, finished_at
                    ) VALUES (?, ?, ?, ?, 0, 0, 0, 0, 'running', '', ?, '', '', 0, '', 0, ?, 0)
                    """,
                    (
                        run_id,
                        room_id,
                        mode,
                        int(batch_start_row_id or 0),
                        str(trigger_source or "manual"),
                        now,
                    ),
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
        summary_status: str = "",
        dream_status: str = "",
        skipped_count: int = 0,
        dream_summary: str = "",
        llm_status_code: int = 0,
        batch_eligible_count: int = 0,
        batch_filtered_count: int = 0,
        pending_before_count: int = 0,
        pending_after_count: int = 0,
        cursor_before: int = 0,
        cursor_after: int = 0,
        summary_duration_ms: int = 0,
        dream_duration_ms: int = 0,
        total_duration_ms: int = 0,
        failure_code: str = "",
        fallback_used: bool = False,
        attempt_count: int = 0,
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
                        summary_status = ?,
                        dream_status = ?,
                        skipped_count = ?,
                        dream_summary = ?,
                        llm_status_code = ?,
                        batch_eligible_count = ?,
                        batch_filtered_count = ?,
                        pending_before_count = ?,
                        pending_after_count = ?,
                        cursor_before = ?,
                        cursor_after = ?,
                        summary_duration_ms = ?,
                        dream_duration_ms = ?,
                        total_duration_ms = ?,
                        failure_code = ?,
                        fallback_used = ?,
                        attempt_count = ?,
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
                        str(summary_status or ""),
                        str(dream_status or ""),
                        int(skipped_count or 0),
                        str(dream_summary or ""),
                        int(llm_status_code or 0),
                        int(batch_eligible_count or 0),
                        int(batch_filtered_count or 0),
                        int(pending_before_count or 0),
                        int(pending_after_count or 0),
                        int(cursor_before or 0),
                        int(cursor_after or 0),
                        int(summary_duration_ms or 0),
                        int(dream_duration_ms or 0),
                        int(total_duration_ms or 0),
                        str(failure_code or "")[:120],
                        1 if fallback_used else 0,
                        int(attempt_count or 0),
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

    def interrupt_running_learning_runs(self, reason: str = "process_restarted") -> int:
        now = int(time.time())
        with self._lock, closing(self._connect()) as conn:
            with conn:
                cursor = conn.execute(
                    """
                    UPDATE wechat_group_learning_runs
                    SET status = 'interrupted',
                        interrupted_reason = ?,
                        finished_at = ?
                    WHERE status = 'running'
                    """,
                    (str(reason or "process_restarted")[:120], now),
                )
                conn.execute(
                    """
                    UPDATE wechat_group_memory_backfill_state
                    SET status = 'interrupted', updated_at = ?
                    WHERE status = 'running'
                    """,
                    (now,),
                )
        return int(cursor.rowcount or 0)

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
                        source_run_id TEXT NOT NULL DEFAULT '',
                        confidence REAL NOT NULL DEFAULT 0,
                        created_at INTEGER NOT NULL,
                        updated_at INTEGER NOT NULL
                    )
                    """
                )
                _ensure_column(conn, "wechat_group_group_memories", "source_run_id", "TEXT NOT NULL DEFAULT ''")
                _ensure_column(conn, "wechat_group_group_memories", "confidence", "REAL NOT NULL DEFAULT 0")
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_wechat_group_group_memories_room_status
                    ON wechat_group_group_memories(room_id, status, updated_at)
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS wechat_group_memory_scheduler_state (
                        room_id TEXT PRIMARY KEY,
                        latest_observed_row_id INTEGER NOT NULL DEFAULT 0,
                        last_signal_at INTEGER NOT NULL DEFAULT 0,
                        last_attempt_at INTEGER NOT NULL DEFAULT 0,
                        last_success_at INTEGER NOT NULL DEFAULT 0,
                        next_retry_at INTEGER NOT NULL DEFAULT 0,
                        consecutive_failures INTEGER NOT NULL DEFAULT 0,
                        last_failed_reason_code TEXT NOT NULL DEFAULT '',
                        initialized_at INTEGER NOT NULL DEFAULT 0,
                        initialization_mode TEXT NOT NULL DEFAULT '',
                        updated_at INTEGER NOT NULL DEFAULT 0
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS wechat_group_memory_backfill_state (
                        room_id TEXT PRIMARY KEY,
                        cursor_row_id INTEGER NOT NULL DEFAULT 0,
                        target_row_id INTEGER NOT NULL DEFAULT 0,
                        status TEXT NOT NULL DEFAULT 'idle',
                        completed_batches INTEGER NOT NULL DEFAULT 0,
                        last_failed_reason_code TEXT NOT NULL DEFAULT '',
                        started_at INTEGER NOT NULL DEFAULT 0,
                        updated_at INTEGER NOT NULL DEFAULT 0,
                        finished_at INTEGER NOT NULL DEFAULT 0
                    )
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
                        trigger_source TEXT NOT NULL DEFAULT 'manual',
                        summary_status TEXT NOT NULL DEFAULT '',
                        dream_status TEXT NOT NULL DEFAULT '',
                        skipped_count INTEGER NOT NULL DEFAULT 0,
                        dream_summary TEXT NOT NULL DEFAULT '',
                        llm_status_code INTEGER NOT NULL DEFAULT 0,
                        interrupted_reason TEXT NOT NULL DEFAULT '',
                        batch_eligible_count INTEGER NOT NULL DEFAULT 0,
                        batch_filtered_count INTEGER NOT NULL DEFAULT 0,
                        pending_before_count INTEGER NOT NULL DEFAULT 0,
                        pending_after_count INTEGER NOT NULL DEFAULT 0,
                        cursor_before INTEGER NOT NULL DEFAULT 0,
                        cursor_after INTEGER NOT NULL DEFAULT 0,
                        summary_duration_ms INTEGER NOT NULL DEFAULT 0,
                        dream_duration_ms INTEGER NOT NULL DEFAULT 0,
                        total_duration_ms INTEGER NOT NULL DEFAULT 0,
                        failure_code TEXT NOT NULL DEFAULT '',
                        fallback_used INTEGER NOT NULL DEFAULT 0,
                        attempt_count INTEGER NOT NULL DEFAULT 0,
                        started_at INTEGER NOT NULL,
                        finished_at INTEGER NOT NULL DEFAULT 0
                    )
                    """
                )
                _ensure_column(conn, "wechat_group_learning_runs", "trigger_source", "TEXT NOT NULL DEFAULT 'manual'")
                _ensure_column(conn, "wechat_group_learning_runs", "summary_status", "TEXT NOT NULL DEFAULT ''")
                _ensure_column(conn, "wechat_group_learning_runs", "dream_status", "TEXT NOT NULL DEFAULT ''")
                _ensure_column(conn, "wechat_group_learning_runs", "skipped_count", "INTEGER NOT NULL DEFAULT 0")
                _ensure_column(conn, "wechat_group_learning_runs", "dream_summary", "TEXT NOT NULL DEFAULT ''")
                _ensure_column(conn, "wechat_group_learning_runs", "llm_status_code", "INTEGER NOT NULL DEFAULT 0")
                _ensure_column(conn, "wechat_group_learning_runs", "interrupted_reason", "TEXT NOT NULL DEFAULT ''")
                _ensure_column(conn, "wechat_group_learning_runs", "batch_eligible_count", "INTEGER NOT NULL DEFAULT 0")
                _ensure_column(conn, "wechat_group_learning_runs", "batch_filtered_count", "INTEGER NOT NULL DEFAULT 0")
                _ensure_column(conn, "wechat_group_learning_runs", "pending_before_count", "INTEGER NOT NULL DEFAULT 0")
                _ensure_column(conn, "wechat_group_learning_runs", "pending_after_count", "INTEGER NOT NULL DEFAULT 0")
                _ensure_column(conn, "wechat_group_learning_runs", "cursor_before", "INTEGER NOT NULL DEFAULT 0")
                _ensure_column(conn, "wechat_group_learning_runs", "cursor_after", "INTEGER NOT NULL DEFAULT 0")
                _ensure_column(conn, "wechat_group_learning_runs", "summary_duration_ms", "INTEGER NOT NULL DEFAULT 0")
                _ensure_column(conn, "wechat_group_learning_runs", "dream_duration_ms", "INTEGER NOT NULL DEFAULT 0")
                _ensure_column(conn, "wechat_group_learning_runs", "total_duration_ms", "INTEGER NOT NULL DEFAULT 0")
                _ensure_column(conn, "wechat_group_learning_runs", "failure_code", "TEXT NOT NULL DEFAULT ''")
                _ensure_column(conn, "wechat_group_learning_runs", "fallback_used", "INTEGER NOT NULL DEFAULT 0")
                _ensure_column(conn, "wechat_group_learning_runs", "attempt_count", "INTEGER NOT NULL DEFAULT 0")
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


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    columns = {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def _empty_scheduler_state(room_id: str) -> Dict[str, Any]:
    return {
        "room_id": room_id,
        "latest_observed_row_id": 0,
        "last_signal_at": 0,
        "last_attempt_at": 0,
        "last_success_at": 0,
        "next_retry_at": 0,
        "consecutive_failures": 0,
        "last_failed_reason_code": "",
        "initialized_at": 0,
        "initialization_mode": "",
        "updated_at": 0,
    }


def _empty_backfill_state(room_id: str) -> Dict[str, Any]:
    return {
        "room_id": room_id,
        "cursor_row_id": 0,
        "target_row_id": 0,
        "status": "idle",
        "completed_batches": 0,
        "last_failed_reason_code": "",
        "started_at": 0,
        "updated_at": 0,
        "finished_at": 0,
    }
