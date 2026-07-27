import unittest
from unittest.mock import Mock, patch

from config import conf
from channel.wechat_group.wechat_group_free_reply_scorer import (
    WechatGroupFreeReplyScorer,
    build_scorer_prompt,
    normalize_scorer_context,
    parse_scorer_response,
)


def scorer_json(
    target="bot",
    followup=True,
    desirability=0.9,
    confidence=0.9,
    action="reply",
):
    return (
        '{"target":"%s","is_followup_to_bot":%s,"reply_desirability":%s,'
        '"confidence":%s,"action":"%s","evidence":["same sender"],'
        '"reason":"clear follow-up"}'
    ) % (
        target,
        "true" if followup else "false",
        desirability,
        confidence,
        action,
    )


class WechatGroupFreeReplyScorerPureFunctionTest(unittest.TestCase):
    def test_parse_maps_direct_soft_and_ignore(self):
        direct = parse_scorer_response(scorer_json(), 0.82, 0.60)
        soft = parse_scorer_response(
            scorer_json(desirability=0.65, confidence=0.60, action="soft_reply"),
            0.82,
            0.60,
        )
        ignored = parse_scorer_response(
            scorer_json(target="user:bob", confidence=0.99),
            0.82,
            0.60,
        )

        self.assertTrue(direct["approved"])
        self.assertEqual("direct", direct["reply_mode"])
        self.assertTrue(soft["approved"])
        self.assertEqual("soft", soft["reply_mode"])
        self.assertFalse(ignored["approved"])
        self.assertEqual("", ignored["reply_mode"])

    def test_parse_honors_threshold_boundaries(self):
        approved = parse_scorer_response(
            scorer_json(desirability=0.82, confidence=0.82),
            0.82,
            0.60,
        )
        rejected = parse_scorer_response(
            scorer_json(followup=False, desirability=0.81, confidence=0.82),
            0.82,
            0.60,
        )

        self.assertTrue(approved["approved"])
        self.assertFalse(rejected["approved"])

    def test_parse_allows_group_soft_reply_and_weights_small_groups(self):
        small_group = parse_scorer_response(
            scorer_json(
                target="group",
                followup=False,
                desirability=0.52,
                confidence=0.52,
                action="soft_reply",
            ),
            0.82,
            0.60,
            group_size=6,
        )
        medium_group = parse_scorer_response(
            scorer_json(
                target="group",
                followup=False,
                desirability=0.52,
                confidence=0.52,
                action="soft_reply",
            ),
            0.82,
            0.60,
            group_size=12,
        )

        self.assertTrue(small_group["approved"])
        self.assertEqual("soft", small_group["reply_mode"])
        self.assertEqual("small", small_group["group_size_band"])
        self.assertEqual(0.50, small_group["effective_threshold"])
        self.assertFalse(medium_group["approved"])
        self.assertEqual(0.60, medium_group["effective_threshold"])

    def test_parse_keeps_large_groups_conservative(self):
        large_group = parse_scorer_response(
            scorer_json(
                target="group",
                followup=False,
                desirability=0.70,
                confidence=0.70,
                action="soft_reply",
            ),
            0.82,
            0.60,
            group_size=30,
        )
        invalid_group_direct = parse_scorer_response(
            scorer_json(
                target="group",
                followup=False,
                desirability=0.99,
                confidence=0.99,
                action="reply",
            ),
            0.82,
            0.60,
            group_size=6,
        )

        self.assertFalse(large_group["approved"])
        self.assertEqual("large", large_group["group_size_band"])
        self.assertEqual(0.75, large_group["effective_threshold"])
        self.assertFalse(invalid_group_direct["approved"])

    def test_parse_rejects_invalid_json_and_schema(self):
        invalid_json = parse_scorer_response("not json", 0.82, 0.60)
        invalid_schema = parse_scorer_response(
            '{"target":"bot","action":"reply"}',
            0.82,
            0.60,
        )

        self.assertEqual("invalid_json", invalid_json["error"])
        self.assertEqual("invalid_schema", invalid_schema["error"])
        self.assertFalse(invalid_json["approved"])
        self.assertFalse(invalid_schema["approved"])

    def test_normalize_marks_current_infers_bot_limits_and_redacts(self):
        rows = [
            {
                "message_id": "m1",
                "created_at": 1,
                "sender_id": "bot",
                "sender_nickname": "LightBot",
                "text": "论文快把我吃了 C:\\secret\\draft.md",
                "media_path": "C:\\private\\image.png",
            },
            {
                "message_id": "m2",
                "created_at": 2,
                "sender_id": "alice",
                "sender_nickname": "Alice",
                "text": "token=super-secret-value",
            },
        ]
        context = normalize_scorer_context(
            {
                "message_id": "m3",
                "timestamp": 3,
                "sender_id": "alice",
                "sender_name": "Alice",
                "bot_sender_id": "bot",
                "text": "啥论文",
            },
            rows,
            2,
        )

        self.assertEqual(2, len(context))
        self.assertEqual("CURRENT_MESSAGE", context[-1]["message_id"])
        self.assertEqual("啥论文", context[-1]["text"])
        self.assertNotIn("media_path", context[0])
        self.assertNotIn("super-secret-value", context[0]["text"])

        full = normalize_scorer_context(
            {
                "message_id": "m3",
                "sender_id": "alice",
                "bot_sender_id": "bot",
                "text": "啥论文",
            },
            rows,
            3,
        )
        self.assertTrue(full[0]["is_bot"])

    def test_normalize_adds_current_when_archive_does_not_contain_it(self):
        context = normalize_scorer_context(
            {"message_id": "current", "sender_id": "alice", "text": "继续"},
            [{"message_id": "old", "sender_id": "bob", "text": "之前"}],
            12,
        )

        self.assertEqual(["old", "CURRENT_MESSAGE"], [item["message_id"] for item in context])

    def test_prompt_contains_current_message_and_only_decision_instruction(self):
        prompt = build_scorer_prompt(
            {
                "room_name": "测试群",
                "group_size": 6,
                "group_size_source": "room_member_cache",
                "messages": [{"message_id": "CURRENT_MESSAGE", "text": "啥论文"}],
                "local_features": {"score": 0, "suppressions": ["below_threshold"]},
            }
        )

        serialized = "\n".join(item["content"] for item in prompt)
        self.assertIn("CURRENT_MESSAGE", serialized)
        self.assertIn("Do not answer the message", serialized)
        self.assertIn("Return one JSON object only", serialized)
        self.assertIn(
            "Write reason and every evidence item in concise Simplified Chinese",
            serialized,
        )
        self.assertIn("Keep reason within 40 Chinese characters", serialized)
        self.assertIn('"size_band":"small"', serialized)
        self.assertIn("ordinary casual participation is welcome", serialized)
        self.assertIn('target="group"', serialized)


