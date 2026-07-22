"""SQLite store for stable WeChat group identities."""

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


def _default_identity_store_path() -> str:
    return os.path.join(os.path.expanduser(_default_data_root()), "wechat_group", "wechat_group_identity.db")


class WechatGroupIdentityStore:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or _default_identity_store_path()
        self._lock = threading.Lock()
        parent = os.path.dirname(self.db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._init_schema()

    def upsert_account(
        self,
        stable_account_id: str,
        display_name: str = "",
        status: str = "legacy_imported",
        confidence: str = "legacy",
        sidecar_memory_path: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        confirmed_at: int = 0,
    ) -> Dict[str, Any]:
        account_id = _require_text("stable_account_id", stable_account_id)
        now = _now()
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            with conn:
                conn.execute(
                    """
                    INSERT INTO wechat_group_identity_accounts (
                        stable_account_id, display_name, status, confidence,
                        sidecar_memory_path, created_at, updated_at, confirmed_at, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(stable_account_id) DO UPDATE SET
                        display_name = excluded.display_name,
                        status = excluded.status,
                        confidence = excluded.confidence,
                        sidecar_memory_path = excluded.sidecar_memory_path,
                        updated_at = excluded.updated_at,
                        confirmed_at = CASE
                            WHEN excluded.confirmed_at > 0 THEN excluded.confirmed_at
                            ELSE wechat_group_identity_accounts.confirmed_at
                        END,
                        metadata = excluded.metadata
                    """,
                    (
                        account_id,
                        str(display_name or ""),
                        str(status or "legacy_imported"),
                        str(confidence or "legacy"),
                        str(sidecar_memory_path or ""),
                        now,
                        now,
                        int(confirmed_at or 0),
                        _json(metadata),
                    ),
                )
                row = conn.execute(
                    "SELECT * FROM wechat_group_identity_accounts WHERE stable_account_id = ?",
                    (account_id,),
                ).fetchone()
        return _dict(row)

    def upsert_room(
        self,
        stable_room_id: str,
        stable_account_id: str,
        canonical_name: str = "",
        status: str = "legacy_imported",
        confidence: str = "legacy",
        metadata: Optional[Dict[str, Any]] = None,
        confirmed_at: int = 0,
    ) -> Dict[str, Any]:
        room_id = _require_text("stable_room_id", stable_room_id)
        account_id = _require_text("stable_account_id", stable_account_id)
        now = _now()
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            with conn:
                conn.execute(
                    """
                    INSERT INTO wechat_group_identity_rooms (
                        stable_room_id, stable_account_id, canonical_name, status,
                        confidence, created_at, updated_at, confirmed_at, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(stable_room_id) DO UPDATE SET
                        stable_account_id = excluded.stable_account_id,
                        canonical_name = excluded.canonical_name,
                        status = excluded.status,
                        confidence = excluded.confidence,
                        updated_at = excluded.updated_at,
                        confirmed_at = CASE
                            WHEN excluded.confirmed_at > 0 THEN excluded.confirmed_at
                            ELSE wechat_group_identity_rooms.confirmed_at
                        END,
                        metadata = excluded.metadata
                    """,
                    (
                        room_id,
                        account_id,
                        str(canonical_name or ""),
                        str(status or "legacy_imported"),
                        str(confidence or "legacy"),
                        now,
                        now,
                        int(confirmed_at or 0),
                        _json(metadata),
                    ),
                )
                row = conn.execute(
                    "SELECT * FROM wechat_group_identity_rooms WHERE stable_room_id = ?",
                    (room_id,),
                ).fetchone()
        return _dict(row)

    def upsert_member(
        self,
        stable_member_id: str,
        stable_room_id: str,
        stable_account_id: str,
        display_name: str = "",
        status: str = "legacy_imported",
        confidence: str = "legacy",
        metadata: Optional[Dict[str, Any]] = None,
        confirmed_at: int = 0,
    ) -> Dict[str, Any]:
        member_id = _require_text("stable_member_id", stable_member_id)
        room_id = _require_text("stable_room_id", stable_room_id)
        account_id = _require_text("stable_account_id", stable_account_id)
        now = _now()
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            with conn:
                conn.execute(
                    """
                    INSERT INTO wechat_group_identity_members (
                        stable_member_id, stable_room_id, stable_account_id, display_name,
                        status, confidence, created_at, updated_at, confirmed_at, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(stable_member_id) DO UPDATE SET
                        stable_room_id = excluded.stable_room_id,
                        stable_account_id = excluded.stable_account_id,
                        display_name = excluded.display_name,
                        status = excluded.status,
                        confidence = excluded.confidence,
                        updated_at = excluded.updated_at,
                        confirmed_at = CASE
                            WHEN excluded.confirmed_at > 0 THEN excluded.confirmed_at
                            ELSE wechat_group_identity_members.confirmed_at
                        END,
                        metadata = excluded.metadata
                    """,
                    (
                        member_id,
                        room_id,
                        account_id,
                        str(display_name or ""),
                        str(status or "legacy_imported"),
                        str(confidence or "legacy"),
                        now,
                        now,
                        int(confirmed_at or 0),
                        _json(metadata),
                    ),
                )
                row = conn.execute(
                    "SELECT * FROM wechat_group_identity_members WHERE stable_member_id = ?",
                    (member_id,),
                ).fetchone()
        return _dict(row)

    def activate_account_alias(
        self,
        stable_account_id: str,
        runtime_self_id: str,
        self_name: str = "",
        sidecar_memory_path: str = "",
        actor: str = "",
        reason: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        account_id = _require_text("stable_account_id", stable_account_id)
        runtime_id = _require_text("runtime_self_id", runtime_self_id)
        now = _now()
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            with conn:
                old_runtime = _active_value(
                    conn,
                    "wechat_group_identity_account_aliases",
                    "runtime_self_id",
                    "stable_account_id = ?",
                    (account_id,),
                )
                conn.execute(
                    """
                    UPDATE wechat_group_identity_account_aliases
                    SET is_active = 0
                    WHERE stable_account_id = ?
                      AND is_active = 1
                      AND (runtime_self_id <> ? OR sidecar_memory_path <> ?)
                    """,
                    (account_id, runtime_id, str(sidecar_memory_path or "")),
                )
                existing = conn.execute(
                    """
                    SELECT id
                    FROM wechat_group_identity_account_aliases
                    WHERE stable_account_id = ? AND runtime_self_id = ? AND sidecar_memory_path = ?
                    """,
                    (account_id, runtime_id, str(sidecar_memory_path or "")),
                ).fetchone()
                if existing:
                    conn.execute(
                        """
                        UPDATE wechat_group_identity_account_aliases
                        SET self_name = ?, last_seen_at = ?, is_active = 1, metadata = ?
                        WHERE id = ?
                        """,
                        (str(self_name or ""), now, _json(metadata), existing[0]),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO wechat_group_identity_account_aliases (
                            stable_account_id, runtime_self_id, self_name, sidecar_memory_path,
                            first_seen_at, last_seen_at, is_active, metadata
                        ) VALUES (?, ?, ?, ?, ?, ?, 1, ?)
                        """,
                        (
                            account_id,
                            runtime_id,
                            str(self_name or ""),
                            str(sidecar_memory_path or ""),
                            now,
                            now,
                            _json(metadata),
                        ),
                    )
                self._insert_event(
                    conn,
                    entity_type="account",
                    stable_account_id=account_id,
                    stable_id=account_id,
                    old_runtime_id=old_runtime if old_runtime != runtime_id else "",
                    new_runtime_id=runtime_id,
                    action="activate_account_alias",
                    actor=actor,
                    reason=reason,
                )
                row = conn.execute(
                    """
                    SELECT *
                    FROM wechat_group_identity_account_aliases
                    WHERE stable_account_id = ? AND runtime_self_id = ? AND sidecar_memory_path = ?
                    """,
                    (account_id, runtime_id, str(sidecar_memory_path or "")),
                ).fetchone()
        return _dict(row)

    def activate_room_alias(
        self,
        stable_account_id: str,
        stable_room_id: str,
        runtime_room_id: str,
        room_name: str = "",
        self_runtime_id: str = "",
        source_kind: str = "manual",
        actor: str = "",
        reason: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        account_id = _require_text("stable_account_id", stable_account_id)
        room_id = _require_text("stable_room_id", stable_room_id)
        runtime_id = _require_text("runtime_room_id", runtime_room_id)
        now = _now()
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            with conn:
                old_runtime = _active_value(
                    conn,
                    "wechat_group_identity_room_aliases",
                    "runtime_room_id",
                    "stable_account_id = ? AND stable_room_id = ?",
                    (account_id, room_id),
                )
                conn.execute(
                    """
                    UPDATE wechat_group_identity_room_aliases
                    SET is_active = 0
                    WHERE stable_account_id = ?
                      AND stable_room_id = ?
                      AND is_active = 1
                      AND runtime_room_id <> ?
                    """,
                    (account_id, room_id, runtime_id),
                )
                existing = conn.execute(
                    """
                    SELECT id
                    FROM wechat_group_identity_room_aliases
                    WHERE stable_account_id = ? AND runtime_room_id = ?
                    """,
                    (account_id, runtime_id),
                ).fetchone()
                if existing:
                    conn.execute(
                        """
                        UPDATE wechat_group_identity_room_aliases
                        SET stable_room_id = ?, room_name = ?, self_runtime_id = ?,
                            source_kind = ?, last_seen_at = ?, is_active = 1, metadata = ?
                        WHERE id = ?
                        """,
                        (
                            room_id,
                            str(room_name or ""),
                            str(self_runtime_id or ""),
                            str(source_kind or "manual"),
                            now,
                            _json(metadata),
                            existing[0],
                        ),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO wechat_group_identity_room_aliases (
                            stable_account_id, stable_room_id, runtime_room_id, room_name,
                            self_runtime_id, source_kind, first_seen_at, last_seen_at, is_active, metadata
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                        """,
                        (
                            account_id,
                            room_id,
                            runtime_id,
                            str(room_name or ""),
                            str(self_runtime_id or ""),
                            str(source_kind or "manual"),
                            now,
                            now,
                            _json(metadata),
                        ),
                    )
                self._insert_event(
                    conn,
                    entity_type="room",
                    stable_account_id=account_id,
                    stable_id=room_id,
                    old_runtime_id=old_runtime if old_runtime != runtime_id else "",
                    new_runtime_id=runtime_id,
                    action="activate_room_alias",
                    actor=actor,
                    reason=reason,
                )
                row = conn.execute(
                    """
                    SELECT *
                    FROM wechat_group_identity_room_aliases
                    WHERE stable_account_id = ? AND runtime_room_id = ?
                    """,
                    (account_id, runtime_id),
                ).fetchone()
        return _dict(row)

    def record_room_alias_candidate(
        self,
        stable_account_id: str,
        stable_room_id: str,
        runtime_room_id: str,
        room_name: str = "",
        self_runtime_id: str = "",
        source_kind: str = "suspected",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        account_id = _require_text("stable_account_id", stable_account_id)
        room_id = _require_text("stable_room_id", stable_room_id)
        runtime_id = _require_text("runtime_room_id", runtime_room_id)
        now = _now()
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            with conn:
                existing = conn.execute(
                    """
                    SELECT id
                    FROM wechat_group_identity_room_aliases
                    WHERE stable_account_id = ? AND runtime_room_id = ?
                    """,
                    (account_id, runtime_id),
                ).fetchone()
                if existing:
                    conn.execute(
                        """
                        UPDATE wechat_group_identity_room_aliases
                        SET stable_room_id = ?, room_name = ?, self_runtime_id = ?,
                            source_kind = ?, last_seen_at = ?, is_active = 0, metadata = ?
                        WHERE id = ?
                        """,
                        (
                            room_id,
                            str(room_name or ""),
                            str(self_runtime_id or ""),
                            str(source_kind or "suspected"),
                            now,
                            _json(metadata),
                            existing[0],
                        ),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO wechat_group_identity_room_aliases (
                            stable_account_id, stable_room_id, runtime_room_id, room_name,
                            self_runtime_id, source_kind, first_seen_at, last_seen_at, is_active, metadata
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
                        """,
                        (
                            account_id,
                            room_id,
                            runtime_id,
                            str(room_name or ""),
                            str(self_runtime_id or ""),
                            str(source_kind or "suspected"),
                            now,
                            now,
                            _json(metadata),
                        ),
                    )
                row = conn.execute(
                    """
                    SELECT *
                    FROM wechat_group_identity_room_aliases
                    WHERE stable_account_id = ? AND runtime_room_id = ?
                    """,
                    (account_id, runtime_id),
                ).fetchone()
        return _dict(row)

    def activate_member_alias(
        self,
        stable_account_id: str,
        stable_room_id: str,
        stable_member_id: str,
        runtime_sender_id: str,
        runtime_room_id: str = "",
        display_name: str = "",
        room_alias: str = "",
        source_kind: str = "manual",
        actor: str = "",
        reason: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        account_id = _require_text("stable_account_id", stable_account_id)
        room_id = _require_text("stable_room_id", stable_room_id)
        member_id = _require_text("stable_member_id", stable_member_id)
        runtime_id = _require_text("runtime_sender_id", runtime_sender_id)
        now = _now()
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            with conn:
                old_runtime = _active_value(
                    conn,
                    "wechat_group_identity_member_aliases",
                    "runtime_sender_id",
                    "stable_account_id = ? AND stable_room_id = ? AND stable_member_id = ?",
                    (account_id, room_id, member_id),
                )
                conn.execute(
                    """
                    UPDATE wechat_group_identity_member_aliases
                    SET is_active = 0
                    WHERE stable_account_id = ?
                      AND stable_room_id = ?
                      AND stable_member_id = ?
                      AND is_active = 1
                      AND runtime_sender_id <> ?
                    """,
                    (account_id, room_id, member_id, runtime_id),
                )
                existing = conn.execute(
                    """
                    SELECT id
                    FROM wechat_group_identity_member_aliases
                    WHERE stable_account_id = ? AND stable_room_id = ? AND runtime_sender_id = ?
                    """,
                    (account_id, room_id, runtime_id),
                ).fetchone()
                if existing:
                    conn.execute(
                        """
                        UPDATE wechat_group_identity_member_aliases
                        SET stable_member_id = ?, runtime_room_id = ?, display_name = ?,
                            room_alias = ?, source_kind = ?, last_seen_at = ?, is_active = 1,
                            metadata = ?
                        WHERE id = ?
                        """,
                        (
                            member_id,
                            str(runtime_room_id or ""),
                            str(display_name or ""),
                            str(room_alias or ""),
                            str(source_kind or "manual"),
                            now,
                            _json(metadata),
                            existing[0],
                        ),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO wechat_group_identity_member_aliases (
                            stable_account_id, stable_room_id, stable_member_id, runtime_sender_id,
                            runtime_room_id, display_name, room_alias, source_kind,
                            first_seen_at, last_seen_at, is_active, metadata
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                        """,
                        (
                            account_id,
                            room_id,
                            member_id,
                            runtime_id,
                            str(runtime_room_id or ""),
                            str(display_name or ""),
                            str(room_alias or ""),
                            str(source_kind or "manual"),
                            now,
                            now,
                            _json(metadata),
                        ),
                    )
                self._insert_event(
                    conn,
                    entity_type="member",
                    stable_account_id=account_id,
                    stable_id=member_id,
                    old_runtime_id=old_runtime if old_runtime != runtime_id else "",
                    new_runtime_id=runtime_id,
                    action="activate_member_alias",
                    actor=actor,
                    reason=reason,
                )
                row = conn.execute(
                    """
                    SELECT *
                    FROM wechat_group_identity_member_aliases
                    WHERE stable_account_id = ? AND stable_room_id = ? AND runtime_sender_id = ?
                    """,
                    (account_id, room_id, runtime_id),
                ).fetchone()
        return _dict(row)

    def record_member_alias_candidate(
        self,
        stable_account_id: str,
        stable_room_id: str,
        stable_member_id: str,
        runtime_sender_id: str,
        runtime_room_id: str = "",
        display_name: str = "",
        room_alias: str = "",
        source_kind: str = "suspected",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        account_id = _require_text("stable_account_id", stable_account_id)
        room_id = _require_text("stable_room_id", stable_room_id)
        member_id = _require_text("stable_member_id", stable_member_id)
        runtime_id = _require_text("runtime_sender_id", runtime_sender_id)
        now = _now()
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            with conn:
                existing = conn.execute(
                    """
                    SELECT id
                    FROM wechat_group_identity_member_aliases
                    WHERE stable_account_id = ? AND stable_room_id = ? AND runtime_sender_id = ?
                    """,
                    (account_id, room_id, runtime_id),
                ).fetchone()
                if existing:
                    conn.execute(
                        """
                        UPDATE wechat_group_identity_member_aliases
                        SET stable_member_id = ?, runtime_room_id = ?, display_name = ?,
                            room_alias = ?, source_kind = ?, last_seen_at = ?, is_active = 0,
                            metadata = ?
                        WHERE id = ?
                        """,
                        (
                            member_id,
                            str(runtime_room_id or ""),
                            str(display_name or ""),
                            str(room_alias or ""),
                            str(source_kind or "suspected"),
                            now,
                            _json(metadata),
                            existing[0],
                        ),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO wechat_group_identity_member_aliases (
                            stable_account_id, stable_room_id, stable_member_id, runtime_sender_id,
                            runtime_room_id, display_name, room_alias, source_kind,
                            first_seen_at, last_seen_at, is_active, metadata
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
                        """,
                        (
                            account_id,
                            room_id,
                            member_id,
                            runtime_id,
                            str(runtime_room_id or ""),
                            str(display_name or ""),
                            str(room_alias or ""),
                            str(source_kind or "suspected"),
                            now,
                            now,
                            _json(metadata),
                        ),
                    )
                row = conn.execute(
                    """
                    SELECT *
                    FROM wechat_group_identity_member_aliases
                    WHERE stable_account_id = ? AND stable_room_id = ? AND runtime_sender_id = ?
                    """,
                    (account_id, room_id, runtime_id),
                ).fetchone()
        return _dict(row)

    def get_account(self, stable_account_id: str) -> Dict[str, Any]:
        return self._get_one(
            "SELECT * FROM wechat_group_identity_accounts WHERE stable_account_id = ?",
            (str(stable_account_id or ""),),
        )

    def get_room(self, stable_room_id: str) -> Dict[str, Any]:
        return self._get_one(
            "SELECT * FROM wechat_group_identity_rooms WHERE stable_room_id = ?",
            (str(stable_room_id or ""),),
        )

    def get_member(self, stable_member_id: str) -> Dict[str, Any]:
        return self._get_one(
            "SELECT * FROM wechat_group_identity_members WHERE stable_member_id = ?",
            (str(stable_member_id or ""),),
        )

    def upsert_member_redirect(
        self,
        stable_room_id: str,
        old_stable_member_id: str,
        canonical_stable_member_id: str,
        actor: str = "",
        reason: str = "",
    ) -> Dict[str, Any]:
        room_id = _require_text("stable_room_id", stable_room_id)
        old_member_id = _require_text("old_stable_member_id", old_stable_member_id)
        canonical_member_id = _require_text("canonical_stable_member_id", canonical_stable_member_id)
        if old_member_id == canonical_member_id:
            raise ValueError("member redirect must target a different stable member")
        old_member = self.get_member(old_member_id)
        canonical_member = self.get_member(canonical_member_id)
        if not old_member or not canonical_member:
            raise ValueError("member redirect requires existing members")
        if (
            str(old_member.get("stable_room_id") or "") != room_id
            or str(canonical_member.get("stable_room_id") or "") != room_id
        ):
            raise ValueError("member redirect must stay within stable room")
        now = _now()
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            with conn:
                conn.execute(
                    """
                    INSERT INTO wechat_group_identity_member_redirects (
                        stable_room_id, old_stable_member_id, canonical_stable_member_id,
                        actor, reason, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(stable_room_id, old_stable_member_id) DO UPDATE SET
                        canonical_stable_member_id = excluded.canonical_stable_member_id,
                        actor = excluded.actor,
                        reason = excluded.reason,
                        updated_at = excluded.updated_at
                    """,
                    (room_id, old_member_id, canonical_member_id, str(actor or ""), str(reason or ""), now, now),
                )
                row = conn.execute(
                    """
                    SELECT * FROM wechat_group_identity_member_redirects
                    WHERE stable_room_id = ? AND old_stable_member_id = ? LIMIT 1
                    """,
                    (room_id, old_member_id),
                ).fetchone()
        return _dict(row)

    def get_member_redirect(self, stable_room_id: str, old_stable_member_id: str) -> Dict[str, Any]:
        return self._get_one(
            """
            SELECT * FROM wechat_group_identity_member_redirects
            WHERE stable_room_id = ? AND old_stable_member_id = ? LIMIT 1
            """,
            (str(stable_room_id or ""), str(old_stable_member_id or "")),
        )

    def find_account_alias(self, runtime_self_id: str, sidecar_memory_path: str = "") -> Dict[str, Any]:
        return self._get_one(
            """
            SELECT *
            FROM wechat_group_identity_account_aliases
            WHERE runtime_self_id = ? AND sidecar_memory_path = ?
            ORDER BY is_active DESC, last_seen_at DESC, id DESC
            LIMIT 1
            """,
            (str(runtime_self_id or ""), str(sidecar_memory_path or "")),
        )

    def list_account_candidates_by_profile(
        self,
        sidecar_memory_path: str,
        self_name: str = "",
    ) -> List[Dict[str, Any]]:
        memory_path = str(sidecar_memory_path or "").strip()
        display_name = str(self_name or "").strip()
        if not memory_path:
            return []
        rows = self._get_many(
            """
            SELECT DISTINCT a.*
            FROM wechat_group_identity_accounts a
            JOIN wechat_group_identity_account_aliases x
              ON x.stable_account_id = a.stable_account_id
            WHERE (x.sidecar_memory_path = ? OR x.sidecar_memory_path = '')
              AND (? = '' OR a.display_name = ? OR x.self_name = ?)
            ORDER BY a.confirmed_at DESC, a.updated_at DESC
            """,
            (memory_path, display_name, display_name, display_name),
        )
        return rows

    def list_account_candidates_by_wechat_id(self, wechat_id: str) -> List[Dict[str, Any]]:
        identity_key = _normalize_identity_key(wechat_id)
        if not identity_key:
            return []
        accounts = self._get_many(
            "SELECT * FROM wechat_group_identity_accounts ORDER BY confirmed_at DESC, updated_at DESC",
            (),
        )
        aliases = self._get_many(
            "SELECT stable_account_id, metadata FROM wechat_group_identity_account_aliases ORDER BY last_seen_at DESC, id DESC",
            (),
        )
        matched_ids = {
            str(row.get("stable_account_id") or "")
            for row in aliases
            if identity_key in _identity_keys(row.get("metadata"))
        }
        for account in accounts:
            if identity_key in _identity_keys(account.get("metadata")):
                matched_ids.add(str(account.get("stable_account_id") or ""))
        return [row for row in accounts if str(row.get("stable_account_id") or "") in matched_ids]

    def find_room_alias(self, stable_account_id: str, runtime_room_id: str) -> Dict[str, Any]:
        return self._get_one(
            """
            SELECT *
            FROM wechat_group_identity_room_aliases
            WHERE stable_account_id = ? AND runtime_room_id = ?
            ORDER BY is_active DESC, last_seen_at DESC, id DESC
            LIMIT 1
            """,
            (str(stable_account_id or ""), str(runtime_room_id or "")),
        )

    def find_room_alias_by_runtime(self, runtime_room_id: str) -> Dict[str, Any]:
        return self._get_one(
            """
            SELECT *
            FROM wechat_group_identity_room_aliases
            WHERE runtime_room_id = ?
            ORDER BY is_active DESC, last_seen_at DESC, id DESC
            LIMIT 1
            """,
            (str(runtime_room_id or ""),),
        )

    def list_room_aliases_by_runtime(self, runtime_room_id: str) -> List[Dict[str, Any]]:
        return self._get_many(
            """
            SELECT *
            FROM wechat_group_identity_room_aliases
            WHERE runtime_room_id = ?
            ORDER BY is_active DESC, last_seen_at DESC, id DESC
            """,
            (str(runtime_room_id or ""),),
        )

    def find_member_alias(self, stable_account_id: str, stable_room_id: str, runtime_sender_id: str) -> Dict[str, Any]:
        return self._get_one(
            """
            SELECT *
            FROM wechat_group_identity_member_aliases
            WHERE stable_account_id = ? AND stable_room_id = ? AND runtime_sender_id = ?
            ORDER BY is_active DESC, last_seen_at DESC, id DESC
            LIMIT 1
            """,
            (str(stable_account_id or ""), str(stable_room_id or ""), str(runtime_sender_id or "")),
        )

    def find_member_alias_by_runtime(self, runtime_room_id: str, runtime_sender_id: str) -> Dict[str, Any]:
        return self._get_one(
            """
            SELECT *
            FROM wechat_group_identity_member_aliases
            WHERE runtime_room_id = ? AND runtime_sender_id = ?
            ORDER BY is_active DESC, last_seen_at DESC, id DESC
            LIMIT 1
            """,
            (str(runtime_room_id or ""), str(runtime_sender_id or "")),
        )

    def list_member_aliases_by_runtime(self, runtime_room_id: str, runtime_sender_id: str) -> List[Dict[str, Any]]:
        return self._get_many(
            """
            SELECT *
            FROM wechat_group_identity_member_aliases
            WHERE runtime_room_id = ? AND runtime_sender_id = ?
            ORDER BY is_active DESC, last_seen_at DESC, id DESC
            """,
            (str(runtime_room_id or ""), str(runtime_sender_id or "")),
        )

    def find_room_candidate_by_name(self, stable_account_id: str, room_name: str) -> Dict[str, Any]:
        rows = self.list_room_candidates_by_name(stable_account_id, room_name)
        return rows[0] if rows else {}

    def list_room_candidates_by_name(self, stable_account_id: str, room_name: str) -> List[Dict[str, Any]]:
        return self._get_many(
            """
            SELECT *
            FROM wechat_group_identity_rooms
            WHERE stable_account_id = ? AND canonical_name = ?
            ORDER BY confirmed_at DESC, updated_at DESC
            """,
            (str(stable_account_id or ""), str(room_name or "")),
        )

    def list_member_candidates_by_wechat_id(
        self,
        stable_account_id: str,
        stable_room_id: str,
        wechat_id: str,
    ) -> List[Dict[str, Any]]:
        identity_key = _normalize_identity_key(wechat_id)
        if not identity_key:
            return []
        account_id = str(stable_account_id or "")
        room_id = str(stable_room_id or "")
        members = self._get_many(
            """
            SELECT *
            FROM wechat_group_identity_members
            WHERE stable_account_id = ? AND stable_room_id = ?
            ORDER BY confirmed_at DESC, updated_at DESC
            """,
            (account_id, room_id),
        )
        aliases = self._get_many(
            """
            SELECT stable_member_id, metadata
            FROM wechat_group_identity_member_aliases
            WHERE stable_account_id = ? AND stable_room_id = ?
            ORDER BY last_seen_at DESC, id DESC
            """,
            (account_id, room_id),
        )
        matched_ids = {
            str(row.get("stable_member_id") or "")
            for row in aliases
            if identity_key in _identity_keys(row.get("metadata"))
        }
        for member in members:
            if identity_key in _identity_keys(member.get("metadata")):
                matched_ids.add(str(member.get("stable_member_id") or ""))
        return [row for row in members if str(row.get("stable_member_id") or "") in matched_ids]

    def find_member_candidate_by_name(self, stable_room_id: str, display_name: str = "", room_alias: str = "") -> Dict[str, Any]:
        names = [str(display_name or "").strip(), str(room_alias or "").strip()]
        names = [name for name in names if name]
        if not names:
            return {}
        placeholders = ",".join("?" for _ in names)
        return self._get_one(
            f"""
            SELECT m.*
            FROM wechat_group_identity_members m
            LEFT JOIN wechat_group_identity_member_aliases a
              ON a.stable_member_id = m.stable_member_id
             AND a.stable_room_id = m.stable_room_id
            WHERE m.stable_room_id = ?
              AND (m.display_name IN ({placeholders}) OR a.display_name IN ({placeholders}) OR a.room_alias IN ({placeholders}))
            ORDER BY m.confirmed_at DESC, m.updated_at DESC
            LIMIT 1
            """,
            (str(stable_room_id or ""), *names, *names, *names),
        )

    def get_active_runtime_room_id(self, stable_account_id: str, stable_room_id: str) -> str:
        return self._get_single_active_value(
            "wechat_group_identity_room_aliases",
            "runtime_room_id",
            "stable_account_id = ? AND stable_room_id = ?",
            (str(stable_account_id or ""), str(stable_room_id or "")),
        )

    def get_active_runtime_sender_id(self, stable_account_id: str, stable_room_id: str, stable_member_id: str) -> str:
        return self._get_single_active_value(
            "wechat_group_identity_member_aliases",
            "runtime_sender_id",
            "stable_account_id = ? AND stable_room_id = ? AND stable_member_id = ?",
            (str(stable_account_id or ""), str(stable_room_id or ""), str(stable_member_id or "")),
        )

    def list_room_aliases(
        self,
        stable_account_id: str,
        stable_room_id: str,
        include_inactive: bool = False,
    ) -> List[Dict[str, Any]]:
        extra = "" if include_inactive else "AND is_active = 1"
        return self._get_many(
            f"""
            SELECT *
            FROM wechat_group_identity_room_aliases
            WHERE stable_account_id = ? AND stable_room_id = ? {extra}
            ORDER BY last_seen_at ASC, id ASC
            """,
            (str(stable_account_id or ""), str(stable_room_id or "")),
        )

    def list_confirmed_room_aliases(
        self,
        stable_account_id: str,
        stable_room_id: str,
    ) -> List[Dict[str, Any]]:
        return self._get_many(
            """
            SELECT a.*
            FROM wechat_group_identity_room_aliases a
            WHERE a.stable_account_id = ?
              AND a.stable_room_id = ?
              AND (
                    a.is_active = 1
                    OR EXISTS (
                        SELECT 1
                        FROM wechat_group_identity_binding_events e
                        WHERE e.entity_type = 'room'
                          AND e.stable_account_id = a.stable_account_id
                          AND e.stable_id = a.stable_room_id
                          AND e.new_runtime_id = a.runtime_room_id
                          AND e.action IN ('activate_room_alias', 'confirm_historical_room_alias')
                    )
              )
            ORDER BY a.first_seen_at ASC, a.id ASC
            """,
            (str(stable_account_id or ""), str(stable_room_id or "")),
        )

    def confirm_historical_room_alias(
        self,
        stable_account_id: str,
        stable_room_id: str,
        runtime_room_id: str,
        room_name: str = "",
        actor: str = "",
        reason: str = "",
    ) -> Dict[str, Any]:
        account_id = _require_text("stable_account_id", stable_account_id)
        room_id = _require_text("stable_room_id", stable_room_id)
        runtime_id = _require_text("runtime_room_id", runtime_room_id)
        now = _now()
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            with conn:
                existing = conn.execute(
                    """
                    SELECT *
                    FROM wechat_group_identity_room_aliases
                    WHERE stable_account_id = ? AND runtime_room_id = ?
                    LIMIT 1
                    """,
                    (account_id, runtime_id),
                ).fetchone()
                if existing and str(existing["stable_room_id"] or "") != room_id:
                    raise ValueError("runtime room alias belongs to another stable room")
                if existing:
                    conn.execute(
                        """
                        UPDATE wechat_group_identity_room_aliases
                        SET room_name = CASE WHEN ? != '' THEN ? ELSE room_name END,
                            source_kind = CASE WHEN is_active = 1 THEN source_kind ELSE 'manual_history' END,
                            last_seen_at = ?
                        WHERE id = ?
                        """,
                        (str(room_name or ""), str(room_name or ""), now, int(existing["id"])),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO wechat_group_identity_room_aliases (
                            stable_account_id, stable_room_id, runtime_room_id, room_name,
                            self_runtime_id, source_kind, first_seen_at, last_seen_at,
                            is_active, metadata
                        ) VALUES (?, ?, ?, ?, '', 'manual_history', ?, ?, 0, '{}')
                        """,
                        (account_id, room_id, runtime_id, str(room_name or ""), now, now),
                    )
                self._insert_event(
                    conn,
                    entity_type="room",
                    stable_account_id=account_id,
                    stable_id=room_id,
                    old_runtime_id="",
                    new_runtime_id=runtime_id,
                    action="confirm_historical_room_alias",
                    actor=actor,
                    reason=reason,
                )
                row = conn.execute(
                    """
                    SELECT *
                    FROM wechat_group_identity_room_aliases
                    WHERE stable_account_id = ? AND runtime_room_id = ?
                    LIMIT 1
                    """,
                    (account_id, runtime_id),
                ).fetchone()
        return _dict(row)

    def list_member_aliases(
        self,
        stable_account_id: str,
        stable_room_id: str,
        stable_member_id: str,
        include_inactive: bool = False,
    ) -> List[Dict[str, Any]]:
        extra = "" if include_inactive else "AND is_active = 1"
        return self._get_many(
            f"""
            SELECT *
            FROM wechat_group_identity_member_aliases
            WHERE stable_account_id = ? AND stable_room_id = ? AND stable_member_id = ? {extra}
            ORDER BY last_seen_at ASC, id ASC
            """,
            (str(stable_account_id or ""), str(stable_room_id or ""), str(stable_member_id or "")),
        )

    def list_binding_events(self, entity_type: str = "") -> List[Dict[str, Any]]:
        if entity_type:
            return self._get_many(
                """
                SELECT *
                FROM wechat_group_identity_binding_events
                WHERE entity_type = ?
                ORDER BY created_at ASC, rowid ASC
                """,
                (str(entity_type),),
            )
        return self._get_many(
            """
            SELECT *
            FROM wechat_group_identity_binding_events
            ORDER BY created_at ASC, rowid ASC
            """,
            (),
        )

    def list_room_binding_candidates(self, stable_room_id: str = "") -> List[Dict[str, Any]]:
        clauses = ["r.status <> 'confirmed'"]
        params: List[Any] = []
        if str(stable_room_id or "").strip():
            clauses.append("r.stable_room_id = ?")
            params.append(str(stable_room_id or "").strip())
        return self._get_many(
            f"""
            SELECT
                r.stable_account_id,
                r.stable_room_id,
                r.canonical_name,
                r.status,
                r.confidence,
                a.runtime_room_id,
                a.room_name,
                a.source_kind,
                a.is_active,
                a.last_seen_at
            FROM wechat_group_identity_rooms r
            LEFT JOIN wechat_group_identity_room_aliases a
              ON a.stable_account_id = r.stable_account_id
             AND a.stable_room_id = r.stable_room_id
            WHERE {' AND '.join(clauses)}
            ORDER BY a.last_seen_at DESC, r.updated_at DESC
            """,
            tuple(params),
        )

    def list_member_binding_candidates(self, stable_room_id: str = "") -> List[Dict[str, Any]]:
        clauses = ["m.status <> 'confirmed'"]
        params: List[Any] = []
        if str(stable_room_id or "").strip():
            clauses.append("m.stable_room_id = ?")
            params.append(str(stable_room_id or "").strip())
        return self._get_many(
            f"""
            SELECT
                m.stable_account_id,
                m.stable_room_id,
                m.stable_member_id,
                m.display_name,
                m.status,
                m.confidence,
                a.runtime_sender_id,
                a.runtime_room_id,
                a.room_alias,
                a.source_kind,
                a.is_active,
                a.last_seen_at
            FROM wechat_group_identity_members m
            LEFT JOIN wechat_group_identity_member_aliases a
              ON a.stable_account_id = m.stable_account_id
             AND a.stable_room_id = m.stable_room_id
             AND a.stable_member_id = m.stable_member_id
            WHERE {' AND '.join(clauses)}
            ORDER BY a.last_seen_at DESC, m.updated_at DESC
            """,
            tuple(params),
        )

    def _get_one(self, sql: str, params: tuple) -> Dict[str, Any]:
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(sql, params).fetchone()
        return _dict(row)

    def _get_many(self, sql: str, params: tuple) -> List[Dict[str, Any]]:
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()
        return [_dict(row) for row in rows]

    def _get_single_active_value(self, table: str, column: str, where_sql: str, params: tuple) -> str:
        with self._lock, closing(self._connect()) as conn:
            rows = conn.execute(
                f"SELECT {column} FROM {table} WHERE {where_sql} AND is_active = 1",
                params,
            ).fetchall()
        if not rows:
            return ""
        if len(rows) > 1:
            raise RuntimeError(f"multiple active aliases found in {table}")
        return str(rows[0][0] or "")

    def _insert_event(
        self,
        conn: sqlite3.Connection,
        entity_type: str,
        stable_account_id: str,
        stable_id: str,
        old_runtime_id: str,
        new_runtime_id: str,
        action: str,
        actor: str = "",
        reason: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        conn.execute(
            """
            INSERT INTO wechat_group_identity_binding_events (
                event_id, entity_type, stable_account_id, stable_id, old_runtime_id,
                new_runtime_id, action, actor, reason, created_at, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                uuid4().hex,
                str(entity_type or ""),
                str(stable_account_id or ""),
                str(stable_id or ""),
                str(old_runtime_id or ""),
                str(new_runtime_id or ""),
                str(action or ""),
                str(actor or ""),
                str(reason or ""),
                _now(),
                _json(metadata),
            ),
        )

    def _init_schema(self) -> None:
        with closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS wechat_group_identity_accounts (
                        stable_account_id TEXT PRIMARY KEY,
                        display_name TEXT NOT NULL DEFAULT '',
                        status TEXT NOT NULL,
                        confidence TEXT NOT NULL,
                        sidecar_memory_path TEXT NOT NULL DEFAULT '',
                        created_at INTEGER NOT NULL,
                        updated_at INTEGER NOT NULL,
                        confirmed_at INTEGER NOT NULL DEFAULT 0,
                        metadata TEXT NOT NULL DEFAULT '{}'
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS wechat_group_identity_account_aliases (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        stable_account_id TEXT NOT NULL,
                        runtime_self_id TEXT NOT NULL DEFAULT '',
                        self_name TEXT NOT NULL DEFAULT '',
                        sidecar_memory_path TEXT NOT NULL DEFAULT '',
                        first_seen_at INTEGER NOT NULL,
                        last_seen_at INTEGER NOT NULL,
                        is_active INTEGER NOT NULL DEFAULT 1,
                        metadata TEXT NOT NULL DEFAULT '{}',
                        UNIQUE(stable_account_id, runtime_self_id, sidecar_memory_path)
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS wechat_group_identity_rooms (
                        stable_room_id TEXT PRIMARY KEY,
                        stable_account_id TEXT NOT NULL DEFAULT '',
                        canonical_name TEXT NOT NULL,
                        status TEXT NOT NULL,
                        confidence TEXT NOT NULL,
                        created_at INTEGER NOT NULL,
                        updated_at INTEGER NOT NULL,
                        confirmed_at INTEGER NOT NULL DEFAULT 0,
                        metadata TEXT NOT NULL DEFAULT '{}'
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS wechat_group_identity_room_aliases (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        stable_account_id TEXT NOT NULL DEFAULT '',
                        stable_room_id TEXT NOT NULL,
                        runtime_room_id TEXT NOT NULL,
                        room_name TEXT NOT NULL DEFAULT '',
                        self_runtime_id TEXT NOT NULL DEFAULT '',
                        source_kind TEXT NOT NULL,
                        first_seen_at INTEGER NOT NULL,
                        last_seen_at INTEGER NOT NULL,
                        is_active INTEGER NOT NULL DEFAULT 1,
                        metadata TEXT NOT NULL DEFAULT '{}',
                        UNIQUE(stable_account_id, runtime_room_id)
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS wechat_group_identity_members (
                        stable_member_id TEXT PRIMARY KEY,
                        stable_room_id TEXT NOT NULL,
                        stable_account_id TEXT NOT NULL DEFAULT '',
                        display_name TEXT NOT NULL DEFAULT '',
                        status TEXT NOT NULL,
                        confidence TEXT NOT NULL,
                        created_at INTEGER NOT NULL,
                        updated_at INTEGER NOT NULL,
                        confirmed_at INTEGER NOT NULL DEFAULT 0,
                        metadata TEXT NOT NULL DEFAULT '{}',
                        UNIQUE(stable_room_id, stable_member_id)
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS wechat_group_identity_member_aliases (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        stable_account_id TEXT NOT NULL DEFAULT '',
                        stable_room_id TEXT NOT NULL,
                        stable_member_id TEXT NOT NULL,
                        runtime_sender_id TEXT NOT NULL,
                        runtime_room_id TEXT NOT NULL DEFAULT '',
                        display_name TEXT NOT NULL DEFAULT '',
                        room_alias TEXT NOT NULL DEFAULT '',
                        source_kind TEXT NOT NULL,
                        first_seen_at INTEGER NOT NULL,
                        last_seen_at INTEGER NOT NULL,
                        is_active INTEGER NOT NULL DEFAULT 1,
                        metadata TEXT NOT NULL DEFAULT '{}',
                        UNIQUE(stable_account_id, stable_room_id, runtime_sender_id)
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS wechat_group_identity_binding_events (
                        event_id TEXT PRIMARY KEY,
                        entity_type TEXT NOT NULL,
                        stable_account_id TEXT NOT NULL DEFAULT '',
                        stable_id TEXT NOT NULL,
                        old_runtime_id TEXT NOT NULL DEFAULT '',
                        new_runtime_id TEXT NOT NULL DEFAULT '',
                        action TEXT NOT NULL,
                        actor TEXT NOT NULL DEFAULT '',
                        reason TEXT NOT NULL DEFAULT '',
                        created_at INTEGER NOT NULL,
                        metadata TEXT NOT NULL DEFAULT '{}'
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS wechat_group_identity_member_redirects (
                        stable_room_id TEXT NOT NULL,
                        old_stable_member_id TEXT NOT NULL,
                        canonical_stable_member_id TEXT NOT NULL,
                        actor TEXT NOT NULL DEFAULT '',
                        reason TEXT NOT NULL DEFAULT '',
                        created_at INTEGER NOT NULL,
                        updated_at INTEGER NOT NULL,
                        PRIMARY KEY(stable_room_id, old_stable_member_id)
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_wechat_group_identity_member_redirects_target
                    ON wechat_group_identity_member_redirects(stable_room_id, canonical_stable_member_id)
                    """
                )
                conn.execute(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_wechat_group_identity_account_aliases_one_active
                    ON wechat_group_identity_account_aliases(stable_account_id)
                    WHERE is_active = 1
                    """
                )
                conn.execute(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_wechat_group_identity_room_aliases_one_active
                    ON wechat_group_identity_room_aliases(stable_account_id, stable_room_id)
                    WHERE is_active = 1
                    """
                )
                conn.execute(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_wechat_group_identity_member_aliases_one_active
                    ON wechat_group_identity_member_aliases(stable_account_id, stable_room_id, stable_member_id)
                    WHERE is_active = 1
                    """
                )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path, timeout=10)


def _active_value(conn: sqlite3.Connection, table: str, column: str, where_sql: str, params: tuple) -> str:
    row = conn.execute(
        f"SELECT {column} FROM {table} WHERE {where_sql} AND is_active = 1 LIMIT 1",
        params,
    ).fetchone()
    return str(row[0] or "") if row else ""


def _require_text(name: str, value: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} is required")
    return text


def _json(value: Optional[Dict[str, Any]]) -> str:
    return json.dumps(value or {}, ensure_ascii=False)


def _metadata_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        loaded = json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _normalize_identity_key(value: Any) -> str:
    return str(value or "").strip().casefold()


def _identity_keys(metadata: Any) -> set[str]:
    payload = _metadata_dict(metadata)
    return {
        normalized
        for normalized in (
            _normalize_identity_key(payload.get("wechat_id")),
            _normalize_identity_key(payload.get("weixin")),
            _normalize_identity_key(payload.get("wxid")),
        )
        if normalized
    }


def _dict(row: Any) -> Dict[str, Any]:
    if not row:
        return {}
    item = dict(row)
    if "is_active" in item:
        item["is_active"] = int(item.get("is_active") or 0)
    return item


def _now() -> int:
    return int(time.time())
