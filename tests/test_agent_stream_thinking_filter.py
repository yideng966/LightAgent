# encoding:utf-8
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.protocol.agent_stream import AgentStreamExecutor
from agent.protocol.models import LLMModel


class ChunkedThinkingModel(LLMModel):
    def __init__(self, deltas, channel_type="wechat_group"):
        super().__init__(model="unit-test-model")
        self.deltas = deltas
        self.channel_type = channel_type

    def call_stream(self, request):
        for index, delta in enumerate(self.deltas):
            yield {
                "choices": [
                    {
                        "delta": delta,
                        "finish_reason": "stop" if index == len(self.deltas) - 1 else None,
                    }
                ]
            }


class TestAgentStreamThinkingFilter(unittest.TestCase):
    @staticmethod
    def _run(
        deltas,
        channel_type="wechat_group",
        thinking_enabled=True,
        context_channel_type=None,
    ):
        events = []
        context = (
            {"channel_type": context_channel_type}
            if context_channel_type is not None
            else None
        )
        executor = AgentStreamExecutor(
            agent=None,
            model=ChunkedThinkingModel(deltas, channel_type=channel_type),
            system_prompt="",
            tools=[],
            messages=[],
            on_event=events.append,
            context=context,
        )
        with patch("config.conf", return_value={"enable_thinking": thinking_enabled}):
            content, tool_calls = executor._call_llm_stream(retry_on_empty=False)
        return content, tool_calls, events, executor.messages

    @staticmethod
    def _event_text(events, event_type):
        return "".join(
            event.get("data", {}).get("delta", "")
            for event in events
            if event.get("type") == event_type
        )

    def test_wechat_group_drops_thinking_when_complete_tags_are_separate_chunks(self):
        private_reasoning = "PRIVATE_REASONING_SHOULD_NOT_LEAK"
        content, tool_calls, events, messages = self._run([
            {"content": "<think>"},
            {"content": private_reasoning},
            {"content": "</think>"},
            {"content": "最终答复"},
        ])

        self.assertEqual("最终答复", content)
        self.assertEqual([], tool_calls)
        self.assertEqual("最终答复", self._event_text(events, "message_update"))
        self.assertNotIn(private_reasoning, str(messages))
        self.assertNotIn("</think>", str(messages))

    def test_wechat_group_handles_tags_split_inside_tag_names(self):
        private_reasoning = "SPLIT_PRIVATE_REASONING"
        content, _, events, messages = self._run([
            {"content": "答复前缀"},
            {"content": "<thi"},
            {"content": "nk>"},
            {"content": private_reasoning},
            {"content": "</th"},
            {"content": "ink>"},
            {"content": "答复后缀"},
        ])

        self.assertEqual("答复前缀答复后缀", content)
        self.assertEqual("答复前缀答复后缀", self._event_text(events, "message_update"))
        self.assertNotIn(private_reasoning, str(messages))

    def test_wechat_group_fails_closed_for_unclosed_thinking_block(self):
        private_reasoning = "UNCLOSED_PRIVATE_REASONING"
        content, _, events, messages = self._run([
            {"content": "可见正文"},
            {"content": "<think>"},
            {"content": private_reasoning},
        ])

        self.assertEqual("可见正文", content)
        self.assertEqual("可见正文", self._event_text(events, "message_update"))
        self.assertNotIn(private_reasoning, str(messages))

    def test_wechat_group_removes_stray_closing_tag(self):
        content, _, events, _ = self._run([
            {"content": "</think>"},
            {"content": "最终答复"},
        ])

        self.assertEqual("最终答复", content)
        self.assertEqual("最终答复", self._event_text(events, "message_update"))

    def test_web_keeps_inline_thinking_text_without_raw_tags(self):
        content, _, events, messages = self._run([
            {"content": "<thi"},
            {"content": "nk>分析过程"},
            {"content": "</think>最终答复"},
        ], channel_type="web")

        self.assertEqual("最终答复", content)
        self.assertEqual("最终答复", self._event_text(events, "message_update"))
        self.assertEqual("分析过程", self._event_text(events, "reasoning_update"))
        self.assertEqual("thinking", messages[-1]["content"][0]["type"])
        self.assertEqual("分析过程", messages[-1]["content"][0]["thinking"])
        self.assertNotIn("<think>", str(messages))
        self.assertNotIn("</think>", str(messages))

    def test_web_drops_inline_thinking_when_thinking_is_disabled(self):
        content, _, events, messages = self._run([
            {"content": "<think>分析过程"},
            {"content": "</think>最终答复"},
        ], channel_type="web", thinking_enabled=False)

        self.assertEqual("最终答复", content)
        self.assertEqual("最终答复", self._event_text(events, "message_update"))
        self.assertNotIn("分析过程", str(messages))

    def test_tag_like_plain_text_is_preserved(self):
        plain_text = "普通文本 <thinker> 与未完成字面量 <thi"
        content, _, events, messages = self._run([
            {"content": plain_text},
        ])

        self.assertEqual(plain_text, content)
        self.assertEqual(plain_text, self._event_text(events, "message_update"))
        self.assertIn(plain_text, str(messages))

    def test_reasoning_content_stays_separate_from_final_text(self):
        private_reasoning = "STANDARD_PRIVATE_REASONING"
        content, _, events, messages = self._run([
            {"reasoning_content": private_reasoning},
            {"content": "最终答复"},
        ])

        self.assertEqual("最终答复", content)
        self.assertEqual("最终答复", self._event_text(events, "message_update"))
        self.assertEqual(private_reasoning, self._event_text(events, "reasoning_update"))
        self.assertEqual("thinking", messages[-1]["content"][0]["type"])
        self.assertEqual("text", messages[-1]["content"][1]["type"])
        self.assertEqual("最终答复", messages[-1]["content"][1]["text"])

    def test_wechat_group_context_overrides_stale_web_model_channel(self):
        private_reasoning = "CONTEXT_SCOPED_PRIVATE_REASONING"
        content, _, events, messages = self._run([
            {"content": "<think>"},
            {"content": private_reasoning},
            {"content": "</think>最终答复"},
        ], channel_type="web", context_channel_type="wechat_group")

        self.assertEqual("最终答复", content)
        self.assertEqual("最终答复", self._event_text(events, "message_update"))
        self.assertNotIn(private_reasoning, str(messages))

    def test_wechat_group_preserves_normal_multi_paragraph_reply(self):
        normal_reply = (
            "用户请求中的“上下文”是发送给模型的系统提示和历史消息。\n\n"
            "我需要先区分请求上下文与持久化会话。\n\n"
            "请求上下文在每次调用时组装，会话历史按 session_id 保存。"
        )
        content, _, events, messages = self._run([
            {"content": normal_reply},
        ], context_channel_type="wechat_group")

        self.assertEqual(normal_reply, content)
        self.assertEqual(normal_reply, self._event_text(events, "message_update"))
        self.assertEqual(normal_reply, messages[-1]["content"][-1]["text"])

    def test_wechat_group_tool_turn_drops_intermediate_content_from_events_and_history(self):
        content, tool_calls, events, messages = self._run([
            {"content": "我先看看项目文件。"},
            {
                "tool_calls": [{
                    "index": 0,
                    "id": "call_read",
                    "function": {
                        "name": "read",
                        "arguments": '{"path":"README.md"}',
                    },
                }],
            },
        ], context_channel_type="wechat_group")

        self.assertEqual("", content)
        self.assertEqual("", self._event_text(events, "message_update"))
        self.assertEqual("read", tool_calls[0]["name"])
        self.assertNotIn("我先看看项目文件", str(messages))
        self.assertEqual(["tool_use"], [block["type"] for block in messages[-1]["content"]])


if __name__ == "__main__":
    unittest.main()
