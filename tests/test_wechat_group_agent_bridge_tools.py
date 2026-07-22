import tempfile
import unittest
from unittest.mock import patch

from agent.memory.config import MemoryConfig
from agent.memory.manager import MemoryManager
from agent.tools.base_tool import BaseTool, ToolResult
from bridge.agent_bridge import AgentBridge
from bridge.context import Context, ContextType
from bridge.reply import ReplyType


WECHAT_STICKER_TRANSPORT_XML = """<?xml version="1.0"?>
<msg>
  <emoji aeskey="masked" cdnurl="masked" md5="masked" hevc_mid_size="31347" />
</msg>
"""


class DummyTool(BaseTool):
    name = "dummy"
    description = "dummy"
    params = {"type": "object", "properties": {}, "required": []}

    def execute(self, params: dict) -> ToolResult:
        return ToolResult.success("dummy")


class FakeAgent:
    def __init__(self, memory_manager):
        self.tools = [DummyTool()]
        self.memory_manager = memory_manager
        self.model = type("FakeModel", (), {})()
        self.extra_system_suffix = ""
        self.seen_tool_names = []
        self.seen_suffix = ""
        self._last_run_new_messages = []

    def run_stream(self, **kwargs):
        self.seen_tool_names = [tool.name for tool in self.tools]
        self.seen_suffix = self.extra_system_suffix
        return "ok"


class HarnessAgentBridge(AgentBridge):
    def __init__(self, agent):
        self._agent = agent

    def get_agent(self, session_id=None):
        return self._agent


class WechatGroupAgentBridgeToolsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.manager = MemoryManager(MemoryConfig(workspace_root=self._tmp.name))

    def tearDown(self):
        self.manager.close()
        self._tmp.cleanup()

    def test_wechat_group_turn_temporarily_attaches_scoped_memory_tools(self):
        agent = FakeAgent(self.manager)
        bridge = HarnessAgentBridge(agent)
        context = Context(ContextType.TEXT, "hello")
        context["channel_type"] = "wechat_group"
        context["wechat_group_room_id"] = "room@@a"
        context["wechat_group_sender_id"] = "wxid_alice"
        context["wechat_group_bot_sender_id"] = "wxid_bot"

        reply = bridge.agent_reply("hello", context=context)

        self.assertEqual(ReplyType.TEXT, reply.type)
        self.assertEqual("ok", reply.content)
        self.assertIn("wechat_group_memory_search", agent.seen_tool_names)
        self.assertIn("wechat_group_profile_get", agent.seen_tool_names)
        self.assertIn("wechat_group_sticker_search", agent.seen_tool_names)
        self.assertIn("wechat_group_sticker_send", agent.seen_tool_names)
        self.assertIn("wechat_group_memory_search", agent.seen_suffix)
        self.assertIn("wechat_group_sticker_search", agent.seen_suffix)
        self.assertEqual(["dummy"], [tool.name for tool in agent.tools])
        self.assertEqual("", agent.extra_system_suffix)

    def test_sticker_tool_prompt_allows_online_id_without_exposing_url(self):
        prompt = AgentBridge._build_wechat_group_memory_tool_prompt()

        self.assertIn("sticker_id or online_id", prompt)
        self.assertIn("Do not expose or invent raw sticker URLs", prompt)

    def test_profile_tool_service_uses_stable_identity_scope(self):
        bridge = HarnessAgentBridge(FakeAgent(self.manager))
        context = Context(ContextType.TEXT, "hello")
        context["channel_type"] = "wechat_group"
        context["wechat_group_stable_room_id"] = "wgr_room"
        context["wechat_group_stable_member_id"] = "wgm_alice"
        identity = object()
        profile_service = object()

        with patch(
            "channel.wechat_group.wechat_group_identity_service.WechatGroupIdentityService",
            return_value=identity,
        ) as identity_class, patch(
            "channel.wechat_group.wechat_group_profile_service.WechatGroupProfileService",
            return_value=profile_service,
        ) as profile_class, patch(
            "channel.wechat_group.wechat_group_memory_tools.create_wechat_group_memory_tools",
            return_value=[],
        ), patch(
            "channel.wechat_group.wechat_group_sticker_tools.create_wechat_group_sticker_tools",
            return_value=[],
        ):
            bridge._create_wechat_group_memory_tools(bridge._agent, context)

        identity_class.assert_called_once_with()
        profile_class.assert_called_once_with(identity_service=identity)

    def test_file_reply_preserves_online_sticker_metadata(self):
        bridge = HarnessAgentBridge(FakeAgent(self.manager))
        context = Context(ContextType.TEXT, "hello")
        context["channel_type"] = "wechat_group"

        reply = bridge._create_file_reply(
            {
                "file_type": "image",
                "path": "/tmp/online.png",
                "online_id": "online-1",
                "wechat_group_sticker_source": "online",
            },
            "（暴漫坏笑.gif）",
            context,
        )

        self.assertEqual(ReplyType.IMAGE_URL, reply.type)
        self.assertEqual("online-1", reply.wechat_group_sticker_online_id)
        self.assertEqual("online", reply.wechat_group_sticker_source)
        self.assertFalse(hasattr(reply, "text_content"))

    def test_file_reply_suppresses_local_sticker_text(self):
        bridge = HarnessAgentBridge(FakeAgent(self.manager))
        context = Context(ContextType.TEXT, "hello")
        context["channel_type"] = "wechat_group"

        reply = bridge._create_file_reply(
            {
                "file_type": "image",
                "path": "/tmp/local.gif",
                "sticker_id": "sticker-1",
            },
            "（本地表情包.gif）",
            context,
        )

        self.assertEqual(ReplyType.IMAGE_URL, reply.type)
        self.assertEqual("sticker-1", reply.wechat_group_sticker_id)
        self.assertFalse(hasattr(reply, "text_content"))

    def test_file_reply_preserves_regular_image_text(self):
        bridge = HarnessAgentBridge(FakeAgent(self.manager))
        context = Context(ContextType.TEXT, "hello")
        context["channel_type"] = "wechat_group"

        reply = bridge._create_file_reply(
            {
                "file_type": "image",
                "path": "/tmp/regular.png",
            },
            "普通图片说明",
            context,
        )

        self.assertEqual(ReplyType.IMAGE_URL, reply.type)
        self.assertEqual("普通图片说明", reply.text_content)

    def test_sticker_search_tool_returns_local_and_online_results_without_url(self):
        from channel.wechat_group.wechat_group_sticker_tools import WechatGroupStickerSearchTool

        class FakeStickerService:
            def search_mixed_stickers(self, room_id, query="", limit=5, seed="", online_opener=None):
                self.args = (room_id, query, limit, seed)
                return [
                    {
                        "source": "local",
                        "sticker_id": "sticker-1",
                        "description": WECHAT_STICKER_TRANSPORT_XML,
                        "use_count": 3,
                    },
                    {
                        "source": "online",
                        "online_id": "online-1",
                        "description": "开心",
                        "provider": "xiaoapi",
                        "width": 240,
                        "height": 180,
                        "_url": "https://biaoqing.gtimg.com/hidden.png",
                    },
                ]

        service = FakeStickerService()
        tool = WechatGroupStickerSearchTool(service, room_id="room@@a")

        result = tool.execute({"query": "开心", "max_results": 2})

        self.assertEqual("success", result.status)
        self.assertEqual(("room@@a", "开心", 2, "room@@a:开心"), service.args)
        self.assertIn("source: local", result.result)
        self.assertIn("sticker_id: sticker-1", result.result)
        self.assertIn("source: online", result.result)
        self.assertIn("online_id: online-1", result.result)
        self.assertNotIn("hidden.png", result.result)
        self.assertIn("description: sticker", result.result)
        for transport_fragment in ("<?xml", "<emoji", "hevc_mid_size", "aeskey", "cdnurl"):
            self.assertNotIn(transport_fragment, result.result)

    def test_sticker_send_tool_supports_online_id_from_cached_search_result(self):
        from channel.wechat_group.wechat_group_sticker_tools import WechatGroupStickerSendTool

        class FakeStickerService:
            def __init__(self):
                self.calls = []

            def prepare_online_send_result(self, room_id, item, message=""):
                self.calls.append((room_id, item, message))
                return {
                    "type": "file_to_send",
                    "file_type": "image",
                    "path": "/tmp/online.png",
                    "online_id": item["online_id"],
                    "description": WECHAT_STICKER_TRANSPORT_XML,
                    "wechat_group_sticker_source": "online",
                }

        cached = {
            "online-1": {
                "source": "online",
                "online_id": "online-1",
                "_url": "https://biaoqing.gtimg.com/hidden.png",
            }
        }
        service = FakeStickerService()
        tool = WechatGroupStickerSendTool(service, room_id="room@@a", online_candidates=cached)

        result = tool.execute({"online_id": "online-1", "message": "发这个"})

        self.assertEqual("success", result.status)
        self.assertEqual("/tmp/online.png", result.result["path"])
        self.assertEqual("sticker", result.result["description"])
        self.assertEqual(("room@@a", cached["online-1"], "发这个"), service.calls[0])

    def test_sticker_send_tool_rejects_unknown_online_id(self):
        from channel.wechat_group.wechat_group_sticker_tools import WechatGroupStickerSendTool

        class FakeStickerService:
            pass

        tool = WechatGroupStickerSendTool(FakeStickerService(), room_id="room@@a", online_candidates={})

        result = tool.execute({"online_id": "online-missing"})

        self.assertEqual("error", result.status)
        self.assertIn("online_id is not available", result.result)


if __name__ == "__main__":
    unittest.main()
