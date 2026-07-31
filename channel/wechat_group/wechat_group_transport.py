"""Wechat transport payload detection for prompt-safe message projection."""

from __future__ import annotations

import html
import re
from typing import Any


_MEDIA_TAG_PATTERN = re.compile(r"<\s*(img|emoji)\b", flags=re.IGNORECASE)
_TRANSPORT_FIELD_MARKERS = (
    "aeskey=",
    "cdnthumburl=",
    "cdnurl=",
    "hevc_mid_size=",
    "encrypturl=",
)
_TRANSPORT_FIELD_NAMES = frozenset(marker[:-1] for marker in _TRANSPORT_FIELD_MARKERS)
MEDIA_SEMANTIC_TEXT_KEY = "media_semantic_text"


def detect_wechat_transport_message_type(value: Any) -> str:
    """Return image/sticker only for WeChat media transport XML payloads."""
    text = str(value or "").strip()
    if not text:
        return ""
    for _ in range(2):
        decoded = html.unescape(text)
        if decoded == text:
            break
        text = decoded
    lowered = text.lower()
    match = _MEDIA_TAG_PATTERN.search(lowered)
    if not match or not any(marker in lowered for marker in _TRANSPORT_FIELD_MARKERS):
        return ""
    return "sticker" if match.group(1).lower() == "emoji" else "image"


def is_wechat_transport_xml(value: Any) -> bool:
    return bool(detect_wechat_transport_message_type(value))


def is_wechat_transport_metadata_term(value: Any) -> bool:
    text = str(value or "").strip().lower().rstrip("=").strip()
    return text in _TRANSPORT_FIELD_NAMES


def project_wechat_message_type(message_type: Any, text: Any = "") -> str:
    detected = detect_wechat_transport_message_type(text)
    if detected:
        return detected
    return str(message_type or "unknown").strip().lower() or "unknown"


def project_wechat_media_semantic_text(
    message_type: Any,
    text: Any = "",
    metadata: Any = None,
) -> str:
    """只投影归档媒体消息中显式保存且可安全进入提示词的语义。"""
    projected_type = project_wechat_message_type(message_type, text)
    if projected_type in ("text", "unknown") or not isinstance(metadata, dict):
        return ""
    semantic = re.sub(
        r"\s+",
        " ",
        str(metadata.get(MEDIA_SEMANTIC_TEXT_KEY) or "").strip(),
    )
    lowered = semantic.lower()
    if (
        not semantic
        or len(semantic) > 120
        or "<" in semantic
        or ">" in semantic
        or "://" in semantic
        or semantic.startswith(("/", "\\"))
        or re.search(r"(?:^|\s)[a-zA-Z]:[\\/]", semantic)
        or any(marker in lowered for marker in _TRANSPORT_FIELD_MARKERS)
    ):
        return ""
    return "[{}: {}]".format(projected_type, semantic)
