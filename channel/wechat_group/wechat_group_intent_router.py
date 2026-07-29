"""Deterministic high-frequency intent routing for WeChat group requests."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import List


@dataclass(frozen=True)
class WechatGroupIntentRoute:
    route: str
    confidence: float
    reason: str
    required_context_mode: str
    suggested_tool_names: List[str]

    def to_dict(self) -> dict:
        return asdict(self)


class WechatGroupIntentRouter:
    _RULES = (
        (
            "summarize",
            re.compile(r"(?:总结|汇总|群聊报告|日报|周报|月报|聊天报告)"),
            "recall",
            ["wechat_group_report", "wechat_group_memory_search"],
        ),
        (
            "recall",
            re.compile(r"(?:谁说|说过什么|历史记录|聊天记录|之前约定|以前聊过)"),
            "recall",
            ["wechat_group_memory_search", "wechat_group_profile_get"],
        ),
        (
            "image_understand",
            re.compile(r"(?:看图|识图|图片里|这张图|引用图片|分析图片)"),
            "contextual",
            [],
        ),
        (
            "image_generate",
            re.compile(r"(?:生成|画|做|来).{0,8}(?:图片|海报|插画|头像)"),
            "contextual",
            [],
        ),
        (
            "sticker",
            re.compile(r"(?:表情包|梗图|斗图|来个表情|发个表情|gif|动图)", re.I),
            "recent",
            ["wechat_group_sticker_search", "wechat_group_sticker_send"],
        ),
        (
            "link_read",
            re.compile(r"https?://|(?:这个|打开|看看|分析|总结).{0,8}(?:链接|网页|网站)"),
            "contextual",
            ["web_fetch", "browser"],
        ),
        (
            "scheduler",
            re.compile(r"(?:提醒我|定时|每隔|每天|每周|闹钟|到点)"),
            "minimal",
            ["scheduler"],
        ),
        (
            "memory_query",
            re.compile(r"(?:群记忆|记得什么|你记得|群规|长期记忆)"),
            "recall",
            ["wechat_group_memory_search", "wechat_group_profile_get"],
        ),
    )

    def route(self, text: str) -> WechatGroupIntentRoute:
        value = str(text or "").strip()
        for route, pattern, context_mode, tools in self._RULES:
            if pattern.search(value):
                return WechatGroupIntentRoute(
                    route=route,
                    confidence=1.0,
                    reason="deterministic_rule",
                    required_context_mode=context_mode,
                    suggested_tool_names=list(tools),
                )
        return WechatGroupIntentRoute(
            route="chat",
            confidence=1.0,
            reason="default_chat",
            required_context_mode="recent",
            suggested_tool_names=[],
        )
