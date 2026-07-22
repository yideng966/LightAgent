"""WeChat group sticker tools for the current Agent turn."""

from __future__ import annotations

from typing import List

from agent.tools.base_tool import BaseTool, ToolResult
from channel.wechat_group.wechat_group_sticker_service import WechatGroupStickerService
from channel.wechat_group.wechat_group_transport import is_wechat_transport_xml


class WechatGroupStickerSearchTool(BaseTool):
    name = "wechat_group_sticker_search"
    description = (
        "Search active stickers for the current WeChat group only. Use this when "
        "a sticker reply would fit better than plain text. Query can be empty to "
        "list the most relevant recent stickers in the current group."
    )
    params = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Optional query for sticker description or file name",
                "default": "",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of stickers to return",
                "default": 5,
            },
        },
        "required": [],
    }

    def __init__(self, service: WechatGroupStickerService, room_id: str):
        super().__init__()
        self.service = service
        self.room_id = room_id
        self.online_candidates = {}

    def execute(self, params: dict) -> ToolResult:
        query = str(params.get("query") or "").strip()
        max_results = _to_int(params.get("max_results"), 5)
        try:
            if hasattr(self.service, "search_mixed_stickers"):
                rows = self.service.search_mixed_stickers(
                    self.room_id,
                    query=query,
                    limit=max_results,
                    seed="{}:{}".format(self.room_id, query),
                )
            else:
                rows = self.service.search_stickers(self.room_id, query=query, limit=max_results)
        except Exception as e:
            return ToolResult.fail(f"Error searching current group stickers: {e}")
        if not rows:
            return ToolResult.success("No active stickers found in the current group.")
        self.online_candidates.clear()
        lines = [f"Found {len(rows)} sticker candidates in the current group:"]
        for idx, item in enumerate(rows, 1):
            source = str(item.get("source") or "local").strip() or "local"
            if source == "online":
                online_id = str(item.get("online_id") or "").strip()
                if online_id:
                    self.online_candidates[online_id] = dict(item)
                lines.append(
                    f"\n{idx}. source: online\n"
                    f"online_id: {online_id}\n"
                    f"description: {_safe_sticker_description(item.get('description'))}\n"
                    f"provider: {item.get('provider', '')}\n"
                    f"size: {item.get('width', 0)}x{item.get('height', 0)}"
                )
            else:
                lines.append(
                    f"\n{idx}. source: local\n"
                    f"sticker_id: {item.get('sticker_id', '')}\n"
                    f"description: {_safe_sticker_description(item.get('description'))}\n"
                    f"use_count: {item.get('use_count', 0)}"
                )
        return ToolResult.success("\n".join(lines))


class WechatGroupStickerSendTool(BaseTool):
    name = "wechat_group_sticker_send"
    description = (
        "Send an active sticker from the current WeChat group by sticker_id. "
        "Always call wechat_group_sticker_search first unless you already know "
        "the exact sticker_id."
    )
    params = {
        "type": "object",
        "properties": {
            "sticker_id": {
                "type": "string",
                "description": "Exact sticker_id returned by wechat_group_sticker_search",
            },
            "online_id": {
                "type": "string",
                "description": "Exact online_id returned by wechat_group_sticker_search for an online candidate",
            },
            "message": {
                "type": "string",
                "description": "Optional short message to accompany the sticker",
                "default": "",
            },
        },
        "required": [],
    }

    def __init__(self, service: WechatGroupStickerService, room_id: str, online_candidates=None):
        super().__init__()
        self.service = service
        self.room_id = room_id
        self.online_candidates = online_candidates if online_candidates is not None else {}

    def execute(self, params: dict) -> ToolResult:
        sticker_id = str(params.get("sticker_id") or "").strip()
        online_id = str(params.get("online_id") or "").strip()
        if not sticker_id and not online_id:
            return ToolResult.fail("Error: sticker_id or online_id parameter is required")
        try:
            if online_id:
                item = self.online_candidates.get(online_id)
                if not item:
                    return ToolResult.fail("Error: online_id is not available from the latest search result")
                payload = self.service.prepare_online_send_result(
                    room_id=self.room_id,
                    item=item,
                    message=str(params.get("message") or "").strip(),
                )
            else:
                payload = self.service.prepare_send_result(
                    room_id=self.room_id,
                    sticker_id=sticker_id,
                    message=str(params.get("message") or "").strip(),
                )
        except Exception as e:
            return ToolResult.fail(f"Error sending current group sticker: {e}")
        if isinstance(payload, dict) and "description" in payload:
            payload = dict(payload)
            payload["description"] = _safe_sticker_description(payload.get("description"))
        return ToolResult.success(payload)


def create_wechat_group_sticker_tools(
    sticker_service: WechatGroupStickerService,
    room_id: str,
) -> List[BaseTool]:
    online_candidates = {}
    search_tool = WechatGroupStickerSearchTool(sticker_service, room_id=room_id)
    search_tool.online_candidates = online_candidates
    return [
        search_tool,
        WechatGroupStickerSendTool(
            sticker_service,
            room_id=room_id,
            online_candidates=online_candidates,
        ),
    ]


def _to_int(value, fallback: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        return fallback
    return max(1, parsed)


def _safe_sticker_description(value) -> str:
    text = str(value or "").strip()
    if is_wechat_transport_xml(text):
        return "sticker"
    return text[:200] or "sticker"
