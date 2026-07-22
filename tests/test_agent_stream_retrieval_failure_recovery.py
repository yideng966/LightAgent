# encoding:utf-8
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.protocol.agent_stream import AgentStreamExecutor
from agent.protocol.models import LLMModel


class DummyModel(LLMModel):
    def __init__(self):
        super().__init__(model="unit-test-model")

    def call_stream(self, request):
        return iter(())


class TestAgentStreamRetrievalFailureRecovery(unittest.TestCase):
    def _executor_with_failures(self, tool_name, failure_count=8):
        executor = AgentStreamExecutor(
            agent=None,
            model=DummyModel(),
            system_prompt="",
            tools={},
            messages=[],
        )
        for index in range(failure_count):
            executor.tool_failure_history.append(
                (tool_name, executor._hash_args({"url": f"https://docs.example.com/missing-{index}"}), False)
            )
        return executor

    def test_web_fetch_consecutive_failure_guard_returns_recoverable_error(self):
        executor = self._executor_with_failures("web_fetch")

        result = executor._execute_tool({
            "id": "call_web_fetch",
            "name": "web_fetch",
            "arguments": {"url": "https://docs.example.com/missing-final"},
        })

        self.assertEqual("error", result["status"])
        self.assertIn("停止继续抓取", result["result"])
        self.assertIn("基于已经成功获取的内容总结", result["result"])
        self.assertIn("向用户询问更准确的链接", result["result"])
        self.assertNotIn("抱歉，我没能完成这个任务", result["result"])

    def test_web_search_consecutive_failure_guard_returns_recoverable_error(self):
        executor = self._executor_with_failures("web_search")

        result = executor._execute_tool({
            "id": "call_web_search",
            "name": "web_search",
            "arguments": {"query": "missing docs page"},
        })

        self.assertEqual("error", result["status"])
        self.assertIn("停止继续抓取", result["result"])
        self.assertIn("基于已经成功获取的内容总结", result["result"])
        self.assertIn("向用户询问更准确的链接", result["result"])

    def test_non_retrieval_tool_keeps_critical_consecutive_failure_guard(self):
        executor = self._executor_with_failures("bash")

        result = executor._execute_tool({
            "id": "call_bash",
            "name": "bash",
            "arguments": {"command": "bad-command"},
        })

        self.assertEqual("critical_error", result["status"])
        self.assertIn("抱歉，我没能完成这个任务", result["result"])


if __name__ == "__main__":
    unittest.main()
