# encoding:utf-8
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.protocol.agent_stream import AgentStreamExecutor
from agent.protocol.models import LLMModel
from agent.tools.base_tool import ToolResult


class TextOnlyModel(LLMModel):
    def __init__(self, text):
        super().__init__(model="unit-test-model")
        self.text = text

    def call_stream(self, request):
        yield {
            "choices": [
                {
                    "delta": {"content": self.text},
                    "finish_reason": "stop",
                }
            ]
        }


class SchedulerCreateThenTextModel(LLMModel):
    def __init__(self):
        super().__init__(model="unit-test-model")
        self.calls = 0

    def call_stream(self, request):
        self.calls += 1
        if self.calls == 1:
            yield {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "call_scheduler_1",
                                    "function": {
                                        "name": "scheduler",
                                        "arguments": (
                                            '{"action":"create","name":"每日喝水提醒",'
                                            '"message":"该喝水了",'
                                            '"schedule_type":"cron",'
                                            '"schedule_value":"0 12 * * *"}'
                                        ),
                                    },
                                }
                            ]
                        },
                        "finish_reason": "tool_calls",
                    }
                ]
            }
            return
        yield {
            "choices": [
                {
                    "delta": {"content": "已设置，每天12点提醒你喝水。"},
                    "finish_reason": "stop",
                }
            ]
        }


class FakeSchedulerTool:
    name = "scheduler"
    description = "manage scheduled tasks"
    params = {"type": "object", "properties": {"action": {"type": "string"}}}

    def __init__(self):
        self.calls = []

    def execute_tool(self, params):
        self.calls.append(params)
        return ToolResult.success("定时任务创建成功")


class TestAgentStreamSchedulerGuard(unittest.TestCase):
    def test_scheduler_request_without_create_is_not_confirmed(self):
        executor = AgentStreamExecutor(
            agent=None,
            model=TextOnlyModel("已设置，每天12点提醒你喝水。"),
            system_prompt="",
            tools=[],
            messages=[],
            context={"intent_requires_scheduler": True},
        )

        response = executor.run_stream("每天12点提醒我喝水")

        self.assertIn("没有成功创建定时任务", response)
        self.assertNotIn("已设置，每天12点提醒你喝水。", response)

    def test_scheduler_request_clarification_without_create_is_preserved(self):
        executor = AgentStreamExecutor(
            agent=None,
            model=TextOnlyModel("你想让我几点提醒？"),
            system_prompt="",
            tools=[],
            messages=[],
            context={"intent_requires_scheduler": True},
        )

        response = executor.run_stream("提醒我喝水")

        self.assertEqual("你想让我几点提醒？", response)

    def test_scheduler_create_success_allows_confirmation(self):
        scheduler = FakeSchedulerTool()
        executor = AgentStreamExecutor(
            agent=None,
            model=SchedulerCreateThenTextModel(),
            system_prompt="",
            tools=[scheduler],
            messages=[],
            context={"intent_requires_scheduler": True},
        )

        response = executor.run_stream("每天12点提醒我喝水")

        self.assertEqual("已设置，每天12点提醒你喝水。", response)
        self.assertEqual("create", scheduler.calls[0]["action"])


if __name__ == "__main__":
    unittest.main()
