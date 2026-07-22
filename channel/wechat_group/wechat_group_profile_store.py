"""Room-scoped SQLite store for WeChat group member profiles."""

from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
import time
from contextlib import closing
from typing import Any, Dict, List, Optional
from uuid import uuid4


def _default_profile_store_path() -> str:
    data_root = os.environ.get("LIGHTAGENT_DATA_DIR") or os.path.join(os.path.expanduser("~"), ".lightagent")
    return os.path.join(os.path.expanduser(data_root), "wechat_group", "wechat_group_profiles.db")


class WechatGroupProfileStore:
    """Owns profile state, evidence, revisions, runs, and learning cursors."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or _default_profile_store_path()
        self._lock = threading.RLock()
        parent = os.path.dirname(self.db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._init_schema()

    def upsert_profile(self, stable_room_id: str, stable_member_id: str, **fields) -> Dict[str, Any]:
        room_id = _require_text("stable_room_id", stable_room_id)
        member_id = _require_text("stable_member_id", stable_member_id)
        now = int(time.time())
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            with conn:
                existing = self._get_profile_row(conn, room_id, member_id)
                data = self._build_profile_data(existing, room_id, member_id, fields, now)
                self._execute_upsert_profile(conn, data)
                row = self._get_profile_row(conn, room_id, member_id)
        return self._profile_row_to_dict(row) if row else {}

    def get_profile(self, stable_room_id: str, stable_member_id: str) -> Optional[Dict[str, Any]]:
        room_id = str(stable_room_id or "").strip()
        member_id = str(stable_member_id or "").strip()
        if not room_id or not member_id:
            return None
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            row = self._get_profile_row(conn, room_id, member_id)
        return self._profile_row_to_dict(row) if row else None

    def list_profiles(
        self,
        stable_room_id: str,
        query: str = "",
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        room_id = _require_text("stable_room_id", stable_room_id)
        max_limit = min(max(int(limit or 20), 1), 500)
        safe_offset = max(int(offset or 0), 0)
        query_text = str(query or "").strip()
        clauses = ["p.stable_room_id = ?", "p.status = 'active'"]
        params: List[Any] = [room_id]
        if query_text:
            like = f"%{query_text}%"
            clauses.append(
                "("
                "p.stable_member_id LIKE ? OR p.primary_nickname LIKE ? OR "
                "p.speak_style LIKE ? OR p.interests_json LIKE ? OR p.common_words_json LIKE ? OR "
                "EXISTS (SELECT 1 FROM wechat_group_member_profile_names n "
                "WHERE n.stable_room_id = p.stable_room_id "
                "AND n.stable_member_id = p.stable_member_id AND n.display_name LIKE ?)"
                ")"
            )
            params.extend([like] * 6)
        params.extend([max_limit, safe_offset])
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"""
                SELECT p.*
                FROM wechat_group_member_profiles p
                WHERE {' AND '.join(clauses)}
                ORDER BY p.updated_at DESC, p.stable_member_id ASC
                LIMIT ? OFFSET ?
                """,
                params,
            ).fetchall()
        return [self._profile_row_to_dict(row) for row in rows]

    def count_profiles(self, stable_room_id: str, query: str = "") -> int:
        room_id = _require_text("stable_room_id", stable_room_id)
        query_text = str(query or "").strip()
        clauses = ["p.stable_room_id = ?", "p.status = 'active'"]
        params: List[Any] = [room_id]
        if query_text:
            like = f"%{query_text}%"
            clauses.append(
                "("
                "p.stable_member_id LIKE ? OR p.primary_nickname LIKE ? OR "
                "p.speak_style LIKE ? OR p.interests_json LIKE ? OR p.common_words_json LIKE ? OR "
                "EXISTS (SELECT 1 FROM wechat_group_member_profile_names n "
                "WHERE n.stable_room_id = p.stable_room_id "
                "AND n.stable_member_id = p.stable_member_id AND n.display_name LIKE ?)"
                ")"
            )
            params.extend([like] * 6)
        with self._lock, closing(self._connect()) as conn:
            row = conn.execute(
                f"SELECT COUNT(*) FROM wechat_group_member_profiles p WHERE {' AND '.join(clauses)}",
                params,
            ).fetchone()
        return int(row[0] or 0) if row else 0

    def delete_profile(self, stable_room_id: str, stable_member_id: str) -> bool:
        room_id = _require_text("stable_room_id", stable_room_id)
        member_id = _require_text("stable_member_id", stable_member_id)
        with self._lock, closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    "DELETE FROM wechat_group_member_profile_names WHERE stable_room_id = ? AND stable_member_id = ?",
                    (room_id, member_id),
                )
                conn.execute(
                    "DELETE FROM wechat_group_member_profile_claims WHERE stable_room_id = ? AND stable_member_id = ?",
                    (room_id, member_id),
                )
                cursor = conn.execute(
                    "DELETE FROM wechat_group_member_profiles WHERE stable_room_id = ? AND stable_member_id = ?",
                    (room_id, member_id),
                )
        return bool(cursor.rowcount)

    def upsert_name_record(
        self,
        stable_room_id: str,
        stable_member_id: str,
        display_name: str,
        source_kind: str = "message",
        confidence: float = 1.0,
        evidence_message_ids: Optional[List[str]] = None,
        run_id: str = "",
        last_seen_at: int = 0,
    ) -> Dict[str, Any]:
        room_id = _require_text("stable_room_id", stable_room_id)
        member_id = _require_text("stable_member_id", stable_member_id)
        name = _require_text("display_name", display_name)
        source = str(source_kind or "message").strip() or "message"
        normalized = _normalize_name_key(name)
        if not normalized:
            raise ValueError("display_name is invalid")
        now = int(time.time())
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            with conn:
                self._execute_upsert_name(
                    conn,
                    room_id=room_id,
                    member_id=member_id,
                    display_name=name,
                    normalized_display_name=normalized,
                    source_kind=source,
                    confidence=confidence,
                    evidence_message_ids=evidence_message_ids or [],
                    run_id=run_id,
                    last_seen_at=last_seen_at,
                    now=now,
                )
                row = conn.execute(
                    """
                    SELECT * FROM wechat_group_member_profile_names
                    WHERE stable_room_id = ? AND stable_member_id = ?
                      AND normalized_display_name = ? AND source_kind = ?
                    LIMIT 1
                    """,
                    (room_id, member_id, normalized, source),
                ).fetchone()
        return self._name_row_to_dict(row) if row else {}

    def list_name_records(
        self,
        stable_room_id: str,
        stable_member_id: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        room_id = str(stable_room_id or "").strip()
        member_id = str(stable_member_id or "").strip()
        if not room_id or not member_id:
            return []
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT * FROM wechat_group_member_profile_names
                WHERE stable_room_id = ? AND stable_member_id = ?
                ORDER BY last_seen_at DESC, updated_at DESC, id DESC
                LIMIT ?
                """,
                (room_id, member_id, min(max(int(limit or 100), 1), 500)),
            ).fetchall()
        return [self._name_row_to_dict(row) for row in rows]

    def apply_manual_update(
        self,
        stable_room_id: str,
        stable_member_id: str,
        fields: Dict[str, Any],
        primary_nickname: str,
        aliases: List[str],
    ) -> Dict[str, Any]:
        room_id = _require_text("stable_room_id", stable_room_id)
        member_id = _require_text("stable_member_id", stable_member_id)
        primary = str(primary_nickname or "").strip()
        alias_values = _dedupe([str(value or "").strip() for value in aliases or []])
        now = int(time.time())
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            with conn:
                existing = self._get_profile_row(conn, room_id, member_id)
                data = self._build_profile_data(existing, room_id, member_id, fields, now)
                self._execute_upsert_profile(conn, data)
                desired = {
                    "manual_primary": {_normalize_name_key(primary)} if primary else set(),
                    "manual": {_normalize_name_key(alias) for alias in alias_values if _normalize_name_key(alias)},
                }
                manual_rows = conn.execute(
                    """
                    SELECT id, normalized_display_name, source_kind
                    FROM wechat_group_member_profile_names
                    WHERE stable_room_id = ? AND stable_member_id = ?
                      AND source_kind IN ('manual_primary', 'manual')
                    """,
                    (room_id, member_id),
                ).fetchall()
                for row in manual_rows:
                    if str(row["normalized_display_name"] or "") not in desired.get(str(row["source_kind"] or ""), set()):
                        conn.execute(
                            "DELETE FROM wechat_group_member_profile_names WHERE id = ?",
                            (int(row["id"]),),
                        )
                last_seen_at = int(data.get("last_observed_at") or 0)
                if primary:
                    self._execute_upsert_name(
                        conn,
                        room_id,
                        member_id,
                        primary,
                        _normalize_name_key(primary),
                        "manual_primary",
                        1.0,
                        [],
                        "",
                        last_seen_at,
                        now,
                    )
                for alias in alias_values:
                    self._execute_upsert_name(
                        conn,
                        room_id,
                        member_id,
                        alias,
                        _normalize_name_key(alias),
                        "manual",
                        1.0,
                        [],
                        "",
                        last_seen_at,
                        now,
                    )
                row = self._get_profile_row(conn, room_id, member_id)
        return self._profile_row_to_dict(row) if row else {}

    def list_claims(
        self,
        stable_room_id: str,
        stable_member_id: str,
        status: str = "accepted",
    ) -> List[Dict[str, Any]]:
        room_id = _require_text("stable_room_id", stable_room_id)
        member_id = _require_text("stable_member_id", stable_member_id)
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT * FROM wechat_group_member_profile_claims
                WHERE stable_room_id = ? AND stable_member_id = ? AND status = ?
                ORDER BY dimension ASC, confidence DESC, updated_at DESC
                """,
                (room_id, member_id, str(status or "accepted")),
            ).fetchall()
        return [self._claim_row_to_dict(row) for row in rows]

    def apply_evolution_update(
        self,
        stable_room_id: str,
        stable_member_id: str,
        fields: Dict[str, Any],
        aliases: List[Dict[str, Any]],
        claims: List[Dict[str, Any]],
        run_id: str,
        evidence_message_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        room_id = _require_text("stable_room_id", stable_room_id)
        member_id = _require_text("stable_member_id", stable_member_id)
        run_text = _require_text("run_id", run_id)
        now = int(time.time())
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            with conn:
                run = conn.execute(
                    """
                    SELECT run_id FROM wechat_group_member_profile_runs
                    WHERE run_id = ? AND stable_room_id = ? AND pipeline = 'evolution'
                    LIMIT 1
                    """,
                    (run_text, room_id),
                ).fetchone()
                if not run:
                    raise ValueError("evolution run does not belong to stable_room_id")
                before_row = self._get_profile_row(conn, room_id, member_id)
                before = self._profile_row_to_dict(before_row) if before_row else {}
                before_names = self._snapshot_name_rows(conn, room_id, member_id)
                before_claims = self._snapshot_claim_rows(conn, room_id, member_id)
                data = self._build_profile_data(before, room_id, member_id, fields, now)
                self._execute_upsert_profile(conn, data)
                for alias in aliases or []:
                    name = str(alias.get("value") or "").strip()
                    if not name:
                        continue
                    self._execute_upsert_name(
                        conn,
                        room_id=room_id,
                        member_id=member_id,
                        display_name=name,
                        normalized_display_name=_normalize_name_key(name),
                        source_kind=str(alias.get("source_kind") or "llm_evolution"),
                        confidence=_to_float(alias.get("confidence"), 0),
                        evidence_message_ids=_normalize_list(alias.get("evidence_message_ids")),
                        run_id=run_text,
                        last_seen_at=int(alias.get("last_seen_at") or now),
                        now=now,
                    )
                for claim in claims or []:
                    self._execute_upsert_claim(conn, room_id, member_id, claim, run_text, now)
                after_row = self._get_profile_row(conn, room_id, member_id)
                after = self._profile_row_to_dict(after_row) if after_row else {}
                after_names = self._snapshot_name_rows(conn, room_id, member_id)
                after_claims = self._snapshot_claim_rows(conn, room_id, member_id)
                if before != after or aliases or claims:
                    conn.execute(
                        """
                        INSERT INTO wechat_group_member_profile_revisions (
                            run_id, stable_room_id, stable_member_id, before_json, after_json,
                            before_names_json, after_names_json, before_claims_json, after_claims_json,
                            evidence_message_ids_json, reason, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'llm_evolution', ?)
                        """,
                        (
                            run_text,
                            room_id,
                            member_id,
                            _json_dumps(before),
                            _json_dumps(after),
                            _json_dumps(before_names),
                            _json_dumps(after_names),
                            _json_dumps(before_claims),
                            _json_dumps(after_claims),
                            _json_dumps(_normalize_list(evidence_message_ids)),
                            now,
                        ),
                    )
        return after

    def create_run(
        self,
        stable_room_id: str,
        trigger_source: str,
        batch_start_row_id: int,
        pipeline: str = "evolution",
    ) -> str:
        room_id = _require_text("stable_room_id", stable_room_id)
        run_id = uuid4().hex
        now = int(time.time())
        with self._lock, closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO wechat_group_member_profile_runs (
                        run_id, stable_room_id, pipeline, trigger_source, batch_start_row_id,
                        status, started_at
                    ) VALUES (?, ?, ?, ?, ?, 'running', ?)
                    """,
                    (run_id, room_id, str(pipeline or "evolution"), str(trigger_source or "manual"), int(batch_start_row_id or 0), now),
                )
        return run_id

    def finish_run(self, run_id: str, **fields) -> None:
        run_text = _require_text("run_id", run_id)
        with self._lock, closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    """
                    UPDATE wechat_group_member_profile_runs
                    SET status = ?, batch_end_row_id = ?, batch_message_count = ?,
                        analyzed_member_count = ?, profile_update_count = ?, alias_update_count = ?,
                        role_hint_update_count = ?, failed_reason = ?, finished_at = ?
                    WHERE run_id = ?
                    """,
                    (
                        str(fields.get("status") or "failed"),
                        int(fields.get("batch_end_row_id") or 0),
                        int(fields.get("batch_message_count") or 0),
                        int(fields.get("analyzed_member_count") or 0),
                        int(fields.get("profile_update_count") or 0),
                        int(fields.get("alias_update_count") or 0),
                        int(fields.get("role_hint_update_count") or 0),
                        str(fields.get("failed_reason") or ""),
                        int(time.time()),
                        run_text,
                    ),
                )

    def list_runs(self, stable_room_id: str, limit: int = 20, pipeline: str = "evolution") -> List[Dict[str, Any]]:
        room_id = _require_text("stable_room_id", stable_room_id)
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT * FROM wechat_group_member_profile_runs
                WHERE stable_room_id = ? AND pipeline = ?
                ORDER BY started_at DESC, run_id DESC
                LIMIT ?
                """,
                (room_id, str(pipeline or "evolution"), min(max(int(limit or 20), 1), 100)),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_run(self, stable_room_id: str, run_id: str) -> Optional[Dict[str, Any]]:
        room_id = str(stable_room_id or "").strip()
        run_text = str(run_id or "").strip()
        if not room_id or not run_text:
            return None
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT * FROM wechat_group_member_profile_runs
                WHERE stable_room_id = ? AND run_id = ? LIMIT 1
                """,
                (room_id, run_text),
            ).fetchone()
        return dict(row) if row else None

    def list_revisions(
        self,
        stable_room_id: str,
        stable_member_id: str = "",
        run_id: str = "",
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        room_id = _require_text("stable_room_id", stable_room_id)
        clauses = ["stable_room_id = ?"]
        params: List[Any] = [room_id]
        if str(stable_member_id or "").strip():
            clauses.append("stable_member_id = ?")
            params.append(str(stable_member_id).strip())
        if str(run_id or "").strip():
            clauses.append("run_id = ?")
            params.append(str(run_id).strip())
        params.append(min(max(int(limit or 100), 1), 500))
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"""
                SELECT * FROM wechat_group_member_profile_revisions
                WHERE {' AND '.join(clauses)}
                ORDER BY created_at DESC, id DESC LIMIT ?
                """,
                params,
            ).fetchall()
        return [self._revision_row_to_dict(row) for row in rows]

    def record_revision(
        self,
        run_id: str,
        stable_room_id: str,
        stable_member_id: str,
        before: Dict[str, Any],
        after: Dict[str, Any],
        evidence_message_ids: Optional[List[str]] = None,
        reason: str = "evolution",
    ) -> None:
        run_text = _require_text("run_id", run_id)
        room_id = _require_text("stable_room_id", stable_room_id)
        member_id = _require_text("stable_member_id", stable_member_id)
        with self._lock, closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO wechat_group_member_profile_revisions (
                        run_id, stable_room_id, stable_member_id, before_json, after_json,
                        before_names_json, after_names_json, before_claims_json, after_claims_json,
                        evidence_message_ids_json, reason, created_at
                    ) VALUES (?, ?, ?, ?, ?, 'null', 'null', 'null', 'null', ?, ?, ?)
                    """,
                    (
                        run_text,
                        room_id,
                        member_id,
                        _json_dumps(before or {}),
                        _json_dumps(after or {}),
                        _json_dumps(_normalize_list(evidence_message_ids)),
                        str(reason or "evolution"),
                        int(time.time()),
                    ),
                )

    def get_learning_state(self, stable_room_id: str, pipeline: str = "evolution") -> Dict[str, Any]:
        room_id = _require_text("stable_room_id", stable_room_id)
        pipeline_text = str(pipeline or "evolution").strip() or "evolution"
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT * FROM wechat_group_member_profile_learning_state
                WHERE stable_room_id = ? AND pipeline = ? LIMIT 1
                """,
                (room_id, pipeline_text),
            ).fetchone()
        if row:
            data = dict(row)
            data["room_id"] = data["stable_room_id"]
            data["running"] = bool(data.get("running"))
            return data
        return {
            "stable_room_id": room_id,
            "room_id": room_id,
            "pipeline": pipeline_text,
            "last_archive_row_id": 0,
            "latest_observed_row_id": 0,
            "last_signal_at": 0,
            "last_success_at": 0,
            "last_failed_at": 0,
            "last_failed_reason": "",
            "running": False,
            "updated_at": 0,
        }

    def update_learning_state(self, stable_room_id: str, pipeline: str = "evolution", **fields) -> Dict[str, Any]:
        room_id = _require_text("stable_room_id", stable_room_id)
        pipeline_text = str(pipeline or "evolution").strip() or "evolution"
        existing = self.get_learning_state(room_id, pipeline_text)
        now = int(time.time())
        data = {
            key: fields.get(key, existing.get(key, default))
            for key, default in (
                ("last_archive_row_id", 0),
                ("latest_observed_row_id", 0),
                ("last_signal_at", 0),
                ("last_success_at", 0),
                ("last_failed_at", 0),
                ("last_failed_reason", ""),
                ("running", False),
            )
        }
        with self._lock, closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO wechat_group_member_profile_learning_state (
                        stable_room_id, pipeline, last_archive_row_id, latest_observed_row_id,
                        last_signal_at, last_success_at, last_failed_at, last_failed_reason,
                        running, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(stable_room_id, pipeline) DO UPDATE SET
                        last_archive_row_id = excluded.last_archive_row_id,
                        latest_observed_row_id = excluded.latest_observed_row_id,
                        last_signal_at = excluded.last_signal_at,
                        last_success_at = excluded.last_success_at,
                        last_failed_at = excluded.last_failed_at,
                        last_failed_reason = excluded.last_failed_reason,
                        running = excluded.running,
                        updated_at = excluded.updated_at
                    """,
                    (
                        room_id,
                        pipeline_text,
                        int(data["last_archive_row_id"] or 0),
                        int(data["latest_observed_row_id"] or 0),
                        int(data["last_signal_at"] or 0),
                        int(data["last_success_at"] or 0),
                        int(data["last_failed_at"] or 0),
                        str(data["last_failed_reason"] or ""),
                        1 if data["running"] else 0,
                        now,
                    ),
                )
        return self.get_learning_state(room_id, pipeline_text)

    def rollback_run(self, stable_room_id: str, run_id: str) -> Dict[str, Any]:
        room_id = _require_text("stable_room_id", stable_room_id)
        run_text = _require_text("run_id", run_id)
        rolled_back = 0
        restored_names = 0
        restored_claims = 0
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            with conn:
                run = conn.execute(
                    """
                    SELECT rowid, * FROM wechat_group_member_profile_runs
                    WHERE stable_room_id = ? AND run_id = ? AND pipeline = 'evolution'
                    LIMIT 1
                    """,
                    (room_id, run_text),
                ).fetchone()
                if not run:
                    raise ValueError("evolution run was not found in stable_room_id")
                if str(run["status"] or "") == "rolled_back":
                    return {
                        "room_id": room_id,
                        "run_id": run_text,
                        "rolled_back": 0,
                        "name_records_restored": 0,
                        "claims_restored": 0,
                        "already_rolled_back": True,
                    }
                newer = conn.execute(
                    """
                    SELECT 1 FROM wechat_group_member_profile_runs
                    WHERE stable_room_id = ? AND pipeline = 'evolution' AND rowid > ?
                      AND status IN ('running', 'success')
                    LIMIT 1
                    """,
                    (room_id, int(run["rowid"])),
                ).fetchone()
                if newer:
                    raise ValueError("only the latest evolution run can be rolled back")
                revisions = conn.execute(
                    """
                    SELECT * FROM wechat_group_member_profile_revisions
                    WHERE stable_room_id = ? AND run_id = ?
                    ORDER BY id DESC
                    """,
                    (room_id, run_text),
                ).fetchall()
                for row in revisions:
                    member_id = str(row["stable_member_id"] or "")
                    before = _loads_json(row["before_json"], {})
                    before_names = _loads_optional_list(row["before_names_json"])
                    before_claims = _loads_optional_list(row["before_claims_json"])
                    if before_names is not None:
                        conn.execute(
                            "DELETE FROM wechat_group_member_profile_names WHERE stable_room_id = ? AND stable_member_id = ?",
                            (room_id, member_id),
                        )
                        for item in before_names:
                            self._restore_name_row(conn, room_id, member_id, item)
                        restored_names += len(before_names)
                    if before_claims is not None:
                        conn.execute(
                            "DELETE FROM wechat_group_member_profile_claims WHERE stable_room_id = ? AND stable_member_id = ?",
                            (room_id, member_id),
                        )
                        for item in before_claims:
                            self._restore_claim_row(conn, room_id, member_id, item)
                        restored_claims += len(before_claims)
                    if before:
                        data = self._build_profile_data({}, room_id, member_id, before, int(time.time()))
                        data["revision"] = int(before.get("revision") or 1)
                        data["created_at"] = int(before.get("created_at") or data["created_at"])
                        data["updated_at"] = int(before.get("updated_at") or data["updated_at"])
                        self._execute_upsert_profile(conn, data)
                    else:
                        conn.execute(
                            "DELETE FROM wechat_group_member_profiles WHERE stable_room_id = ? AND stable_member_id = ?",
                            (room_id, member_id),
                        )
                    rolled_back += 1
                conn.execute(
                    "UPDATE wechat_group_member_profile_runs SET status = 'rolled_back' WHERE stable_room_id = ? AND run_id = ?",
                    (room_id, run_text),
                )
        return {
            "room_id": room_id,
            "run_id": run_text,
            "rolled_back": rolled_back,
            "name_records_restored": restored_names,
            "claims_restored": restored_claims,
            "already_rolled_back": False,
        }

    def merge_profile_subjects(
        self,
        stable_room_id: str,
        old_stable_member_id: str,
        canonical_stable_member_id: str,
    ) -> Dict[str, Any]:
        """Move current profile state to a canonical member after an identity redirect."""
        room_id = _require_text("stable_room_id", stable_room_id)
        old_member_id = _require_text("old_stable_member_id", old_stable_member_id)
        canonical_member_id = _require_text("canonical_stable_member_id", canonical_stable_member_id)
        if old_member_id == canonical_member_id:
            return self.get_profile(room_id, canonical_member_id) or {}
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            with conn:
                old_row = self._get_profile_row(conn, room_id, old_member_id)
                canonical_row = self._get_profile_row(conn, room_id, canonical_member_id)
                old_profile = self._profile_row_to_dict(old_row) if old_row else {}
                canonical_profile = self._profile_row_to_dict(canonical_row) if canonical_row else {}
                if old_profile:
                    merged = self._merge_profiles_for_canonical_member(
                        old_profile,
                        canonical_profile,
                        room_id,
                        canonical_member_id,
                    )
                    self._execute_upsert_profile(conn, merged)
                self._merge_name_subject(conn, room_id, old_member_id, canonical_member_id)
                self._merge_claim_subject(conn, room_id, old_member_id, canonical_member_id)
                conn.execute(
                    "UPDATE wechat_group_member_profile_revisions SET stable_member_id = ? "
                    "WHERE stable_room_id = ? AND stable_member_id = ?",
                    (canonical_member_id, room_id, old_member_id),
                )
                conn.execute(
                    "DELETE FROM wechat_group_member_profiles WHERE stable_room_id = ? AND stable_member_id = ?",
                    (room_id, old_member_id),
                )
                result = self._get_profile_row(conn, room_id, canonical_member_id)
        return self._profile_row_to_dict(result) if result else {}

    def integrity_check(self) -> str:
        with self._lock, closing(self._connect()) as conn:
            row = conn.execute("PRAGMA integrity_check").fetchone()
        return str(row[0] or "") if row else ""

    def table_counts(self) -> Dict[str, int]:
        tables = (
            "wechat_group_member_profiles",
            "wechat_group_member_profile_names",
            "wechat_group_member_profile_claims",
            "wechat_group_member_profile_revisions",
            "wechat_group_member_profile_runs",
            "wechat_group_member_profile_learning_state",
        )
        with self._lock, closing(self._connect()) as conn:
            return {table: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) for table in tables}

    def _init_schema(self) -> None:
        with closing(self._connect()) as conn:
            with conn:
                conn.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS wechat_group_member_profiles (
                        stable_room_id TEXT NOT NULL,
                        stable_member_id TEXT NOT NULL,
                        primary_nickname TEXT NOT NULL DEFAULT '',
                        speak_style TEXT NOT NULL DEFAULT '',
                        role_hints_json TEXT NOT NULL DEFAULT '[]',
                        interests_json TEXT NOT NULL DEFAULT '[]',
                        common_words_json TEXT NOT NULL DEFAULT '[]',
                        activity_score INTEGER NOT NULL DEFAULT 0,
                        intimacy_score INTEGER NOT NULL DEFAULT 0,
                        msg_count INTEGER NOT NULL DEFAULT 0,
                        first_observed_at INTEGER NOT NULL DEFAULT 0,
                        last_observed_at INTEGER NOT NULL DEFAULT 0,
                        revision INTEGER NOT NULL DEFAULT 1,
                        status TEXT NOT NULL DEFAULT 'active',
                        created_at INTEGER NOT NULL,
                        updated_at INTEGER NOT NULL,
                        PRIMARY KEY (stable_room_id, stable_member_id)
                    );

                    CREATE INDEX IF NOT EXISTS idx_wechat_group_member_profiles_room_updated
                    ON wechat_group_member_profiles(stable_room_id, status, updated_at, stable_member_id);

                    CREATE TABLE IF NOT EXISTS wechat_group_member_profile_names (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        stable_room_id TEXT NOT NULL,
                        stable_member_id TEXT NOT NULL,
                        normalized_display_name TEXT NOT NULL,
                        display_name TEXT NOT NULL,
                        source_kind TEXT NOT NULL,
                        confidence REAL NOT NULL DEFAULT 0,
                        evidence_message_ids_json TEXT NOT NULL DEFAULT '[]',
                        run_id TEXT NOT NULL DEFAULT '',
                        first_seen_at INTEGER NOT NULL DEFAULT 0,
                        last_seen_at INTEGER NOT NULL DEFAULT 0,
                        seen_count INTEGER NOT NULL DEFAULT 1,
                        created_at INTEGER NOT NULL,
                        updated_at INTEGER NOT NULL,
                        UNIQUE(stable_room_id, stable_member_id, normalized_display_name, source_kind)
                    );

                    CREATE INDEX IF NOT EXISTS idx_wechat_group_member_profile_names_member
                    ON wechat_group_member_profile_names(stable_room_id, stable_member_id, last_seen_at, id);

                    CREATE TABLE IF NOT EXISTS wechat_group_member_profile_claims (
                        claim_id TEXT PRIMARY KEY,
                        stable_room_id TEXT NOT NULL,
                        stable_member_id TEXT NOT NULL,
                        dimension TEXT NOT NULL,
                        normalized_value TEXT NOT NULL,
                        value TEXT NOT NULL,
                        confidence REAL NOT NULL DEFAULT 0,
                        evidence_message_ids_json TEXT NOT NULL DEFAULT '[]',
                        source_kind TEXT NOT NULL,
                        run_id TEXT NOT NULL DEFAULT '',
                        status TEXT NOT NULL DEFAULT 'accepted',
                        first_seen_at INTEGER NOT NULL,
                        last_seen_at INTEGER NOT NULL,
                        created_at INTEGER NOT NULL,
                        updated_at INTEGER NOT NULL,
                        UNIQUE(stable_room_id, stable_member_id, dimension, normalized_value, source_kind)
                    );

                    CREATE INDEX IF NOT EXISTS idx_wechat_group_member_profile_claims_member
                    ON wechat_group_member_profile_claims(stable_room_id, stable_member_id, status, dimension);

                    CREATE TABLE IF NOT EXISTS wechat_group_member_profile_revisions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        run_id TEXT NOT NULL DEFAULT '',
                        stable_room_id TEXT NOT NULL,
                        stable_member_id TEXT NOT NULL,
                        before_json TEXT NOT NULL DEFAULT '{}',
                        after_json TEXT NOT NULL DEFAULT '{}',
                        before_names_json TEXT NOT NULL DEFAULT 'null',
                        after_names_json TEXT NOT NULL DEFAULT 'null',
                        before_claims_json TEXT NOT NULL DEFAULT 'null',
                        after_claims_json TEXT NOT NULL DEFAULT 'null',
                        evidence_message_ids_json TEXT NOT NULL DEFAULT '[]',
                        reason TEXT NOT NULL DEFAULT '',
                        created_at INTEGER NOT NULL
                    );

                    CREATE INDEX IF NOT EXISTS idx_wechat_group_member_profile_revisions_run
                    ON wechat_group_member_profile_revisions(stable_room_id, run_id, id);

                    CREATE TABLE IF NOT EXISTS wechat_group_member_profile_runs (
                        run_id TEXT PRIMARY KEY,
                        stable_room_id TEXT NOT NULL,
                        pipeline TEXT NOT NULL DEFAULT 'evolution',
                        trigger_source TEXT NOT NULL DEFAULT 'manual',
                        batch_start_row_id INTEGER NOT NULL DEFAULT 0,
                        batch_end_row_id INTEGER NOT NULL DEFAULT 0,
                        batch_message_count INTEGER NOT NULL DEFAULT 0,
                        analyzed_member_count INTEGER NOT NULL DEFAULT 0,
                        profile_update_count INTEGER NOT NULL DEFAULT 0,
                        alias_update_count INTEGER NOT NULL DEFAULT 0,
                        role_hint_update_count INTEGER NOT NULL DEFAULT 0,
                        status TEXT NOT NULL,
                        failed_reason TEXT NOT NULL DEFAULT '',
                        started_at INTEGER NOT NULL,
                        finished_at INTEGER NOT NULL DEFAULT 0
                    );

                    CREATE INDEX IF NOT EXISTS idx_wechat_group_member_profile_runs_room
                    ON wechat_group_member_profile_runs(stable_room_id, pipeline, started_at, run_id);

                    CREATE TABLE IF NOT EXISTS wechat_group_member_profile_learning_state (
                        stable_room_id TEXT NOT NULL,
                        pipeline TEXT NOT NULL,
                        last_archive_row_id INTEGER NOT NULL DEFAULT 0,
                        latest_observed_row_id INTEGER NOT NULL DEFAULT 0,
                        last_signal_at INTEGER NOT NULL DEFAULT 0,
                        last_success_at INTEGER NOT NULL DEFAULT 0,
                        last_failed_at INTEGER NOT NULL DEFAULT 0,
                        last_failed_reason TEXT NOT NULL DEFAULT '',
                        running INTEGER NOT NULL DEFAULT 0,
                        updated_at INTEGER NOT NULL DEFAULT 0,
                        PRIMARY KEY(stable_room_id, pipeline)
                    );
                    """
                )
                self._ensure_revision_snapshot_columns(conn)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path, timeout=10)

    @staticmethod
    def _ensure_revision_snapshot_columns(conn: sqlite3.Connection) -> None:
        existing = {
            str(row[1])
            for row in conn.execute("PRAGMA table_info(wechat_group_member_profile_revisions)").fetchall()
        }
        for column in (
            "before_names_json",
            "after_names_json",
            "before_claims_json",
            "after_claims_json",
        ):
            if column not in existing:
                conn.execute(
                    f"ALTER TABLE wechat_group_member_profile_revisions "
                    f"ADD COLUMN {column} TEXT NOT NULL DEFAULT 'null'"
                )

    @staticmethod
    def _get_profile_row(conn: sqlite3.Connection, room_id: str, member_id: str):
        return conn.execute(
            """
            SELECT * FROM wechat_group_member_profiles
            WHERE stable_room_id = ? AND stable_member_id = ? LIMIT 1
            """,
            (room_id, member_id),
        ).fetchone()

    @staticmethod
    def _build_profile_data(existing: Any, room_id: str, member_id: str, fields: Dict[str, Any], now: int) -> Dict[str, Any]:
        existing_data = WechatGroupProfileStore._profile_row_to_dict(existing) if isinstance(existing, sqlite3.Row) else dict(existing or {})
        first_observed = int(
            existing_data.get("first_observed_at")
            or fields.get("first_observed_at")
            or fields.get("last_observed_at")
            or now
        )
        return {
            "stable_room_id": room_id,
            "stable_member_id": member_id,
            "primary_nickname": fields.get("primary_nickname", existing_data.get("primary_nickname", "")),
            "speak_style": fields.get("speak_style", existing_data.get("speak_style", "")),
            "role_hints": fields.get("role_hints", existing_data.get("role_hints", [])),
            "interests": fields.get("interests", existing_data.get("interests", [])),
            "common_words": fields.get("common_words", existing_data.get("common_words", [])),
            "activity_score": int(fields.get("activity_score", existing_data.get("activity_score", 0)) or 0),
            "intimacy_score": int(fields.get("intimacy_score", existing_data.get("intimacy_score", 0)) or 0),
            "msg_count": int(fields.get("msg_count", existing_data.get("msg_count", 0)) or 0),
            "first_observed_at": first_observed,
            "last_observed_at": int(fields.get("last_observed_at", existing_data.get("last_observed_at", 0)) or 0),
            "revision": int(fields.get("revision") or (int(existing_data.get("revision") or 0) + 1) or 1),
            "status": str(fields.get("status", existing_data.get("status", "active")) or "active"),
            "created_at": int(existing_data.get("created_at") or fields.get("created_at") or now),
            "updated_at": int(fields.get("updated_at") or now),
        }

    @staticmethod
    def _execute_upsert_profile(conn: sqlite3.Connection, data: Dict[str, Any]) -> None:
        conn.execute(
            """
            INSERT INTO wechat_group_member_profiles (
                stable_room_id, stable_member_id, primary_nickname, speak_style,
                role_hints_json, interests_json, common_words_json, activity_score,
                intimacy_score, msg_count, first_observed_at, last_observed_at,
                revision, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(stable_room_id, stable_member_id) DO UPDATE SET
                primary_nickname = excluded.primary_nickname,
                speak_style = excluded.speak_style,
                role_hints_json = excluded.role_hints_json,
                interests_json = excluded.interests_json,
                common_words_json = excluded.common_words_json,
                activity_score = excluded.activity_score,
                intimacy_score = excluded.intimacy_score,
                msg_count = excluded.msg_count,
                first_observed_at = excluded.first_observed_at,
                last_observed_at = excluded.last_observed_at,
                revision = excluded.revision,
                status = excluded.status,
                updated_at = excluded.updated_at
            """,
            (
                data["stable_room_id"],
                data["stable_member_id"],
                str(data["primary_nickname"] or ""),
                str(data["speak_style"] or ""),
                _json_dumps(_normalize_list(data["role_hints"])),
                _json_dumps(_normalize_list(data["interests"])),
                _json_dumps(_normalize_list(data["common_words"])),
                int(data["activity_score"] or 0),
                int(data["intimacy_score"] or 0),
                int(data["msg_count"] or 0),
                int(data["first_observed_at"] or 0),
                int(data["last_observed_at"] or 0),
                int(data["revision"] or 1),
                str(data["status"] or "active"),
                int(data["created_at"]),
                int(data["updated_at"]),
            ),
        )

    @staticmethod
    def _execute_upsert_name(
        conn: sqlite3.Connection,
        room_id: str,
        member_id: str,
        display_name: str,
        normalized_display_name: str,
        source_kind: str,
        confidence: float,
        evidence_message_ids: List[str],
        run_id: str,
        last_seen_at: int,
        now: int,
    ) -> None:
        if not normalized_display_name:
            return
        existing = conn.execute(
            """
            SELECT evidence_message_ids_json, first_seen_at, last_seen_at, seen_count
            FROM wechat_group_member_profile_names
            WHERE stable_room_id = ? AND stable_member_id = ?
              AND normalized_display_name = ? AND source_kind = ?
            LIMIT 1
            """,
            (room_id, member_id, normalized_display_name, source_kind),
        ).fetchone()
        existing_evidence = _loads_json(existing[0], []) if existing else []
        merged_evidence = _dedupe(existing_evidence + _normalize_list(evidence_message_ids))
        seen_at = int(last_seen_at or now)
        first_seen_at = int(existing[1] or seen_at) if existing else seen_at
        latest_seen_at = max(int(existing[2] or 0), seen_at) if existing else seen_at
        seen_count = int(existing[3] or 0) + 1 if existing else 1
        conn.execute(
            """
            INSERT INTO wechat_group_member_profile_names (
                stable_room_id, stable_member_id, normalized_display_name, display_name,
                source_kind, confidence, evidence_message_ids_json, run_id,
                first_seen_at, last_seen_at, seen_count, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(stable_room_id, stable_member_id, normalized_display_name, source_kind)
            DO UPDATE SET
                display_name = excluded.display_name,
                confidence = MAX(wechat_group_member_profile_names.confidence, excluded.confidence),
                evidence_message_ids_json = excluded.evidence_message_ids_json,
                run_id = CASE WHEN excluded.run_id != '' THEN excluded.run_id ELSE wechat_group_member_profile_names.run_id END,
                first_seen_at = excluded.first_seen_at,
                last_seen_at = excluded.last_seen_at,
                seen_count = excluded.seen_count,
                updated_at = excluded.updated_at
            """,
            (
                room_id,
                member_id,
                normalized_display_name,
                display_name,
                source_kind,
                max(min(_to_float(confidence, 0), 1.0), 0.0),
                _json_dumps(merged_evidence),
                str(run_id or ""),
                first_seen_at,
                latest_seen_at,
                seen_count,
                now,
                now,
            ),
        )

    @staticmethod
    def _execute_upsert_claim(
        conn: sqlite3.Connection,
        room_id: str,
        member_id: str,
        claim: Dict[str, Any],
        run_id: str,
        now: int,
    ) -> None:
        dimension = str(claim.get("dimension") or "").strip()
        value = str(claim.get("value") or "").strip()
        normalized_value = _normalize_name_key(value)
        evidence = _normalize_list(claim.get("evidence_message_ids"))
        if not dimension or not value or not normalized_value or not evidence:
            return
        source_kind = str(claim.get("source_kind") or "llm_evolution")
        existing = conn.execute(
            """
            SELECT claim_id, evidence_message_ids_json, first_seen_at
            FROM wechat_group_member_profile_claims
            WHERE stable_room_id = ? AND stable_member_id = ? AND dimension = ?
              AND normalized_value = ? AND source_kind = ? LIMIT 1
            """,
            (room_id, member_id, dimension, normalized_value, source_kind),
        ).fetchone()
        claim_id = str(existing[0]) if existing else uuid4().hex
        merged_evidence = _dedupe((_loads_json(existing[1], []) if existing else []) + evidence)
        first_seen_at = int(existing[2] or now) if existing else now
        conn.execute(
            """
            INSERT INTO wechat_group_member_profile_claims (
                claim_id, stable_room_id, stable_member_id, dimension, normalized_value,
                value, confidence, evidence_message_ids_json, source_kind, run_id,
                status, first_seen_at, last_seen_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'accepted', ?, ?, ?, ?)
            ON CONFLICT(stable_room_id, stable_member_id, dimension, normalized_value, source_kind)
            DO UPDATE SET
                value = excluded.value,
                confidence = MAX(wechat_group_member_profile_claims.confidence, excluded.confidence),
                evidence_message_ids_json = excluded.evidence_message_ids_json,
                run_id = excluded.run_id,
                status = 'accepted',
                last_seen_at = excluded.last_seen_at,
                updated_at = excluded.updated_at
            """,
            (
                claim_id,
                room_id,
                member_id,
                dimension,
                normalized_value,
                value,
                max(min(_to_float(claim.get("confidence"), 0), 1.0), 0.0),
                _json_dumps(merged_evidence),
                source_kind,
                run_id,
                first_seen_at,
                now,
                now,
                now,
            ),
        )

    @staticmethod
    def _snapshot_name_rows(conn: sqlite3.Connection, room_id: str, member_id: str) -> List[Dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT * FROM wechat_group_member_profile_names
            WHERE stable_room_id = ? AND stable_member_id = ?
            ORDER BY id ASC
            """,
            (room_id, member_id),
        ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _snapshot_claim_rows(conn: sqlite3.Connection, room_id: str, member_id: str) -> List[Dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT * FROM wechat_group_member_profile_claims
            WHERE stable_room_id = ? AND stable_member_id = ?
            ORDER BY claim_id ASC
            """,
            (room_id, member_id),
        ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _restore_name_row(
        conn: sqlite3.Connection,
        room_id: str,
        member_id: str,
        item: Dict[str, Any],
    ) -> None:
        conn.execute(
            """
            INSERT INTO wechat_group_member_profile_names (
                id, stable_room_id, stable_member_id, normalized_display_name, display_name,
                source_kind, confidence, evidence_message_ids_json, run_id, first_seen_at,
                last_seen_at, seen_count, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(item.get("id") or 0) or None,
                room_id,
                member_id,
                str(item.get("normalized_display_name") or ""),
                str(item.get("display_name") or ""),
                str(item.get("source_kind") or ""),
                _to_float(item.get("confidence"), 0),
                str(item.get("evidence_message_ids_json") or "[]"),
                str(item.get("run_id") or ""),
                int(item.get("first_seen_at") or 0),
                int(item.get("last_seen_at") or 0),
                int(item.get("seen_count") or 1),
                int(item.get("created_at") or 0),
                int(item.get("updated_at") or 0),
            ),
        )

    @staticmethod
    def _restore_claim_row(
        conn: sqlite3.Connection,
        room_id: str,
        member_id: str,
        item: Dict[str, Any],
    ) -> None:
        conn.execute(
            """
            INSERT INTO wechat_group_member_profile_claims (
                claim_id, stable_room_id, stable_member_id, dimension, normalized_value,
                value, confidence, evidence_message_ids_json, source_kind, run_id, status,
                first_seen_at, last_seen_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(item.get("claim_id") or uuid4().hex),
                room_id,
                member_id,
                str(item.get("dimension") or ""),
                str(item.get("normalized_value") or ""),
                str(item.get("value") or ""),
                _to_float(item.get("confidence"), 0),
                str(item.get("evidence_message_ids_json") or "[]"),
                str(item.get("source_kind") or ""),
                str(item.get("run_id") or ""),
                str(item.get("status") or "accepted"),
                int(item.get("first_seen_at") or 0),
                int(item.get("last_seen_at") or 0),
                int(item.get("created_at") or 0),
                int(item.get("updated_at") or 0),
            ),
        )

    @staticmethod
    def _merge_profiles_for_canonical_member(
        old_profile: Dict[str, Any],
        canonical_profile: Dict[str, Any],
        room_id: str,
        canonical_member_id: str,
    ) -> Dict[str, Any]:
        now = int(time.time())
        first_observed = _min_positive(
            old_profile.get("first_observed_at"),
            canonical_profile.get("first_observed_at"),
        )
        return {
            "stable_room_id": room_id,
            "stable_member_id": canonical_member_id,
            "primary_nickname": canonical_profile.get("primary_nickname") or old_profile.get("primary_nickname") or "",
            "speak_style": canonical_profile.get("speak_style") or old_profile.get("speak_style") or "",
            "role_hints": _dedupe(
                list(canonical_profile.get("role_hints") or []) + list(old_profile.get("role_hints") or [])
            ),
            "interests": _dedupe(
                list(canonical_profile.get("interests") or []) + list(old_profile.get("interests") or [])
            ),
            "common_words": _dedupe(
                list(canonical_profile.get("common_words") or []) + list(old_profile.get("common_words") or [])
            ),
            "activity_score": max(
                int(canonical_profile.get("activity_score") or 0),
                int(old_profile.get("activity_score") or 0),
            ),
            "intimacy_score": max(
                int(canonical_profile.get("intimacy_score") or 0),
                int(old_profile.get("intimacy_score") or 0),
            ),
            "msg_count": max(
                int(canonical_profile.get("msg_count") or 0),
                int(old_profile.get("msg_count") or 0),
            ),
            "first_observed_at": first_observed,
            "last_observed_at": max(
                int(canonical_profile.get("last_observed_at") or 0),
                int(old_profile.get("last_observed_at") or 0),
            ),
            "revision": max(
                int(canonical_profile.get("revision") or 0),
                int(old_profile.get("revision") or 0),
            ) + 1,
            "status": "active",
            "created_at": _min_positive(
                old_profile.get("created_at"),
                canonical_profile.get("created_at"),
            ) or now,
            "updated_at": now,
        }

    @staticmethod
    def _merge_name_subject(
        conn: sqlite3.Connection,
        room_id: str,
        old_member_id: str,
        canonical_member_id: str,
    ) -> None:
        rows = conn.execute(
            """
            SELECT * FROM wechat_group_member_profile_names
            WHERE stable_room_id = ? AND stable_member_id = ? ORDER BY id ASC
            """,
            (room_id, old_member_id),
        ).fetchall()
        for row in rows:
            item = dict(row)
            target = conn.execute(
                """
                SELECT * FROM wechat_group_member_profile_names
                WHERE stable_room_id = ? AND stable_member_id = ?
                  AND normalized_display_name = ? AND source_kind = ? LIMIT 1
                """,
                (
                    room_id,
                    canonical_member_id,
                    item["normalized_display_name"],
                    item["source_kind"],
                ),
            ).fetchone()
            if target:
                target_data = dict(target)
                evidence = _dedupe(
                    _loads_json(target_data.get("evidence_message_ids_json"), [])
                    + _loads_json(item.get("evidence_message_ids_json"), [])
                )
                conn.execute(
                    """
                    UPDATE wechat_group_member_profile_names
                    SET display_name = ?, confidence = ?, evidence_message_ids_json = ?,
                        run_id = ?, first_seen_at = ?, last_seen_at = ?, seen_count = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        target_data.get("display_name") or item.get("display_name") or "",
                        max(_to_float(target_data.get("confidence"), 0), _to_float(item.get("confidence"), 0)),
                        _json_dumps(evidence),
                        target_data.get("run_id") or item.get("run_id") or "",
                        _min_positive(target_data.get("first_seen_at"), item.get("first_seen_at")),
                        max(int(target_data.get("last_seen_at") or 0), int(item.get("last_seen_at") or 0)),
                        int(target_data.get("seen_count") or 0) + int(item.get("seen_count") or 0),
                        int(time.time()),
                        int(target_data["id"]),
                    ),
                )
                conn.execute("DELETE FROM wechat_group_member_profile_names WHERE id = ?", (int(item["id"]),))
            else:
                conn.execute(
                    "UPDATE wechat_group_member_profile_names SET stable_member_id = ? WHERE id = ?",
                    (canonical_member_id, int(item["id"])),
                )

    @staticmethod
    def _merge_claim_subject(
        conn: sqlite3.Connection,
        room_id: str,
        old_member_id: str,
        canonical_member_id: str,
    ) -> None:
        rows = conn.execute(
            """
            SELECT * FROM wechat_group_member_profile_claims
            WHERE stable_room_id = ? AND stable_member_id = ? ORDER BY claim_id ASC
            """,
            (room_id, old_member_id),
        ).fetchall()
        for row in rows:
            item = dict(row)
            target = conn.execute(
                """
                SELECT * FROM wechat_group_member_profile_claims
                WHERE stable_room_id = ? AND stable_member_id = ? AND dimension = ?
                  AND normalized_value = ? AND source_kind = ? LIMIT 1
                """,
                (
                    room_id,
                    canonical_member_id,
                    item["dimension"],
                    item["normalized_value"],
                    item["source_kind"],
                ),
            ).fetchone()
            if target:
                target_data = dict(target)
                evidence = _dedupe(
                    _loads_json(target_data.get("evidence_message_ids_json"), [])
                    + _loads_json(item.get("evidence_message_ids_json"), [])
                )
                conn.execute(
                    """
                    UPDATE wechat_group_member_profile_claims
                    SET value = ?, confidence = ?, evidence_message_ids_json = ?, run_id = ?,
                        status = ?, first_seen_at = ?, last_seen_at = ?, updated_at = ?
                    WHERE claim_id = ?
                    """,
                    (
                        target_data.get("value") or item.get("value") or "",
                        max(_to_float(target_data.get("confidence"), 0), _to_float(item.get("confidence"), 0)),
                        _json_dumps(evidence),
                        target_data.get("run_id") or item.get("run_id") or "",
                        target_data.get("status") or item.get("status") or "accepted",
                        _min_positive(target_data.get("first_seen_at"), item.get("first_seen_at")),
                        max(int(target_data.get("last_seen_at") or 0), int(item.get("last_seen_at") or 0)),
                        int(time.time()),
                        target_data["claim_id"],
                    ),
                )
                conn.execute(
                    "DELETE FROM wechat_group_member_profile_claims WHERE claim_id = ?",
                    (item["claim_id"],),
                )
            else:
                conn.execute(
                    "UPDATE wechat_group_member_profile_claims SET stable_member_id = ? WHERE claim_id = ?",
                    (canonical_member_id, item["claim_id"]),
                )

    @staticmethod
    def _profile_row_to_dict(row: Any) -> Dict[str, Any]:
        data = dict(row or {})
        data["role_hints"] = _loads_json(data.pop("role_hints_json", "[]"), [])
        data["interests"] = _loads_json(data.pop("interests_json", "[]"), [])
        data["common_words"] = _loads_json(data.pop("common_words_json", "[]"), [])
        data["sender_id"] = data.get("stable_member_id", "")
        data["last_seen_at"] = int(data.get("last_observed_at") or 0)
        return data

    @staticmethod
    def _name_row_to_dict(row: Any) -> Dict[str, Any]:
        data = dict(row or {})
        data["evidence_message_ids"] = _loads_json(data.pop("evidence_message_ids_json", "[]"), [])
        data["sender_id"] = data.get("stable_member_id", "")
        data["room_id"] = data.get("stable_room_id", "")
        return data

    @staticmethod
    def _claim_row_to_dict(row: Any) -> Dict[str, Any]:
        data = dict(row or {})
        data["evidence_message_ids"] = _loads_json(data.pop("evidence_message_ids_json", "[]"), [])
        return data

    @staticmethod
    def _revision_row_to_dict(row: Any) -> Dict[str, Any]:
        data = dict(row or {})
        data["before"] = _loads_json(data.pop("before_json", "{}"), {})
        data["after"] = _loads_json(data.pop("after_json", "{}"), {})
        for key in ("before_names", "after_names", "before_claims", "after_claims"):
            value = _loads_optional_list(data.pop(f"{key}_json", "null"))
            if value is not None:
                data[key] = value
        data["evidence_message_ids"] = _loads_json(data.pop("evidence_message_ids_json", "[]"), [])
        data["sender_id"] = data.get("stable_member_id", "")
        data["room_id"] = data.get("stable_room_id", "")
        return data


def _require_text(name: str, value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} is required")
    return text


def _normalize_list(value: Any) -> List[str]:
    if value is None:
        items = []
    elif isinstance(value, list):
        items = value
    else:
        items = str(value).replace("\n", ",").split(",")
    return _dedupe([str(item or "").strip() for item in items])


def _dedupe(values: List[str]) -> List[str]:
    result = []
    for value in values or []:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def _normalize_name_key(value: Any) -> str:
    text = re.sub(r"\s+", "", str(value or "").strip().casefold())
    return text[:200]


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _loads_json(value: Any, default: Any) -> Any:
    if not value:
        return default
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, type(default)) else default
    except Exception:
        return default


def _loads_optional_list(value: Any) -> Optional[List[Dict[str, Any]]]:
    if value in (None, "", "null"):
        return None
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
    except Exception:
        return None
    if not isinstance(parsed, list):
        return None
    return [dict(item) for item in parsed if isinstance(item, dict)]


def _min_positive(*values: Any) -> int:
    candidates = [int(value or 0) for value in values if int(value or 0) > 0]
    return min(candidates) if candidates else 0


def _to_float(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except Exception:
        return fallback
