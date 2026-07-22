from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agent.chat.history_migration import run_legacy_chat_history_migration
from agent.memory.config import get_default_memory_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Migrate legacy BaiLongmaPro chat history into LightAgent conversation store.",
    )
    parser.add_argument(
        "--source-db",
        required=True,
        help="Path to the legacy BaiLongmaPro jarvis.db file.",
    )
    parser.add_argument(
        "--target-db",
        default=str(get_default_memory_config().get_db_path()),
        help="Path to the LightAgent target SQLite DB. Defaults to the current conversation store.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write changes to the target DB. Omit this flag to run a dry-run.",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip backup creation before writing.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    result = run_legacy_chat_history_migration(
        source_db_path=Path(args.source_db),
        target_db_path=Path(args.target_db),
        dry_run=not args.apply,
        create_backup=not args.no_backup,
    )
    print(json.dumps({
        "dry_run": result.dry_run,
        "source_row_count": result.source_row_count,
        "session_count": result.imported_sessions,
        "message_count": result.imported_messages,
        "backup_path": result.backup_path,
        "session_ids": result.session_ids,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
