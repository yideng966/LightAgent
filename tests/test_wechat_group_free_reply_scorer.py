import os
import unittest
from unittest.mock import Mock, patch

from config import conf
from models.openai.openai_http_client import OpenAIHTTPError
from channel.wechat_group.wechat_group_free_reply_scorer import (
    WechatGroupFreeReplyScorer,
    _resolve_scorer_credentials,
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
        self._original_key = conf().get("wechat_group_free_reply_scorer_api_key")
        conf()["wechat_group_free_reply_scorer_api_key"] = "config-key"

    def tearDown(self):
        if self._original_key is None:
            conf().pop("wechat_group_free_reply_scorer_api_key", None)
        else:
            conf()["wechat_group_free_reply_scorer_api_key"] = self._original_key

    @staticmethod
    def config(**overrides):
        result = {
            "scorer_provider": "openai_compatible",
            "scorer_model": "scorer-model",
            "scorer_api_base": "https://scorer.example/v1",
            "scorer_timeout_seconds": 5,
            "scorer_context_limit": 12,
            "scorer_reply_threshold": 0.82,
            "scorer_soft_reply_threshold": 0.60,
            "scorer_temperature": 0.0,
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

    def test_score_calls_independent_client_with_explicit_settings(self):
        client = Mock()
        client.chat_completions.return_value = {
            "choices": [{"message": {"content": scorer_json()}}]
        }
        scorer = WechatGroupFreeReplyScorer(client=client)

        decision = scorer.score(self.task(), self.config())

        self.assertTrue(decision["approved"])
        kwargs = client.chat_completions.call_args.kwargs
        self.assertEqual("config-key", kwargs["api_key"])
        self.assertEqual("https://scorer.example/v1", kwargs["api_base"])
        self.assertEqual("scorer-model", kwargs["model"])
        self.assertEqual(5, kwargs["timeout"])
        self.assertEqual(0.0, kwargs["temperature"])
        self.assertEqual(256, kwargs["max_tokens"])
        self.assertEqual("none", kwargs["reasoning_effort"])
        self.assertEqual({"type": "json_object"}, kwargs["response_format"])

    def test_score_retries_basic_payload_when_structured_options_are_unsupported(self):
        client = Mock()
        client.chat_completions.side_effect = [
            OpenAIHTTPError(
                400,
                {"error": {"message": "Unsupported parameter: reasoning_effort"}},
            ),
            {"choices": [{"message": {"content": scorer_json()}}]},
        ]

        decision = WechatGroupFreeReplyScorer(client=client).score(
            self.task(), self.config()
        )

        self.assertTrue(decision["approved"])
        self.assertEqual(2, client.chat_completions.call_count)
        first = client.chat_completions.call_args_list[0].kwargs
        second = client.chat_completions.call_args_list[1].kwargs
        self.assertEqual("none", first["reasoning_effort"])
        self.assertEqual({"type": "json_object"}, first["response_format"])
        self.assertNotIn("reasoning_effort", second)
        self.assertNotIn("response_format", second)

    def test_non_bot_target_is_ignored(self):
        client = Mock()
        client.chat_completions.return_value = {
            "choices": [{"message": {"content": scorer_json(target="user:bob")}}]
        }

        decision = WechatGroupFreeReplyScorer(client=client).score(
            self.task(), self.config()
        )

        self.assertFalse(decision["approved"])

    def test_group_soft_reply_uses_task_group_size(self):
        client = Mock()
        client.chat_completions.return_value = {
            "choices": [{
                "message": {
                    "content": scorer_json(
                        target="group",
                        followup=False,
                        desirability=0.52,
                        confidence=0.52,
                        action="soft_reply",
                    )
                }
            }]
        }
        task = self.task()
        task["group_size"] = 6
        task["group_size_source"] = "room_member_cache"

        decision = WechatGroupFreeReplyScorer(client=client).score(
            task,
            self.config(),
        )

        self.assertTrue(decision["approved"])
        self.assertEqual("soft", decision["reply_mode"])
        self.assertEqual(6, decision["group_size"])
        self.assertEqual("room_member_cache", decision["group_size_source"])

    def test_invalid_json_falls_back_or_closes(self):
        client = Mock()
        client.chat_completions.return_value = {
            "choices": [{"message": {"content": "invalid"}}]
        }
        scorer = WechatGroupFreeReplyScorer(client=client)

        fallback = scorer.score(self.task(), self.config(scorer_fallback_to_rules=True))
        closed = scorer.score(self.task(), self.config(scorer_fallback_to_rules=False))

        self.assertTrue(fallback["fallback_to_rules"])
        self.assertFalse(closed["fallback_to_rules"])
        self.assertFalse(closed["approved"])
        self.assertEqual(2, scorer.status()["invalid_json"])

    def test_timeout_and_exception_fail_closed(self):
        timeout_client = Mock()
        timeout_client.chat_completions.side_effect = OpenAIHTTPError(408, {})
        timeout_scorer = WechatGroupFreeReplyScorer(client=timeout_client)
        exception_client = Mock()
        exception_client.chat_completions.side_effect = RuntimeError("offline")

        timeout = timeout_scorer.score(
            self.task(), self.config(scorer_fallback_to_rules=False)
        )
        exception = WechatGroupFreeReplyScorer(client=exception_client).score(
            self.task(), self.config(scorer_fallback_to_rules=False)
        )

        self.assertEqual("timeout", timeout["error"])
        self.assertEqual(1, timeout_scorer.status()["timeout"])
        self.assertEqual("exception", exception["error"])
        self.assertFalse(exception["approved"])

    def test_credentials_prefer_environment_then_config_then_custom(self):
        with patch.dict(os.environ, {"WECHAT_GROUP_FREE_REPLY_SCORER_API_KEY": "env-key"}), \
                patch(
                    "channel.wechat_group.wechat_group_free_reply_scorer.resolve_custom_provider_config",
                    return_value={
                        "api_key": "custom-key",
                        "api_base": "https://custom.example/v1",
                        "model": "custom-model",
                    },
                ):
            self.assertEqual(
                ("env-key", "https://custom.example/v1", "custom-model"),
                _resolve_scorer_credentials({"scorer_provider": "custom:p1"}),
            )

        with patch.dict(os.environ, {}, clear=False), patch(
            "channel.wechat_group.wechat_group_free_reply_scorer.resolve_custom_provider_config",
            return_value={
                "api_key": "custom-key",
                "api_base": "https://custom.example/v1",
                "model": "custom-model",
            },
        ):
            os.environ.pop("WECHAT_GROUP_FREE_REPLY_SCORER_API_KEY", None)
            self.assertEqual(
                ("config-key", "https://custom.example/v1", "custom-model"),
                _resolve_scorer_credentials({"scorer_provider": "custom:p1"}),
            )
            conf()["wechat_group_free_reply_scorer_api_key"] = ""
            self.assertEqual(
                ("custom-key", "https://custom.example/v1", "custom-model"),
                _resolve_scorer_credentials({"scorer_provider": "custom:p1"}),
            )


if __name__ == "__main__":
    unittest.main()
