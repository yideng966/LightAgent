"""WeChat group knowledge tools for the current Agent turn."""

from __future__ import annotations

from typing import List, Optional

from agent.tools.base_tool import BaseTool, ToolResult
from channel.wechat_group.wechat_group_knowledge_service import WechatGroupKnowledgeService
from channel.wechat_group.wechat_group_profile_service import WechatGroupProfileService


class WechatGroupMemorySearchTool(BaseTool):
    name = "wechat_group_memory_search"
    description = (
        "Search long-term memories for the current WeChat group only. "
        "Use this for current group rules, preferences, historical agreements, "
        "project facts, or recurring decisions. The current room is bound by "
        "the server and cannot be changed by tool arguments."
    )
    params = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query for current group memory",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of memories to return",
                "default": 5,
            },
            "min_score": {
                "type": "number",
                "description": "Minimum relevance score from 0 to 1",
                "default": 0,
            },
        },
        "required": ["query"],
    }

    def __init__(self, service: WechatGroupKnowledgeService, room_id: str):
        super().__init__()
        self.service = service
        self.room_id = room_id

    def execute(self, params: dict) -> ToolResult:
        query = str(params.get("query") or "").strip()
        if not query:
            return ToolResult.fail("Error: query parameter is required")
        max_results = _to_int(params.get("max_results"), 5)
        try:
            rows = self.service.search_group_memories(
                self.room_id,
                query=query,
                limit=max_results,
            )
        except Exception as e:
            return ToolResult.fail(f"Error searching current group memory: {e}")

        if not rows:
            return ToolResult.success("No current group memories found.")
        lines = [f"Found {len(rows)} current group memories:"]
        for idx, item in enumerate(rows, 1):
            lines.append(f"\n{idx}. {item.get('content', '')}")
        return ToolResult.success("\n".join(lines))


class WechatGroupProfileGetTool(BaseTool):
    name = "wechat_group_profile_get"
    description = (
        "Read a member profile for the current WeChat sender context. Use this "
        "for member style, interests, common words, aliases, or profile facts. "
        "Provide sender_id for an exact profile, query to search related profiles, "
        "or list_all=true to list current-room profiles."
    )
    params = {
        "type": "object",
        "properties": {
            "sender_id": {
                "type": "string",
                "description": "Optional member sender_id in the current group; omit for current speaker",
            },
            "query": {
                "type": "string",
                "description": "Optional semantic search query for current-room member profiles",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of profiles to return for query search",
                "default": 1,
            },
            "list_all": {
                "type": "boolean",
                "description": "List member profiles from the current WeChat group only",
                "default": False,
            },
        },
        "required": [],
    }

    def __init__(
        self,
        service: WechatGroupProfileService,
        sender_id: str,
        room_id: str = "",
        bot_sender_id: Optional[str] = None,
    ):
        super().__init__()
        self.service = service
        self.sender_id = sender_id
        self.room_id = room_id
        self.bot_sender_id = bot_sender_id or ""

    def execute(self, params: dict) -> ToolResult:
        requested_sender_id = str(params.get("sender_id") or "").strip()
        query = str(params.get("query") or "").strip()
        list_all = _to_bool(params.get("list_all"))
        speaker_member_id = self.service.resolve_canonical_member_id(self.room_id, self.sender_id)
        bot_member_id = self.service.resolve_canonical_member_id(self.room_id, self.bot_sender_id)
        if (query or list_all) and not requested_sender_id:
            try:
                rows = self.service.list_profiles(
                    query="" if list_all else query,
                    limit=_to_int(params.get("max_results"), 1),
                    room_id=self.room_id,
                )
            except Exception as e:
                return ToolResult.fail(f"Error searching current member profiles: {e}")

            rows = [
                profile for profile in rows
                if profile.get("stable_member_id") not in (
                    {bot_member_id} if list_all else {speaker_member_id, bot_member_id}
                )
            ]
            if not rows:
                return ToolResult.success("No matching member profiles found.")
            lines = [f"Found {len(rows)} member profiles:"]
            for idx, profile in enumerate(rows, 1):
                sender_id = profile.get("sender_id") or ""
                lines.append(
                    f"\n{idx}. sender_id: {sender_id}\n"
                    f"{profile.get('content', '')}"
                )
            return ToolResult.success("\n".join(lines))

        requested_sender_id = requested_sender_id or self.sender_id or ""
        if not requested_sender_id:
            return ToolResult.fail("Error: sender_id is required when current speaker is unknown")
        if self.bot_sender_id and requested_sender_id == self.bot_sender_id:
            return ToolResult.success("No member profile returned for the bot itself.")

        try:
            if self.room_id:
                profile = self.service.get_profile(requested_sender_id, room_id=self.room_id)
            else:
                profile = self.service.get_profile(requested_sender_id)
        except Exception as e:
            return ToolResult.fail(f"Error reading current member profile: {e}")

        if not profile:
            return ToolResult.success(f"No profile found for sender_id={requested_sender_id}.")
        return ToolResult.success(
            "Current member profile:\n"
            f"sender_id: {profile.get('stable_member_id') or profile.get('sender_id') or ''}\n"
            f"{profile.get('content', '')}"
        )


def create_wechat_group_memory_tools(
    knowledge_service: WechatGroupKnowledgeService,
    profile_service: WechatGroupProfileService,
    room_id: str,
    sender_id: str,
    bot_sender_id: Optional[str] = None,
) -> List[BaseTool]:
    return [
        WechatGroupMemorySearchTool(knowledge_service, room_id=room_id),
        WechatGroupProfileGetTool(
            profile_service,
            sender_id=sender_id,
            room_id=room_id,
            bot_sender_id=bot_sender_id,
        ),
    ]


def _to_int(value, fallback: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        return fallback
    return max(1, parsed)


def _to_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}
