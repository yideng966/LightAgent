"""Prompt context helpers for the WeChat group channel."""

import time
import re
from typing import Any, Dict, Iterable

from channel.wechat_group.wechat_group_transport import project_wechat_message_type


_TRANSPORT_PAYLOAD_RE = re.compile(
    r"(?is)^\s*(?:<\?xml\b[^>]*>\s*)?<(?:msg|appmsg|img|emoji|videomsg|voicemsg)\b"
)
_SENSITIVE_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(api[_ -]?key|access[_ -]?token|refresh[_ -]?token|token|secret|password|cookie|aeskey)"
    r"\b\s*[:=]\s*[^\s,;]+"
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


def _summarize_message_safe(row: Dict[str, Any], max_length: int = 160) -> str:
    msg_type = project_wechat_message_type(row.get("message_type") or "text", row.get("text"))
    if msg_type and msg_type != "text":
        return "[{} message]".format(msg_type)
    if is_wechat_group_transport_payload(row.get("text")):
        return "[media message]"
    text = sanitize_wechat_group_prompt_text(row.get("text"), max_length)
    if not text:
        return "[{} message]".format(row.get("message_type") or "unknown")
    return text


def is_wechat_group_transport_payload(value: Any) -> bool:
    return bool(_TRANSPORT_PAYLOAD_RE.search(str(value or "")))


def sanitize_wechat_group_prompt_text(value: Any, max_length: int = 160) -> str:

    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"<[^>]{1,200}>", "", text)
    text = text.replace("<", "").replace(">", "")
    text = " ".join(text.split())
    text = _SENSITIVE_ASSIGNMENT_RE.sub(r"\1=[redacted]", text)
    text = _strip_local_paths(text)
    text = _strip_base64_like_chunks(text)
    text = _strip_url_query_values(text)
    if len(text) <= max_length:
        return text
    return text[: max_length - 1].rstrip() + "..."


def _sanitize_prompt_text(value: Any, max_length: int = 160) -> str:
    return sanitize_wechat_group_prompt_text(value, max_length)


def _strip_local_paths(text: str) -> str:
    return re.sub(
        r"(?i)(?:[a-z]:[\\/]|file://|/users/|/home/|\\\\)[^\s]+",
        "[local-path]",
        text,
    )


def _strip_base64_like_chunks(text: str) -> str:
    return re.sub(r"\b[A-Za-z0-9+/]{80,}={0,2}\b", "[base64]", text)


def _strip_url_query_values(text: str) -> str:
    return re.sub(
        r"(?i)(https?://[^\s?#]+)\?[^\s]+",
        r"\1?[query-redacted]",
        text,
    )
