"""SQLite store for WeChat group emotion state."""

from __future__ import annotations

import os
import sqlite3
import threading
from contextlib import closing
from typing import Dict, Optional


def _default_emotion_store_path() -> str:
    data_root = os.environ.get("LIGHTAGENT_DATA_DIR") or os.path.join(os.path.expanduser("~"), ".lightagent")
    return os.path.join(os.path.expanduser(data_root), "wechat_group", "wechat_group_emotion.db")


class WechatGroupEmotionStore:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or _default_emotion_store_path()
        self._lock = threading.Lock()
        parent = os.path.dirname(self.db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._init_schema()

    def get_state(self, room_id: str) -> Optional[Dict]:
        room_text = str(room_id or "").strip()
        if not room_text:
            return None
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT *
                FROM wechat_group_emotion_states
                WHERE room_id = ?
                LIMIT 1
                """,
                (room_text,),
            ).fetchone()
        return dict(row) if row else None

    def upsert_state(
        self,
        room_id: str,
        valence: float,
        energy: float,
        sociability: float,
        last_decay_at: int,
        last_reply_at: int,
        reply_count_1h: int,
        updated_at: int,
    ) -> Dict:
        room_text = str(room_id or "").strip()
        if not room_text:
            raise ValueError("room_id is required")
        with self._lock, closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO wechat_group_emotion_states (
                        room_id, valence, energy, sociability,
                        last_decay_at, last_reply_at, reply_count_1h, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(room_id) DO UPDATE SET
                        valence = excluded.valence,
                        energy = excluded.energy,
                        sociability = excluded.sociability,
                        last_decay_at = excluded.last_decay_at,
                        last_reply_at = excluded.last_reply_at,
                        reply_count_1h = excluded.reply_count_1h,
                        updated_at = excluded.updated_at
                    """,
                    (
                        room_text,
                        float(valence),
                        float(energy),
                        float(sociability),
                        int(last_decay_at or 0),
                        int(last_reply_at or 0),
                        int(reply_count_1h or 0),
                        int(updated_at or 0),
                    ),
                )
        return self.get_state(room_text) or {}

    def _init_schema(self) -> None:
        with closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS wechat_group_emotion_states (
                        room_id TEXT PRIMARY KEY,
                        valence REAL NOT NULL,
                        energy REAL NOT NULL,
                        sociability REAL NOT NULL,
                        last_decay_at INTEGER NOT NULL DEFAULT 0,
                        last_reply_at INTEGER NOT NULL DEFAULT 0,
                        reply_count_1h INTEGER NOT NULL DEFAULT 0,
                        updated_at INTEGER NOT NULL DEFAULT 0
                    )
                    """
                )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path, timeout=10)
