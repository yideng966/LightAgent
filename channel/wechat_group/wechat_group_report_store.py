"""SQLite persistence for WeChat group report settings, snapshots and deliveries."""

from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
import time
from contextlib import closing
from copy import deepcopy
from typing import Any, Dict, Iterable, List, Optional
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from config import conf


REPORT_SCHEMA_VERSION = 1
ACTIVE_JOB_STATES = {"queued", "collecting", "summarizing", "validating"}
DELIVERY_STATES = {
    "pending", "rendering", "sending", "sent", "fallback_sending",
    "fallback_sent", "partial_failed", "delivery_unknown", "failed",
}
PREVIEW_STATES = {"pending", "rendering", "ready", "text_ready", "failed"}


class ReportVersionConflict(ValueError):
    """Raised when a settings write uses a stale optimistic-lock version."""


def _default_report_store_path() -> str:
    data_root = os.environ.get("LIGHTAGENT_DATA_DIR") or os.path.join(os.path.expanduser("~"), ".lightagent")
    return os.path.join(os.path.expanduser(data_root), "wechat_group", "wechat_group_reports.db")


def default_report_settings() -> Dict[str, Any]:
    """Resolve per-room defaults from the configuration center only."""
    config = conf()
    output_mode = str(config.get("wechat_group_report_default_output_mode", "image_preferred") or "image_preferred")
    image_source = str(config.get("wechat_group_report_default_image_template_source", "skill") or "skill")
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "version": 0,
        "enabled": bool(config.get("wechat_group_report_default_enabled", False)),
        "timezone": str(config.get("wechat_group_report_timezone", "Asia/Shanghai") or "Asia/Shanghai"),
        "manual_admin_only": True,
        "save_daily_topics_to_group_memory": False,
        "schedules": {
            "daily": {"enabled": False, "send_time": "09:00"},
            "weekly": {"enabled": False, "send_time": "09:00"},
            "monthly": {"enabled": False, "send_time": "09:00"},
        },
        "output": {
            "mode": output_mode if output_mode in {"text", "image", "image_preferred"} else "image_preferred",
            "text_template_source": "builtin",
            "builtin_text_template_id": str(config.get("wechat_group_report_default_text_template_id", "standard_text") or "standard_text"),
            "custom_text_template": "",
            "image_template_source": image_source if image_source in {"builtin", "skill"} else "skill",
            "builtin_image_template_id": "",
            "skill_image_template_name": str(
                config.get(
                    "wechat_group_report_default_skill_image_template_name",
                    "wechat-group-report-cyber-intelligence",
                ) or "wechat-group-report-cyber-intelligence"
            ),
        },
        "schedule_sync_status": "not_saved",
        "schedule_sync_error": "",
    }


