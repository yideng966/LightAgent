"""Safe text template support for the six-module WeChat group report."""

from __future__ import annotations

import os
import re
import string
from datetime import datetime
from typing import Any, Dict, Iterable, List, Tuple


TEXT_TEMPLATE_MAX_BYTES = 64 * 1024
BUILTIN_TEXT_TEMPLATE_ID = "standard_text"
BUILTIN_TEXT_TEMPLATE_FILES = {
    "standard_text": "standard_text.txt",
    "compact_text": "compact_text.txt",
}
ALLOWED_TEMPLATE_FIELDS = frozenset({
    "room_name", "report_type", "period_start", "period_end", "timezone",
    "active_speaker_count", "total_messages", "top_speaker_name",
    "top_speaker_message_count", "topic_count", "ranking_block", "topics_block",
    "highlights_block", "links_block", "archive_message_count",
    "unresolved_message_count", "generated_at",
})
REQUIRED_TEMPLATE_FIELDS = frozenset({
    "room_name", "period_start", "period_end", "active_speaker_count", "total_messages",
    "top_speaker_name", "topic_count", "ranking_block", "topics_block", "highlights_block",
    "links_block", "archive_message_count", "unresolved_message_count", "generated_at",
})


def builtin_text_template_path(template_id: str = BUILTIN_TEXT_TEMPLATE_ID) -> str:
    resolved_id = str(template_id or BUILTIN_TEXT_TEMPLATE_ID).strip() or BUILTIN_TEXT_TEMPLATE_ID
    filename = BUILTIN_TEXT_TEMPLATE_FILES.get(resolved_id)
    if not filename:
        raise ValueError("unknown builtin text template")
    return os.path.join(os.path.dirname(__file__), "report_templates", filename)


def get_builtin_text_template(template_id: str = BUILTIN_TEXT_TEMPLATE_ID) -> str:
    with open(builtin_text_template_path(template_id), "r", encoding="utf-8") as handle:
        return handle.read()


def validate_text_template(template: Any) -> Dict[str, Any]:
    text = str(template or "")
    encoded = text.encode("utf-8")
    if not text.strip():
        raise ValueError("text template cannot be empty")
    if len(encoded) > TEXT_TEMPLATE_MAX_BYTES:
        raise ValueError("text template exceeds 64 KiB")
    formatter = string.Formatter()
    fields = set()
    try:
        parsed = list(formatter.parse(text))
    except ValueError as exc:
        raise ValueError("text template contains unmatched braces") from exc
    for _, field_name, format_spec, conversion in parsed:
        if field_name is None:
            continue
        if field_name not in ALLOWED_TEMPLATE_FIELDS:
            raise ValueError(f"unsupported text template field: {field_name}")
        if format_spec or conversion:
            raise ValueError("text template format specifiers are not allowed")
        fields.add(field_name)
    missing = sorted(REQUIRED_TEMPLATE_FIELDS - fields)
    if missing:
        raise ValueError("text template misses required fields: " + ", ".join(missing))
    return {"valid": True, "fields": sorted(fields), "size_bytes": len(encoded)}


def render_text_report(report: Dict[str, Any], template: str) -> str:
    validate_text_template(template)
    values = build_text_template_values(report)
    rendered = str(template).format_map(values)
    return sanitize_report_text(rendered)


def build_text_template_values(report: Dict[str, Any]) -> Dict[str, str]:
    data = dict(report or {})
    top = data.get("top_speaker") if isinstance(data.get("top_speaker"), dict) else {}
    return {
        "room_name": _visible(data.get("room_name") or "未命名群聊", 100),
        "report_type": _report_type_name(data.get("report_type")),
        "period_start": _format_timestamp(data.get("period_start"), data.get("timezone")),
        "period_end": _format_timestamp(data.get("period_end"), data.get("timezone")),
        "timezone": _visible(data.get("timezone") or "Asia/Shanghai", 80),
        "active_speaker_count": str(max(int(data.get("active_speaker_count") or 0), 0)),
        "total_messages": str(max(int(data.get("total_messages") or 0), 0)),
        "top_speaker_name": _visible(top.get("display_name") or "暂无", 100),
        "top_speaker_message_count": str(max(int(top.get("message_count") or 0), 0)),
        "topic_count": str(max(int(data.get("topic_count") or 0), 0)),
        "ranking_block": render_ranking_block(data.get("ranking")),
        "topics_block": render_topics_block(data.get("topics")),
        "highlights_block": render_highlights_block(data.get("highlights")),
        "links_block": render_links_block(data.get("links")),
        "archive_message_count": str(max(int(data.get("archive_message_count") or 0), 0)),
        "unresolved_message_count": str(max(int(data.get("unresolved_message_count") or 0), 0)),
        "generated_at": _format_timestamp(data.get("generated_at"), data.get("timezone")),
    }


