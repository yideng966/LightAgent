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
            )

        self.assertTrue(result["success"])
        self.assertEqual("title", result["content"])
        self.assertEqual({}, router.sessions._sessions)

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
