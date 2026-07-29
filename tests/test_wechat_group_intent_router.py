import unittest
from types import SimpleNamespace

from bridge.agent_bridge import AgentBridge
from channel.wechat_group.wechat_group_intent_router import WechatGroupIntentRouter


class WechatGroupIntentRouterTest(unittest.TestCase):
    def setUp(self):
        self.router = WechatGroupIntentRouter()

    def test_routes_high_frequency_intents(self):
        cases = {
            "总结一下昨天群里聊了什么": "summarize",
            "之前谁说过周五发布": "recall",
            "看看这张图里是什么": "image_understand",
            "帮我生成一张海报": "image_generate",
            "来个表情包": "sticker",
            "分析一下 https://example.com": "link_read",
            "每天九点提醒我开会": "scheduler",
            "这个怎么算": "chat",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(expected, self.router.route(text).route)

    def test_route_tool_narrowing_cannot_restore_filtered_tools(self):
        bridge = AgentBridge.__new__(AgentBridge)
        tools = [
            SimpleNamespace(name="web_fetch"),
            SimpleNamespace(name="browser"),
            SimpleNamespace(name="write"),
        ]
        route = self.router.route("分析 https://example.com")
        allowed = set(route.suggested_tool_names)
        narrowed = [tool for tool in tools if tool.name in allowed]

        self.assertEqual(["web_fetch", "browser"], [tool.name for tool in narrowed])
        self.assertNotIn("write", allowed)


if __name__ == "__main__":
    unittest.main()
