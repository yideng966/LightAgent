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

        self.assertEqual("分析过程最终答复", content)
        self.assertEqual("分析过程最终答复", self._event_text(events, "message_update"))
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

    def test_wechat_group_strips_untagged_reasoning_preamble_before_events_and_history(self):
        leaked_reasoning = (
            "用户@我说话了，先看看上下文。一灯发了个图让我找番号，但群内敏感内容识别容易触发热词拦截。\n\n"
            "我应该用自然接话的方式回应“镜像拉了好久了还不行”，不用太严肃。\n\n"
            "镜像拉这么久还不行啊，是网络慢还是源有问题啊？[捂脸]"
        )
        content, _, events, messages = self._run([
            {"content": leaked_reasoning[:42]},
            {"content": leaked_reasoning[42:96]},
            {"content": leaked_reasoning[96:]},
        ], context_channel_type="wechat_group")

        self.assertEqual("镜像拉这么久还不行啊，是网络慢还是源有问题啊？[捂脸]", content)
        self.assertEqual(content, self._event_text(events, "message_update"))
        self.assertNotIn("先看看上下文", str(messages))
        self.assertNotIn("我应该用自然接话", str(messages))

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

    def test_wechat_group_strips_single_newline_untagged_reasoning(self):
        leaked_reasoning = (
            "用户@小灯说话了，先看看上下文。\n"
            "我看看聊天记录，再决定怎么接话。\n"
            "不过需要保持简短自然。\n"
            "最终答复第一行。\n最终答复第二行。"
        )
        content, _, events, messages = self._run([
            {"content": leaked_reasoning},
        ], context_channel_type="wechat_group")

        self.assertEqual("最终答复第一行。\n最终答复第二行。", content)
        self.assertEqual(content, self._event_text(events, "message_update"))
        self.assertNotIn("先看看上下文", str(messages))
        self.assertNotIn("我看看聊天记录", str(messages))

    def test_wechat_group_preserves_normal_multi_paragraph_reply(self):
        normal_reply = (
            "用户可以先检查镜像源和网络连接。\n\n"
            "我建议再运行 docker stats 看看资源占用。\n\n"
            "如果下载进度仍然不动，再检查代理配置。"
        )
        content, _, events, messages = self._run([
            {"content": normal_reply},
        ], context_channel_type="wechat_group")

        self.assertEqual(normal_reply, content)
        self.assertEqual(normal_reply, self._event_text(events, "message_update"))
        self.assertEqual(normal_reply, messages[-1]["content"][-1]["text"])


if __name__ == "__main__":
    unittest.main()
