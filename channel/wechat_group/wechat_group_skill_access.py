"""Persistent per-skill access control for the WeChat group channel."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import time
from contextlib import closing
from typing import Any, Dict, Iterable, List, Optional, Tuple

from common.log import logger


MODE_UNRESTRICTED = "unrestricted"
MODE_RESTRICTED = "restricted"
MODE_DISABLED = "disabled_for_wechat_group"
VALID_MODES = {MODE_UNRESTRICTED, MODE_RESTRICTED, MODE_DISABLED}
GRANT_ROOM = "room"
GRANT_MEMBER = "member"
DENIAL_TEXT = "你没有使用「{skill_name}」的权限，请联系当前群管理员授权。"


def _default_db_path() -> str:
    root = os.environ.get("LIGHTAGENT_DATA_DIR") or os.path.join(
        os.path.expanduser("~"), ".lightagent"
    )
    return os.path.join(root, "wechat_group", "wechat_group_skill_access.db")


def _now() -> int:
    return int(time.time())


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _row(row: Optional[sqlite3.Row]) -> Dict[str, Any]:
    return dict(row) if row is not None else {}


class WechatGroupSkillAccessStore:
    """SQLite persistence for catalog entries, grants, templates and audit."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or _default_db_path()
        self._lock = threading.RLock()
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_schema()

    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def _init_schema(self) -> None:
        with self._lock, closing(self._connect()) as conn, conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS skill_access_policies (
                    policy_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    skill_key TEXT NOT NULL,
                    skill_name TEXT NOT NULL,
                    display_name TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT '',
                    source_identity TEXT NOT NULL,
                    content_fingerprint TEXT NOT NULL DEFAULT '',
                    installed_state TEXT NOT NULL DEFAULT 'active',
                    mode TEXT NOT NULL DEFAULT 'restricted',
                    version INTEGER NOT NULL DEFAULT 1,
                    is_new INTEGER NOT NULL DEFAULT 1,
                    first_seen_at INTEGER NOT NULL,
                    last_seen_at INTEGER NOT NULL,
                    inactive_at INTEGER NOT NULL DEFAULT 0,
                    UNIQUE(skill_key, source_identity)
                );
                CREATE INDEX IF NOT EXISTS idx_skill_access_policy_active_name
                    ON skill_access_policies(skill_name, installed_state);

                CREATE TABLE IF NOT EXISTS skill_access_grants (
                    grant_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    policy_id INTEGER NOT NULL,
                    stable_room_id TEXT NOT NULL,
                    grant_type TEXT NOT NULL,
                    stable_member_id TEXT NOT NULL DEFAULT '',
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    UNIQUE(policy_id, stable_room_id, grant_type, stable_member_id),
                    FOREIGN KEY(policy_id) REFERENCES skill_access_policies(policy_id)
                        ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_skill_access_grant_lookup
                    ON skill_access_grants(policy_id, stable_room_id, stable_member_id);

                CREATE TABLE IF NOT EXISTS skill_access_audit (
                    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL DEFAULT '',
                    policy_id INTEGER,
                    skill_name TEXT NOT NULL,
                    stable_room_id TEXT NOT NULL DEFAULT '',
                    stable_member_id TEXT NOT NULL DEFAULT '',
                    allowed INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_skill_access_audit_created
                    ON skill_access_audit(created_at);

                CREATE TABLE IF NOT EXISTS skill_access_meta (
                    meta_key TEXT PRIMARY KEY,
                    meta_value TEXT NOT NULL,
                    updated_at INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS skill_access_templates (
                    template_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    grants_json TEXT NOT NULL DEFAULT '[]',
                    is_default INTEGER NOT NULL DEFAULT 0,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                );
                """
            )

    def get_meta(self, key: str, default: str = "") -> str:
        with self._lock, closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT meta_value FROM skill_access_meta WHERE meta_key = ?", (key,)
            ).fetchone()
        return str(row["meta_value"]) if row else default

    def set_meta(self, key: str, value: str) -> None:
        with self._lock, closing(self._connect()) as conn, conn:
            conn.execute(
                """
                INSERT INTO skill_access_meta(meta_key, meta_value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(meta_key) DO UPDATE SET
                    meta_value = excluded.meta_value,
                    updated_at = excluded.updated_at
                """,
                (key, value, _now()),
            )


class WechatGroupSkillAccessService:
    """Catalog synchronization, administration and runtime authorization."""

    def __init__(
        self,
        store: Optional[WechatGroupSkillAccessStore] = None,
        identity_service=None,
    ):
        self.store = store or WechatGroupSkillAccessStore()
        if identity_service is None:
            from channel.wechat_group.wechat_group_identity_service import (
                WechatGroupIdentityService,
            )

            identity_service = WechatGroupIdentityService()
        self.identity_service = identity_service
        self._cache_lock = threading.Lock()
        self._decision_cache: Dict[Tuple[Any, ...], Tuple[float, bool, str]] = {}

    @staticmethod
    def _catalog_identity(manager, name: str, entry) -> Dict[str, str]:
        skill = entry.skill
        metadata = entry.metadata
        skill_key = str(
            getattr(metadata, "skill_key", None)
            or skill.frontmatter.get("skill_key")
            or name
        ).strip()
        configured = manager.skills_config.get(name, {})
        source = str(skill.source or configured.get("source") or "custom")
        explicit_source = (
            configured.get("source_identity")
            or
            skill.frontmatter.get("source_identity")
            or skill.frontmatter.get("repository")
            or skill.frontmatter.get("homepage")
            or getattr(metadata, "homepage", None)
            or configured.get("source")
        )
        if explicit_source:
            source_identity = f"{source}:{explicit_source}"
        else:
            source_identity = f"{source}:{os.path.realpath(skill.base_dir)}"
        content = skill.content or ""
        fingerprint = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return {
            "skill_key": skill_key,
            "skill_name": name,
            "display_name": str(configured.get("display_name") or name),
            "source": source,
            "source_identity": source_identity,
            "content_fingerprint": fingerprint,
        }

    def sync_skill_catalog(self, manager) -> None:
        """Idempotently register every scanned skill and retain inactive history."""
        now = _now()
        catalog = [
            self._catalog_identity(manager, name, entry)
            for name, entry in manager.skills.items()
        ]
        bootstrap = self.store.get_meta("bootstrap_completed") == "1"
        default_template = self._get_default_template()
        active_ids: List[int] = []
        created: List[Tuple[int, str]] = []
        with self.store._lock, closing(self.store._connect()) as conn, conn:
            for item in catalog:
                existing = conn.execute(
                    """
                    SELECT * FROM skill_access_policies
                    WHERE skill_key = ? AND source_identity = ?
                    """,
                    (item["skill_key"], item["source_identity"]),
                ).fetchone()
                if existing:
                    policy_id = int(existing["policy_id"])
                    conn.execute(
                        """
                        UPDATE skill_access_policies SET
                            skill_name = ?, display_name = ?, source = ?,
                            content_fingerprint = ?, installed_state = 'active',
                            last_seen_at = ?, inactive_at = 0
                        WHERE policy_id = ?
                        """,
                        (
                            item["skill_name"],
                            item["display_name"],
                            item["source"],
                            item["content_fingerprint"],
                            now,
                            policy_id,
                        ),
                    )
                else:
                    mode = MODE_UNRESTRICTED if not bootstrap else MODE_RESTRICTED
                    if bootstrap and default_template:
                        mode = default_template["mode"]
                    cursor = conn.execute(
                        """
                        INSERT INTO skill_access_policies(
                            skill_key, skill_name, display_name, source,
                            source_identity, content_fingerprint, installed_state,
                            mode, version, is_new, first_seen_at, last_seen_at
                        ) VALUES (?, ?, ?, ?, ?, ?, 'active', ?, 1, ?, ?, ?)
                        """,
                        (
                            item["skill_key"],
                            item["skill_name"],
                            item["display_name"],
                            item["source"],
                            item["source_identity"],
                            item["content_fingerprint"],
                            mode,
                            0 if not bootstrap else 1,
                            now,
                            now,
                        ),
                    )
                    policy_id = int(cursor.lastrowid)
                    created.append((policy_id, mode))
                active_ids.append(policy_id)

            if active_ids:
                placeholders = ",".join("?" for _ in active_ids)
                conn.execute(
                    f"""
                    UPDATE skill_access_policies
                    SET installed_state = 'inactive',
                        inactive_at = CASE WHEN inactive_at = 0 THEN ? ELSE inactive_at END
                    WHERE installed_state = 'active' AND policy_id NOT IN ({placeholders})
                    """,
                    (now, *active_ids),
                )
            else:
                conn.execute(
                    """
                    UPDATE skill_access_policies
                    SET installed_state = 'inactive',
                        inactive_at = CASE WHEN inactive_at = 0 THEN ? ELSE inactive_at END
                    WHERE installed_state = 'active'
                    """,
                    (now,),
                )
            if bootstrap and default_template:
                for policy_id, _mode in created:
                    self._replace_grants(
                        conn, policy_id, default_template.get("grants", []), validate=False
                    )

        if not bootstrap:
            self.store.set_meta("bootstrap_completed", "1")
            self.store.set_meta("schema_version", "1")
        self.invalidate_cache()

    def list_skills(self, manager) -> List[Dict[str, Any]]:
        self.sync_skill_catalog(manager)
        with self.store._lock, closing(self.store._connect()) as conn:
            rows = conn.execute(
                """
                SELECT p.*,
                    COUNT(DISTINCT g.stable_room_id) AS authorized_room_count,
                    COUNT(DISTINCT CASE WHEN g.grant_type = 'member'
                        THEN g.stable_member_id END) AS authorized_member_count
                FROM skill_access_policies p
                LEFT JOIN skill_access_grants g ON g.policy_id = p.policy_id
                WHERE p.installed_state = 'active'
                GROUP BY p.policy_id
                """
            ).fetchall()
        by_name = {str(row["skill_name"]): dict(row) for row in rows}
        result = []
        for name, config in manager.get_skills_config().items():
            item = dict(config)
            policy = by_name.get(name, {})
            item.update(
                {
                    "skill_key": policy.get("skill_key", name),
                    "access_mode": policy.get("mode", MODE_RESTRICTED),
                    "access_version": int(policy.get("version") or 1),
                    "authorized_room_count": int(
                        policy.get("authorized_room_count") or 0
                    ),
                    "authorized_member_count": int(
                        policy.get("authorized_member_count") or 0
                    ),
                    "is_new": bool(policy.get("is_new", 0)),
                    "installed_state": policy.get("installed_state", "active"),
                }
            )
            result.append(item)
        return result

    def _active_policy(self, conn, skill_name: str):
        return conn.execute(
            """
            SELECT * FROM skill_access_policies
            WHERE skill_name = ? AND installed_state = 'active'
            ORDER BY last_seen_at DESC, policy_id DESC LIMIT 1
            """,
            (str(skill_name or "").strip(),),
        ).fetchone()

    def get_access(self, skill_name: str, manager=None) -> Dict[str, Any]:
        if manager is not None:
            self.sync_skill_catalog(manager)
        with self.store._lock, closing(self.store._connect()) as conn:
            policy = self._active_policy(conn, skill_name)
            if not policy:
                raise ValueError("skill is not installed")
            grants = conn.execute(
                """
                SELECT stable_room_id, grant_type, stable_member_id
                FROM skill_access_grants WHERE policy_id = ?
                ORDER BY stable_room_id, grant_type, stable_member_id
                """,
                (policy["policy_id"],),
            ).fetchall()
        return {
            "skill_key": policy["skill_key"],
            "skill_name": policy["skill_name"],
            "display_name": policy["display_name"],
            "mode": policy["mode"],
            "version": int(policy["version"]),
            "is_new": bool(policy["is_new"]),
            "grants": [dict(item) for item in grants],
        }

    def _canonical_grants(self, grants: Iterable[Dict[str, Any]]) -> List[Dict[str, str]]:
        normalized = []
        seen = set()
        for raw in grants or []:
            room_id = str(raw.get("stable_room_id") or "").strip()
            grant_type = str(raw.get("grant_type") or "").strip()
            member_id = str(raw.get("stable_member_id") or "").strip()
            room = self.identity_service.store.get_room(room_id) if room_id else {}
            if not room or room.get("status") != "confirmed":
                raise ValueError("stable_room_id is not a confirmed room")
            if grant_type == GRANT_ROOM:
                member_id = ""
            elif grant_type == GRANT_MEMBER:
                canonical = self.identity_service.resolve_canonical_member_id(
                    room_id, member_id
                )
                member = (
                    self.identity_service.store.get_member(canonical) if canonical else {}
                )
                if (
                    not member
                    or str(member.get("stable_room_id") or "") != room_id
                    or member.get("status") != "confirmed"
                ):
                    raise ValueError(
                        "stable_member_id is not a confirmed member of stable_room_id"
                    )
                member_id = canonical
            else:
                raise ValueError("grant_type must be room or member")
            key = (room_id, grant_type, member_id)
            if key not in seen:
                seen.add(key)
                normalized.append(
                    {
                        "stable_room_id": room_id,
                        "grant_type": grant_type,
                        "stable_member_id": member_id,
                    }
                )
        return normalized

    @staticmethod
    def _replace_grants(conn, policy_id: int, grants, validate: bool = True) -> None:
        del validate
        now = _now()
        conn.execute(
            "DELETE FROM skill_access_grants WHERE policy_id = ?", (policy_id,)
        )
        for grant in grants or []:
            conn.execute(
                """
                INSERT INTO skill_access_grants(
                    policy_id, stable_room_id, grant_type,
                    stable_member_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    policy_id,
                    grant["stable_room_id"],
                    grant["grant_type"],
                    grant.get("stable_member_id", ""),
                    now,
                    now,
                ),
            )

    def save_access(
        self,
        skill_name: str,
        mode: str,
        grants: Iterable[Dict[str, Any]],
        expected_version: Optional[int],
        manager=None,
    ) -> Dict[str, Any]:
        if mode not in VALID_MODES:
            raise ValueError("invalid access mode")
        if manager is not None:
            self.sync_skill_catalog(manager)
        normalized = self._canonical_grants(grants)
        with self.store._lock, closing(self.store._connect()) as conn, conn:
            policy = self._active_policy(conn, skill_name)
            if not policy:
                raise ValueError("skill is not installed")
            current_version = int(policy["version"])
            if expected_version is not None and int(expected_version) != current_version:
                raise RuntimeError("skill access version conflict")
            self._replace_grants(conn, int(policy["policy_id"]), normalized)
            conn.execute(
                """
                UPDATE skill_access_policies
                SET mode = ?, version = version + 1, is_new = 0
                WHERE policy_id = ?
                """,
                (mode, policy["policy_id"]),
            )
        self.invalidate_cache()
        return self.get_access(skill_name)

    def bulk_apply(self, payload: Dict[str, Any], manager=None) -> List[Dict[str, Any]]:
        names = [
            str(name).strip()
            for name in payload.get("skill_names", [])
            if str(name).strip()
        ]
        operation = str(payload.get("operation") or "apply")
        if operation == "copy":
            source = self.get_access(str(payload.get("source_skill_name") or ""), manager)
            mode, grants = source["mode"], source["grants"]
        elif operation == "template":
            template = self.get_template(str(payload.get("template_id") or ""))
            mode, grants = template["mode"], template["grants"]
        else:
            mode = str(payload.get("mode") or MODE_RESTRICTED)
            grants = payload.get("grants", [])
        results = []
        for name in names:
            current = self.get_access(name, manager)
            results.append(
                self.save_access(
                    name,
                    mode,
                    grants,
                    current["version"],
                    manager=None,
                )
            )
        return results

    def list_templates(self) -> List[Dict[str, Any]]:
        with self.store._lock, closing(self.store._connect()) as conn:
            rows = conn.execute(
                "SELECT * FROM skill_access_templates ORDER BY name"
            ).fetchall()
        return [self._template_row(item) for item in rows]

    def get_template(self, template_id: str) -> Dict[str, Any]:
        with self.store._lock, closing(self.store._connect()) as conn:
            row = conn.execute(
                "SELECT * FROM skill_access_templates WHERE template_id = ?",
                (template_id,),
            ).fetchone()
        if not row:
            raise ValueError("template not found")
        return self._template_row(row)

    @staticmethod
    def _template_row(row) -> Dict[str, Any]:
        return {
            "template_id": row["template_id"],
            "name": row["name"],
            "mode": row["mode"],
            "grants": json.loads(row["grants_json"] or "[]"),
            "is_default": bool(row["is_default"]),
        }

    def save_template(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        template_id = str(payload.get("template_id") or "").strip()
        name = str(payload.get("name") or "").strip()
        mode = str(payload.get("mode") or MODE_RESTRICTED)
        if not template_id or not name:
            raise ValueError("template_id and name are required")
        if mode not in VALID_MODES:
            raise ValueError("invalid access mode")
        grants = self._canonical_grants(payload.get("grants", []))
        is_default = bool(payload.get("is_default", False))
        now = _now()
        with self.store._lock, closing(self.store._connect()) as conn, conn:
            if is_default:
                conn.execute("UPDATE skill_access_templates SET is_default = 0")
            conn.execute(
                """
                INSERT INTO skill_access_templates(
                    template_id, name, mode, grants_json, is_default,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(template_id) DO UPDATE SET
                    name = excluded.name, mode = excluded.mode,
                    grants_json = excluded.grants_json,
                    is_default = excluded.is_default,
                    updated_at = excluded.updated_at
                """,
                (
                    template_id,
                    name,
                    mode,
                    _json(grants),
                    int(is_default),
                    now,
                    now,
                ),
            )
        return self.get_template(template_id)

    def _get_default_template(self) -> Optional[Dict[str, Any]]:
        with self.store._lock, closing(self.store._connect()) as conn:
            row = conn.execute(
                "SELECT * FROM skill_access_templates WHERE is_default = 1 LIMIT 1"
            ).fetchone()
        return self._template_row(row) if row else None

    def delete_template(self, template_id: str) -> None:
        with self.store._lock, closing(self.store._connect()) as conn, conn:
            conn.execute(
                "DELETE FROM skill_access_templates WHERE template_id = ?",
                (template_id,),
            )

    def invalidate_cache(self) -> None:
        with self._cache_lock:
            self._decision_cache.clear()

    def check_access(
        self,
        skill_name: str,
        stable_room_id: str,
        stable_member_id: str,
        request_id: str = "",
        manager=None,
        audit: bool = True,
    ) -> Tuple[bool, str]:
        if manager is not None:
            self.sync_skill_catalog(manager)
        room_id = str(stable_room_id or "").strip()
        canonical_member = self.identity_service.resolve_canonical_member_id(
            room_id, stable_member_id
        )
        with self.store._lock, closing(self.store._connect()) as conn:
            policy = self._active_policy(conn, skill_name)
            if not policy:
                allowed, reason = False, "skill_not_registered"
                policy_id, version = None, 0
            else:
                policy_id, version = int(policy["policy_id"]), int(policy["version"])
                key = (policy_id, version, room_id, canonical_member)
                with self._cache_lock:
                    cached = self._decision_cache.get(key)
                if cached and cached[0] > time.monotonic():
                    allowed, reason = cached[1], cached[2]
                else:
                    allowed, reason = self._evaluate_policy(
                        conn, policy, room_id, canonical_member
                    )
                    with self._cache_lock:
                        self._decision_cache[key] = (
                            time.monotonic() + 5.0,
                            allowed,
                            reason,
                        )
        if audit:
            self.audit(
                request_id,
                policy_id,
                skill_name,
                room_id,
                canonical_member,
                allowed,
                reason,
            )
        return allowed, reason

    def _evaluate_policy(self, conn, policy, room_id: str, member_id: str):
        mode = str(policy["mode"])
        if mode == MODE_DISABLED:
            return False, "disabled_for_wechat_group"
        if mode == MODE_UNRESTRICTED:
            return True, "unrestricted"
        room_grant = conn.execute(
            """
            SELECT 1 FROM skill_access_grants
            WHERE policy_id = ? AND stable_room_id = ?
              AND grant_type = 'room' LIMIT 1
            """,
            (policy["policy_id"], room_id),
        ).fetchone()
        if room_grant:
            return True, "room_grant"
        if member_id:
            member_grants = conn.execute(
                """
                SELECT stable_member_id FROM skill_access_grants
                WHERE policy_id = ? AND stable_room_id = ?
                  AND grant_type = 'member'
                """,
                (policy["policy_id"], room_id),
            ).fetchall()
            for grant in member_grants:
                granted = str(grant["stable_member_id"])
                canonical_granted = self.identity_service.resolve_canonical_member_id(
                    room_id, granted
                )
                if canonical_granted and canonical_granted == member_id:
                    return True, "member_grant"
        return False, "no_matching_grant"

    def allowed_skill_names(
        self,
        manager,
        stable_room_id: str,
        stable_member_id: str,
        request_id: str = "",
    ) -> List[str]:
        self.sync_skill_catalog(manager)
        result = []
        for name in manager.skills:
            if not manager.is_skill_enabled(name):
                continue
            allowed, _ = self.check_access(
                name,
                stable_room_id,
                stable_member_id,
                request_id=request_id,
                audit=False,
            )
            if allowed:
                result.append(name)
        return result

    def audit(
        self,
        request_id: str,
        policy_id: Optional[int],
        skill_name: str,
        room_id: str,
        member_id: str,
        allowed: bool,
        reason: str,
    ) -> None:
        with self.store._lock, closing(self.store._connect()) as conn, conn:
            conn.execute(
                """
                INSERT INTO skill_access_audit(
                    request_id, policy_id, skill_name, stable_room_id,
                    stable_member_id, allowed, reason, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(request_id or ""),
                    policy_id,
                    str(skill_name or ""),
                    str(room_id or ""),
                    str(member_id or ""),
                    int(bool(allowed)),
                    str(reason or ""),
                    _now(),
                ),
            )
        if not allowed:
            logger.info(
                "skill_permission_denied skill=%s room=%s member=%s request_id=%s reason=%s",
                skill_name,
                room_id,
                member_id,
                request_id,
                reason,
            )

    def cleanup_inactive(self, retention_days: int = 90) -> int:
        cutoff = _now() - max(1, int(retention_days)) * 86400
        with self.store._lock, closing(self.store._connect()) as conn, conn:
            cursor = conn.execute(
                """
                DELETE FROM skill_access_policies
                WHERE installed_state = 'inactive'
                  AND inactive_at > 0 AND inactive_at < ?
                """,
                (cutoff,),
            )
            return int(cursor.rowcount or 0)


_service = None
_service_lock = threading.Lock()


def get_wechat_group_skill_access_service() -> WechatGroupSkillAccessService:
    global _service
    with _service_lock:
        if _service is None:
            _service = WechatGroupSkillAccessService()
        return _service
