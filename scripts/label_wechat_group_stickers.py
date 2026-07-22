"""Generate semantic descriptions for legacy WeChat group stickers."""

from __future__ import annotations

import argparse
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from channel.wechat_group.wechat_group_sticker_labeling import (
    LABEL_QUESTION,
    backup_database,
    default_sticker_db_path,
    description_matches_type,
    find_legacy_stickers,
    normalize_semantic_label,
    prepare_sticker_image,
    run_labeling,
    vision_label,
)

default_db_path = default_sticker_db_path
_description_matches_type = description_matches_type


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=default_db_path(), help="Path to wechat_group_sticker.db")
    parser.add_argument("--apply", action="store_true", help="Call Vision and update successful labels")
    parser.add_argument("--limit", type=int, default=0, help="Maximum rows to process; 0 means all")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between successful calls")
    parser.add_argument(
        "--description-type",
        choices=("xml", "opaque", "all", "pending"),
        default="xml",
        help="Descriptions to process; pending also includes empty and placeholder descriptions",
    )
    parser.add_argument("--workers", type=int, default=1, help="Concurrent Vision calls (1-4)")
    parser.add_argument("--room-id", default="", help="Optional stable room id filter")
    args = parser.parse_args()
    if args.apply:
        from config import load_config

        load_config()
    report = run_labeling(
        args.db,
        apply=args.apply,
        limit=max(args.limit, 0),
        delay_seconds=max(args.delay, 0),
        description_type=args.description_type,
        workers=min(max(args.workers, 1), 4),
        room_id=str(args.room_id or "").strip(),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not args.apply:
        return 0
    return 0 if report["failed"] == 0 and report["missing_files"] == 0 and report["empty_files"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
