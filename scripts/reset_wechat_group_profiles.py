"""Rebuild the WeChat group profile database without migrating legacy profiles."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from contextlib import closing
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from channel.wechat_group.wechat_group_profile_store import WechatGroupProfileStore


PROFILE_DB_NAME = "wechat_group_profiles.db"
LEGACY_EVOLUTION_DB_NAME = "wechat_group_profile_evolution.db"
ARCHIVE_DB_NAME = "wechat_group_archive.db"
IDENTITY_DB_NAME = "wechat_group_identity.db"


def default_data_root() -> Path:
    return Path(os.environ.get("LIGHTAGENT_DATA_DIR") or Path.home() / ".lightagent").expanduser().resolve()


def reset_wechat_group_profiles(
    data_root: str,
    stable_room_ids: Optional[Iterable[str]] = None,
    config_path: str = "",
    apply: bool = False,
    timestamp: str = "",
) -> Dict[str, Any]:
    root = Path(data_root).expanduser().resolve()
    profile_dir = (root / "wechat_group").resolve()
    _require_child_path(root, profile_dir)
    profile_dir.mkdir(parents=True, exist_ok=True)

    profile_path = profile_dir / PROFILE_DB_NAME
    legacy_evolution_path = profile_dir / LEGACY_EVOLUTION_DB_NAME
    archive_path = profile_dir / ARCHIVE_DB_NAME
    identity_path = profile_dir / IDENTITY_DB_NAME
    selected_rooms = _resolve_stable_room_ids(root, stable_room_ids, config_path)
    if apply and not selected_rooms:
        raise ValueError("at least one stable room id is required when applying profile reset")
    archive_high_water = {
        room_id: _archive_high_water(archive_path, room_id)
        for room_id in selected_rooms
    }
    report: Dict[str, Any] = {
        "status": "planned" if not apply else "running",
        "data_root": str(root),
        "profile_path": str(profile_path),
        "legacy_evolution_path": str(legacy_evolution_path),
        "stable_room_ids": selected_rooms,
        "archive_high_water": archive_high_water,
        "backup_dir": "",
        "integrity_check": "",
        "table_counts": {},
    }
    if not apply:
        return report

    stamp = timestamp or time.strftime("%Y%m%d_%H%M%S")
    backup_dir = (profile_dir / "profile-reset-backups" / stamp).resolve()
    _require_child_path(profile_dir, backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=False)
    report["backup_dir"] = str(backup_dir)

    for source in (profile_path, legacy_evolution_path, identity_path):
        if source.exists():
            _sqlite_backup(source, backup_dir / f"{source.stem}.sqlite-backup.db")

    next_path = profile_dir / f"{PROFILE_DB_NAME}.next"
    _require_child_path(profile_dir, next_path)
    if next_path.exists():
        next_path.unlink()
    next_store = WechatGroupProfileStore(str(next_path))
    for room_id, row_id in archive_high_water.items():
        for pipeline in ("heuristic", "evolution"):
            next_store.update_learning_state(
                room_id,
                pipeline=pipeline,
                last_archive_row_id=row_id,
                latest_observed_row_id=row_id,
                running=False,
            )

    integrity = next_store.integrity_check()
    counts = next_store.table_counts()
    _validate_new_store(counts, len(selected_rooms), integrity)
    report["integrity_check"] = integrity
    report["table_counts"] = counts

    moved_profile = None
    moved_evolution = None
    moved_profile_sidecars: List[tuple[Path, Path]] = []
    moved_evolution_sidecars: List[tuple[Path, Path]] = []
    try:
        if profile_path.exists():
            moved_profile = backup_dir / f"{PROFILE_DB_NAME}.retired"
            os.replace(profile_path, moved_profile)
        moved_profile_sidecars = _move_sqlite_sidecars(profile_path, backup_dir)
        if legacy_evolution_path.exists():
            moved_evolution = backup_dir / f"{LEGACY_EVOLUTION_DB_NAME}.retired"
            os.replace(legacy_evolution_path, moved_evolution)
        moved_evolution_sidecars = _move_sqlite_sidecars(legacy_evolution_path, backup_dir)
        os.replace(next_path, profile_path)
        final_store = WechatGroupProfileStore(str(profile_path))
        final_integrity = final_store.integrity_check()
        final_counts = final_store.table_counts()
        _validate_new_store(final_counts, len(selected_rooms), final_integrity)
    except Exception:
        if profile_path.exists() and moved_profile is not None:
            profile_path.unlink()
        if moved_profile is not None and moved_profile.exists():
            os.replace(moved_profile, profile_path)
        _restore_sidecars(moved_profile_sidecars)
        if moved_evolution is not None and moved_evolution.exists():
            os.replace(moved_evolution, legacy_evolution_path)
        _restore_sidecars(moved_evolution_sidecars)
        raise

    retired_evolution = str(moved_evolution) if moved_evolution is not None else ""
    report.update({
        "status": "success",
        "integrity_check": final_integrity,
        "table_counts": final_counts,
        "retired_evolution_path": retired_evolution,
    })
    manifest_path = backup_dir / "reset-manifest.json"
    manifest_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["manifest_path"] = str(manifest_path)
    return report


def _resolve_stable_room_ids(
    data_root: Path,
    stable_room_ids: Optional[Iterable[str]],
    config_path: str,
) -> List[str]:
    explicit = _dedupe(stable_room_ids or [])
    if explicit:
        return explicit
    candidates = []
    if config_path:
        candidates.append(Path(config_path).expanduser().resolve())
    candidates.append(data_root / "config.json")
    for candidate in candidates:
        if not candidate.exists():
            continue
        with candidate.open("r", encoding="utf-8-sig") as handle:
            config = json.load(handle)
        return _dedupe(config.get("wechat_group_stable_room_ids") or [])
    return []


def _archive_high_water(archive_path: Path, stable_room_id: str) -> int:
    if not archive_path.exists():
        return 0
    uri = archive_path.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as conn:
        tables = {str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        if "wechat_group_messages" not in tables:
            return 0
        columns = {
            str(row[1])
            for row in conn.execute("PRAGMA table_info(wechat_group_messages)").fetchall()
        }
        if "stable_room_id" in columns:
            row = conn.execute(
                """
                SELECT COALESCE(MAX(id), 0) FROM wechat_group_messages
                WHERE stable_room_id = ? OR room_id = ?
                """,
                (stable_room_id, stable_room_id),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT COALESCE(MAX(id), 0) FROM wechat_group_messages WHERE room_id = ?",
                (stable_room_id,),
            ).fetchone()
    return int(row[0] or 0) if row else 0


def _sqlite_backup(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(str(source))) as source_conn, closing(sqlite3.connect(str(destination))) as dest_conn:
        source_conn.backup(dest_conn)


def _move_sqlite_sidecars(database_path: Path, backup_dir: Path) -> List[tuple[Path, Path]]:
    moved = []
    for suffix in ("-wal", "-shm", "-journal"):
        source = Path(str(database_path) + suffix)
        if not source.exists():
            continue
        destination = backup_dir / f"{database_path.name}{suffix}.retired"
        os.replace(source, destination)
        moved.append((source, destination))
    return moved


def _restore_sidecars(moved: List[tuple[Path, Path]]) -> None:
    for source, destination in moved:
        if destination.exists():
            os.replace(destination, source)


def _validate_new_store(counts: Dict[str, int], room_count: int, integrity: str) -> None:
    if integrity.lower() != "ok":
        raise RuntimeError(f"new profile database integrity check failed: {integrity}")
    for table in (
        "wechat_group_member_profiles",
        "wechat_group_member_profile_names",
        "wechat_group_member_profile_claims",
        "wechat_group_member_profile_revisions",
        "wechat_group_member_profile_runs",
    ):
        if int(counts.get(table) or 0) != 0:
            raise RuntimeError(f"new profile database is not empty: {table}")
    expected_states = room_count * 2
    if int(counts.get("wechat_group_member_profile_learning_state") or 0) != expected_states:
        raise RuntimeError("new profile database learning baselines are incomplete")


def _require_child_path(parent: Path, child: Path) -> None:
    try:
        common = Path(os.path.commonpath([str(parent), str(child)]))
    except ValueError as exc:
        raise ValueError("target path is outside data root") from exc
    if common != parent:
        raise ValueError("target path is outside data root")


def _dedupe(values: Iterable[Any]) -> List[str]:
    result = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", default=str(default_data_root()))
    parser.add_argument("--config-path", default="")
    parser.add_argument("--stable-room-id", action="append", default=[])
    parser.add_argument("--apply", action="store_true", help="Apply backups and replace the profile database")
    args = parser.parse_args()
    report = reset_wechat_group_profiles(
        data_root=args.data_root,
        stable_room_ids=args.stable_room_id,
        config_path=args.config_path,
        apply=args.apply,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
