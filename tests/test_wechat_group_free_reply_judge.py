import unittest
from unittest.mock import Mock

from channel.wechat_group.wechat_group_free_reply_judge import (
    WechatGroupFreeReplyJudge,
    build_free_reply_judge_prompt,
    parse_free_reply_judge_reply,
)


class WechatGroupFreeReplyJudgeTest(unittest.TestCase):
    def test_parse_approved_json_decision(self):
        result = parse_free_reply_judge_reply(
            '{"should_reply": true, "confidence": 0.82, "reason": "可接话", "tone": "natural"}',
            0.6,
        )

        self.assertTrue(result["approved"])
        self.assertEqual(0.82, result["confidence"])

    def test_parse_rejected_json_decision(self):
        result = parse_free_reply_judge_reply(
            '{"should_reply": false, "confidence": 0.9, "reason": "两人私聊", "tone": "silent"}',
            0.6,
        )

        self.assertFalse(result["approved"])
        self.assertEqual("两人私聊", result["reason"])

    def test_invalid_json_is_rejected(self):
        result = parse_free_reply_judge_reply("我觉得可以接", 0.6)

        self.assertFalse(result["approved"])
        self.assertEqual("invalid_json", result["error"])

    def test_low_confidence_is_rejected(self):
        result = parse_free_reply_judge_reply(
            '{"should_reply": true, "confidence": 0.4, "reason": "不确定", "tone": "natural"}',
            0.6,
        )

        self.assertFalse(result["approved"])
        self.assertEqual("low_confidence", result["error"])

    def test_prompt_contains_decision_constraints(self):
        prompt = build_free_reply_judge_prompt({
            "room_name": "测试群",
            "sender_name": "Alice",
            "text": "谁能总结一下？",
            "local_decision": {
                "score": 55,
                "threshold": 50,
                "reasons": ["group_question"],
                "suppressions": [],
            },
        })

        self.assertIn("只判断是否适合接话", prompt)
        self.assertIn("只返回 JSON", prompt)
        self.assertIn("不要生成最终回复", prompt)
        self.assertIn("不要调用工具", prompt)
        self.assertIn("不要写入记忆", prompt)

    def test_judge_uses_bridge_and_parses_reply(self):
        bridge = Mock()
        bridge.fetch_reply_content.return_value = (
            '{"should_reply": true, "confidence": 0.8, "reason": "可接话", "tone": "natural"}'
        )
        judge = WechatGroupFreeReplyJudge(bridge=bridge)

        result = judge.judge(
            {
                "room_id": "room@@abc",
                "room_name": "测试群",
                "sender_name": "Alice",
                "text": "谁能总结一下？",
                "local_decision": {"score": 55, "threshold": 50, "reasons": [], "suppressions": []},
            },
            {"llm_judge_min_confidence": 0.6},
        )

        self.assertTrue(result["approved"])
        bridge.fetch_reply_content.assert_called_once()


if __name__ == "__main__":
    unittest.main()
