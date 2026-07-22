# encoding:utf-8
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bridge.context import Context, ContextType
from bridge.agent_event_handler import AgentEventHandler
from common import const


class FakeChannel:
    def __init__(self):
        self.sent = []

    def _send(self, reply, context):
        self.sent.append((reply, context))


class TestAgentEventHandlerWechatGroup(unittest.TestCase):
    def _handler(self, channel_type):
        channel = FakeChannel()
        context = Context(
            ContextType.TEXT,
            "hello",
            kwargs={"channel": channel, "channel_type": channel_type},
        )
        return AgentEventHandler(context=context), channel

    def test_wechat_group_suppresses_tool_call_intermediate_message(self):
        handler, channel = self._handler(const.WECHAT_GROUP)

        handler.handle_event({"type": "turn_start", "data": {"turn": 1}})
        handler.handle_event({"type": "message_update", "data": {"delta": "我先看看文档"}})
        handler.handle_event({
            "type": "message_end",
            "data": {"tool_calls": [{"name": "web_fetch"}]},
        })

        self.assertEqual([], channel.sent)

    def test_non_wechat_group_keeps_tool_call_intermediate_message(self):
        handler, channel = self._handler("web")

        handler.handle_event({"type": "turn_start", "data": {"turn": 1}})
        handler.handle_event({"type": "message_update", "data": {"delta": "我先看看文档"}})
        handler.handle_event({
            "type": "message_end",
            "data": {"tool_calls": [{"name": "web_fetch"}]},
        })

        self.assertEqual(1, len(channel.sent))
        self.assertEqual("我先看看文档", channel.sent[0][0].content)


if __name__ == "__main__":
    unittest.main()
