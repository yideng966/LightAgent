"""Migrate legacy WeChat group runtime ids to stable LightAgent identities."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sqlite3
from contextlib import closing
from typing import Any, Dict, Iterable, List, Optional

from channel.wechat_group.wechat_group_identity_store import WechatGroupIdentityStore


def run_migration(
    config_path: str,
    identity_db_path: str = "",
    sqlite_paths: Optional[List[str]] = None,
    scheduler_tasks_path: str = "",
    apply: bool = False,
) -> Dict[str, Any]:
    config_path = os.path.abspath(config_path)
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    migrated_config = copy.deepcopy(config)
    stable_config_repairs = _repair_runtime_ids_in_stable_room_config(
        migrated_config,
        identity_db_path,
    )
    repaired_room_ids = {
        str(item.get("runtime_room_id") or ""): str(item.get("stable_room_id") or "")
        for item in stable_config_repairs
        if item.get("status") == "repaired"
    }
    stable_account_id = _stable_id("wga", os.path.dirname(config_path) or "default")
    room_mappings = _build_room_mappings(
        config,
        stable_account_id,
        repaired_room_ids=repaired_room_ids,
    )
    _mark_existing_confirmed_room_mappings(room_mappings, identity_db_path)
    member_mappings = _build_member_mappings(config, room_mappings)
    _mark_existing_confirmed_member_mappings(member_mappings, identity_db_path)
    report = {
        "dry_run": not apply,
        "stable_account_id": stable_account_id,
        "rooms": list(room_mappings.values()),
        "members": list(member_mappings.values()),
        "sqlite": [],
        "scheduler": {},
        "conflicts": [],
        "manual_confirmation": [],
        "missing_media": [],
        "stable_config_repairs": stable_config_repairs,
        "summary": {
            "rooms": len([item for item in room_mappings.values() if not item.get("already_confirmed")]),
            "existing_confirmed_rooms": len([
                item for item in room_mappings.values() if item.get("already_confirmed")
            ]),
            "members": len([item for item in member_mappings.values() if not item.get("already_confirmed")]),
            "existing_confirmed_members": len([
                item for item in member_mappings.values() if item.get("already_confirmed")
            ]),
            "sqlite_updates": 0,
            "scheduler_tasks": 0,
            "stable_config_repairs": len([
                item for item in stable_config_repairs if item.get("status") == "repaired"
            ]),
        },
    }
    report["conflicts"] = _detect_identity_conflicts(identity_db_path, stable_account_id, room_mappings)
    config_manual_confirmation = _migrate_config(
        migrated_config,
        room_mappings,
        member_mappings,
        repaired_room_ids=repaired_room_ids,
    )
    if apply:
        _write_json(config_path, migrated_config)
        _write_identity_store(identity_db_path, stable_account_id, room_mappings, member_mappings)
    else:
        report["config_preview"] = migrated_config

    for db_path in sqlite_paths or []:
        db_report = _migrate_sqlite_db(db_path, room_mappings, member_mappings, apply=apply)
        report["sqlite"].append(db_report)
        report["summary"]["sqlite_updates"] += db_report.get("updated_rows", 0)
        report["missing_media"].extend(db_report.get("missing_media", []))

    if scheduler_tasks_path:
        scheduler_report = _migrate_scheduler_tasks(scheduler_tasks_path, room_mappings, apply=apply)
        report["scheduler"] = scheduler_report
        report["summary"]["scheduler_tasks"] = scheduler_report.get("updated_tasks", 0)

    repair_manual_confirmation = [
        {
            "entity_type": "room",
            "runtime_room_id": item.get("runtime_room_id", ""),
            "candidate_stable_room_ids": item.get("candidate_stable_room_ids", []),
            "reason": item.get("reason", "invalid_stable_room_config_requires_binding"),
        }
        for item in stable_config_repairs
        if item.get("status") != "repaired"
    ]
    report["manual_confirmation"] = (
        _build_manual_confirmation(report)
        + config_manual_confirmation
        + repair_manual_confirmation
    )
    report["summary"]["manual_confirmation"] = len(report["manual_confirmation"])
    report["summary"]["missing_media"] = len(report["missing_media"])
    return report


def _repair_runtime_ids_in_stable_room_config(
    config: Dict[str, Any],
    identity_db_path: str,
) -> List[Dict[str, Any]]:
    configured = _string_list(config.get("wechat_group_stable_room_ids"))
    if not configured:
        return []
    stable_ids = []
    runtime_ids = _string_list(config.get("wechat_group_room_ids"))
    repairs: List[Dict[str, Any]] = []
    conn = None
    if identity_db_path and os.path.exists(identity_db_path):
        conn = sqlite3.connect(identity_db_path)
        conn.row_factory = sqlite3.Row
    try:
        for configured_id in configured:
            if configured_id.startswith("wgr_"):
                if configured_id not in stable_ids:
                    stable_ids.append(configured_id)
                continue
            if configured_id not in runtime_ids:
                runtime_ids.append(configured_id)
            candidates = []
            if conn is not None:
                try:
                    rows = conn.execute(
                        """
                        SELECT DISTINCT a.stable_room_id
                        FROM wechat_group_identity_room_aliases a
                        INNER JOIN wechat_group_identity_rooms r
                          ON r.stable_room_id = a.stable_room_id
                        INNER JOIN wechat_group_identity_accounts ac
                          ON ac.stable_account_id = a.stable_account_id
                        WHERE a.runtime_room_id = ?
                          AND r.status = 'confirmed'
                          AND ac.status = 'confirmed'
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
                        """,
                        (configured_id,),
                    ).fetchall()
                    candidates = sorted({str(row[0] or "") for row in rows if str(row[0] or "")})
                except sqlite3.Error:
                    candidates = []
            if len(candidates) == 1:
                if candidates[0] not in stable_ids:
                    stable_ids.append(candidates[0])
                repairs.append({
                    "status": "repaired",
                    "runtime_room_id": configured_id,
                    "stable_room_id": candidates[0],
                    "reason": "runtime_id_was_written_to_stable_config",
                })
            else:
                repairs.append({
                    "status": "unresolved",
                    "runtime_room_id": configured_id,
                    "candidate_stable_room_ids": candidates,
                    "reason": (
                        "runtime_stable_config_is_ambiguous"
                        if len(candidates) > 1
                        else "runtime_stable_config_requires_binding"
                    ),
                })
    finally:
        if conn is not None:
            conn.close()
    config["wechat_group_stable_room_ids"] = stable_ids
    config["wechat_group_room_ids"] = runtime_ids
    return repairs


def _build_room_mappings(
    config: Dict[str, Any],
    stable_account_id: str,
    repaired_room_ids: Optional[Dict[str, str]] = None,
) -> Dict[str, Dict[str, Any]]:
    runtime_ids = _string_list(config.get("wechat_group_room_ids"))
    stable_ids = _string_list(config.get("wechat_group_stable_room_ids"))
    names = _string_list(config.get("wechat_group_names"))
    repaired_room_ids = repaired_room_ids or {}
    mappings: Dict[str, Dict[str, Any]] = {}
    for index, runtime_room_id in enumerate(runtime_ids):
        configured_stable_room_id = stable_ids[index] if index < len(stable_ids) else ""
        if configured_stable_room_id.startswith("wgr_"):
            stable_room_id = configured_stable_room_id
        elif repaired_room_ids.get(runtime_room_id):
            stable_room_id = repaired_room_ids[runtime_room_id]
        elif configured_stable_room_id:
            continue
        else:
            stable_room_id = _stable_id("wgr", runtime_room_id)
        mappings[runtime_room_id] = {
            "stable_account_id": stable_account_id,
            "stable_room_id": stable_room_id,
            "runtime_room_id": runtime_room_id,
            "room_name": names[index] if index < len(names) else "",
            "confidence": "legacy_config",
        }
    return mappings


def _build_member_mappings(config: Dict[str, Any], room_mappings: Dict[str, Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    mappings: Dict[str, Dict[str, str]] = {}
    for member in config.get("wechat_group_admin_members", []) or []:
        if not isinstance(member, dict):
            continue
        runtime_room_id = str(member.get("legacy_room_id") or member.get("room_id") or "").strip()
        runtime_sender_id = str(member.get("legacy_sender_id") or member.get("sender_id") or "").strip()
        if not runtime_room_id or not runtime_sender_id:
            continue
        room = room_mappings.get(runtime_room_id)
        if not room:
            continue
        key = _member_key(runtime_room_id, runtime_sender_id)
        mappings[key] = {
            "stable_account_id": room["stable_account_id"],
            "stable_room_id": room["stable_room_id"],
            "runtime_room_id": runtime_room_id,
            "stable_member_id": str(member.get("stable_member_id") or _stable_id("wgm", "{}|{}".format(room["stable_room_id"], runtime_sender_id))),
            "runtime_sender_id": runtime_sender_id,
            "display_name": str(member.get("sender_nickname") or member.get("wechat_id") or runtime_sender_id),
            "confidence": "legacy_admin",
        }
    blocked_sender_ids = _string_list(config.get("wechat_group_blocked_sender_ids"))
    if len(room_mappings) == 1:
        room = next(iter(room_mappings.values()))
        for runtime_sender_id in blocked_sender_ids:
            if runtime_sender_id.startswith("wgm_"):
                continue
            key = _member_key(room["runtime_room_id"], runtime_sender_id)
            mappings.setdefault(key, {
                "stable_account_id": room["stable_account_id"],
                "stable_room_id": room["stable_room_id"],
                "runtime_room_id": room["runtime_room_id"],
                "stable_member_id": _stable_id("wgm", "{}|{}".format(room["stable_room_id"], runtime_sender_id)),
                "runtime_sender_id": runtime_sender_id,
                "display_name": runtime_sender_id,
                "confidence": "legacy_blocked_sender",
            })
    return mappings


def _mark_existing_confirmed_member_mappings(
    member_mappings: Dict[str, Dict[str, Any]],
    identity_db_path: str,
) -> None:
    if not member_mappings or not identity_db_path or not os.path.exists(identity_db_path):
        return
    with closing(sqlite3.connect(identity_db_path)) as conn:
        conn.row_factory = sqlite3.Row
        for mapping in member_mappings.values():
            try:
                row = conn.execute(
                    """
                    SELECT a.stable_account_id
                    FROM wechat_group_identity_member_aliases a
                    INNER JOIN wechat_group_identity_members m
                      ON m.stable_member_id = a.stable_member_id
                     AND m.stable_room_id = a.stable_room_id
                     AND m.stable_account_id = a.stable_account_id
                    INNER JOIN wechat_group_identity_rooms r
                      ON r.stable_room_id = a.stable_room_id
                     AND r.stable_account_id = a.stable_account_id
                    INNER JOIN wechat_group_identity_accounts ac
                      ON ac.stable_account_id = a.stable_account_id
                    WHERE a.stable_room_id = ?
                      AND a.stable_member_id = ?
                      AND a.runtime_sender_id = ?
                      AND m.status = 'confirmed'
                      AND r.status = 'confirmed'
                      AND ac.status = 'confirmed'
                      AND (
                            a.is_active = 1
                            OR EXISTS (
                                SELECT 1
                                FROM wechat_group_identity_binding_events e
                                WHERE e.entity_type = 'member'
                                  AND e.stable_account_id = a.stable_account_id
                                  AND e.stable_id = a.stable_member_id
                                  AND e.new_runtime_id = a.runtime_sender_id
                                  AND e.action = 'activate_member_alias'
                            )
                      )
                    LIMIT 1
                    """,
                    (
                        mapping.get("stable_room_id", ""),
                        mapping.get("stable_member_id", ""),
                        mapping.get("runtime_sender_id", ""),
                    ),
                ).fetchone()
            except sqlite3.Error:
                return
            if not row:
                continue
            mapping["stable_account_id"] = str(row["stable_account_id"] or "")
            mapping["already_confirmed"] = True
            mapping["confidence"] = "confirmed_identity"


def _mark_existing_confirmed_room_mappings(
    room_mappings: Dict[str, Dict[str, Any]],
    identity_db_path: str,
) -> None:
    if not room_mappings or not identity_db_path or not os.path.exists(identity_db_path):
        return
    with closing(sqlite3.connect(identity_db_path)) as conn:
        conn.row_factory = sqlite3.Row
        for mapping in room_mappings.values():
            try:
                row = conn.execute(
                    """
                    SELECT a.stable_account_id, r.canonical_name
                    FROM wechat_group_identity_room_aliases a
                    INNER JOIN wechat_group_identity_rooms r
                      ON r.stable_room_id = a.stable_room_id
                     AND r.stable_account_id = a.stable_account_id
                    INNER JOIN wechat_group_identity_accounts ac
                      ON ac.stable_account_id = a.stable_account_id
                    WHERE a.runtime_room_id = ?
                      AND a.stable_room_id = ?
                      AND r.status = 'confirmed'
                      AND ac.status = 'confirmed'
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
                    LIMIT 1
                    """,
                    (mapping.get("runtime_room_id", ""), mapping.get("stable_room_id", "")),
                ).fetchone()
            except sqlite3.Error:
                return
            if not row:
                continue
            mapping["stable_account_id"] = str(row["stable_account_id"] or "")
            mapping["already_confirmed"] = True
            mapping["confidence"] = "confirmed_identity"
            if not str(mapping.get("room_name") or "").strip():
                mapping["room_name"] = str(row["canonical_name"] or "")


def _migrate_config(
    config: Dict[str, Any],
    room_mappings: Dict[str, Dict[str, str]],
    member_mappings: Dict[str, Dict[str, str]],
    repaired_room_ids: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    manual_confirmation: List[Dict[str, Any]] = []
    runtime_rooms = _string_list(config.get("wechat_group_room_ids"))
    migrated_stable_rooms = [
        room_mappings[item]["stable_room_id"]
        for item in runtime_rooms
        if item in room_mappings
    ]
    config["wechat_group_stable_room_ids"] = _merge_string_lists(
        config.get("wechat_group_stable_room_ids"),
        migrated_stable_rooms,
    )
    legacy_free_reply_rooms = _string_list(config.get("wechat_group_free_reply_room_ids"))
    stable_free_reply_rooms = _string_list(config.get("wechat_group_free_reply_stable_room_ids"))
    repaired_room_ids = repaired_room_ids or {}
    for legacy_room_id in legacy_free_reply_rooms:
        if legacy_room_id.startswith("wgr_"):
            stable_free_reply_rooms = _merge_string_lists(stable_free_reply_rooms, [legacy_room_id])
            continue
        room = room_mappings.get(legacy_room_id)
        if room:
            stable_free_reply_rooms = _merge_string_lists(stable_free_reply_rooms, [room["stable_room_id"]])
            continue
        repaired_stable_room_id = str(repaired_room_ids.get(legacy_room_id) or "").strip()
        if repaired_stable_room_id:
            stable_free_reply_rooms = _merge_string_lists(stable_free_reply_rooms, [repaired_stable_room_id])
            continue
        manual_confirmation.append({
            "entity_type": "room",
            "runtime_room_id": legacy_room_id,
            "reason": "legacy_free_reply_room_requires_binding",
        })
    if stable_free_reply_rooms or "wechat_group_free_reply_stable_room_ids" in config:
        config["wechat_group_free_reply_stable_room_ids"] = stable_free_reply_rooms
    for key in ("wechat_group_ambient_room_ids",):
        if key in config:
            config[key] = [
                room_mappings.get(item, {}).get("stable_room_id", item)
                for item in _string_list(config.get(key))
            ]
    blocked_stable_member_ids = _string_list(config.get("wechat_group_blocked_stable_member_ids"))
    for runtime_sender_id in _string_list(config.get("wechat_group_blocked_sender_ids")):
        if runtime_sender_id.startswith("wgm_"):
            blocked_stable_member_ids = _merge_string_lists(blocked_stable_member_ids, [runtime_sender_id])
            continue
        matches = _merge_string_lists([
            member.get("stable_member_id", "")
            for member in member_mappings.values()
            if member.get("runtime_sender_id") == runtime_sender_id
        ])
        if len(matches) == 1:
            blocked_stable_member_ids = _merge_string_lists(blocked_stable_member_ids, matches)
            continue
        manual_confirmation.append({
            "entity_type": "member",
            "runtime_sender_id": runtime_sender_id,
            "candidate_stable_member_ids": matches,
            "reason": (
                "legacy_blocked_sender_is_ambiguous"
                if len(matches) > 1
                else "legacy_blocked_sender_requires_room_binding"
            ),
        })
    if blocked_stable_member_ids:
        config["wechat_group_blocked_stable_member_ids"] = blocked_stable_member_ids
    migrated_admins = []
    for member in config.get("wechat_group_admin_members", []) or []:
        if not isinstance(member, dict):
            continue
        item = dict(member)
        runtime_room_id = str(item.get("legacy_room_id") or item.get("room_id") or "").strip()
        runtime_sender_id = str(item.get("legacy_sender_id") or item.get("sender_id") or "").strip()
        mapping = member_mappings.get(_member_key(runtime_room_id, runtime_sender_id))
        if mapping:
            item["stable_room_id"] = mapping["stable_room_id"]
            item["stable_member_id"] = mapping["stable_member_id"]
            item["legacy_room_id"] = runtime_room_id
            item["legacy_sender_id"] = runtime_sender_id
            item["room_id"] = mapping["stable_room_id"]
            item["sender_id"] = mapping["stable_member_id"]
            item["identity_status"] = (
                "confirmed" if mapping.get("already_confirmed") else "legacy_imported"
            )
        migrated_admins.append(item)
    if migrated_admins:
        config["wechat_group_admin_members"] = migrated_admins
    return manual_confirmation


def _detect_identity_conflicts(
    identity_db_path: str,
    stable_account_id: str,
    room_mappings: Dict[str, Dict[str, str]],
) -> List[Dict[str, Any]]:
    if not identity_db_path or not os.path.exists(identity_db_path):
        return []
    conflicts: List[Dict[str, Any]] = []
    with closing(sqlite3.connect(identity_db_path)) as conn:
        conn.row_factory = sqlite3.Row
        try:
            for room in room_mappings.values():
                if room.get("already_confirmed"):
                    continue
                room_name = str(room.get("room_name") or "").strip()
                if not room_name:
                    continue
                rows = conn.execute(
                    """
                    SELECT stable_account_id, stable_room_id, canonical_name
                    FROM wechat_group_identity_rooms
                    WHERE canonical_name = ? AND stable_account_id <> ?
                    """,
                    (room_name, str(room.get("stable_account_id") or stable_account_id)),
                ).fetchall()
                for row in rows:
                    conflicts.append({
                        "entity_type": "room",
                        "reason": "same_room_name_different_stable_account",
                        "room_name": room_name,
                        "incoming_stable_account_id": stable_account_id,
                        "incoming_stable_room_id": room.get("stable_room_id", ""),
                        "incoming_runtime_room_id": room.get("runtime_room_id", ""),
                        "existing_stable_account_id": str(row["stable_account_id"] or ""),
                        "existing_stable_room_id": str(row["stable_room_id"] or ""),
                    })
        except sqlite3.Error:
            return []
    return conflicts


def _write_identity_store(
    identity_db_path: str,
    stable_account_id: str,
    room_mappings: Dict[str, Dict[str, str]],
    member_mappings: Dict[str, Dict[str, str]],
) -> None:
    store = WechatGroupIdentityStore(identity_db_path or None)
    needs_default_account = any(
        not room.get("already_confirmed")
        and str(room.get("stable_account_id") or stable_account_id) == stable_account_id
        for room in room_mappings.values()
    ) or any(
        not member.get("already_confirmed")
        and str(member.get("stable_account_id") or stable_account_id) == stable_account_id
        for member in member_mappings.values()
    )
    if needs_default_account:
        store.upsert_account(
            stable_account_id,
            display_name="Legacy WeChat Group Account",
            status="legacy_imported",
            confidence="migration",
        )
    for room in room_mappings.values():
        if room.get("already_confirmed"):
            continue
        account_id = str(room.get("stable_account_id") or stable_account_id)
        store.upsert_room(
            room["stable_room_id"],
            account_id,
            canonical_name=room.get("room_name", ""),
            status="legacy_imported",
            confidence=room.get("confidence") or "migration",
        )
        store.activate_room_alias(
            account_id,
            room["stable_room_id"],
            room["runtime_room_id"],
            room_name=room.get("room_name", ""),
            source_kind="migration",
            actor="migration",
            reason="legacy runtime room import",
        )
    for member in member_mappings.values():
        if member.get("already_confirmed"):
            continue
        account_id = str(member.get("stable_account_id") or stable_account_id)
        store.upsert_member(
            member["stable_member_id"],
            member["stable_room_id"],
            account_id,
            display_name=member.get("display_name", ""),
            status="legacy_imported",
            confidence=member.get("confidence") or "migration",
        )
        store.activate_member_alias(
            account_id,
            member["stable_room_id"],
            member["stable_member_id"],
            member["runtime_sender_id"],
            runtime_room_id=member["runtime_room_id"],
            display_name=member.get("display_name", ""),
            source_kind="migration",
            actor="migration",
            reason="legacy runtime member import",
        )


def _migrate_sqlite_db(
    db_path: str,
    room_mappings: Dict[str, Dict[str, str]],
    member_mappings: Dict[str, Dict[str, str]],
    apply: bool,
) -> Dict[str, Any]:
    db_path = os.path.abspath(db_path)
    report = {"path": db_path, "updated_rows": 0, "tables": [], "missing_media": []}
    if not os.path.exists(db_path):
        report["missing"] = True
        return report
    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        for table in _sqlite_tables(conn):
            columns = _sqlite_columns(conn, table)
            if "media_path" in columns:
                report["missing_media"].extend(_find_missing_media(conn, db_path, table))
            if "room_id" not in columns:
                continue
            rows = conn.execute(f"SELECT rowid AS __rowid, * FROM {table}").fetchall()
            table_updates = 0
            for row in rows:
                runtime_room_id = str(row["room_id"] or "").strip()
                room = room_mappings.get(runtime_room_id)
                if not room:
                    continue
                updates = {}
                if "stable_room_id" in columns and not str(row["stable_room_id"] or "").strip():
                    updates["stable_room_id"] = room["stable_room_id"]
                if "runtime_room_id" in columns and not str(row["runtime_room_id"] or "").strip():
                    updates["runtime_room_id"] = runtime_room_id
                if "sender_id" in columns:
                    runtime_sender_id = str(row["sender_id"] or "").strip()
                    member = member_mappings.get(_member_key(runtime_room_id, runtime_sender_id))
                    if member and "stable_member_id" in columns and not str(row["stable_member_id"] or "").strip():
                        updates["stable_member_id"] = member["stable_member_id"]
                    if member and "runtime_sender_id" in columns and not str(row["runtime_sender_id"] or "").strip():
                        updates["runtime_sender_id"] = runtime_sender_id
                if updates:
                    table_updates += 1
                    if apply:
                        assignments = ", ".join(f"{column} = ?" for column in updates)
                        conn.execute(
                            f"UPDATE {table} SET {assignments} WHERE rowid = ?",
                            (*updates.values(), row["__rowid"]),
                        )
            if table_updates:
                report["tables"].append({"table": table, "updated_rows": table_updates})
                report["updated_rows"] += table_updates
        if apply:
            conn.commit()
    return report


def _migrate_scheduler_tasks(
    tasks_path: str,
    room_mappings: Dict[str, Dict[str, str]],
    apply: bool,
) -> Dict[str, Any]:
    tasks_path = os.path.abspath(tasks_path)
    report = {"path": tasks_path, "updated_tasks": 0}
    if not os.path.exists(tasks_path):
        report["missing"] = True
        return report
    with open(tasks_path, "r", encoding="utf-8") as f:
        tasks = json.load(f)
    changed = False
    iterable = tasks.values() if isinstance(tasks, dict) else tasks
    for task in iterable:
        if not isinstance(task, dict):
            continue
        action = task.get("action") if isinstance(task.get("action"), dict) else task
        if str(action.get("channel_type") or "") != "wechat_group":
            continue
        runtime_receiver = str(action.get("runtime_receiver") or action.get("receiver") or "").strip()
        room = room_mappings.get(runtime_receiver)
        if not room:
            continue
        action["receiver_kind"] = "wechat_group"
        action["stable_receiver"] = room["stable_room_id"]
        action["runtime_receiver"] = runtime_receiver
        action["notify_session_id"] = "wechat_group:{}".format(room["stable_room_id"])
        changed = True
        report["updated_tasks"] += 1
    if apply and changed:
        _write_json(tasks_path, tasks)
    return report


def _build_manual_confirmation(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = []
    for room in report.get("rooms", []):
        if room.get("already_confirmed"):
            continue
        items.append({
            "entity_type": "room",
            "stable_room_id": room.get("stable_room_id", ""),
            "runtime_room_id": room.get("runtime_room_id", ""),
            "reason": "legacy_runtime_import_requires_first_relogin_confirmation",
        })
    for member in report.get("members", []):
        if member.get("already_confirmed"):
            continue
        items.append({
            "entity_type": "member",
            "stable_room_id": member.get("stable_room_id", ""),
            "stable_member_id": member.get("stable_member_id", ""),
            "runtime_sender_id": member.get("runtime_sender_id", ""),
            "reason": "legacy_member_import_requires_confirmation_before_sensitive_permission_inheritance",
        })
    return items


def _sqlite_tables(conn: sqlite3.Connection) -> Iterable[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'").fetchall()
    return [str(row[0]) for row in rows]


def _sqlite_columns(conn: sqlite3.Connection, table: str) -> List[str]:
    return [str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def _string_list(value: Any) -> List[str]:
    if isinstance(value, list):
        raw = value
    elif value is None:
        raw = []
    else:
        raw = str(value).replace("\n", ",").split(",")
    result = []
    for item in raw:
        text = str(item or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def _merge_string_lists(*values: Any) -> List[str]:
    merged: List[str] = []
    for value in values:
        for item in _string_list(value):
            if item not in merged:
                merged.append(item)
    return merged


def _find_missing_media(conn: sqlite3.Connection, db_path: str, table: str) -> List[Dict[str, Any]]:
    missing: List[Dict[str, Any]] = []
    rows = conn.execute(f"SELECT rowid AS __rowid, media_path FROM {table}").fetchall()
    for row in rows:
        media_path = str(row["media_path"] or "").strip()
        if not media_path or media_path.lower().startswith(("http://", "https://", "data:")):
            continue
        expanded_path = os.path.expanduser(media_path)
        resolved_path = (
            expanded_path
            if os.path.isabs(expanded_path)
            else os.path.abspath(os.path.join(os.path.dirname(db_path), expanded_path))
        )
        if os.path.exists(resolved_path):
            continue
        missing.append({
            "db_path": db_path,
            "table": table,
            "rowid": int(row["__rowid"]),
            "media_path": media_path,
            "resolved_path": resolved_path,
        })
    return missing


def _stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha1(str(value or "").encode("utf-8")).hexdigest()[:20]
    return f"{prefix}_{digest}"


def _member_key(runtime_room_id: str, runtime_sender_id: str) -> str:
    return "{}\n{}".format(str(runtime_room_id or "").strip(), str(runtime_sender_id or "").strip())


def _write_json(path: str, payload: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Migrate WeChat group runtime ids to stable identities.")
    parser.add_argument("--config", required=True, help="Path to config.json")
    parser.add_argument("--identity-db", default="", help="Path to wechat_group_identity.db")
    parser.add_argument("--sqlite-db", action="append", default=[], help="Wechat group SQLite db path; can be repeated")
    parser.add_argument("--scheduler-tasks", default="", help="Path to scheduler tasks.json")
    parser.add_argument("--apply", action="store_true", help="Write changes. Default is dry-run.")
    args = parser.parse_args(argv)
    report = run_migration(
        config_path=args.config,
        identity_db_path=args.identity_db,
        sqlite_paths=args.sqlite_db,
        scheduler_tasks_path=args.scheduler_tasks,
        apply=args.apply,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
