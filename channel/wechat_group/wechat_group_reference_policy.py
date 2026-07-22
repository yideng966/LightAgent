"""Reference and link policy prompt helpers for WeChat group replies."""

from __future__ import annotations

import re


def build_wechat_group_reference_policy_block(
    msg,
    user_content: str,
    reference_enabled: bool = True,
    link_enabled: bool = True,
) -> str:
    parts = []
    if reference_enabled and getattr(msg, "quote", None):
        parts.append("If a quoted message is relevant, prefer that quoted context over unrelated recent messages.")
    if reference_enabled and _looks_like_image_reference(user_content):
        parts.append("For image references, use only matched image context. If no image context is provided, say it is unavailable.")
    if link_enabled and _contains_link(user_content):
        parts.append("For links, do not invent page contents. Only summarize link contents after a tool or provided context has read them.")
    if not parts:
        return ""
    return "<wechat-group-reference-policy>\n{}\n</wechat-group-reference-policy>".format(
        "\n".join(parts)
    )


def _looks_like_image_reference(text: str) -> bool:
    value = str(text or "").lower()
    return any(token in value for token in ("image", "picture", "photo", "screenshot", "图", "图片", "照片", "这张"))


def _contains_link(text: str) -> bool:
    return bool(re.search(r"https?://|www\.", str(text or ""), flags=re.I))
