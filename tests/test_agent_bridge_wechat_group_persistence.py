import threading
import unittest

from bridge.agent_bridge import AgentBridge
from bridge.context import Context, ContextType
from config import conf


class AgentBridgeWechatGroupPersistenceTest(unittest.TestCase):
    def setUp(self):
        self._original_config = {
            "wechat_group_context_persist_raw_user_only": conf().get("wechat_group_context_persist_raw_user_only"),
        }
        conf()["wechat_group_context_persist_raw_user_only"] = True

    def tearDown(self):
        for key, value in self._original_config.items():
            if value is None:
                conf().pop(key, None)
            else:
                conf()[key] = value

    def _bridge(self):
        return AgentBridge.__new__(AgentBridge)

    def test_select_persisted_user_query_uses_wechat_group_raw_content(self):
        context = Context(ContextType.TEXT, "enhanced")
        context["channel_type"] = "wechat_group"
        context["wechat_group_user_content"] = "raw user text"

        result = self._bridge()._select_persisted_user_query("enhanced prompt", context)

        self.assertEqual("raw user text", result)

    def test_select_persisted_user_query_can_be_disabled(self):
        conf()["wechat_group_context_persist_raw_user_only"] = False
        context = Context(ContextType.TEXT, "enhanced")
        context["channel_type"] = "wechat_group"
        context["wechat_group_user_content"] = "raw user text"

        result = self._bridge()._select_persisted_user_query("enhanced prompt", context)

        self.assertEqual("enhanced prompt", result)

    def test_sanitize_wechat_group_runtime_messages_replaces_current_user_turn(self):
        enhanced = "<wechat-group-reply-policy>\ninternal\n</wechat-group-reply-policy>\n\nraw user text"
        raw = "raw user text"

        class FakeAgent:
            def __init__(self):
                self.messages_lock = threading.Lock()
                self.messages = [
                    {"role": "user", "content": [{"type": "text", "text": "older"}]},
                    {"role": "assistant", "content": [{"type": "text", "text": "older reply"}]},
                    {"role": "user", "content": [{"type": "text", "text": enhanced}]},
                ]
                self._last_run_new_messages = [
                    {"role": "user", "content": [{"type": "text", "text": enhanced}]},
                    {"role": "assistant", "content": [{"type": "text", "text": "answer"}]},
                ]

        agent = FakeAgent()

        changed = self._bridge()._sanitize_wechat_group_runtime_messages(agent, enhanced, raw)

        self.assertTrue(changed)
        self.assertEqual(raw, agent.messages[-1]["content"][0]["text"])
        self.assertEqual(raw, agent._last_run_new_messages[0]["content"][0]["text"])
        self.assertEqual("older", agent.messages[0]["content"][0]["text"])


if __name__ == "__main__":
    unittest.main()
