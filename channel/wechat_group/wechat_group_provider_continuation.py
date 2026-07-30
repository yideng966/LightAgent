"""Provider-side continuation state for confirmed WeChat group turns."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import time
from contextlib import closing
from dataclasses import dataclass
from typing import Any, Dict, Optional


CAPABILITY_NONE = "none"
CAPABILITY_IMMUTABLE_PARENT = "immutable_parent"


def _default_path() -> str:
    root = os.environ.get("LIGHTAGENT_DATA_DIR") or os.path.join(
        os.path.expanduser("~"), ".lightagent"
    )
    return os.path.join(
        os.path.expanduser(root),
        "wechat_group",
        "provider_continuations.db",
    )


def opaque_hash(value: str) -> str:
    text = str(value or "")
    return hashlib.sha256(text.encode("utf-8")).hexdigest() if text else ""


def endpoint_fingerprint(provider_key: str, api_base: str) -> str:
    endpoint = str(api_base or "__provider_default__").strip().rstrip("/").lower()
    return opaque_hash("{}\n{}".format(str(provider_key or "").strip(), endpoint))


def permission_fingerprint(context: Dict[str, Any]) -> str:
    from config import conf

    payload = {
        "identity_status": str(context.get("identity_status") or ""),
        "identity_confirmed": context.get("identity_confirmed") is True,
        "is_admin": context.get("is_admin") is True,
        "required_permissions": conf().get(
            "wechat_group_admin_required_permissions", {}
        ),
    }
    return opaque_hash(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )


@dataclass(frozen=True)
class ProviderContinuationCapability:
    mode: str = CAPABILITY_NONE
    provider_key: str = ""
    model: str = ""
    endpoint_fingerprint: str = ""
    anchor_type: str = ""

    @property
    def supported(self) -> bool:
        return self.mode == CAPABILITY_IMMUTABLE_PARENT and bool(self.anchor_type)

    def to_dict(self) -> Dict[str, str]:
        return {
            "mode": self.mode,
            "provider_key": self.provider_key,
            "model": self.model,
            "endpoint_fingerprint": self.endpoint_fingerprint,
            "anchor_type": self.anchor_type,
        }


@dataclass(frozen=True)
class ProviderContinuationScope:
    stable_account_scope: str
    stable_room_id: str
    stable_member_id: str
    owner_session_id: str
    thread_id: str
    provider_key: str
    model: str
    endpoint_fingerprint: str
    permission_fingerprint: str

    def valid(self) -> bool:
        return all(
            str(value or "").strip()
            for value in (
                self.stable_account_scope,
                self.stable_room_id,
                self.stable_member_id,
                self.owner_session_id,
                self.thread_id,
                self.provider_key,
                self.model,
                self.endpoint_fingerprint,
                self.permission_fingerprint,
            )
        )

    def values(self):
        return (
            self.stable_account_scope,
            self.stable_room_id,
            self.stable_member_id,
            self.owner_session_id,
            self.thread_id,
            self.provider_key,
            self.model,
            self.endpoint_fingerprint,
            self.permission_fingerprint,
        )


@dataclass(frozen=True)
class ProviderContinuationAnchor:
    row_id: int
    scope: ProviderContinuationScope
    anchor_type: str
    anchor_value: str
    parent_anchor_hash: str
    request_id: str
    status: str
    created_at: int
    expires_at: int

    @property
    def hash_prefix(self) -> str:
        return opaque_hash(self.anchor_value)[:12]


def normalize_capability(
    raw,
    provider_key: str,
    model: str,
    fingerprint: str,
) -> ProviderContinuationCapability:
    if isinstance(raw, ProviderContinuationCapability):
        mode = raw.mode
        anchor_type = raw.anchor_type
    elif isinstance(raw, dict):
        mode = str(raw.get("mode") or CAPABILITY_NONE).strip().lower()
        anchor_type = str(raw.get("anchor_type") or "").strip()
    else:
        mode = CAPABILITY_NONE
        anchor_type = ""
    if mode != CAPABILITY_IMMUTABLE_PARENT or not anchor_type:
        mode = CAPABILITY_NONE
        anchor_type = ""
    return ProviderContinuationCapability(
        mode=mode,
        provider_key=str(provider_key or "").strip(),
        model=str(model or "").strip(),
        endpoint_fingerprint=str(fingerprint or "").strip(),
        anchor_type=anchor_type,
    )


class ProviderContinuationStore:
    _SCOPE_COLUMNS = (
        "stable_account_scope", "stable_room_id", "stable_member_id",
        "owner_session_id", "thread_id", "provider_key", "model",
        "endpoint_fingerprint", "permission_fingerprint",
    )

    def __init__(self, db_path: str = ""):
        self.db_path = str(db_path or _default_path())
        self._lock = threading.RLock()
        parent = os.path.dirname(self.db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with closing(self._connect()) as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS provider_continuation_anchors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stable_account_scope TEXT NOT NULL,
                    stable_room_id TEXT NOT NULL,
                    stable_member_id TEXT NOT NULL,
                    owner_session_id TEXT NOT NULL,
                    thread_id TEXT NOT NULL,
                    provider_key TEXT NOT NULL,
                    model TEXT NOT NULL,
                    endpoint_fingerprint TEXT NOT NULL,
                    permission_fingerprint TEXT NOT NULL,
                    anchor_type TEXT NOT NULL,
                    anchor_value TEXT NOT NULL,
                    parent_anchor_hash TEXT NOT NULL DEFAULT '',
                    request_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_provider_continuation_scope
                ON provider_continuation_anchors (
                    stable_account_scope, stable_room_id, stable_member_id,
                    owner_session_id, thread_id, provider_key, model,
                    endpoint_fingerprint, permission_fingerprint,
                    status, expires_at
                );
                CREATE INDEX IF NOT EXISTS idx_provider_continuation_request
                ON provider_continuation_anchors (request_id, status);
                """
            )
            conn.commit()

    def get_committed(
        self,
        scope: ProviderContinuationScope,
        now: Optional[int] = None,
    ) -> Optional[ProviderContinuationAnchor]:
        if not scope.valid():
            return None
        current = int(now or time.time())
        where = self._scope_where()
        with self._lock, closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    "UPDATE provider_continuation_anchors SET status = 'expired' "
                    "WHERE status IN ('pending', 'committed') AND expires_at <= ?",
                    (current,),
                )
                row = conn.execute(
                    "SELECT * FROM provider_continuation_anchors WHERE {} "
                    "AND status = 'committed' AND expires_at > ? "
                    "ORDER BY id DESC LIMIT 1".format(where),
                    (*scope.values(), current),
                ).fetchone()
        return self._row_to_anchor(row) if row else None

    def stage(
        self,
        scope: ProviderContinuationScope,
        anchor_type: str,
        anchor_value: str,
        request_id: str,
        ttl_seconds: int,
        parent_anchor_value: str = "",
        now: Optional[int] = None,
    ) -> Optional[ProviderContinuationAnchor]:
        value = str(anchor_value or "").strip()
        request = str(request_id or "").strip()
        kind = str(anchor_type or "").strip()
        if not scope.valid() or not value or not request or not kind:
            return None
        if len(value) > 8192 or len(kind) > 128:
            return None
        current = int(now or time.time())
        ttl = min(max(int(ttl_seconds or 0), 60), 24 * 60 * 60)
        with self._lock, closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    "UPDATE provider_continuation_anchors SET status = 'discarded' "
                    "WHERE request_id = ? AND status = 'pending'",
                    (request,),
                )
                cursor = conn.execute(
                    """
                    INSERT INTO provider_continuation_anchors (
                        stable_account_scope, stable_room_id, stable_member_id,
                        owner_session_id, thread_id, provider_key, model,
                        endpoint_fingerprint, permission_fingerprint,
                        anchor_type, anchor_value, parent_anchor_hash,
                        request_id, status, created_at, expires_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
                    """,
                    (
                        *scope.values(), kind, value,
                        opaque_hash(parent_anchor_value), request,
                        current, current + ttl,
                    ),
                )
                row_id = int(cursor.lastrowid or 0)
                row = conn.execute(
                    "SELECT * FROM provider_continuation_anchors WHERE id = ?",
                    (row_id,),
                ).fetchone()
        return self._row_to_anchor(row) if row else None

    def commit(self, request_id: str, now: Optional[int] = None) -> bool:
        request = str(request_id or "").strip()
        if not request:
            return False
        current = int(now or time.time())
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            with conn:
                row = conn.execute(
                    "SELECT * FROM provider_continuation_anchors "
                    "WHERE request_id = ? AND status = 'pending' "
                    "AND expires_at > ? ORDER BY id DESC LIMIT 1",
                    (request, current),
                ).fetchone()
                if not row:
                    return False
                scope = self._scope_from_row(row)
                conn.execute(
                    "UPDATE provider_continuation_anchors SET status = 'discarded' "
                    "WHERE {} AND status = 'committed'".format(self._scope_where()),
                    scope.values(),
                )
                cursor = conn.execute(
                    "UPDATE provider_continuation_anchors SET status = 'committed' "
                    "WHERE id = ? AND status = 'pending'",
                    (int(row["id"]),),
                )
        return bool(cursor.rowcount)

    def discard(self, request_id: str) -> int:
        request = str(request_id or "").strip()
        if not request:
            return 0
        with self._lock, closing(self._connect()) as conn:
            with conn:
                cursor = conn.execute(
                    "UPDATE provider_continuation_anchors SET status = 'discarded' "
                    "WHERE request_id = ? AND status = 'pending'",
                    (request,),
                )
        return int(cursor.rowcount or 0)

    def expire(self, row_id: int) -> bool:
        try:
            target = int(row_id)
        except (TypeError, ValueError):
            return False
        with self._lock, closing(self._connect()) as conn:
            with conn:
                cursor = conn.execute(
                    "UPDATE provider_continuation_anchors SET status = 'expired' "
                    "WHERE id = ? AND status = 'committed'",
                    (target,),
                )
        return bool(cursor.rowcount)

    def list_for_request(self, request_id: str):
        with self._lock, closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM provider_continuation_anchors "
                "WHERE request_id = ? ORDER BY id ASC",
                (str(request_id or ""),),
            ).fetchall()
        return [self._row_to_anchor(row) for row in rows]

    @classmethod
    def _scope_where(cls) -> str:
        return " AND ".join("{} = ?".format(name) for name in cls._SCOPE_COLUMNS)

    @staticmethod
    def _scope_from_row(row) -> ProviderContinuationScope:
        return ProviderContinuationScope(
            stable_account_scope=str(row["stable_account_scope"] or ""),
            stable_room_id=str(row["stable_room_id"] or ""),
            stable_member_id=str(row["stable_member_id"] or ""),
            owner_session_id=str(row["owner_session_id"] or ""),
            thread_id=str(row["thread_id"] or ""),
            provider_key=str(row["provider_key"] or ""),
            model=str(row["model"] or ""),
            endpoint_fingerprint=str(row["endpoint_fingerprint"] or ""),
            permission_fingerprint=str(row["permission_fingerprint"] or ""),
        )

    @classmethod
    def _row_to_anchor(cls, row) -> ProviderContinuationAnchor:
        if not isinstance(row, sqlite3.Row):
            keys = [
                "id", *cls._SCOPE_COLUMNS, "anchor_type", "anchor_value",
                "parent_anchor_hash", "request_id", "status", "created_at",
                "expires_at",
            ]
            row = dict(zip(keys, row))
        return ProviderContinuationAnchor(
            row_id=int(row["id"]),
            scope=cls._scope_from_row(row),
            anchor_type=str(row["anchor_type"] or ""),
            anchor_value=str(row["anchor_value"] or ""),
            parent_anchor_hash=str(row["parent_anchor_hash"] or ""),
            request_id=str(row["request_id"] or ""),
            status=str(row["status"] or ""),
            created_at=int(row["created_at"] or 0),
            expires_at=int(row["expires_at"] or 0),
        )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn
