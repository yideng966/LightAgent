"""Archive evidence helpers for WeChat group humanized context."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from channel.wechat_group.wechat_group_context import build_safe_wechat_group_context_lines
from channel.wechat_group.wechat_group_transport import project_wechat_message_type


def build_archive_evidence_block(
    archive,
    room_id: str,
    query: str,
    now: int,
    days: int = 90,
    limit: int = 48,
    recent_limit: int = 16,
    exclude_message_id: str = "",
) -> str:
    if not archive or not room_id:
        return ""
    rows = archive.search_messages(
        room_id,
        query=query,
        since_ts=int(now or 0) - max(int(days or 90), 1) * 86400,
        until_ts=now,
        limit=limit,
        exclude_message_id=exclude_message_id,
    )
    if recent_limit and len(rows) < min(int(limit or 48), 100):
        rows = _append_recent_fallback(
            rows,
            archive.get_recent_messages(
                room_id,
                limit=max(int(recent_limit or 0), 0),
                minutes=max(int(days or 90), 1) * 1440,
                now=now,
            ),
            limit=limit,
            exclude_message_id=exclude_message_id,
        )
    lines = build_safe_wechat_group_context_lines(rows)
    if not lines:
        return ""
    return "<wechat-group-archive-evidence>\n{}\n</wechat-group-archive-evidence>".format(
        "\n".join(lines)
    )


def build_local_extractive_summary_block(
    archive,
    room_id: str,
    now: int,
    hours: int = 24,
    limit: int = 100,
    exclude_message_id: str = "",
) -> str:
    if not archive or not room_id:
        return ""
    rows = archive.get_messages_for_distill(
        room_id,
        since_ts=int(now or 0) - max(int(hours or 24), 1) * 3600,
        until_ts=now,
        limit=min(max(int(limit or 100), 1), 500),
    )
    excluded = str(exclude_message_id or "").strip()
    lines = []
    for row in rows:
        if excluded and str(row.get("message_id") or "") == excluded:
            continue
        if project_wechat_message_type(row.get("message_type") or "text", row.get("text")) != "text":
            continue
        text = str(row.get("text") or "").strip()
        if not text:
            continue
        sender = str(row.get("sender_nickname") or row.get("sender_id") or "unknown").strip()
        lines.append("{}: {}".format(sender, " ".join(text.split())))
    if not lines:
        return ""
    return "<local-extractive-summary>\n{}\n</local-extractive-summary>".format(
        "\n".join(lines)
    )


def _append_recent_fallback(
    rows: Iterable[Dict[str, Any]],
    recent_rows: Iterable[Dict[str, Any]],
    limit: int,
    exclude_message_id: str = "",
) -> List[Dict[str, Any]]:
    max_limit = min(max(int(limit or 48), 1), 100)
    excluded = str(exclude_message_id or "").strip()
    merged = []
    seen = set()
    for row in list(rows or []) + list(recent_rows or []):
        message_id = str(row.get("message_id") or "").strip()
        if excluded and message_id == excluded:
            continue
        if message_id and message_id in seen:
            continue
        if message_id:
            seen.add(message_id)
        merged.append(row)
        if len(merged) >= max_limit:
            break
    merged.sort(key=lambda item: (int(item.get("created_at") or 0), int(item.get("id") or 0)))
    return merged
