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
