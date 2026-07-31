# encoding:utf-8
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.protocol.agent_stream import AgentStreamExecutor
from agent.protocol.models import (
    AGENT_FINISH_TOOL_NAME,
    LLMModel,
)
from agent.tools.base_tool import BaseTool, ToolResult


class FakeSearchTool(BaseTool):
    name = "web_search"
    description = "Search the web"
    params = {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    }

    def execute(self, params):
        return ToolResult.success({"results": [{"title": "显卡价格走势"}]})


class ScriptedToolModel(LLMModel):
    def __init__(self, second_turn, third_turn=None):
        super().__init__(model="unit-test-model")
        self.channel_type = "wechat_group"
        self.second_turn = second_turn
        self.third_turn = third_turn
        self.requests = []

    def call_stream(self, request):
        self.requests.append(request)
        if len(self.requests) == 1:
            yield {
                "choices": [{
                    "delta": {"tool_calls": [{
                        "index": 0,
                        "id": "call-search",
                        "function": {
                            "name": "web_search",
                            "arguments": '{"query":"显卡价格"}',
                        },
                    }]},
                    "finish_reason": "tool_calls",
                }],
            }
            return
        if len(self.requests) == 2 or self.third_turn is None:
            yield self.second_turn
            return
        yield self.third_turn


class AgentStreamFinishToolTest(unittest.TestCase):
    @staticmethod
    def _executor(second_turn, third_turn=None):
        events = []
        model = ScriptedToolModel(second_turn, third_turn)
        executor = AgentStreamExecutor(
            agent=None,
            model=model,
            system_prompt="",
            tools=[FakeSearchTool()],
            messages=[],
            on_event=events.append,
            context={"channel_type": "wechat_group"},
        )
        return executor, model, events

    def test_tool_result_is_completed_through_native_finish_tool(self):
        final_text = "显卡价格较2025年618上涨约20%。"
        executor, model, events = self._executor({
            "choices": [{
                "delta": {"tool_calls": [{
                    "index": 0,
                    "id": "call-finish",
                    "function": {
                        "name": AGENT_FINISH_TOOL_NAME,
                        "arguments": '{"message":"' + final_text + '"}',
                    },
                }]},
                "finish_reason": "tool_calls",
            }],
        })

        with patch("config.conf", return_value={"enable_thinking": False}):
            result = executor.run_stream("现在显卡涨价多少？")

        self.assertEqual(final_text, result)
        self.assertEqual(2, len(model.requests))
        self.assertTrue(model.requests[1].require_finish_tool)
        self.assertIn(
            AGENT_FINISH_TOOL_NAME,
            {tool["name"] for tool in model.requests[1].tools},
        )
        self.assertNotIn("tool_use", str(executor.messages[-1]))
        self.assertEqual(final_text, executor.messages[-1]["content"][-1]["text"])
        self.assertIn(final_text, str(events))

    def test_plain_progress_text_after_tool_result_is_hidden_and_retried(self):
        intermediate = "搜到了一些相关信息，但不太完整。让我看看更具体的内容。"
        final_text = "显卡价格较2025年618上涨约20%。"
        executor, model, events = self._executor(
            {
                "choices": [{
                    "delta": {"content": intermediate},
                    "finish_reason": "stop",
                }],
            },
            {
                "choices": [{
                    "delta": {"content": final_text},
                    "finish_reason": "stop",
                }],
            },
        )

        with patch("config.conf", return_value={"enable_thinking": False}):
            result = executor.run_stream("现在显卡涨价多少？")

        self.assertEqual(final_text, result)
        self.assertEqual(3, len(model.requests))
        self.assertTrue(model.requests[1].require_finish_tool)
        self.assertFalse(model.requests[2].require_finish_tool)
        self.assertNotIn(
            AGENT_FINISH_TOOL_NAME,
            {tool["name"] for tool in model.requests[2].tools},
        )
        self.assertNotIn(intermediate, str(executor.messages))
        self.assertNotIn(intermediate, str(events))
        self.assertIn(final_text, str(executor.messages))
        self.assertIn(final_text, str(events))


if __name__ == "__main__":
    unittest.main()
