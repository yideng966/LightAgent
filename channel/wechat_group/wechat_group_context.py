"""Prompt context helpers for the WeChat group channel."""

import time
from typing import Any, Dict, Iterable

from channel.wechat_group.wechat_group_transport import project_wechat_message_type


def build_wechat_group_recent_context_block(
    archive,
    room_id: str,
    limit: int = 20,
    minutes: int = 60,
    now: int = None,
) -> str:
    rows = archive.get_recent_messages(room_id, limit=limit, minutes=minutes, now=now)
    return build_wechat_group_recent_context_block_from_rows(rows)


def build_wechat_group_recent_context_block_from_rows(rows: Iterable[Dict[str, Any]]) -> str:
    rows = list(rows or [])
    if not rows:
        return ""
    lines = [_format_recent_context_line(row) for row in rows]
    lines = [line for line in lines if line]
    if not lines:
        return ""
    return "<recent-wechat-group-transcript>\n{}\n</recent-wechat-group-transcript>".format(
        "\n".join(lines)
    )


def build_safe_wechat_group_recent_context_block_from_rows(rows: Iterable[Dict[str, Any]]) -> str:
    lines = build_safe_wechat_group_context_lines(rows)
    if not lines:
        return ""
    return "<recent-wechat-group-transcript>\n{}\n</recent-wechat-group-transcript>".format(
        "\n".join(lines)
    )


def build_safe_wechat_group_context_lines(rows: Iterable[Dict[str, Any]]) -> list:
    result = []
    for row in rows or []:
        line = _format_safe_recent_context_line(row)
        if line:
            result.append(line)
    return result


def _format_recent_context_line(row: Dict[str, Any]) -> str:
    timestamp = _format_timestamp(row.get("created_at"))
    msg_type = project_wechat_message_type(row.get("message_type") or "text", row.get("text"))
    sender = str(row.get("sender_nickname") or row.get("sender_id") or "unknown")
    summary = _summarize_message(row)
    if not summary:
        return ""
    return "{} [{}] {}: {}".format(timestamp, msg_type, sender, summary).strip()


def _format_safe_recent_context_line(row: Dict[str, Any]) -> str:
    timestamp = _format_timestamp(row.get("created_at"))
    msg_type = project_wechat_message_type(row.get("message_type") or "text", row.get("text"))
    sender = _sanitize_prompt_text(str(row.get("sender_nickname") or row.get("sender_id") or "unknown"), 80)
    summary = _summarize_message_safe(row)
    if not summary:
        return ""
    return "{} [{}] {}: {}".format(timestamp, msg_type, sender, summary).strip()


def _format_timestamp(value: Any) -> str:
    try:
        return time.strftime("%m-%d %H:%M", time.localtime(int(value)))
    except Exception:
        return ""


def _summarize_message(row: Dict[str, Any], max_length: int = 160) -> str:
    msg_type = project_wechat_message_type(row.get("message_type") or "text", row.get("text"))
    if msg_type and msg_type != "text":
        message_id = str(row.get("message_id") or "").strip()
        if message_id:
            return "[{} message_id={}]".format(msg_type, message_id)
        return "[{} message]".format(msg_type)
    text = str(row.get("text") or "").replace("\r\n", "\n").replace("\r", "\n")
    text = " ".join(text.split())
    if not text:
        text = "[{} message]".format(row.get("message_type") or "unknown")
    if len(text) <= max_length:
        return text
    return text[: max_length - 1].rstrip() + "..."


def _summarize_message_safe(row: Dict[str, Any], max_length: int = 160) -> str:
    msg_type = project_wechat_message_type(row.get("message_type") or "text", row.get("text"))
    if msg_type and msg_type != "text":
        return "[{} message]".format(msg_type)
    text = _sanitize_prompt_text(row.get("text"), max_length)
    if not text:
        return "[{} message]".format(row.get("message_type") or "unknown")
    return text


def _sanitize_prompt_text(value: Any, max_length: int = 160) -> str:
    import re

    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"<[^>]{1,200}>", "", text)
    text = text.replace("<", "").replace(">", "")
    text = " ".join(text.split())
    text = _strip_local_paths(text)
    text = _strip_base64_like_chunks(text)
    if len(text) <= max_length:
        return text
    return text[: max_length - 1].rstrip() + "..."


def _strip_local_paths(text: str) -> str:
    import re

    return re.sub(
        r"(?i)(?:[a-z]:[\\/]|file://|/users/|/home/|\\\\)[^\s]+",
        "[local-path]",
        text,
    )


def _strip_base64_like_chunks(text: str) -> str:
    import re

    return re.sub(r"\b[A-Za-z0-9+/]{80,}={0,2}\b", "[base64]", text)
