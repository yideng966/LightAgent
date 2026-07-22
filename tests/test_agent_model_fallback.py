# encoding:utf-8
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class FakeConfig(dict):
    def get(self, key, default=None):
        return super().get(key, default)


class FakeBot:
    def __init__(self, *, stream_chunks=None, sync_response=None):
        self.stream_chunks = list(stream_chunks or [])
        self.sync_response = sync_response
        self.calls = []

    def call_with_tools(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("stream"):
            return iter(self.stream_chunks)
        return self.sync_response


class MutableClock:
    def __init__(self, value=0):
        self.value = value

    def __call__(self):
        return self.value


class TestAgentModelFallback(unittest.TestCase):
    def _request(self):
        from agent.protocol import LLMRequest

        return LLMRequest(
            messages=[{"role": "user", "content": "hello"}],
            tools=[],
            system="system prompt",
            stream=True,
        )

    def test_call_stream_falls_back_after_rate_limit_chunk(self):
        from bridge.agent_bridge import AgentLLMModel

        config = FakeConfig({
            "model": "primary-model",
            "bot_type": "openai",
            "model_fallbacks": [
                {"bot_type": "deepseek", "model": "backup-model"},
            ],
            "use_linkai": False,
            "linkai_api_key": "",
            "enable_thinking": False,
        })
        primary = FakeBot(stream_chunks=[{
            "error": True,
            "message": "Rate limit exceeded. Please try again later.",
            "status_code": 429,
        }])
        backup = FakeBot(stream_chunks=[{
            "choices": [{
                "delta": {"content": "backup ok"},
                "finish_reason": "stop",
            }],
        }])

        with patch("bridge.agent_bridge.conf", return_value=config):
            with patch("models.bot_factory.create_bot", side_effect=[primary, backup]):
                model = AgentLLMModel(bridge=None)
                chunks = list(model.call_stream(self._request()))

        self.assertEqual(1, len(chunks))
        self.assertEqual("backup ok", chunks[0]["choices"][0]["delta"]["content"])
        self.assertEqual("primary-model", primary.calls[0]["model"])
        self.assertEqual("backup-model", backup.calls[0]["model"])

    def test_call_stream_does_not_fallback_for_non_transient_error(self):
        from bridge.agent_bridge import AgentLLMModel

        config = FakeConfig({
            "model": "primary-model",
            "bot_type": "openai",
            "model_fallbacks": [
                {"bot_type": "deepseek", "model": "backup-model"},
            ],
            "use_linkai": False,
            "linkai_api_key": "",
            "enable_thinking": False,
        })
        primary_error = {
            "error": {
                "message": "invalid request",
                "type": "invalid_request_error",
            },
            "message": "invalid request",
            "status_code": 400,
        }
        primary = FakeBot(stream_chunks=[primary_error])
        backup = FakeBot(stream_chunks=[{
            "choices": [{"delta": {"content": "should not run"}}],
        }])

        with patch("bridge.agent_bridge.conf", return_value=config):
            with patch("models.bot_factory.create_bot", side_effect=[primary, backup]) as create_bot:
                model = AgentLLMModel(bridge=None)
                chunks = list(model.call_stream(self._request()))

        self.assertEqual([primary_error], chunks)
        self.assertEqual(1, create_bot.call_count)
        self.assertEqual([], backup.calls)

    def test_fallback_without_bot_type_infers_provider_from_model_name(self):
        from bridge.agent_bridge import AgentLLMModel

        config = FakeConfig({
            "model": "primary-model",
            "bot_type": "openai",
            "model_fallbacks": ["deepseek-v4-flash"],
            "use_linkai": False,
            "linkai_api_key": "",
            "enable_thinking": False,
        })
        primary = FakeBot(stream_chunks=[{
            "error": True,
            "message": "Rate limit exceeded",
            "status_code": 429,
        }])
        backup = FakeBot(stream_chunks=[{
            "choices": [{"delta": {"content": "deepseek ok"}}],
        }])

        with patch("bridge.agent_bridge.conf", return_value=config):
            with patch("models.bot_factory.create_bot", side_effect=[primary, backup]) as create_bot:
                model = AgentLLMModel(bridge=None)
                chunks = list(model.call_stream(self._request()))

        self.assertEqual("deepseek ok", chunks[0]["choices"][0]["delta"]["content"])
        self.assertEqual("openai", create_bot.call_args_list[0].args[0])
        self.assertEqual("deepseek", create_bot.call_args_list[1].args[0])
        self.assertEqual("deepseek-v4-flash", backup.calls[0]["model"])

    def test_call_falls_back_after_sync_rate_limit_response(self):
        from bridge.agent_bridge import AgentLLMModel

        config = FakeConfig({
            "model": "primary-model",
            "bot_type": "openai",
            "model_fallbacks": [
                {"bot_type": "deepseek", "model": "backup-model"},
            ],
            "use_linkai": False,
            "linkai_api_key": "",
            "enable_thinking": False,
        })
        primary = FakeBot(sync_response={
            "error": True,
            "message": "FreeUsageLimitError: Rate limit exceeded",
            "status_code": 429,
        })
        backup_response = {
            "choices": [{
                "message": {"content": "sync backup ok"},
                "finish_reason": "stop",
            }],
        }
        backup = FakeBot(sync_response=backup_response)

        with patch("bridge.agent_bridge.conf", return_value=config):
            with patch("models.bot_factory.create_bot", side_effect=[primary, backup]):
                model = AgentLLMModel(bridge=None)
                response = model.call(self._request())

        self.assertEqual(backup_response, response)
        self.assertEqual("primary-model", primary.calls[0]["model"])
        self.assertEqual("backup-model", backup.calls[0]["model"])

    def test_consecutive_primary_failures_open_circuit_until_probe_recovers(self):
        from bridge.agent_bridge import AgentLLMModel, _ModelFailoverState

        config = FakeConfig({
            "model": "primary-model",
            "bot_type": "openai",
            "model_fallbacks": [
                {"bot_type": "deepseek", "model": "backup-model"},
            ],
            "model_failover_failure_threshold": 3,
            "model_failover_cooldown_seconds": 300,
            "use_linkai": False,
            "linkai_api_key": "",
            "enable_thinking": False,
        })
        primary = FakeBot(stream_chunks=[{
            "error": True,
            "message": "Rate limit exceeded",
            "status_code": 429,
        }])
        backup = FakeBot(stream_chunks=[{
            "choices": [{"delta": {"content": "backup ok"}, "finish_reason": "stop"}],
        }])
        clock = MutableClock()
        failover_state = _ModelFailoverState(clock=clock)

        with patch("bridge.agent_bridge.conf", return_value=config):
            with patch("models.bot_factory.create_bot", side_effect=[primary, backup]):
                model = AgentLLMModel(bridge=None, failover_state=failover_state)

                for _ in range(3):
                    self.assertEqual("backup ok", list(model.call_stream(self._request()))[0]["choices"][0]["delta"]["content"])

                # Circuit is open: the next call starts directly from fallback.
                self.assertEqual("backup ok", list(model.call_stream(self._request()))[0]["choices"][0]["delta"]["content"])
                self.assertEqual(3, len(primary.calls))
                self.assertEqual(4, len(backup.calls))

                # Cooldown permits one primary probe. A failed probe reopens the circuit.
                clock.value = 301
                self.assertEqual("backup ok", list(model.call_stream(self._request()))[0]["choices"][0]["delta"]["content"])
                self.assertEqual(4, len(primary.calls))
                self.assertEqual(5, len(backup.calls))

                # The next successful probe closes the circuit; following calls use primary.
                clock.value = 602
                primary.stream_chunks = [{
                    "choices": [{"delta": {"content": "primary recovered"}, "finish_reason": "stop"}],
                }]
                self.assertEqual("primary recovered", list(model.call_stream(self._request()))[0]["choices"][0]["delta"]["content"])
                self.assertEqual("primary recovered", list(model.call_stream(self._request()))[0]["choices"][0]["delta"]["content"])
                self.assertEqual(6, len(primary.calls))
                self.assertEqual(5, len(backup.calls))

    def test_primary_success_resets_consecutive_failure_count(self):
        from bridge.agent_bridge import AgentLLMModel, _ModelFailoverState

        config = FakeConfig({
            "model": "primary-model",
            "bot_type": "openai",
            "model_fallbacks": [
                {"bot_type": "deepseek", "model": "backup-model"},
            ],
            "model_failover_failure_threshold": 3,
            "model_failover_cooldown_seconds": 300,
            "use_linkai": False,
            "linkai_api_key": "",
            "enable_thinking": False,
        })
        primary = FakeBot(stream_chunks=[])
        backup = FakeBot(stream_chunks=[{
            "choices": [{"delta": {"content": "backup ok"}, "finish_reason": "stop"}],
        }])
        failover_state = _ModelFailoverState(clock=MutableClock())

        def set_primary_error():
            primary.stream_chunks = [{
                "error": True,
                "message": "Service unavailable",
                "status_code": 503,
            }]

        def set_primary_success():
            primary.stream_chunks = [{
                "choices": [{"delta": {"content": "primary ok"}, "finish_reason": "stop"}],
            }]

        with patch("bridge.agent_bridge.conf", return_value=config):
            with patch("models.bot_factory.create_bot", side_effect=[primary, backup]):
                model = AgentLLMModel(bridge=None, failover_state=failover_state)
                set_primary_error()
                list(model.call_stream(self._request()))
                set_primary_success()
                list(model.call_stream(self._request()))
                set_primary_error()
                list(model.call_stream(self._request()))
                list(model.call_stream(self._request()))
                set_primary_success()
                chunks = list(model.call_stream(self._request()))

        self.assertEqual("primary ok", chunks[0]["choices"][0]["delta"]["content"])
        self.assertEqual(5, len(primary.calls))

    def test_final_fallback_error_is_marked_exhausted(self):
        from bridge.agent_bridge import AgentLLMModel

        config = FakeConfig({
            "model": "primary-model",
            "bot_type": "openai",
            "model_fallbacks": [
                {"bot_type": "deepseek", "model": "backup-model"},
            ],
            "use_linkai": False,
            "linkai_api_key": "",
            "enable_thinking": False,
        })
        error = {
            "error": True,
            "message": "Rate limit exceeded",
            "status_code": 429,
        }
        primary = FakeBot(stream_chunks=[error])
        backup = FakeBot(stream_chunks=[error])

        with patch("bridge.agent_bridge.conf", return_value=config):
            with patch("models.bot_factory.create_bot", side_effect=[primary, backup]):
                chunks = list(AgentLLMModel(bridge=None).call_stream(self._request()))

        self.assertEqual(1, len(chunks))
        self.assertTrue(chunks[0]["model_fallback_exhausted"])

    def test_agent_stream_does_not_retry_exhausted_fallback_chain(self):
        from agent.protocol.agent_stream import AgentStreamExecutor
        from agent.protocol.models import LLMModel

        class ExhaustedModel(LLMModel):
            def __init__(self):
                super().__init__(model="unit-test-model")
                self.calls = 0

            def call_stream(self, request):
                self.calls += 1
                yield {
                    "error": True,
                    "message": "Rate limit exceeded",
                    "status_code": 429,
                    "model_fallback_exhausted": True,
                }

        model = ExhaustedModel()
        executor = AgentStreamExecutor(
            agent=None,
            model=model,
            system_prompt="",
            tools=[],
            messages=[],
        )

        with patch("agent.protocol.agent_stream.time.sleep") as sleep:
            with self.assertRaisesRegex(Exception, "Rate limit exceeded") as captured:
                executor._call_llm_stream(retry_on_empty=False)

        self.assertEqual(1, model.calls)
        self.assertNotIn("MODEL_FALLBACK_EXHAUSTED", str(captured.exception))
        sleep.assert_not_called()

    def test_bridge_reset_clears_model_failover_state(self):
        from bridge.bridge import Bridge

        bridge = Bridge()
        bridge._agent_model_failover_state = object()

        bridge.reset_bot()

        self.assertIsNone(bridge._agent_model_failover_state)

    def test_half_open_allows_only_one_probe_across_shared_models(self):
        from bridge.agent_bridge import AgentLLMModel, _ModelFailoverState

        config = FakeConfig({
            "model": "primary-model",
            "bot_type": "openai",
            "model_fallbacks": [
                {"bot_type": "deepseek", "model": "backup-model"},
            ],
            "use_linkai": False,
            "linkai_api_key": "",
        })
        clock = MutableClock()
        bridge = type("FakeBridge", (), {})()
        shared_state = _ModelFailoverState(clock=clock)
        bridge._agent_model_failover_state = shared_state

        with patch("bridge.agent_bridge.conf", return_value=config):
            first_model = AgentLLMModel(bridge=bridge)
            second_model = AgentLLMModel(bridge=bridge)
            primary = first_model._build_model_candidates()[0]
            shared_state.record_transient_failure(
                first_model._route_key(primary),
                threshold=1,
                cooldown_seconds=300,
            )
            clock.value = 301

            probe_candidates = first_model._build_model_candidates()
            concurrent_candidates = second_model._build_model_candidates()

        self.assertEqual("primary", probe_candidates[0]["source"])
        self.assertTrue(all(item["source"] == "fallback" for item in concurrent_candidates))


if __name__ == "__main__":
    unittest.main()
