"""长期记忆写入路由与渠道隔离规则。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class MemoryRoute:
    channel_type: str = ""
    scope_type: str = "shared"
    scope_id: str = ""
    allow_shared_flush: bool = True
    allow_shared_evolution: bool = True


def resolve_memory_route(
    context: Optional[Any] = None,
    *,
    agent: Optional[Any] = None,
    session_id: str = "",
    channel_type: str = "",
    stable_room_id: str = "",
) -> MemoryRoute:
    """解析当前请求的记忆写入域，微信群始终 fail-closed。"""
    session_text = str(session_id or _context_value(context, "session_id") or "").strip()
    context_channel = str(_context_value(context, "channel_type") or "").strip()
    explicit_channel = context_channel or str(channel_type or "").strip()

    agent_route = getattr(agent, "_memory_route", None)
    if not explicit_channel and isinstance(agent_route, MemoryRoute):
        explicit_channel = agent_route.channel_type

    if not explicit_channel and session_text:
        explicit_channel = _session_channel_type(session_text)

    legacy_group = session_text.startswith("wechat_group:")
    if explicit_channel == "wechat_group" or legacy_group:
        room_id = str(
            _context_value(context, "wechat_group_stable_room_id")
            or stable_room_id
            or (agent_route.scope_id if isinstance(agent_route, MemoryRoute) else "")
            or _stable_room_from_session(session_text)
            or ""
        ).strip()
        return MemoryRoute(
            channel_type="wechat_group",
            scope_type="wechat_group",
            scope_id=room_id,
            allow_shared_flush=False,
            allow_shared_evolution=False,
        )

    return MemoryRoute(channel_type=explicit_channel, scope_type="shared")


def is_wechat_group_route(route: Optional[MemoryRoute]) -> bool:
    return bool(route and route.scope_type == "wechat_group")


def allow_shared_memory_write(route: Optional[MemoryRoute], purpose: str = "flush") -> bool:
    if route is None:
        return True
    if purpose == "evolution":
        return bool(route.allow_shared_evolution)
    return bool(route.allow_shared_flush)


def _context_value(context: Optional[Any], key: str) -> Any:
    if context is None:
        return None
    getter = getattr(context, "get", None)
    if callable(getter):
        try:
            return getter(key)
        except Exception:
            return None
    return None


def _stable_room_from_session(session_id: str) -> str:
    parts = str(session_id or "").split(":", 2)
    if len(parts) >= 2 and parts[0] == "wechat_group":
        return parts[1].strip()
    return ""


def _session_channel_type(session_id: str) -> str:
    try:
        from agent.memory.conversation_store import get_conversation_store

        return get_conversation_store().get_session_channel_type(session_id)
    except Exception:
        return ""
