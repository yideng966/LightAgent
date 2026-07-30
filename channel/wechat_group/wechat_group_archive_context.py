"""Archive evidence helpers for WeChat group humanized context."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from channel.wechat_group.wechat_group_context import (
    build_safe_wechat_group_context_lines,
)


def build_archive_evidence_block(
    archive,
    room_id: str,
    query: str,
    now: int,
    days: int = 90,
    limit: int = 48,
    exclude_message_id: str = "",
    exclude_source_event_ids: Iterable[str] = (),
    max_chars: int = 3200,
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
    excluded_sources = {
        str(item or "").strip()
        for item in (exclude_source_event_ids or [])
        if str(item or "").strip()
    }
    if excluded_sources:
        rows = [
            row for row in rows
            if _source_event_id(row) not in excluded_sources
        ]
    lines = _bounded_lines(build_safe_wechat_group_context_lines(rows), max_chars)
    if not lines:
        return ""
    return "<wechat-group-archive-evidence>\n{}\n</wechat-group-archive-evidence>".format(
        "\n".join(lines)
    )


def _source_event_id(row: Dict[str, Any]) -> str:
    source_id = str(row.get("source_event_id") or "").strip()
    if source_id:
        return source_id
    try:
        return "inbound:{}".format(int(row.get("id") or 0))
    except (TypeError, ValueError):
        return ""


def _bounded_lines(lines: Iterable[str], max_chars: int) -> List[str]:
    limit = max(int(max_chars or 3200), 200)
    selected = []
    used = 0
    for line in lines or []:
        text = str(line or "").strip()
        if not text:
            continue
        addition = len(text) + (1 if selected else 0)
        if selected and used + addition > limit:
            break
        if not selected and addition > limit:
            text = text[:limit]
            addition = len(text)
        selected.append(text)
        used += addition
    return selected