class WechatGroupReportStore:
    """Thread-safe store. Every public read/write remains stable-room scoped."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path or _default_report_store_path()
        self._lock = threading.RLock()
        parent = os.path.dirname(self.db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._init_schema()

    def get_settings(self, stable_room_id: str) -> Dict[str, Any]:
        room_id = _require_room(stable_room_id)
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM wechat_group_report_settings WHERE stable_room_id = ?",
                (room_id,),
            ).fetchone()
        if not row:
            return default_report_settings()
        result = default_report_settings()
        result.update(_loads_json(row["settings_json"], {}))
        result["version"] = int(row["version"] or 0)
        result["schedule_sync_status"] = str(row["schedule_sync_status"] or "unknown")
        result["schedule_sync_error"] = str(row["schedule_sync_error"] or "")
        return normalize_report_settings(result)

    def save_settings(
        self,
        stable_room_id: str,
        settings: Dict[str, Any],
        expected_version: Any,
        actor: str = "",
        schedule_sync_status: str = "pending",
        schedule_sync_error: str = "",
    ) -> Dict[str, Any]:
        room_id = _require_room(stable_room_id)
        try:
            expected = int(expected_version)
        except (TypeError, ValueError) as exc:
            raise ValueError("expected_version is required") from exc
        normalized = normalize_report_settings(settings)
        now = int(time.time())
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            with conn:
                row = conn.execute(
                    "SELECT version FROM wechat_group_report_settings WHERE stable_room_id = ?",
                    (room_id,),
                ).fetchone()
                actual = int(row["version"] or 0) if row else 0
                if actual != expected:
                    raise ReportVersionConflict("settings version conflict")
                version = actual + 1
                normalized["version"] = version
                conn.execute(
                    """
                    INSERT INTO wechat_group_report_settings (
                        stable_room_id, settings_json, version, schedule_sync_status,
                        schedule_sync_error, updated_by, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(stable_room_id) DO UPDATE SET
                        settings_json = excluded.settings_json,
                        version = excluded.version,
                        schedule_sync_status = excluded.schedule_sync_status,
                        schedule_sync_error = excluded.schedule_sync_error,
                        updated_by = excluded.updated_by,
                        updated_at = excluded.updated_at
                    """,
                    (
                        room_id,
                        json.dumps(normalized, ensure_ascii=False, separators=(",", ":")),
                        version,
                        str(schedule_sync_status or "pending"),
                        _safe_error(schedule_sync_error),
                        str(actor or ""),
                        now,
                        now,
                    ),
                )
        return normalized

    def update_schedule_sync_status(
        self,
        stable_room_id: str,
        status: str,
        error: str = "",
    ) -> Dict[str, Any]:
        room_id = _require_room(stable_room_id)
        with self._lock, closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    """
                    UPDATE wechat_group_report_settings
                    SET schedule_sync_status = ?, schedule_sync_error = ?, updated_at = ?
                    WHERE stable_room_id = ?
                    """,
                    (str(status or "unknown"), _safe_error(error), int(time.time()), room_id),
                )
        return self.get_settings(room_id)

    def list_settings_room_ids(self) -> List[str]:
        with self._lock, closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT stable_room_id FROM wechat_group_report_settings ORDER BY stable_room_id ASC"
            ).fetchall()
        return [str(row[0] or "").strip() for row in rows if str(row[0] or "").strip()]

    def create_or_reuse_job(
        self,
        stable_room_id: str,
        report_type: str,
        period_start: str,
        period_end: str,
        source_watermark: int,
        content_version: str,
        actor: str,
        draft_settings: Optional[Dict[str, Any]] = None,
        force_regenerate: bool = False,
    ) -> Dict[str, Any]:
        room_id = _require_room(stable_room_id)
        key = build_generation_idempotency_key(
            room_id, report_type, period_start, period_end, source_watermark, content_version,
            force_regenerate=force_regenerate,
        )
        now = int(time.time())
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            with conn:
                existing = conn.execute(
                    "SELECT * FROM wechat_group_report_jobs WHERE idempotency_key = ?",
                    (key,),
                ).fetchone()
                if existing and str(existing["state"] or "") in ACTIVE_JOB_STATES:
                    return self._job_row_to_dict(existing)
                job_id = uuid4().hex
                conn.execute(
                    """
                    INSERT INTO wechat_group_report_jobs (
                        job_id, idempotency_key, stable_room_id, report_type, period_start,
                        period_end, source_watermark, content_version, actor, draft_settings_json,
                        state, stage, completed_items, total_items, error_code, created_at,
                        started_at, finished_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'queued', 'queued', 0, 0, '', ?, 0, 0)
                    ON CONFLICT(idempotency_key) DO UPDATE SET
                        job_id = excluded.job_id, stable_room_id = excluded.stable_room_id,
                        report_type = excluded.report_type, period_start = excluded.period_start,
                        period_end = excluded.period_end, source_watermark = excluded.source_watermark,
                        content_version = excluded.content_version, actor = excluded.actor,
                        draft_settings_json = excluded.draft_settings_json, state = 'queued',
                        stage = 'queued', completed_items = 0, total_items = 0, error_code = '',
                        created_at = excluded.created_at, started_at = 0, finished_at = 0
                    """,
                    (
                        job_id, key, room_id, str(report_type or ""), str(period_start or ""),
                        str(period_end or ""), int(source_watermark or 0), str(content_version or "1"),
                        str(actor or ""), json.dumps(draft_settings or {}, ensure_ascii=False), now,
                    ),
                )
                row = conn.execute(
                    "SELECT * FROM wechat_group_report_jobs WHERE idempotency_key = ?", (key,)
                ).fetchone()
        return self._job_row_to_dict(row)

    def get_job(self, job_id: str, stable_room_id: str = "") -> Optional[Dict[str, Any]]:
        job_text = str(job_id or "").strip()
        if not job_text:
            return None
        clauses = ["job_id = ?"]
        params: List[Any] = [job_text]
        if stable_room_id:
            clauses.append("stable_room_id = ?")
            params.append(_require_room(stable_room_id))
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM wechat_group_report_jobs WHERE " + " AND ".join(clauses), params
            ).fetchone()
        return self._job_row_to_dict(row) if row else None

    def update_job(
        self,
        job_id: str,
        stable_room_id: str,
        state: Optional[str] = None,
        stage: Optional[str] = None,
        completed_items: Optional[int] = None,
        total_items: Optional[int] = None,
        error_code: Optional[str] = None,
        report_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        job = self.get_job(job_id, stable_room_id)
        if not job:
            raise ValueError("job not found")
        updates: Dict[str, Any] = {}
        if state is not None:
            updates["state"] = str(state)
            if state in {"collecting", "summarizing", "validating"} and not job.get("started_at"):
                updates["started_at"] = int(time.time())
            if state in {"ready", "failed"}:
                updates["finished_at"] = int(time.time())
        if stage is not None:
            updates["stage"] = str(stage)
        if completed_items is not None:
            updates["completed_items"] = max(int(completed_items), 0)
        if total_items is not None:
            updates["total_items"] = max(int(total_items), 0)
        if error_code is not None:
            updates["error_code"] = _safe_error(error_code, limit=120)
        if report_id is not None:
            updates["report_id"] = str(report_id or "")
        if not updates:
            return job
        assignments = ", ".join(f"{key} = ?" for key in updates)
        with self._lock, closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    f"UPDATE wechat_group_report_jobs SET {assignments} WHERE job_id = ? AND stable_room_id = ?",
                    [*updates.values(), str(job_id), _require_room(stable_room_id)],
                )
        return self.get_job(job_id, stable_room_id) or {}

    def recover_incomplete_jobs(self) -> int:
        """Mark interrupted work as queued so the runner can safely resume it."""
        with self._lock, closing(self._connect()) as conn:
            with conn:
                cursor = conn.execute(
                    """
                    UPDATE wechat_group_report_jobs
                    SET state = 'queued', stage = 'recovered', error_code = ''
                    WHERE state IN ('collecting', 'summarizing', 'validating')
                    """
                )
        return int(cursor.rowcount or 0)

    def list_queued_jobs(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT * FROM wechat_group_report_jobs
                WHERE state = 'queued'
                ORDER BY created_at ASC, job_id ASC LIMIT ?
                """,
                (min(max(int(limit or 100), 1), 500),),
            ).fetchall()
        return [self._job_row_to_dict(row) for row in rows]

    def find_reusable_report(
        self,
        stable_room_id: str,
        report_type: str,
        period_start: str,
        period_end: str,
        source_watermark: int,
        content_version: str,
    ) -> Optional[Dict[str, Any]]:
        report_key = build_report_key(stable_room_id, report_type, period_start, period_end)
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT * FROM wechat_group_reports
                WHERE report_key = ? AND source_watermark = ? AND content_version = ? AND state = 'ready'
                ORDER BY revision DESC LIMIT 1
                """,
                (report_key, int(source_watermark or 0), str(content_version or "1")),
            ).fetchone()
        return self._report_row_to_dict(row) if row else None

    def create_report(
        self,
        stable_room_id: str,
        report_type: str,
        period_start: str,
        period_end: str,
        source_watermark: int,
        content_version: str,
        payload: Dict[str, Any],
        force_regenerate: bool = False,
    ) -> Dict[str, Any]:
        room_id = _require_room(stable_room_id)
        report_key = build_report_key(room_id, report_type, period_start, period_end)
        now = int(time.time())
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            with conn:
                if not force_regenerate:
                    existing = conn.execute(
                        """
                        SELECT * FROM wechat_group_reports
                        WHERE report_key = ? AND source_watermark = ? AND content_version = ? AND state = 'ready'
                        ORDER BY revision DESC LIMIT 1
                        """,
                        (report_key, int(source_watermark or 0), str(content_version or "1")),
                    ).fetchone()
                    if existing:
                        return self._report_row_to_dict(existing)
                previous = conn.execute(
                    "SELECT report_id, COALESCE(MAX(revision), 0) FROM wechat_group_reports WHERE report_key = ?",
                    (report_key,),
                ).fetchone()
                previous_id = str(previous[0] or "") if previous else ""
                revision = int(previous[1] or 0) + 1 if previous else 1
                report_id = uuid4().hex
                conn.execute(
                    """
                    INSERT INTO wechat_group_reports (
                        report_id, stable_room_id, report_key, revision, report_type, period_start,
                        period_end, source_watermark, content_version, payload_json, state,
                        supersedes_report_id, generated_at, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ready', ?, ?, ?)
                    """,
                    (
                        report_id, room_id, report_key, revision, str(report_type or ""),
                        str(period_start or ""), str(period_end or ""), int(source_watermark or 0),
                        str(content_version or "1"), json.dumps(payload or {}, ensure_ascii=False),
                        previous_id, now, now,
                    ),
                )
                row = conn.execute(
                    "SELECT * FROM wechat_group_reports WHERE report_id = ?", (report_id,)
                ).fetchone()
        return self._report_row_to_dict(row)

    def get_report(self, report_id: str, stable_room_id: str = "") -> Optional[Dict[str, Any]]:
        report_text = str(report_id or "").strip()
        if not report_text:
            return None
        clauses = ["report_id = ?"]
        params: List[Any] = [report_text]
        if stable_room_id:
            clauses.append("stable_room_id = ?")
            params.append(_require_room(stable_room_id))
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM wechat_group_reports WHERE " + " AND ".join(clauses), params
            ).fetchone()
        return self._report_row_to_dict(row) if row else None

    def get_room_overview(self, stable_room_id: str) -> Dict[str, Any]:
        room_id = _require_room(stable_room_id)
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            latest_report = conn.execute(
                """
                SELECT * FROM wechat_group_reports WHERE stable_room_id = ?
                ORDER BY generated_at DESC, revision DESC LIMIT 1
                """, (room_id,)
            ).fetchone()
            latest_delivery = conn.execute(
                """
                SELECT * FROM wechat_group_report_deliveries WHERE stable_room_id = ?
                ORDER BY created_at DESC LIMIT 1
                """, (room_id,)
            ).fetchone()
        return {
            "latest_report": self._report_row_to_dict(latest_report) if latest_report else None,
            "latest_delivery": self._delivery_row_to_dict(latest_delivery) if latest_delivery else None,
        }

    def create_delivery(
        self,
        report_id: str,
        stable_room_id: str,
        actor: str,
        output_settings: Dict[str, Any],
        confirmation_token: str = "",
    ) -> Dict[str, Any]:
        room_id = _require_room(stable_room_id)
        report = self.get_report(report_id, room_id)
        if not report or report.get("state") != "ready":
            raise ValueError("ready report is required")
        output = dict((output_settings or {}).get("output") or output_settings or {})
        mode = str(output.get("mode") or "image_preferred")
        if mode not in {"text", "image", "image_preferred"}:
            raise ValueError("invalid output mode")
        delivery_id = uuid4().hex
        now = int(time.time())
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            with conn:
                conn.execute(
                    """
                    INSERT INTO wechat_group_report_deliveries (
                        delivery_id, report_id, stable_room_id, actor, output_mode, actual_output,
                        output_settings_json, template_id, template_version, fallback_reason,
                        confirmation_token, state, error_code, created_at, sent_at
                    ) VALUES (?, ?, ?, ?, ?, '', ?, '', '', '', ?, 'pending', '', ?, 0)
                    """,
                    (
                        delivery_id, str(report_id), room_id, str(actor or ""), mode,
                        json.dumps(output, ensure_ascii=False), str(confirmation_token or ""), now,
                    ),
                )
                row = conn.execute(
                    "SELECT * FROM wechat_group_report_deliveries WHERE delivery_id = ?", (delivery_id,)
                ).fetchone()
        return self._delivery_row_to_dict(row)

    def issue_send_confirmation(self, report_id: str, stable_room_id: str, ttl_seconds: int = 900) -> str:
        report = self.get_report(report_id, stable_room_id)
        if not report or report.get("state") != "ready":
            raise ValueError("ready report is required")
        token = uuid4().hex
        now = int(time.time())
        with self._lock, closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO wechat_group_report_confirmations (
                        token, report_id, stable_room_id, expires_at, consumed_at, created_at
                    ) VALUES (?, ?, ?, ?, 0, ?)
                    """,
                    (token, str(report_id), _require_room(stable_room_id), now + max(int(ttl_seconds), 60), now),
                )
        return token

    def consume_send_confirmation(self, token: str, report_id: str, stable_room_id: str) -> bool:
        token_text = str(token or "").strip()
        if not token_text:
            return False
        now = int(time.time())
        with self._lock, closing(self._connect()) as conn:
            with conn:
                cursor = conn.execute(
                    """
                    UPDATE wechat_group_report_confirmations
                    SET consumed_at = ?
                    WHERE token = ? AND report_id = ? AND stable_room_id = ?
                      AND consumed_at = 0 AND expires_at >= ?
                    """,
                    (now, token_text, str(report_id), _require_room(stable_room_id), now),
                )
        return bool(cursor.rowcount)

    def get_delivery(self, delivery_id: str, stable_room_id: str = "") -> Optional[Dict[str, Any]]:
        delivery_text = str(delivery_id or "").strip()
        if not delivery_text:
            return None
        clauses = ["delivery_id = ?"]
        params: List[Any] = [delivery_text]
        if stable_room_id:
            clauses.append("stable_room_id = ?")
            params.append(_require_room(stable_room_id))
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM wechat_group_report_deliveries WHERE " + " AND ".join(clauses), params
            ).fetchone()
        return self._delivery_row_to_dict(row) if row else None

    def update_delivery(self, delivery_id: str, stable_room_id: str, **updates: Any) -> Dict[str, Any]:
        delivery = self.get_delivery(delivery_id, stable_room_id)
        if not delivery:
            raise ValueError("delivery not found")
        allowed = {
            "state", "actual_output", "template_id", "template_version", "fallback_reason",
            "error_code", "sent_at", "confirmation_token",
        }
        values = {key: value for key, value in updates.items() if key in allowed}
        if "state" in values and values["state"] not in DELIVERY_STATES:
            raise ValueError("invalid delivery state")
        if "error_code" in values:
            values["error_code"] = _safe_error(values["error_code"], limit=120)
        if not values:
            return delivery
        assignments = ", ".join(f"{key} = ?" for key in values)
        with self._lock, closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    f"UPDATE wechat_group_report_deliveries SET {assignments} WHERE delivery_id = ? AND stable_room_id = ?",
                    [*values.values(), str(delivery_id), _require_room(stable_room_id)],
                )
        return self.get_delivery(delivery_id, stable_room_id) or {}

    def upsert_delivery_part(
        self,
        delivery_id: str,
        stable_room_id: str,
        part_index: int,
        part_type: str,
        content_hash: str = "",
        relative_path: str = "",
        request_id: str = "",
        state: str = "pending",
        attempt_count: int = 0,
        error_code: str = "",
    ) -> Dict[str, Any]:
        room_id = _require_room(stable_room_id)
        if not self.get_delivery(delivery_id, room_id):
            raise ValueError("delivery not found")
        index = max(int(part_index), 0)
        if str(part_type) not in {"text", "image"}:
            raise ValueError("invalid delivery part type")
        relative = validate_report_asset_relative_path(relative_path) if relative_path else ""
        now = int(time.time())
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            with conn:
                conn.execute(
                    """
                    INSERT INTO wechat_group_report_delivery_parts (
                        delivery_id, part_index, part_type, content_hash, relative_path, request_id,
                        state, attempt_count, error_code, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(delivery_id, part_index) DO UPDATE SET
                        part_type = excluded.part_type, content_hash = excluded.content_hash,
                        relative_path = excluded.relative_path, request_id = excluded.request_id,
                        state = excluded.state, attempt_count = excluded.attempt_count,
                        error_code = excluded.error_code, updated_at = excluded.updated_at
                    """,
                    (
                        str(delivery_id), index, str(part_type), str(content_hash or ""), relative,
                        str(request_id or ""), str(state or "pending"), max(int(attempt_count or 0), 0),
                        _safe_error(error_code, limit=120), now, now,
                    ),
                )
                row = conn.execute(
                    """
                    SELECT * FROM wechat_group_report_delivery_parts
                    WHERE delivery_id = ? AND part_index = ?
                    """, (str(delivery_id), index),
                ).fetchone()
        return self._part_row_to_dict(row)

    def list_delivery_parts(self, delivery_id: str, stable_room_id: str) -> List[Dict[str, Any]]:
        room_id = _require_room(stable_room_id)
        if not self.get_delivery(delivery_id, room_id):
            return []
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT * FROM wechat_group_report_delivery_parts
                WHERE delivery_id = ? ORDER BY part_index ASC
                """, (str(delivery_id),),
            ).fetchall()
        return [self._part_row_to_dict(row) for row in rows]

    def get_delivery_asset_path(
        self,
        delivery_id: str,
        stable_room_id: str,
        part_index: int,
    ) -> str:
        room_id = _require_room(stable_room_id)
        if not self.get_delivery(delivery_id, room_id):
            return ""
        with self._lock, closing(self._connect()) as conn:
            row = conn.execute(
                """
                SELECT relative_path FROM wechat_group_report_delivery_parts
                WHERE delivery_id = ? AND part_index = ? AND part_type = 'image'
                """, (str(delivery_id), int(part_index)),
            ).fetchone()
        return validate_report_asset_relative_path(row[0]) if row and row[0] else ""

    def create_preview(
        self,
        preview_id: str,
        job_id: str,
        report_id: str,
        stable_room_id: str,
        output_settings: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Persist one Web preview attempt without treating it as a delivery."""
        room_id = _require_room(stable_room_id)
        preview_text = str(preview_id or "").strip()
        job_text = str(job_id or "").strip()
        report_text = str(report_id or "").strip()
        if not preview_text or not job_text or not report_text:
            raise ValueError("preview_id, job_id, and report_id are required")
        report = self.get_report(report_text, room_id)
        if not report or report.get("state") != "ready":
            raise ValueError("ready report is required")
        output = dict((output_settings or {}).get("output") or output_settings or {})
        mode = str(output.get("mode") or "image_preferred")
        if mode not in {"text", "image", "image_preferred"}:
            raise ValueError("invalid output mode")
        now = int(time.time())
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            with conn:
                conn.execute(
                    """
                    INSERT INTO wechat_group_report_previews (
                        preview_id, job_id, report_id, stable_room_id, output_mode,
                        actual_output, output_settings_json, state, fallback_reason,
                        error_code, text_parts_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, '', ?, 'pending', '', '', '[]', ?, ?)
                    ON CONFLICT(preview_id) DO UPDATE SET
                        job_id = excluded.job_id, report_id = excluded.report_id,
                        stable_room_id = excluded.stable_room_id,
                        output_mode = excluded.output_mode,
                        actual_output = '', output_settings_json = excluded.output_settings_json,
                        state = 'pending', fallback_reason = '', error_code = '',
                        text_parts_json = '[]', updated_at = excluded.updated_at
                    """,
                    (
                        preview_text, job_text, report_text, room_id, mode,
                        json.dumps(output, ensure_ascii=False), now, now,
                    ),
                )
                row = conn.execute(
                    "SELECT * FROM wechat_group_report_previews WHERE preview_id = ?", (preview_text,)
                ).fetchone()
        return self._preview_row_to_dict(row)

    def get_preview(self, preview_id: str, stable_room_id: str = "") -> Optional[Dict[str, Any]]:
        preview_text = str(preview_id or "").strip()
        if not preview_text:
            return None
        clauses = ["preview_id = ?"]
        params: List[Any] = [preview_text]
        if stable_room_id:
            clauses.append("stable_room_id = ?")
            params.append(_require_room(stable_room_id))
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM wechat_group_report_previews WHERE " + " AND ".join(clauses), params
            ).fetchone()
        return self._preview_row_to_dict(row) if row else None

    def update_preview(self, preview_id: str, stable_room_id: str, **updates: Any) -> Dict[str, Any]:
        preview = self.get_preview(preview_id, stable_room_id)
        if not preview:
            raise ValueError("preview not found")
        allowed = {"state", "actual_output", "fallback_reason", "error_code", "text_parts"}
        values = {key: value for key, value in updates.items() if key in allowed}
        if "state" in values and values["state"] not in PREVIEW_STATES:
            raise ValueError("invalid preview state")
        if "error_code" in values:
            values["error_code"] = _safe_error(values["error_code"], limit=120)
        if "fallback_reason" in values:
            values["fallback_reason"] = _safe_error(values["fallback_reason"], limit=120)
        if "text_parts" in values:
            parts = values.pop("text_parts")
            values["text_parts_json"] = json.dumps(
                [str(item) for item in parts] if isinstance(parts, list) else [],
                ensure_ascii=False,
            )
        if not values:
            return preview
        values["updated_at"] = int(time.time())
        assignments = ", ".join(f"{key} = ?" for key in values)
        with self._lock, closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    f"UPDATE wechat_group_report_previews SET {assignments} WHERE preview_id = ? AND stable_room_id = ?",
                    [*values.values(), str(preview_id), _require_room(stable_room_id)],
                )
        return self.get_preview(preview_id, stable_room_id) or {}

    def replace_preview_parts(
        self,
        preview_id: str,
        stable_room_id: str,
        parts: Iterable[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        room_id = _require_room(stable_room_id)
        if not self.get_preview(preview_id, room_id):
            raise ValueError("preview not found")
        rows = []
        for index, item in enumerate(parts or []):
            row = item if isinstance(item, dict) else {}
            relative_path = validate_report_asset_relative_path(row.get("relative_path"))
            rows.append((index, relative_path, max(int(row.get("width") or 0), 0), max(int(row.get("height") or 0), 0)))
        now = int(time.time())
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            with conn:
                conn.execute(
                    "DELETE FROM wechat_group_report_preview_parts WHERE preview_id = ?", (str(preview_id),)
                )
                conn.executemany(
                    """
                    INSERT INTO wechat_group_report_preview_parts (
                        preview_id, part_index, relative_path, width, height, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    [(str(preview_id), index, path, width, height, now) for index, path, width, height in rows],
                )
                saved = conn.execute(
                    """
                    SELECT * FROM wechat_group_report_preview_parts
                    WHERE preview_id = ? ORDER BY part_index ASC
                    """, (str(preview_id),)
                ).fetchall()
        return [dict(row) for row in saved]

    def list_preview_parts(self, preview_id: str, stable_room_id: str) -> List[Dict[str, Any]]:
        room_id = _require_room(stable_room_id)
        if not self.get_preview(preview_id, room_id):
            return []
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT * FROM wechat_group_report_preview_parts
                WHERE preview_id = ? ORDER BY part_index ASC
                """, (str(preview_id),)
            ).fetchall()
        return [dict(row) for row in rows]

    def get_preview_asset_path(self, preview_id: str, stable_room_id: str, part_index: int) -> str:
        room_id = _require_room(stable_room_id)
        if not self.get_preview(preview_id, room_id):
            return ""
        with self._lock, closing(self._connect()) as conn:
            row = conn.execute(
                """
                SELECT relative_path FROM wechat_group_report_preview_parts
                WHERE preview_id = ? AND part_index = ?
                """, (str(preview_id), int(part_index)),
            ).fetchone()
        return validate_report_asset_relative_path(row[0]) if row and row[0] else ""

    def _init_schema(self) -> None:
        with closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS wechat_group_report_settings (
                        stable_room_id TEXT PRIMARY KEY,
                        settings_json TEXT NOT NULL,
                        version INTEGER NOT NULL DEFAULT 0,
                        schedule_sync_status TEXT NOT NULL DEFAULT 'not_saved',
                        schedule_sync_error TEXT NOT NULL DEFAULT '',
                        updated_by TEXT NOT NULL DEFAULT '',
                        created_at INTEGER NOT NULL,
                        updated_at INTEGER NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS wechat_group_report_jobs (
                        job_id TEXT PRIMARY KEY,
                        idempotency_key TEXT NOT NULL UNIQUE,
                        stable_room_id TEXT NOT NULL,
                        report_type TEXT NOT NULL,
                        period_start TEXT NOT NULL,
                        period_end TEXT NOT NULL,
                        source_watermark INTEGER NOT NULL DEFAULT 0,
                        content_version TEXT NOT NULL,
                        actor TEXT NOT NULL DEFAULT '',
                        draft_settings_json TEXT NOT NULL DEFAULT '{}',
                        report_id TEXT NOT NULL DEFAULT '',
                        state TEXT NOT NULL,
                        stage TEXT NOT NULL,
                        completed_items INTEGER NOT NULL DEFAULT 0,
                        total_items INTEGER NOT NULL DEFAULT 0,
                        error_code TEXT NOT NULL DEFAULT '',
                        created_at INTEGER NOT NULL,
                        started_at INTEGER NOT NULL DEFAULT 0,
                        finished_at INTEGER NOT NULL DEFAULT 0
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_wechat_group_report_jobs_room_time
                    ON wechat_group_report_jobs(stable_room_id, created_at, job_id)
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS wechat_group_reports (
                        report_id TEXT PRIMARY KEY,
                        stable_room_id TEXT NOT NULL,
                        report_key TEXT NOT NULL,
                        revision INTEGER NOT NULL,
                        report_type TEXT NOT NULL,
                        period_start TEXT NOT NULL,
                        period_end TEXT NOT NULL,
                        source_watermark INTEGER NOT NULL,
                        content_version TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        state TEXT NOT NULL,
                        supersedes_report_id TEXT NOT NULL DEFAULT '',
                        generated_at INTEGER NOT NULL,
                        created_at INTEGER NOT NULL,
                        UNIQUE(report_key, revision)
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_wechat_group_reports_room_time
                    ON wechat_group_reports(stable_room_id, generated_at, revision)
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS wechat_group_report_deliveries (
                        delivery_id TEXT PRIMARY KEY,
                        report_id TEXT NOT NULL,
                        stable_room_id TEXT NOT NULL,
                        actor TEXT NOT NULL DEFAULT '',
                        output_mode TEXT NOT NULL,
                        actual_output TEXT NOT NULL DEFAULT '',
                        output_settings_json TEXT NOT NULL DEFAULT '{}',
                        template_id TEXT NOT NULL DEFAULT '',
                        template_version TEXT NOT NULL DEFAULT '',
                        fallback_reason TEXT NOT NULL DEFAULT '',
                        confirmation_token TEXT NOT NULL DEFAULT '',
                        state TEXT NOT NULL,
                        error_code TEXT NOT NULL DEFAULT '',
                        created_at INTEGER NOT NULL,
                        sent_at INTEGER NOT NULL DEFAULT 0
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_wechat_group_report_deliveries_room_time
                    ON wechat_group_report_deliveries(stable_room_id, created_at, delivery_id)
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS wechat_group_report_delivery_parts (
                        delivery_id TEXT NOT NULL,
                        part_index INTEGER NOT NULL,
                        part_type TEXT NOT NULL,
                        content_hash TEXT NOT NULL DEFAULT '',
                        relative_path TEXT NOT NULL DEFAULT '',
                        request_id TEXT NOT NULL DEFAULT '',
                        state TEXT NOT NULL,
                        attempt_count INTEGER NOT NULL DEFAULT 0,
                        error_code TEXT NOT NULL DEFAULT '',
                        created_at INTEGER NOT NULL,
                        updated_at INTEGER NOT NULL,
                        PRIMARY KEY(delivery_id, part_index)
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS wechat_group_report_confirmations (
                        token TEXT PRIMARY KEY,
                        report_id TEXT NOT NULL,
                        stable_room_id TEXT NOT NULL,
                        expires_at INTEGER NOT NULL,
                        consumed_at INTEGER NOT NULL DEFAULT 0,
                        created_at INTEGER NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS wechat_group_report_previews (
                        preview_id TEXT PRIMARY KEY,
                        job_id TEXT NOT NULL,
                        report_id TEXT NOT NULL,
                        stable_room_id TEXT NOT NULL,
                        output_mode TEXT NOT NULL,
                        actual_output TEXT NOT NULL DEFAULT '',
                        output_settings_json TEXT NOT NULL DEFAULT '{}',
                        state TEXT NOT NULL,
                        fallback_reason TEXT NOT NULL DEFAULT '',
                        error_code TEXT NOT NULL DEFAULT '',
                        text_parts_json TEXT NOT NULL DEFAULT '[]',
                        created_at INTEGER NOT NULL,
                        updated_at INTEGER NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_wechat_group_report_previews_room_time
                    ON wechat_group_report_previews(stable_room_id, created_at, preview_id)
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS wechat_group_report_preview_parts (
                        preview_id TEXT NOT NULL,
                        part_index INTEGER NOT NULL,
                        relative_path TEXT NOT NULL,
                        width INTEGER NOT NULL DEFAULT 0,
                        height INTEGER NOT NULL DEFAULT 0,
                        created_at INTEGER NOT NULL,
                        PRIMARY KEY(preview_id, part_index)
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_wechat_group_report_confirmations_report
                    ON wechat_group_report_confirmations(report_id, stable_room_id, expires_at)
                    """
                )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path, timeout=15)

    @staticmethod
    def _job_row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        data = dict(row)
        data["draft_settings"] = _loads_json(data.pop("draft_settings_json", "{}"), {})
        return data

    @staticmethod
    def _report_row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        data = dict(row)
        data["payload"] = _loads_json(data.pop("payload_json", "{}"), {})
        return data

    @staticmethod
    def _delivery_row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        data = dict(row)
        data["output_settings"] = _loads_json(data.pop("output_settings_json", "{}"), {})
        return data

    @staticmethod
    def _part_row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        return dict(row)

    @staticmethod
    def _preview_row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        data = dict(row)
        data["output_settings"] = _loads_json(data.pop("output_settings_json", "{}"), {})
        data["text_parts"] = _loads_json(data.pop("text_parts_json", "[]"), [])
        return data


def normalize_report_settings(value: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and normalize the room-scoped settings document."""
    raw = deepcopy(value or {})
    if "schema_version" in raw:
        try:
            schema_version = int(raw["schema_version"])
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid report settings schema version") from exc
        if schema_version != REPORT_SCHEMA_VERSION:
            raise ValueError("unsupported report settings schema version")
    defaults = default_report_settings()
    result = deepcopy(defaults)
    result.update({key: raw[key] for key in ("enabled", "timezone", "manual_admin_only", "save_daily_topics_to_group_memory") if key in raw})
    result["schema_version"] = REPORT_SCHEMA_VERSION
    result["enabled"] = bool(result["enabled"])
    result["manual_admin_only"] = bool(result["manual_admin_only"])
    result["save_daily_topics_to_group_memory"] = bool(result["save_daily_topics_to_group_memory"])
    result["timezone"] = str(result["timezone"] or "Asia/Shanghai").strip() or "Asia/Shanghai"
    try:
        ZoneInfo(result["timezone"])
    except ZoneInfoNotFoundError as exc:
        raise ValueError("invalid report timezone") from exc
    schedules = raw.get("schedules") if isinstance(raw.get("schedules"), dict) else {}
    result["schedules"] = {}
    for report_type in ("daily", "weekly", "monthly"):
        source = schedules.get(report_type) if isinstance(schedules.get(report_type), dict) else {}
        default_schedule = defaults["schedules"][report_type]
        send_time = str(source.get("send_time", default_schedule["send_time"]) or "").strip()
        if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", send_time):
            raise ValueError(f"invalid {report_type} send_time")
        result["schedules"][report_type] = {
            "enabled": bool(source.get("enabled", default_schedule["enabled"])),
            "send_time": send_time,
        }
    output = raw.get("output") if isinstance(raw.get("output"), dict) else {}
    result["output"].update(output)
    mode = str(result["output"].get("mode") or "").strip()
    if mode not in {"text", "image", "image_preferred"}:
        raise ValueError("invalid report output mode")
    result["output"]["mode"] = mode
    text_source = str(result["output"].get("text_template_source") or "builtin").strip()
    if text_source not in {"builtin", "custom"}:
        raise ValueError("invalid text template source")
    result["output"]["text_template_source"] = text_source
    custom = str(result["output"].get("custom_text_template") or "")
    if len(custom.encode("utf-8")) > 64 * 1024:
        raise ValueError("custom text template exceeds 64 KiB")
    result["output"]["custom_text_template"] = custom
    builtin_text_template_id = str(result["output"].get("builtin_text_template_id") or "standard_text")
    if text_source == "builtin":
        from channel.wechat_group.wechat_group_report_templates import get_builtin_text_template

        get_builtin_text_template(builtin_text_template_id)
    result["output"]["builtin_text_template_id"] = builtin_text_template_id
    image_source = str(result["output"].get("image_template_source") or "skill").strip()
    if image_source not in {"builtin", "skill"}:
        raise ValueError("invalid image template source")
    result["output"]["image_template_source"] = image_source
    result["output"]["builtin_image_template_id"] = str(result["output"].get("builtin_image_template_id") or "")
    result["output"]["skill_image_template_name"] = str(result["output"].get("skill_image_template_name") or "")
    result["schedule_sync_status"] = str(raw.get("schedule_sync_status") or defaults["schedule_sync_status"])
    result["schedule_sync_error"] = _safe_error(raw.get("schedule_sync_error") or "")
    result["version"] = int(raw.get("version") or 0)
    return result


def build_report_key(stable_room_id: str, report_type: str, period_start: str, period_end: str) -> str:
    return "|".join([
        _require_room(stable_room_id), str(report_type or ""), str(period_start or ""), str(period_end or ""),
    ])


def build_generation_idempotency_key(
    stable_room_id: str,
    report_type: str,
    period_start: str,
    period_end: str,
    source_watermark: int,
    content_version: str,
    force_regenerate: bool = False,
) -> str:
    key = "|".join([
        build_report_key(stable_room_id, report_type, period_start, period_end),
        str(int(source_watermark or 0)), str(content_version or "1"),
    ])
    return f"{key}|force" if force_regenerate else key


def validate_report_asset_relative_path(value: Any) -> str:
    path = str(value or "").replace("\\", "/").strip("/")
    if not path or path.startswith("/") or "\x00" in path:
        raise ValueError("invalid report asset path")
    parts = path.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("invalid report asset path")
    return "/".join(parts)


def _require_room(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("stable_room_id is required")
    return text


def _safe_error(value: Any, limit: int = 240) -> str:
    text = re.sub(r"[\r\n\t]+", " ", str(value or "")).strip()
    return text[:limit]


def _loads_json(value: Any, default: Any) -> Any:
    try:
        parsed = json.loads(value or "")
        return parsed if isinstance(parsed, type(default)) else default
    except Exception:
        return default
