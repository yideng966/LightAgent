"""Outgoing text cleanup for WeChat group replies."""

from __future__ import annotations

import re
from typing import Any


def cleanup_wechat_group_reply_text(text: Any, max_chars: int = 800) -> str:
    value = str(text or "").strip()
    if not value:
        return ""
    value = _strip_prompt_blocks(value)
    value = _strip_status_lines(value)
    value = _strip_markdown_for_wechat(value)
    value = _strip_fixed_openings(value)
    value = _strip_tail_questions(value)
    value = _normalize_space(value)
    try:
        limit = max(int(max_chars or 800), 1)
    except Exception:
        limit = 800
    if len(value) > limit:
        value = value[:limit].rstrip()
    return value


def _strip_prompt_blocks(text: str) -> str:
    patterns = (
        r"<wechat-group-[^>]*>.*?</wechat-group-[^>]*>",
        r"<recent-wechat-group-transcript>.*?</recent-wechat-group-transcript>",
        r"<local-extractive-summary>.*?</local-extractive-summary>",
        r"<group-long-term-memory>.*?</group-long-term-memory>",
    )
    result = text
    for pattern in patterns:
        result = re.sub(pattern, "", result, flags=re.I | re.S)
    return result


def _strip_status_lines(text: str) -> str:
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(r"(?i)^(trigger_source|is_at_bot|is_quote_self|policy|status)\s*:", stripped):
            continue
        lines.append(stripped)
    return "\n".join(lines)


def _strip_markdown_for_wechat(text: str) -> str:
    result = text
    result = re.sub(r"(?m)^\s{0,3}#{1,6}\s+", "", result)
    result = re.sub(r"(?m)^\s{0,3}>\s?", "", result)
    result = re.sub(r"(?m)^\s{0,3}[*+-]\s+", "", result)
    result = re.sub(r"(?m)^\s*(```+|~~~+).*$", "", result)
    result = re.sub(r"`([^`\n]+)`", r"\1", result)

    def replace_link(match):
        label = match.group(1).strip()
        url = match.group(2).strip()
        if label == url:
            return url
        return "{} {}".format(label, url).strip()

    result = re.sub(r"\[([^\]\n]+)\]\((https?://[^)\s]+)\)", replace_link, result)
    result = re.sub(r"(?<!\w)(\*\*|__)(\S(?:.*?\S)?)\1(?!\w)", r"\2", result)
    result = re.sub(r"(?<![\w*])\*(\S(?:.*?\S)?)\*(?![\w*])", r"\1", result)
    result = re.sub(r"(?<![\w_])_(\S(?:.*?\S)?)_(?![\w_])", r"\1", result)
    return result


def _strip_fixed_openings(text: str) -> str:
    openings = (
        r"^我来整理一下[:：]\s*",
        r"^我先整理一下[:：]\s*",
        r"^我来总结一下[:：]\s*",
        r"^收到[，,。.\s]*",
        r"(?i)^i can help with that[:：]\s*",
        r"(?i)^sure[,，:]?\s*",
        r"(?i)^here(?:'s| is) (?:a )?(?:quick )?(?:summary|answer)[:：]\s*",
    )
    result = text.strip()
    changed = True
    while changed:
        changed = False
        for pattern in openings:
            next_value = re.sub(pattern, "", result, count=1).strip()
            if next_value != result:
                result = next_value
                changed = True
    return result


def _strip_tail_questions(text: str) -> str:
    tail_patterns = (
        r"(?:\n|\s)*如果你还想了解更多，我可以继续说明。?$",
        r"(?:\n|\s)*如果你还需要.*$",
        r"(?:\n|\s)*你想了解(?:具体的?)?(?:哪|哪个|哪些)方面[？?].*$",
        r"(?:\n|\s)*(?:要不要|要我|需要我|我可以)(?:继续|再)?(?:帮你)?(?:展开|细说|对比|比较).*?[？?]$",
        r"(?i)(?:\n|\s)*let me know if you.*$",
        r"(?i)(?:\n|\s)*if you want.*$",
    )
    result = text.strip()
    for pattern in tail_patterns:
        result = re.sub(pattern, "", result).strip()
    return result


def _normalize_space(text: str) -> str:
    lines = [" ".join(line.split()) for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines).strip()
