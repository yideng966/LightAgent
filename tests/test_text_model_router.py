# encoding:utf-8
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class FakeConfig(dict):
    def get(self, key, default=None):
        return super().get(key, default)


class FakeBot:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def call_with_tools(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


class FakeBridge:
    def __init__(self):
        self._agent_model_failover_state = None
        self._text_model_sessions = None


class TestTextModelRouter(unittest.TestCase):
    def _config(self):
        return FakeConfig({
            "model": "primary-model",
            "bot_type": "openai",
            "model_fallbacks": [
                {"bot_type": "deepseek", "model": "backup-model"},
            ],
            "model_failover_failure_threshold": 3,
            "model_failover_cooldown_seconds": 300,
            "character_desc": "system",
            "conversation_max_tokens": 10000,
            "use_linkai": False,
            "linkai_api_key": "",
            "enable_thinking": False,
        })

    @staticmethod
    def _context():
        from bridge.context import Context, ContextType

        return Context(ContextType.TEXT, kwargs={"session_id": "session-1"})

    def test_legacy_chat_fallback_preserves_history_and_commits_once(self):
        from bridge.agent_bridge import TextModelRouter

        transient = {"error": True, "message": "rate limit", "status_code": 429}
        primary = FakeBot([transient, transient])
        backup = FakeBot([
            {"choices": [{"message": {"content": "first answer"}}]},
            {"choices": [{"message": {"content": "second answer"}}]},
        ])

        with patch("bridge.agent_bridge.conf", return_value=self._config()), \
                patch("models.bot_factory.create_bot", side_effect=[primary, backup]):
            router = TextModelRouter(FakeBridge())
            first = router.reply("first question", self._context())
            second = router.reply("second question", self._context())

        self.assertEqual("first answer", first.content)
        self.assertEqual("second answer", second.content)
        self.assertEqual(
            ["system", "first question", "first answer", "second question"],
            [item["content"] for item in backup.calls[1]["messages"]],
        )
        history = router.sessions.build_session("session-1").messages
        self.assertEqual(
            ["system", "first question", "first answer", "second question", "second answer"],
            [item["content"] for item in history],
        )

    def test_failed_candidates_do_not_write_error_into_history(self):
        from bridge.agent_bridge import TextModelRouter
        from bridge.reply import ReplyType

        error = {"error": True, "message": "invalid request", "status_code": 400}
        primary = FakeBot([error])
        with patch("bridge.agent_bridge.conf", return_value=self._config()), \
                patch("models.bot_factory.create_bot", return_value=primary):
            router = TextModelRouter(FakeBridge())
            reply = router.reply("bad question", self._context())

        self.assertEqual(ReplyType.ERROR, reply.type)
        self.assertEqual(
            ["system"],
            [item["content"] for item in router.sessions.build_session("session-1").messages],
        )

    def test_complete_is_stateless(self):
        from bridge.agent_bridge import TextModelRouter

        primary = FakeBot([{"choices": [{"message": {"content": "title"}}]}])
        with patch("bridge.agent_bridge.conf", return_value=self._config()), \
                patch("models.bot_factory.create_bot", return_value=primary):
            router = TextModelRouter(FakeBridge())
            result = router.complete(
                [{"role": "user", "content": "make title"}],
                purpose="session_title",
                temperature=0.2,
            )

        self.assertTrue(result["success"])
        self.assertEqual("title", result["content"])
        self.assertEqual(0.2, primary.calls[0]["temperature"])
        self.assertEqual({}, router.sessions._sessions)

    def test_complete_model_override_uses_only_selected_candidate(self):
        from bridge.agent_bridge import TextModelRouter

        override = FakeBot([
            {"choices": [{"message": {"content": "scored"}}]},
        ])
        config = self._config()
        with patch("bridge.agent_bridge.conf", return_value=config), \
                patch("models.bot_factory.create_bot", return_value=override) as create_bot:
            router = TextModelRouter(FakeBridge())
            result = router.complete(
                [{"role": "user", "content": "score"}],
                purpose="wechat_group_free_reply_scorer",
                provider="openai",
                model="scorer-model",
            )

        self.assertTrue(result["success"])
        self.assertEqual("scored", result["content"])
        create_bot.assert_called_once_with("chatGPT")
        self.assertEqual("scorer-model", override.calls[0]["model"])
        self.assertEqual("primary-model", config["model"])
        self.assertEqual("openai", config["bot_type"])
        self.assertEqual({}, router._failover_state._routes)

    def test_complete_request_options_are_scoped_to_one_call(self):
        from bridge.agent_bridge import TextModelRouter

        primary = FakeBot([
            {"choices": [{"message": {"content": "scored"}}]},
            {"choices": [{"message": {"content": "main answer"}}]},
        ])
        with patch("bridge.agent_bridge.conf", return_value=self._config()), \
                patch("models.bot_factory.create_bot", return_value=primary):
            router = TextModelRouter(FakeBridge())
            scored = router.complete(
                [{"role": "user", "content": "score"}],
                request_options={
                    "reasoning_effort": "none",
                    "response_format": {"type": "json_object"},
                },
            )
            main = router.complete(
                [{"role": "user", "content": "answer normally"}],
            )

        self.assertTrue(scored["success"])
        self.assertTrue(main["success"])
        self.assertEqual(
            {
                "reasoning_effort": "none",
                "response_format": {"type": "json_object"},
            },
            primary.calls[0]["request_options"],
        )
        self.assertNotIn("request_options", primary.calls[1])

    def test_request_level_none_disables_global_thinking_for_one_call(self):
        from bridge.agent_bridge import TextModelRouter

        bot = FakeBot([
            {"choices": [{"message": {"content": "scored"}}]},
            {"choices": [{"message": {"content": "main answer"}}]},
        ])
        config = self._config()
        config["enable_thinking"] = True
        config["reasoning_effort"] = "high"
        with patch("bridge.agent_bridge.conf", return_value=config), \
                patch("models.bot_factory.create_bot", return_value=bot):
            router = TextModelRouter(FakeBridge())
            router.complete(
                [{"role": "user", "content": "score"}],
                request_options={"reasoning_effort": "none"},
            )
            router.complete([{"role": "user", "content": "answer"}])

        self.assertEqual({"type": "disabled"}, bot.calls[0]["thinking"])
        self.assertNotIn("reasoning_effort", bot.calls[0])
        self.assertEqual({"type": "enabled"}, bot.calls[1]["thinking"])
        self.assertEqual("high", bot.calls[1]["reasoning_effort"])

    def test_complete_model_override_does_not_fallback_or_update_primary_circuit(self):
        from bridge.agent_bridge import TextModelRouter

        transient = {"error": True, "message": "rate limit", "status_code": 429}
        override = FakeBot([transient])
        config = self._config()
        with patch("bridge.agent_bridge.conf", return_value=config), \
                patch("models.bot_factory.create_bot", return_value=override) as create_bot:
            router = TextModelRouter(FakeBridge())
            result = router.complete(
                [{"role": "user", "content": "score"}],
                provider="openai",
                model="scorer-model",
            )

        self.assertFalse(result["success"])
        self.assertIs(transient, result["raw"])
        create_bot.assert_called_once_with("chatGPT")
        self.assertEqual(1, len(override.calls))
        self.assertEqual({}, router._failover_state._routes)

    def test_complete_custom_override_reuses_custom_provider_credentials(self):
        from bridge.agent_bridge import TextModelRouter

        override = FakeBot([
            {"choices": [{"message": {"content": "custom scored"}}]},
        ])
        override.args = {}
        config = self._config()
        provider = {
            "id": "scorer",
            "api_key": "scorer-key",
            "api_base": "https://scorer.example/v1",
            "model": "default-scorer-model",
        }
        with patch("bridge.agent_bridge.conf", return_value=config), \
                patch("models.bot_factory.create_bot", return_value=override), \
                patch("models.custom_provider.get_custom_providers", return_value=[provider]), \
                patch("models.openai.openai_http_client.OpenAIHTTPClient") as http_client:
            router = TextModelRouter(FakeBridge())
            result = router.complete(
                [{"role": "user", "content": "score"}],
                provider="custom:scorer",
                model="selected-scorer-model",
            )

        self.assertTrue(result["success"])
        self.assertEqual("selected-scorer-model", override.args["model"])
        http_client.assert_called_once_with(
            api_key="scorer-key",
            api_base="https://scorer.example/v1",
            proxy=None,
        )
        self.assertEqual("primary-model", config["model"])

    def test_missing_custom_override_fails_without_chat_provider_fallback(self):
        from bridge.agent_bridge import TextModelRouter

        override = FakeBot([])
        with patch("bridge.agent_bridge.conf", return_value=self._config()), \
                patch("models.bot_factory.create_bot", return_value=override), \
                patch("models.custom_provider.get_custom_providers", return_value=[]):
            router = TextModelRouter(FakeBridge())
            with self.assertRaisesRegex(ValueError, "custom provider not found: missing"):
                router.complete(
                    [{"role": "user", "content": "score"}],
                    provider="custom:missing",
                    model="scorer-model",
                )

        self.assertEqual([], override.calls)

    def test_clear_memory_command_does_not_call_model(self):
        from bridge.agent_bridge import TextModelRouter
        from bridge.reply import ReplyType

        primary = FakeBot([])
        with patch("bridge.agent_bridge.conf", return_value=self._config()), \
                patch("models.bot_factory.create_bot", return_value=primary):
            router = TextModelRouter(FakeBridge())
            router.sessions.commit_exchange("session-1", "question", "answer")
            reply = router.reply("#清除记忆", self._context())

        self.assertEqual(ReplyType.INFO, reply.type)
        self.assertEqual([], primary.calls)
        self.assertNotIn("session-1", router.sessions._sessions)

    def test_non_text_reply_keeps_dedicated_chat_bot_path(self):
        from bridge.agent_bridge import TextModelRouter
        from bridge.context import Context, ContextType

        expected = object()
        dedicated_bot = unittest.mock.Mock()
        dedicated_bot.reply.return_value = expected
        bridge = FakeBridge()
        bridge.get_bot = unittest.mock.Mock(return_value=dedicated_bot)

        router = TextModelRouter(bridge)
        context = Context(ContextType.IMAGE_CREATE, kwargs={"session_id": "session-1"})

        self.assertIs(expected, router.reply("draw", context))
        bridge.get_bot.assert_called_once_with("chat")
        dedicated_bot.reply.assert_called_once_with("draw", context)

    def test_complete_and_agent_adapter_share_circuit_state(self):
        from agent.protocol.models import LLMRequest
        from bridge.agent_bridge import AgentLLMModel, TextModelRouter

        config = self._config()
        config["model_failover_failure_threshold"] = 1
        transient = {"error": True, "message": "rate limit", "status_code": 429}
        complete_primary = FakeBot([transient])
        complete_backup = FakeBot([{"choices": [{"message": {"content": "backup title"}}]}])
        agent_primary = FakeBot([])
        agent_backup = FakeBot([{"choices": [{"message": {"content": "agent backup"}}]}])
        bridge = FakeBridge()

        with patch("bridge.agent_bridge.conf", return_value=config), \
                patch(
                    "models.bot_factory.create_bot",
                    side_effect=[complete_primary, complete_backup, agent_backup],
                ):
            router = TextModelRouter(bridge)
            self.assertTrue(router.complete([{"role": "user", "content": "title"}])["success"])
            agent_model = AgentLLMModel(bridge)
            agent_model._bot = agent_primary
            agent_model._bot_model = "primary-model"
            agent_model._bot_type = "openai"
            response = agent_model.call(LLMRequest(messages=[{"role": "user", "content": "task"}]))

        self.assertEqual("agent backup", response["choices"][0]["message"]["content"])
        self.assertEqual([], agent_primary.calls)
        self.assertEqual(1, len(agent_backup.calls))

    def test_agent_initializer_injects_shared_router_into_memory(self):
        from bridge.agent_initializer import AgentInitializer

        router = object()
        bridge = unittest.mock.Mock()
        bridge.get_text_model_router.return_value = router
        initializer = AgentInitializer(bridge, unittest.mock.Mock())
        memory_manager = unittest.mock.Mock()

        with tempfile.TemporaryDirectory() as tmp, \
                patch("agent.memory.MemoryManager", return_value=memory_manager) as manager_cls, \
                patch.object(initializer, "_init_embedding_provider", return_value=object()), \
                patch.object(initializer, "_sync_memory"):
            manager, _ = initializer._setup_memory_system(tmp, "session-1")

        self.assertIs(memory_manager, manager)
        self.assertIs(router, manager_cls.call_args.kwargs["llm_model"])

    def test_exhausted_agent_exception_does_not_replay_legacy_chat(self):
        from channel.channel import Channel
        from bridge.reply import ReplyType

        exhausted = RuntimeError("rate limit")
        exhausted.model_fallback_exhausted = True
        bridge = unittest.mock.Mock()
        bridge.fetch_agent_reply.side_effect = exhausted
        context = self._context()
        channel = Channel.__new__(Channel)
        channel.channel_type = "web"

        with patch("channel.channel.conf", return_value={"agent": True}), \
                patch("channel.channel.Bridge", return_value=bridge):
            reply = channel.build_reply_content("hello", context)

        self.assertEqual(ReplyType.ERROR, reply.type)
        bridge.fetch_reply_content.assert_not_called()


if __name__ == "__main__":
    unittest.main()
