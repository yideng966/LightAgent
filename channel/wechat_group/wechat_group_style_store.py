"""SQLite store for WeChat group style cards."""

from __future__ import annotations

import hashlib
import os
import sqlite3
import threading
import time
from contextlib import closing
from typing import Dict, List, Optional


def _default_style_store_path() -> str:
    data_root = os.environ.get("LIGHTAGENT_DATA_DIR") or os.path.join(os.path.expanduser("~"), ".lightagent")
    return os.path.join(os.path.expanduser(data_root), "wechat_group", "wechat_group_style.db")


class WechatGroupStyleStore:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or _default_style_store_path()
        self._lock = threading.Lock()
        parent = os.path.dirname(self.db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._init_schema()

    def upsert_style_card(
        self,
        room_id: str,
        intent: str,
        tone: str,
        trigger_rule: str,
        avoid_rule: str,
        example: str,
        evidence_count: int,
        status: str = "candidate",
        style_id: str = "",
        created_at: Optional[int] = None,
        updated_at: Optional[int] = None,
    ) -> Dict:
        room_text = str(room_id or "").strip()
        if not room_text:
            raise ValueError("room_id is required")
        style_text = str(style_id or "").strip()
        if not style_text:
            style_text = _build_style_signature(
                room_id=room_text,
                intent=intent,
                tone=tone,
                trigger_rule=trigger_rule,
                avoid_rule=avoid_rule,
            )
        now = _coerce_timestamp(updated_at)
        created_ts = _coerce_timestamp(created_at) if created_at is not None else now
        with self._lock, closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO wechat_group_style_cards (
                        style_id, room_id, intent, tone, trigger_rule, avoid_rule,
                        example, evidence_count, status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(style_id) DO UPDATE SET
                        room_id = excluded.room_id,
                        intent = excluded.intent,
                        tone = excluded.tone,
                        trigger_rule = excluded.trigger_rule,
                        avoid_rule = excluded.avoid_rule,
                        example = excluded.example,
                        evidence_count = excluded.evidence_count,
                        status = excluded.status,
                        updated_at = excluded.updated_at
                    """,
                    (
                        style_text,
                        room_text,
                        str(intent or "").strip(),
                        str(tone or "").strip(),
                        str(trigger_rule or "").strip(),
                        str(avoid_rule or "").strip(),
                        str(example or "").strip(),
                        max(int(evidence_count or 0), 0),
                        str(status or "candidate").strip() or "candidate",
                        created_ts,
                        now,
                    ),
                )
        return self.get_style(room_text, style_text) or {}

    def get_style(self, room_id: str, style_id: str) -> Optional[Dict]:
        room_text = str(room_id or "").strip()
        style_text = str(style_id or "").strip()
        if not room_text or not style_text:
            return None
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT *
                FROM wechat_group_style_cards
                WHERE room_id = ? AND style_id = ?
                LIMIT 1
                """,
                (room_text, style_text),
            ).fetchone()
        return dict(row) if row else None

    def list_styles(self, room_id: str, status: str = "", limit: int = 20) -> List[Dict]:
        room_text = str(room_id or "").strip()
        if not room_text:
            return []
        max_limit = min(max(int(limit or 20), 1), 100)
        clauses = ["room_id = ?"]
        params = [room_text]
        status_text = str(status or "").strip()
        if status_text:
            clauses.append("status = ?")
            params.append(status_text)
        params.append(max_limit)
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"""
                SELECT *
                FROM wechat_group_style_cards
                WHERE {' AND '.join(clauses)}
                ORDER BY evidence_count DESC, updated_at DESC, style_id DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def update_status(self, room_id: str, style_id: str, status: str) -> Dict:
        room_text = str(room_id or "").strip()
        style_text = str(style_id or "").strip()
        if not room_text or not style_text:
            raise ValueError("room_id and style_id are required")
        with self._lock, closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    """
                    UPDATE wechat_group_style_cards
                    SET status = ?, updated_at = ?
                    WHERE room_id = ? AND style_id = ?
                    """,
                    (str(status or "candidate"), int(time.time()), room_text, style_text),
                )
        return self.get_style(room_text, style_text) or {}

    def _init_schema(self):
        with closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS wechat_group_style_cards (
                        style_id TEXT PRIMARY KEY,
                        room_id TEXT NOT NULL,
                        intent TEXT NOT NULL DEFAULT '',
                        tone TEXT NOT NULL DEFAULT '',
                        trigger_rule TEXT NOT NULL DEFAULT '',
                        avoid_rule TEXT NOT NULL DEFAULT '',
                        example TEXT NOT NULL DEFAULT '',
                        evidence_count INTEGER NOT NULL DEFAULT 0,
                        status TEXT NOT NULL DEFAULT 'candidate',
                        created_at INTEGER NOT NULL,
                        updated_at INTEGER NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_wechat_group_style_cards_room_status
                    ON wechat_group_style_cards(room_id, status, updated_at)
                    """
                )

    def _connect(self):
        return sqlite3.connect(self.db_path, timeout=10)


def _coerce_timestamp(value=None) -> int:
    try:
        return int(value)
    except Exception:
        return int(time.time())


def _build_style_signature(
    room_id: str,
    intent: str,
    tone: str,
    trigger_rule: str,
    avoid_rule: str,
) -> str:
    payload = "|".join(
        [
            str(room_id or "").strip(),
            str(intent or "").strip(),
            str(tone or "").strip(),
            str(trigger_rule or "").strip(),
            str(avoid_rule or "").strip(),
        ]
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:24]