class WechatGroupFreeReplyScorerTest(unittest.TestCase):
    def setUp(self):
        self._original_provider = conf().get("wechat_group_free_reply_scorer_provider")
        self._original_model = conf().get("wechat_group_free_reply_scorer_model")
        conf()["wechat_group_free_reply_scorer_provider"] = "custom:scorer"
        conf()["wechat_group_free_reply_scorer_model"] = "scorer-model"

    def tearDown(self):
        for key, value in (
            ("wechat_group_free_reply_scorer_provider", self._original_provider),
            ("wechat_group_free_reply_scorer_model", self._original_model),
        ):
            if value is None:
                conf().pop(key, None)
            else:
                conf()[key] = value

    @staticmethod
    def config(**overrides):
        result = {
            "scorer_context_limit": 12,
            "scorer_reply_threshold": 0.82,
            "scorer_soft_reply_threshold": 0.60,
            "scorer_max_tokens": 256,
            "scorer_fallback_to_rules": True,
        }
        result.update(overrides)
        return result

    @staticmethod
    def task():
        return {
            "room_id": "wgr_room",
            "room_name": "测试群",
            "sender_id": "wgm_alice",
            "sender_name": "Alice",
            "text": "啥论文",
            "msg": Mock(msg_id="m2", create_time=2, to_user_id="wxid_bot"),
            "recent_messages": [
                {
                    "message_id": "m1",
                    "created_at": 1,
                    "sender_id": "wxid_bot",
                    "sender_nickname": "LightBot",
                    "text": "论文快把我吃了",
                }
            ],
            "local_decision": {
                "score": 0,
                "threshold": 50,
                "reasons": [],
                "suppressions": ["below_threshold"],
            },
        }

    def test_score_calls_shared_router_with_model_override(self):
        router = Mock()
        router.complete.return_value = {
            "success": True,
            "content": scorer_json(),
        }
        scorer = WechatGroupFreeReplyScorer(router=router)

        decision = scorer.score(self.task(), self.config())

        self.assertTrue(decision["approved"])
        args, kwargs = router.complete.call_args
        self.assertEqual(2, len(args[0]))
        self.assertEqual("wechat_group_free_reply_scorer", kwargs["purpose"])
        self.assertEqual("custom:scorer", kwargs["provider"])
        self.assertEqual("scorer-model", kwargs["model"])
        self.assertEqual(256, kwargs["max_tokens"])
        self.assertEqual(
            {
                "reasoning_effort": "none",
                "response_format": {"type": "json_object"},
            },
            kwargs["request_options"],
        )

    def test_runtime_router_is_resolved_again_after_bridge_reset(self):
        first_router = Mock()
        second_router = Mock()
        first_router.complete.return_value = {
            "success": True,
            "content": scorer_json(),
        }
        second_router.complete.return_value = {
            "success": True,
            "content": scorer_json(),
        }
        bridge = Mock()
        bridge.get_text_model_router.side_effect = [first_router, second_router]

        with patch(
            "channel.wechat_group.wechat_group_free_reply_scorer.Bridge",
            return_value=bridge,
        ):
            scorer = WechatGroupFreeReplyScorer()
            scorer.score(self.task(), self.config())
            scorer.score(self.task(), self.config())

        self.assertEqual(2, bridge.get_text_model_router.call_count)
        first_router.complete.assert_called_once()
        second_router.complete.assert_called_once()

    def test_unconfigured_model_falls_back_without_calling_router(self):
        conf()["wechat_group_free_reply_scorer_provider"] = ""
        router = Mock()

        decision = WechatGroupFreeReplyScorer(router=router).score(
            self.task(),
            self.config(scorer_fallback_to_rules=True),
        )

        self.assertFalse(decision["approved"])
        self.assertEqual("scorer_model_unconfigured", decision["error"])
        self.assertTrue(decision["fallback_to_rules"])
        router.complete.assert_not_called()

    def test_non_bot_target_is_ignored(self):
        router = Mock()
        router.complete.return_value = {
            "success": True,
            "content": scorer_json(target="user:bob"),
        }

        decision = WechatGroupFreeReplyScorer(router=router).score(
            self.task(), self.config()
        )

        self.assertFalse(decision["approved"])

    def test_group_soft_reply_uses_task_group_size(self):
        router = Mock()
        router.complete.return_value = {
            "success": True,
            "content": scorer_json(
                target="group",
                followup=False,
                desirability=0.52,
                confidence=0.52,
                action="soft_reply",
            ),
        }
        task = self.task()
        task["group_size"] = 6
        task["group_size_source"] = "room_member_cache"

        decision = WechatGroupFreeReplyScorer(router=router).score(
            task,
            self.config(),
        )

        self.assertTrue(decision["approved"])
        self.assertEqual("soft", decision["reply_mode"])
        self.assertEqual(6, decision["group_size"])
        self.assertEqual("room_member_cache", decision["group_size_source"])

    def test_invalid_json_falls_back_or_closes(self):
        router = Mock()
        router.complete.return_value = {"success": True, "content": "invalid"}
        scorer = WechatGroupFreeReplyScorer(router=router)

        fallback = scorer.score(self.task(), self.config(scorer_fallback_to_rules=True))
        closed = scorer.score(self.task(), self.config(scorer_fallback_to_rules=False))

        self.assertTrue(fallback["fallback_to_rules"])
        self.assertFalse(closed["fallback_to_rules"])
        self.assertFalse(closed["approved"])
        self.assertEqual(2, scorer.status()["invalid_json"])

    def test_model_failure_and_exception_fail_closed(self):
        failed_router = Mock()
        failed_router.complete.return_value = {
            "success": False,
            "content": "temporarily unavailable",
            "raw": {"error": True, "status_code": 503},
        }
        exception_router = Mock()
        exception_router.complete.side_effect = RuntimeError("offline")

        failed = WechatGroupFreeReplyScorer(router=failed_router).score(
            self.task(), self.config(scorer_fallback_to_rules=False)
        )
        exception = WechatGroupFreeReplyScorer(router=exception_router).score(
            self.task(), self.config(scorer_fallback_to_rules=False)
        )

        self.assertEqual("model_error", failed["error"])
        self.assertIn("temporarily unavailable", failed["reason"])
        self.assertEqual("exception", exception["error"])
        self.assertFalse(exception["approved"])

    def test_timeout_envelope_is_counted(self):
        router = Mock()
        router.complete.return_value = {
            "success": False,
            "content": "request timeout",
            "raw": {"error": True, "status_code": 408},
        }
        scorer = WechatGroupFreeReplyScorer(router=router)

        decision = scorer.score(
            self.task(),
            self.config(scorer_fallback_to_rules=False),
        )

        self.assertEqual("timeout", decision["error"])
        self.assertEqual(1, scorer.status()["timeout"])


if __name__ == "__main__":
    unittest.main()
