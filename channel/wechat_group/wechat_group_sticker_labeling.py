"""Shared semantic labeling helpers for WeChat group stickers."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import os
import re
import sqlite3
import tempfile
import time
from typing import Any, Callable, Dict, List, Optional

from agent.tools.vision.vision import Vision
from channel.wechat_group.wechat_group_transport import is_wechat_transport_xml


LABEL_QUESTION = (
    "这是一张群聊表情包。只输出一条10到30字的中文短语，不换行、不加引号，"
    "按‘主体+动作或表情+表达的情绪或意图’描述；如果图片含文字，保留最关键文字。"
    "忽略文件名，不解释分析过程。"
)

_PLACEHOLDER_DESCRIPTIONS = frozenset({
    "表情包",
    "群聊表情包",
    "微信表情包",
    "emoji",
    "sticker",
    "wechat sticker",
})


def default_sticker_db_path() -> str:
    data_root = os.environ.get("LIGHTAGENT_DATA_DIR") or os.path.join(os.path.expanduser("~"), ".lightagent")
    return os.path.join(os.path.expanduser(data_root), "wechat_group", "wechat_group_sticker.db")


def is_sticker_transport_description(value: Any) -> bool:
    text = str(value or "").strip()
    if is_wechat_transport_xml(text):
        return True
    lowered = text.lower()
    return "<msg" in lowered and "<emoji" in lowered


def is_opaque_sticker_description(value: Any) -> bool:
    text = str(value or "").strip().lower()
    if text.isdigit():
        return True
    return len(text) >= 24 and all(char in "0123456789abcdef" for char in text)


def is_pending_sticker_description(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(
        not text
        or text.lower() in _PLACEHOLDER_DESCRIPTIONS
        or is_sticker_transport_description(text)
        or is_opaque_sticker_description(text)
    )


def description_matches_type(value: Any, description_type: str) -> bool:
    kind = str(description_type or "xml").strip().lower()
    if kind == "xml":
        return is_sticker_transport_description(value)
    if kind == "opaque":
        return is_opaque_sticker_description(value)
    if kind == "all":
        return is_sticker_transport_description(value) or is_opaque_sticker_description(value)
    if kind == "pending":
        return is_pending_sticker_description(value)
    raise ValueError("unsupported description type: {}".format(description_type))


def normalize_manual_description(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if not text or len(text) > 200:
        raise ValueError("description must be between 1 and 200 characters")
    if is_pending_sticker_description(text):
        raise ValueError("description must contain semantic content")
    return text


def normalize_semantic_label(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"^```(?:json|text)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    text = text.splitlines()[0].strip() if text else ""
    text = re.sub(r"^(?:描述|标签|语义)\s*[:：]\s*", "", text)
    text = text.strip(" \t\r\n'\"`“”‘’")
    text = re.sub(r"\s+", " ", text)
    rejected_markers = (
        "只输出",
        "忽略文件名",
        "主体+动作",
        "这是一个表情包",
        "这是一张表情包",
        "这是一张群聊表情包",
        "表情丰富，表情丰富",
        "你正在扮演",
        "用户发来一张",
        "角色：",
    )
    if (
        not text
        or len(text) > 45
        or is_pending_sticker_description(text)
        or "**" in text
        or any(marker in text for marker in rejected_markers)
    ):
        return ""
    return text


def vision_label(image_path: str, vision: Optional[Vision] = None) -> str:
    prepared_path, cleanup_path = prepare_sticker_image(image_path)
    try:
        result = (vision or Vision()).execute({"image": prepared_path, "question": LABEL_QUESTION})
        if getattr(result, "status", "") != "success":
            return ""
        payload = getattr(result, "result", {}) or {}
        content = payload.get("content", "") if isinstance(payload, dict) else payload
        return normalize_semantic_label(content)
    finally:
        if cleanup_path and os.path.isfile(cleanup_path):
            os.remove(cleanup_path)


def prepare_sticker_image(image_path: str):
    if os.path.splitext(image_path)[1].lower() != ".gif":
        return image_path, ""
    from PIL import Image

    with Image.open(image_path) as source:
        frame_count = max(int(getattr(source, "n_frames", 1) or 1), 1)
        indexes = sorted({0, frame_count // 3, (frame_count * 2) // 3, frame_count - 1})
        frames = []
        for index in indexes:
            source.seek(index)
            frame = source.convert("RGBA")
            frame.thumbnail((512, 512))
            frames.append(frame.copy())
    width = max(frame.width for frame in frames)
    height = max(frame.height for frame in frames)
    columns = 2 if len(frames) > 1 else 1
    rows = (len(frames) + columns - 1) // columns
    canvas = Image.new("RGBA", (width * columns, height * rows), "white")
    for index, frame in enumerate(frames):
        x = (index % columns) * width + (width - frame.width) // 2
        y = (index // columns) * height + (height - frame.height) // 2
        canvas.alpha_composite(frame, (x, y))
    target = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    target.close()
    try:
        canvas.convert("RGB").save(target.name, format="PNG")
    except Exception:
        if os.path.isfile(target.name):
            os.remove(target.name)
        raise
    return target.name, target.name


def backup_database(db_path: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup_path = "{}.semantic-labels.{}.bak".format(db_path, timestamp)
    source = sqlite3.connect(db_path)
    target = sqlite3.connect(backup_path)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    return backup_path


def find_legacy_stickers(
    conn: sqlite3.Connection,
    limit: int = 0,
    description_type: str = "xml",
    room_id: str = "",
) -> List[Dict[str, Any]]:
    columns = _table_columns(conn)
    room_text = str(room_id or "").strip()
    if room_text and "room_id" not in columns:
        raise ValueError("room_id filtering is not supported by this sticker database")
    selected_columns = ["sticker_id", "media_path", "description"]
    if "room_id" in columns:
        selected_columns.append("room_id")
    clauses = ["status = 'active'"]
    params = []
    if room_text:
        clauses.append("room_id = ?")
        params.append(room_text)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT {} FROM wechat_group_stickers WHERE {} ORDER BY sticker_id".format(
            ", ".join(selected_columns),
            " AND ".join(clauses),
        ),
        params,
    ).fetchall()
    selected = [dict(row) for row in rows if description_matches_type(row["description"], description_type)]
    if limit > 0:
        selected = selected[: int(limit)]
    return selected


def inspect_labeling_candidates(
    db_path: str,
    room_id: str = "",
    description_type: str = "pending",
    limit: int = 0,
) -> Dict[str, Any]:
    path = _resolve_db_path(db_path)
    conn = sqlite3.connect(path, timeout=30)
    try:
        rows = find_legacy_stickers(
            conn,
            limit=limit,
            description_type=description_type,
            room_id=room_id,
        )
        report, _ = _partition_candidates(rows)
        return report
    finally:
        conn.close()


def run_labeling(
    db_path: str,
    apply: bool = False,
    limit: int = 0,
    delay_seconds: float = 0.5,
    description_type: str = "xml",
    workers: int = 1,
    labeler: Callable[[str], str] = vision_label,
    room_id: str = "",
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    progress_output: bool = True,
) -> Dict[str, Any]:
    path = _resolve_db_path(db_path)
    conn = sqlite3.connect(path, timeout=30)
    report = {}
    try:
        rows = find_legacy_stickers(
            conn,
            limit=limit,
            description_type=description_type,
            room_id=room_id,
        )
        report, pending = _partition_candidates(rows)
        report.update({
            "apply": bool(apply),
            "backup_path": "",
            "processed": 0,
            "updated": 0,
            "failed": 0,
            "skipped_changed": 0,
        })
        if not apply:
            return report
        report["backup_path"] = backup_database(path)
        _notify_progress(progress_callback, report)
        columns = _table_columns(conn)

        def apply_label(row, label):
            if not label:
                report["failed"] += 1
                return
            updated = _update_description_if_unchanged(conn, columns, row, label)
            if updated:
                report["updated"] += 1
            else:
                report["skipped_changed"] += 1

        max_workers = min(max(int(workers or 1), 1), 4)
        if max_workers == 1:
            for row, image_path in pending:
                try:
                    label = normalize_semantic_label(labeler(image_path))
                except Exception:
                    label = ""
                report["processed"] += 1
                apply_label(row, label)
                _report_progress(report, progress_callback, progress_output)
                if delay_seconds > 0:
                    time.sleep(delay_seconds)
            return report

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(labeler, image_path): row for row, image_path in pending}
            for future in as_completed(futures):
                row = futures[future]
                try:
                    label = normalize_semantic_label(future.result())
                except Exception:
                    label = ""
                report["processed"] += 1
                apply_label(row, label)
                _report_progress(report, progress_callback, progress_output)
                if delay_seconds > 0:
                    time.sleep(delay_seconds)
        return report
    finally:
        conn.close()


def _resolve_db_path(db_path: str) -> str:
    path = os.path.abspath(os.path.expanduser(db_path))
    if not os.path.isfile(path):
        raise FileNotFoundError("sticker database not found: {}".format(path))
    return path


def _table_columns(conn: sqlite3.Connection):
    return {str(row[1]) for row in conn.execute("PRAGMA table_info(wechat_group_stickers)").fetchall()}


def _partition_candidates(rows):
    report = {
        "candidates": len(rows),
        "pending": len(rows),
        "processable": 0,
        "missing_files": 0,
        "empty_files": 0,
    }
    pending = []
    for row in rows:
        image_path = str(row.get("media_path") or "").strip()
        if not image_path or not os.path.isfile(image_path):
            report["missing_files"] += 1
            continue
        try:
            file_size = os.path.getsize(image_path)
        except OSError:
            report["missing_files"] += 1
            continue
        if file_size <= 0:
            report["empty_files"] += 1
            continue
        pending.append((row, image_path))
    report["processable"] = len(pending)
    return report, pending


def _update_description_if_unchanged(conn, columns, row, label):
    set_clause = "description = ?"
    params = [label]
    if "updated_at" in columns:
        set_clause += ", updated_at = ?"
        params.append(int(time.time()))
    clauses = ["sticker_id = ?", "description = ?"]
    params.extend([row["sticker_id"], row["description"]])
    if row.get("room_id") and "room_id" in columns:
        clauses.append("room_id = ?")
        params.append(row["room_id"])
    with conn:
        cursor = conn.execute(
            "UPDATE wechat_group_stickers SET {} WHERE {}".format(set_clause, " AND ".join(clauses)),
            params,
        )
    return int(cursor.rowcount or 0)


def _report_progress(report, callback, write_stdout):
    if write_stdout:
        print("[{}/{}] processed".format(report["processed"], report["processable"]), flush=True)
    _notify_progress(callback, report)


def _notify_progress(callback, report):
    if not callback:
        return
    try:
        callback(dict(report))
    except Exception:
        pass