def render_ranking_block(items: Any) -> str:
    rows = items if isinstance(items, list) else []
    if not rows:
        return "本周期暂无可稳定归属的发言排行。"
    lines = []
    for index, item in enumerate(rows[:5], 1):
        row = item if isinstance(item, dict) else {}
        rank = max(int(row.get("rank") or index), 1)
        lines.append(
            f"{rank}. {_visible(row.get('display_name') or '未命名群友', 100)}："
            f"{max(int(row.get('message_count') or 0), 0)} 条"
        )
    return "\n".join(lines)


def render_topics_block(items: Any) -> str:
    rows = items if isinstance(items, list) else []
    lines = []
    for index in range(3):
        item = rows[index] if index < len(rows) and isinstance(rows[index], dict) else None
        if not item:
            lines.append(f"{index + 1}. 本周期有效话题不足")
            continue
        lines.append(
            f"{index + 1}. {_visible(item.get('title') or '群内讨论', 100)} "
            f"(热度 {max(int(item.get('heat') or 0), 0)})\n"
            f"{_visible(item.get('summary') or '暂无概括。', 360)}"
        )
    return "\n".join(lines)


def render_highlights_block(items: Any) -> str:
    rows = items if isinstance(items, list) else []
    lines = []
    for index in range(3):
        item = rows[index] if index < len(rows) and isinstance(rows[index], dict) else None
        if not item:
            lines.append(f"{index + 1}. 本周期有效精彩发言不足")
            continue
        lines.append(
            f"{index + 1}. {_visible(item.get('speaker_display_name') or '未命名群友', 100)}："
            f"“{_visible(item.get('quote') or '', 280)}”\n"
            f"点评：{_visible(item.get('commentary') or '这句话把讨论说得很有画面。', 180)}"
        )
    return "\n".join(lines)


def render_links_block(items: Any) -> str:
    rows = items if isinstance(items, list) else []
    if not rows:
        return "本周期未收集到链接。"
    lines = []
    for index, item in enumerate(rows, 1):
        row = item if isinstance(item, dict) else {}
        providers = row.get("provider_display_names") if isinstance(row.get("provider_display_names"), list) else []
        provider_text = "、".join(_visible(value, 80) for value in providers if str(value or "").strip())
        lines.append(
            f"{index}. {_visible(row.get('domain') or '链接', 160)}\n"
            f"{_visible(row.get('url') or '', 2048)}\n"
            f"提供人：{provider_text or '未稳定归属'}\n"
            f"{_link_summary(row)}"
        )
    return "\n".join(lines)


def split_report_text(text: Any, max_chars: int = 1000) -> List[str]:
    """Split a report at paragraph or newline boundaries without truncation."""
    value = sanitize_report_text(str(text or "")).strip()
    if not value:
        return []
    limit = min(max(int(max_chars or 1000), 200), 2000)
    parts: List[str] = []
    current = ""
    paragraphs = re.split(r"(\n\s*\n)", value)
    for paragraph in paragraphs:
        if not paragraph:
            continue
        if len(paragraph) > limit:
            for line in _split_long_text(paragraph, limit):
                if current and len(current) + len(line) > limit:
                    parts.append(current)
                    current = ""
                current += line
            continue
        if current and len(current) + len(paragraph) > limit:
            parts.append(current)
            current = ""
        current += paragraph
    if current:
        parts.append(current)
    return parts


def sanitize_report_text(value: Any) -> str:
    text = str(value or "")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    # Do not expose archive/internal identity values even if a custom template
    # author accidentally copied one into static text.
    text = re.sub(r"\b(?:wgr|wgm|wga)_[A-Za-z0-9_-]+\b", "[内部标识已隐藏]", text)
    text = re.sub(r"(?:[A-Za-z]:\\|/(?:home|app|tmp|var)/)[^\s]+", "[本机路径已隐藏]", text)
    return text.strip()


def _split_long_text(value: str, limit: int) -> List[str]:
    result = []
    remaining = value
    while len(remaining) > limit:
        boundary = max(remaining.rfind("\n", 0, limit), remaining.rfind("。", 0, limit), remaining.rfind(" ", 0, limit))
        if boundary < max(1, limit // 3):
            boundary = limit
        else:
            boundary += 1
        result.append(remaining[:boundary])
        remaining = remaining[boundary:]
    if remaining:
        result.append(remaining)
    return result


def _visible(value: Any, limit: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return sanitize_report_text(text)[:limit]


def _format_timestamp(value: Any, timezone_name: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "-"
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return _visible(text, 80)


def _report_type_name(value: Any) -> str:
    return {"daily": "日报", "weekly": "周报", "monthly": "月报", "custom": "自定义报告"}.get(
        str(value or "").lower(), "群聊报告"
    )


def _link_summary(item: Dict[str, Any]) -> str:
    status = str(item.get("fetch_status") or "").strip()
    summary = _visible(item.get("summary") or "", 360)
    if status == "blocked":
        return summary or "链接因安全策略被拒绝。"
    if status == "timeout":
        return summary or "链接抓取超时。"
    if status == "login_required":
        return summary or "链接需要登录后访问。"
    if status == "empty":
        return summary or "链接正文为空或不可解析。"
    if status == "failed":
        return summary or "链接抓取失败。"
    return summary or "已安全抓取链接正文。"
