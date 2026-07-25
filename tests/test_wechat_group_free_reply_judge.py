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
        bridge.complete_text.return_value = {
            "success": True,
            "content": '{"should_reply": true, "confidence": 0.8, "reason": "可接话", "tone": "natural"}',
        }
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
        bridge.complete_text.assert_called_once()
        self.assertEqual(
            "wechat_group_free_reply_judge",
            bridge.complete_text.call_args.kwargs["purpose"],
        )

    def test_judge_rejects_failed_stateless_completion(self):
        bridge = Mock()
        bridge.complete_text.return_value = {"success": False, "content": "rate limit"}

        result = WechatGroupFreeReplyJudge(bridge=bridge).judge(
            {"room_id": "room@@abc", "text": "hello", "local_decision": {}},
            {"llm_judge_min_confidence": 0.6},
        )

        self.assertFalse(result["approved"])
        self.assertEqual("model_error", result["error"])

    def test_enabled_scorer_is_used_without_bridge(self):
        bridge = Mock()
        scorer = Mock()
        scorer.score.return_value = {
            "approved": True,
            "reply_mode": "direct",
            "confidence": 0.9,
            "source": "scorer",
        }
        judge = WechatGroupFreeReplyJudge(bridge=bridge, scorer=scorer)
        task = {
            "room_id": "wgr_room",
            "text": "啥论文",
            "local_decision": {"reasons": [], "suppressions": ["below_threshold"]},
        }

        result = judge.judge(task, {"scorer_enabled": True})

        self.assertTrue(result["approved"])
        scorer.score.assert_called_once()
        bridge.fetch_reply_content.assert_not_called()

    def test_scorer_failure_falls_back_to_bridge_when_enabled(self):
        bridge = Mock()
        bridge.complete_text.return_value = {
            "success": True,
            "content": '{"should_reply": true, "confidence": 0.8, "reason": "可接话", "tone": "natural"}',
        }
        scorer = Mock()
        scorer.score.return_value = {
            "approved": False,
            "error": "timeout",
            "fallback_to_rules": True,
            "source": "scorer",
        }
        judge = WechatGroupFreeReplyJudge(bridge=bridge, scorer=scorer)

        result = judge.judge(
            {
                "room_id": "wgr_room",
                "text": "啥论文",
                "local_decision": {"reasons": [], "suppressions": ["below_threshold"]},
            },
            {
                "scorer_enabled": True,
                "llm_judge_enabled": True,
                "llm_judge_min_confidence": 0.6,
            },
        )

        self.assertTrue(result["approved"])
        scorer.score.assert_called_once()
        bridge.complete_text.assert_called_once()

    def test_scorer_failure_without_fallback_is_rejected(self):
        bridge = Mock()
        scorer = Mock()
        scorer.score.return_value = {
            "approved": False,
            "error": "timeout",
            "fallback_to_rules": False,
            "source": "scorer",
        }
        judge = WechatGroupFreeReplyJudge(bridge=bridge, scorer=scorer)

        result = judge.judge(
            {"local_decision": {"reasons": []}},
            {"scorer_enabled": True, "scorer_fallback_to_rules": False},
        )

        self.assertFalse(result["approved"])
        bridge.fetch_reply_content.assert_not_called()

    def test_force_keyword_bypasses_scorer(self):
        scorer = Mock()
        judge = WechatGroupFreeReplyJudge(bridge=Mock(), scorer=scorer)

        result = judge.judge(
            {"local_decision": {"reasons": ["force_keyword_match"]}},
            {"scorer_enabled": True},
        )

        self.assertTrue(result["approved"])
        self.assertEqual("local", result["source"])
        scorer.score.assert_not_called()


if __name__ == "__main__":
    unittest.main()
