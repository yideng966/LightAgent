# encoding:utf-8
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bridge.context import Context, ContextType
from models.chatgpt.chat_gpt_bot import _format_query_for_log


class ChatGPTLoggingTest(unittest.TestCase):
    def test_free_reply_judge_query_log_is_summarized(self):
        prompt = "\n".join([
            "\u4f60\u662f LightAgent \u5fae\u4fe1\u7fa4\u81ea\u7531\u56de\u590d\u7684\u8f7b\u91cf\u5224\u5b9a\u5668\u3002",
            "",
            "\u53ea\u5224\u65ad\u662f\u5426\u9002\u5408\u63a5\u8bdd\uff0c\u4e0d\u8981\u751f\u6210\u6700\u7ec8\u56de\u590d\u3002",
            "\u53ea\u8fd4\u56de JSON\uff0c\u4e0d\u8981\u8fd4\u56de Markdown\u3002",
            "\u4e0d\u8981\u8c03\u7528\u5de5\u5177\uff0c\u4e0d\u8981\u5199\u5165\u8bb0\u5fc6\uff0c\u4e0d\u8981\u53d1\u9001\u6d88\u606f\u3002",
            "\u5982\u679c\u6d89\u53ca\u654f\u611f\u3001\u9690\u79c1\u3001\u5371\u9669\u3001\u4f4e\u4fe1\u606f\u3001\u4e24\u4eba\u79c1\u804a\u3001\u5237\u5c4f\u573a\u666f\uff0c\u8fd4\u56de should_reply=false\u3002",
            "",
            "\u8fd4\u56de\u683c\u5f0f\uff1a{\"should_reply\": true, \"confidence\": 0.82, \"reason\": \"\u4e00\u53e5\u8bdd\u539f\u56e0\", \"tone\": \"natural\"}",
            "",
            "\u7fa4\u540d\uff1apter\u5bb6\u5ead\u5f71\u9662\u3001\u5f71\u89c6\u4ea4\u6d41",
            "\u53d1\u9001\u8005\uff1a@0dd79585accacb4aca6566c4d15e1967",
            "\u6587\u672c\uff1a\u5c0f\u5c0f\u706f\u5417",
            "\u672c\u5730\u5f97\u5206\uff1a100",
            "\u672c\u5730\u9608\u503c\uff1a50",
            "\u52a0\u5206\u539f\u56e0\uff1abot_name_match, group_question, unanswered_question",
            "\u6291\u5236\u539f\u56e0\uff1a",
        ])
        context = Context(
            ContextType.TEXT,
            prompt,
            {"wechat_group_free_reply_judge": True},
        )

        summary = _format_query_for_log(prompt, context)

        self.assertIn("free_reply_judge", summary)
        self.assertIn("room=pter", summary)
        self.assertIn("text=\u5c0f\u5c0f\u706f\u5417", summary)
        self.assertIn("score=100", summary)
        self.assertIn("threshold=50", summary)
        self.assertIn("chars=", summary)
        self.assertNotIn("\u53ea\u5224\u65ad\u662f\u5426\u9002\u5408\u63a5\u8bdd", summary)
        self.assertNotIn("Markdown", summary)
        self.assertNotIn("\n", summary)

    def test_short_query_log_keeps_original_text(self):
        self.assertEqual("hello", _format_query_for_log("hello"))


if __name__ == "__main__":
    unittest.main()
