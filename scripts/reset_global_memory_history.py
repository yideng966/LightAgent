"""Reset shared memory and self-evolution history without touching scoped data."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import sys
from contextlib import closing
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def reset_global_memory_history(workspace: str, apply: bool = False) -> Dict[str, Any]:
    root = Path(workspace).expanduser().resolve()
    _validate_workspace(root)
    memory_dir = (root / "memory").resolve()
    _require_child_path(root, memory_dir)
    db_path = memory_dir / "long-term" / "index.db"
    targets = _collect_global_memory_targets(root, memory_dir)
    shared_chunk_count, shared_paths = _inspect_shared_memory_chunks(db_path)
    evolution_refs = _find_evolution_message_refs(db_path)

    report: Dict[str, Any] = {
        "status": "planned" if not apply else "running",
        "workspace": str(root),
        "index_db": str(db_path),
        "memory_file": str(root / "MEMORY.md"),
        "planned_paths": [str(path.relative_to(root)) for path in targets],
        "planned_file_count": len(targets) + 1,
        "shared_memory_chunk_count": shared_chunk_count,
        "shared_memory_index_paths": sorted(shared_paths),
        "evolution_message_count": len(evolution_refs),
        "deleted_path_count": 0,
        "deleted_shared_chunk_count": 0,
        "deleted_evolution_message_count": 0,
    }
    if not apply:
        return report

    from agent.prompt.workspace import _get_memory_template

    (root / "MEMORY.md").write_text(_get_memory_template(), encoding="utf-8")
    deleted_paths = 0
    for target in targets:
        if target.is_dir():
            shutil.rmtree(target)
            deleted_paths += 1
        elif target.exists():
            target.unlink()
            deleted_paths += 1

    deleted_chunks, deleted_messages = _clean_index_and_evolution_messages(
        db_path,
        shared_paths=shared_paths,
        evolution_refs=evolution_refs,
    )
    report.update({
        "status": "success",
        "deleted_path_count": deleted_paths,
        "deleted_shared_chunk_count": deleted_chunks,
        "deleted_evolution_message_count": deleted_messages,
    })
    return report


def _collect_global_memory_targets(root: Path, memory_dir: Path) -> List[Path]:
    targets: List[Path] = []
    if memory_dir.exists():
        for path in sorted(memory_dir.glob("*.md"), key=lambda item: item.name):
            resolved = path.resolve()
            _require_child_path(root, resolved)
            targets.append(resolved)
        for name in ("shared", "dreams", "evolution", ".evolution_backups"):
            path = (memory_dir / name).resolve()
            _require_child_path(root, path)
            if path.exists():
                targets.append(path)
    return targets


def _inspect_shared_memory_chunks(db_path: Path) -> Tuple[int, Set[str]]:
    if not db_path.exists():
        return 0, set()
    with closing(sqlite3.connect(str(db_path))) as conn:
        if not _table_exists(conn, "chunks"):
            return 0, set()
        columns = _table_columns(conn, "chunks")
        condition = _shared_memory_condition(columns)
        rows = conn.execute(
            f"SELECT path FROM chunks WHERE {condition}"
        ).fetchall()
    return len(rows), {str(row[0] or "") for row in rows if str(row[0] or "")}


def _find_evolution_message_refs(db_path: Path) -> Set[Tuple[str, int]]:
    if not db_path.exists():
        return set()
    with closing(sqlite3.connect(str(db_path))) as conn:
        if not _table_exists(conn, "messages"):
            return set()
        rows = conn.execute(
            "SELECT session_id, seq, role, content FROM messages ORDER BY session_id, seq"
        ).fetchall()

    refs: Set[Tuple[str, int]] = set()
    previous: Dict[str, Tuple[int, str, str]] = {}
    for session_id, seq, role, raw_content in rows:
        session = str(session_id or "")
        text = _extract_message_text(raw_content)
        if str(role or "") == "assistant" and text.lstrip().startswith("[EVOLUTION]"):
            refs.add((session, int(seq)))
            prior = previous.get(session)
            if prior and prior[1] == "user" and _is_evolution_schedule_marker(prior[2]):
                refs.add((session, prior[0]))
        previous[session] = (int(seq), str(role or ""), text)
    return refs


def _clean_index_and_evolution_messages(
    db_path: Path,
    *,
    shared_paths: Iterable[str],
    evolution_refs: Iterable[Tuple[str, int]],
) -> Tuple[int, int]:
    if not db_path.exists():
        return 0, 0
    deleted_chunks = 0
    deleted_messages = 0
    with closing(sqlite3.connect(str(db_path), timeout=10)) as conn:
        with conn:
            if _table_exists(conn, "chunks"):
                columns = _table_columns(conn, "chunks")
                cursor = conn.execute(
                    f"DELETE FROM chunks WHERE {_shared_memory_condition(columns)}"
                )
                deleted_chunks = max(int(cursor.rowcount or 0), 0)
            paths = {str(path or "") for path in shared_paths if str(path or "")}
            if _table_exists(conn, "files"):
                paths.update(
                    str(row[0] or "")
                    for row in conn.execute(
                        "SELECT path FROM files WHERE source = 'memory'"
                    ).fetchall()
                    if _is_global_memory_index_path(row[0])
                )
            paths = sorted(paths)
            if paths and _table_exists(conn, "files"):
                placeholders = ",".join("?" for _ in paths)
                conn.execute(
                    f"DELETE FROM files WHERE path IN ({placeholders})",
                    paths,
                )

            refs_by_session: Dict[str, List[int]] = {}
            for session_id, seq in evolution_refs:
                refs_by_session.setdefault(str(session_id), []).append(int(seq))
            if refs_by_session and _table_exists(conn, "messages"):
                for session_id, seqs in refs_by_session.items():
                    unique_seqs = sorted(set(seqs))
                    placeholders = ",".join("?" for _ in unique_seqs)
                    cursor = conn.execute(
                        f"DELETE FROM messages WHERE session_id = ? AND seq IN ({placeholders})",
                        (session_id, *unique_seqs),
                    )
                    deleted_messages += max(int(cursor.rowcount or 0), 0)
                    if _table_exists(conn, "sessions"):
                        conn.execute(
                            """
                            UPDATE sessions
                            SET msg_count = (
                                SELECT COUNT(*) FROM messages WHERE session_id = ?
                            )
                            WHERE session_id = ?
                            """,
                            (session_id, session_id),
                        )
    return deleted_chunks, deleted_messages


def _shared_memory_condition(columns: Set[str]) -> str:
    source_clause = "source = 'memory'" if "source" in columns else "1 = 1"
    user_clause = "COALESCE(user_id, '') = ''" if "user_id" in columns else "1 = 1"
    if "scope_type" in columns and "scope" in columns:
        scope_clause = "COALESCE(NULLIF(scope_type, ''), scope, 'shared') = 'shared'"
    elif "scope_type" in columns:
        scope_clause = "COALESCE(NULLIF(scope_type, ''), 'shared') = 'shared'"
    elif "scope" in columns:
        scope_clause = "COALESCE(scope, 'shared') = 'shared'"
    else:
        scope_clause = "1 = 1"
    return f"{source_clause} AND {user_clause} AND {scope_clause}"


def _is_global_memory_index_path(value: Any) -> bool:
    path = str(value or "").replace("\\", "/").strip("/")
    if path == "MEMORY.md":
        return True
    if not path.startswith("memory/"):
        return False
    relative = path[len("memory/"):]
    if "/" not in relative and relative.lower().endswith(".md"):
        return True
    return relative.startswith(("shared/", "dreams/", "evolution/", ".evolution_backups/"))


def _extract_message_text(raw_content: Any) -> str:
    try:
        content = json.loads(raw_content) if isinstance(raw_content, str) else raw_content
    except Exception:
        content = raw_content
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return "\n".join(
            str(block.get("text") or "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ).strip()
    return ""


def _is_evolution_schedule_marker(text: str) -> bool:
    value = str(text or "").strip().lower()
    return (
        value.startswith("[scheduled] self-evolution")
        or value.startswith("scheduled task self-evolution")
    )


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return bool(row)


def _table_columns(conn: sqlite3.Connection, table: str) -> Set[str]:
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _validate_workspace(root: Path) -> None:
    if not root.exists() or not root.is_dir():
        raise ValueError("workspace must be an existing directory")
    if root.parent == root:
        raise ValueError("filesystem root cannot be used as workspace")


def _require_child_path(parent: Path, child: Path) -> None:
    try:
        common = Path(os.path.commonpath([str(parent), str(child)]))
    except ValueError as exc:
        raise ValueError("target path is outside workspace") from exc
    if common != parent:
        raise ValueError("target path is outside workspace")


def _default_workspace() -> str:
    from common.utils import expand_path
    from config import conf, load_config

    load_config()
    return str(Path(expand_path(conf().get("agent_workspace", "~/lightagent"))).resolve())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default="")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    report = reset_global_memory_history(
        workspace=args.workspace or _default_workspace(),
        apply=bool(args.apply),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
