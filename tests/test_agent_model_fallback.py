# encoding:utf-8
import os
import sys
import threading
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


class MutatingBot(FakeBot):
    def call_with_tools(self, **kwargs):
        self.calls.append(kwargs)
        kwargs["messages"][0]["content"] = "mutated-by-primary"
        if kwargs.get("tools"):
            kwargs["tools"][0]["name"] = "mutated-tool"
        if kwargs.get("request_options"):
            kwargs["request_options"]["mode"] = "mutated-option"
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

    def test_stream_fallback_uses_an_immutable_request_snapshot(self):
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
        primary = MutatingBot(stream_chunks=[{
            "error": True,
            "message": "Rate limit exceeded",
            "status_code": 429,
        }])
        backup = FakeBot(stream_chunks=[{
            "choices": [{"delta": {"content": "backup ok"}, "finish_reason": "stop"}],
        }])
        request = self._request()
        request.tools = [{"name": "read", "input_schema": {}}]
        request.request_options = {"mode": "original-option"}

        with patch("bridge.agent_bridge.conf", return_value=config):
            with patch("models.bot_factory.create_bot", side_effect=[primary, backup]):
                chunks = list(AgentLLMModel(bridge=None).call_stream(request))

        self.assertEqual("backup ok", chunks[0]["choices"][0]["delta"]["content"])
        self.assertEqual("hello", backup.calls[0]["messages"][0]["content"])
        self.assertEqual("read", backup.calls[0]["tools"][0]["name"])
        self.assertEqual("original-option", backup.calls[0]["request_options"]["mode"])
        self.assertEqual("hello", request.messages[0]["content"])
        self.assertEqual("read", request.tools[0]["name"])
        self.assertEqual("original-option", request.request_options["mode"])

    def test_candidates_are_rebuilt_from_attached_source_snapshot(self):
        from agent.protocol import LLMRequest, LLMRequestSourceSnapshot
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
        primary = MutatingBot(stream_chunks=[{
            "error": True,
            "message": "Rate limit exceeded",
            "status_code": 429,
        }])
        backup = FakeBot(stream_chunks=[{
            "choices": [{"delta": {"content": "backup ok"}, "finish_reason": "stop"}],
        }])
        source = LLMRequestSourceSnapshot(
            messages=[{"role": "user", "content": "source-original"}],
            tools=[{"name": "read", "input_schema": {"type": "object"}}],
            system="source-system",
            stream=True,
            request_options={"mode": "source-option"},
        )
        request = LLMRequest(
            messages=[{"role": "user", "content": "polluted-finished-request"}],
            tools=[{"name": "polluted-tool", "input_schema": {}}],
            system="polluted-system",
            stream=True,
        )
        request._source_snapshot = source

        with patch("bridge.agent_bridge.conf", return_value=config):
            with patch("models.bot_factory.create_bot", side_effect=[primary, backup]):
                chunks = list(AgentLLMModel(bridge=None).call_stream(request))

        self.assertEqual("backup ok", chunks[0]["choices"][0]["delta"]["content"])
        self.assertEqual("source-original", backup.calls[0]["messages"][0]["content"])
        self.assertEqual("read", backup.calls[0]["tools"][0]["name"])
        self.assertEqual("source-option", backup.calls[0]["request_options"]["mode"])
        self.assertIn("source-system", backup.calls[0]["system"])
        self.assertIsNot(primary.calls[0]["messages"], backup.calls[0]["messages"])
        self.assertEqual("polluted-finished-request", request.messages[0]["content"])

    def test_sync_fallback_uses_an_immutable_request_snapshot(self):
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
        primary = MutatingBot(sync_response={
            "error": True,
            "message": "Rate limit exceeded",
            "status_code": 429,
        })
        backup_response = {
            "choices": [{"message": {"content": "backup ok"}, "finish_reason": "stop"}],
        }
        backup = FakeBot(sync_response=backup_response)
        request = self._request()

        with patch("bridge.agent_bridge.conf", return_value=config):
            with patch("models.bot_factory.create_bot", side_effect=[primary, backup]):
                response = AgentLLMModel(bridge=None).call(request)

        self.assertEqual(backup_response, response)
        self.assertEqual("hello", backup.calls[0]["messages"][0]["content"])
        self.assertEqual("hello", request.messages[0]["content"])

    def test_wechat_group_uses_configured_fallback_and_disables_thinking(self):
        from bridge.agent_bridge import AgentLLMModel

        config = FakeConfig({
            "model": "primary-model",
            "bot_type": "openai",
            "model_fallbacks": [
                {"bot_type": "deepseek", "model": "backup-model"},
            ],
            "use_linkai": False,
            "linkai_api_key": "",
            "enable_thinking": True,
            "reasoning_effort": "high",
        })
        primary = FakeBot(stream_chunks=[{
            "error": True,
            "message": "Rate limit exceeded",
            "status_code": 429,
        }])
        backup = FakeBot(stream_chunks=[{
            "choices": [{"delta": {"content": "backup ok"}, "finish_reason": "stop"}],
        }])

        with patch("bridge.agent_bridge.conf", return_value=config):
            with patch("models.bot_factory.create_bot", side_effect=[primary, backup]) as create_bot:
                model = AgentLLMModel(bridge=None)
                model.channel_type = "wechat_group"
                chunks = list(model.call_stream(self._request()))

        self.assertEqual("backup ok", chunks[0]["choices"][0]["delta"]["content"])
        self.assertEqual(2, create_bot.call_count)
        self.assertEqual("backup-model", backup.calls[0]["model"])
        self.assertEqual({"type": "disabled"}, backup.calls[0]["thinking"])
        self.assertNotIn("reasoning_effort", backup.calls[0])
        self.assertIn("只输出面向用户的最终答复", backup.calls[0]["system"])

    def test_open_primary_circuit_starts_with_wechat_group_fallback(self):
        from bridge.agent_bridge import AgentLLMModel, _ModelFailoverState

        config = FakeConfig({
            "model": "primary-model",
            "bot_type": "openai",
            "model_fallbacks": [{
                "bot_type": "deepseek",
                "model": "backup-model",
            }],
            "model_failover_failure_threshold": 1,
            "model_failover_cooldown_seconds": 300,
            "use_linkai": False,
            "linkai_api_key": "",
            "enable_thinking": True,
        })
        failover_state = _ModelFailoverState(clock=MutableClock())
        failover_state.record_transient_failure(
            ("openai", "primary-model"), threshold=1, cooldown_seconds=300
        )
        backup = FakeBot(stream_chunks=[{
            "choices": [{"delta": {"content": "backup ok"}, "finish_reason": "stop"}],
        }])

        with patch("bridge.agent_bridge.conf", return_value=config):
            with patch("models.bot_factory.create_bot", return_value=backup) as create_bot:
                model = AgentLLMModel(bridge=None, failover_state=failover_state)
                model.channel_type = "wechat_group"
                chunks = list(model.call_stream(self._request()))

        self.assertEqual("backup ok", chunks[0]["choices"][0]["delta"]["content"])
        create_bot.assert_called_once_with("deepseek")
        self.assertEqual("hello", backup.calls[0]["messages"][0]["content"])
        self.assertEqual({"type": "disabled"}, backup.calls[0]["thinking"])

    def test_non_wechat_channel_keeps_all_fallback_candidates(self):
        from bridge.agent_bridge import AgentLLMModel

        config = FakeConfig({
            "model": "primary-model",
            "bot_type": "openai",
            "model_fallbacks": [
                {"bot_type": "deepseek", "model": "backup-model"},
            ],
            "use_linkai": False,
            "linkai_api_key": "",
            "enable_thinking": True,
            "reasoning_effort": "high",
        })
        primary = FakeBot(stream_chunks=[{
            "error": True,
            "message": "Rate limit exceeded",
            "status_code": 429,
        }])
        backup = FakeBot(stream_chunks=[{
            "choices": [{"delta": {"content": "backup ok"}, "finish_reason": "stop"}],
        }])

        with patch("bridge.agent_bridge.conf", return_value=config):
            with patch("models.bot_factory.create_bot", side_effect=[primary, backup]):
                model = AgentLLMModel(bridge=None)
                model.channel_type = "web"
                list(model.call_stream(self._request()))

        self.assertEqual("backup-model", backup.calls[0]["model"])
        self.assertEqual({"type": "enabled"}, backup.calls[0]["thinking"])
        self.assertEqual("high", backup.calls[0]["reasoning_effort"])

    def test_stream_does_not_switch_candidates_after_visible_output(self):
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
        primary = FakeBot(stream_chunks=[
            {"choices": [{"delta": {"content": "partial"}, "finish_reason": None}]},
            {"error": True, "message": "Rate limit exceeded", "status_code": 429},
        ])
        backup = FakeBot(stream_chunks=[{
            "choices": [{"delta": {"content": "must not run"}, "finish_reason": "stop"}],
        }])

        with patch("bridge.agent_bridge.conf", return_value=config):
            with patch("models.bot_factory.create_bot", side_effect=[primary, backup]) as create_bot:
                chunks = list(AgentLLMModel(bridge=None).call_stream(self._request()))

        self.assertEqual("partial", chunks[0]["choices"][0]["delta"]["content"])
        self.assertTrue(chunks[1]["error"])
        self.assertEqual(1, create_bot.call_count)
        self.assertEqual([], backup.calls)

    def test_wechat_group_discards_partial_candidate_before_fallback(self):
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
        primary = FakeBot(stream_chunks=[
            {"choices": [{"delta": {"content": "polluted partial"}, "finish_reason": None}]},
            {"error": True, "message": "Rate limit exceeded", "status_code": 429},
        ])
        backup = FakeBot(stream_chunks=[{
            "choices": [{"delta": {"content": "backup only"}, "finish_reason": "stop"}],
        }])

        with patch("bridge.agent_bridge.conf", return_value=config):
            with patch("models.bot_factory.create_bot", side_effect=[primary, backup]):
                model = AgentLLMModel(bridge=None)
                model.channel_type = "wechat_group"
                chunks = list(model.call_stream(self._request()))

        self.assertEqual(1, len(chunks))
        self.assertEqual("backup only", chunks[0]["choices"][0]["delta"]["content"])
        self.assertNotIn("polluted partial", str(chunks))
        self.assertEqual(1, len(backup.calls))

    def test_wechat_group_rejects_invalid_tool_protocol_before_fallback(self):
        from bridge.agent_bridge import AgentLLMModel

        invalid_calls = {
            "empty-name": {
                "index": 0,
                "id": "call-empty",
                "function": {"name": "", "arguments": "{}"},
            },
            "unknown-name": {
                "index": 0,
                "id": "call-unknown",
                "function": {"name": "missing_tool", "arguments": "{}"},
            },
            "malformed-arguments": {
                "index": 0,
                "id": "call-bad-json",
                "function": {"name": "read", "arguments": '{"path":'},
            },
        }

        for label, tool_call in invalid_calls.items():
            with self.subTest(label=label):
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
                    "choices": [{
                        "delta": {"tool_calls": [tool_call]},
                        "finish_reason": "tool_calls",
                    }],
                }])
                backup = FakeBot(stream_chunks=[{
                    "choices": [{
                        "delta": {"content": "backup safe"},
                        "finish_reason": "stop",
                    }],
                }])
                request = self._request()
                request.tools = [{
                    "name": "read",
                    "input_schema": {"type": "object"},
                }]

                with patch("bridge.agent_bridge.conf", return_value=config):
                    with patch(
                        "models.bot_factory.create_bot",
                        side_effect=[primary, backup],
                    ):
                        model = AgentLLMModel(bridge=None)
                        model.channel_type = "wechat_group"
                        chunks = list(model.call_stream(request))

                self.assertEqual(1, len(chunks))
                self.assertEqual(
                    "backup safe",
                    chunks[0]["choices"][0]["delta"]["content"],
                )
                self.assertNotIn("tool_calls", str(chunks))

    def test_wechat_group_rejects_known_provider_protocol_fragments(self):
        from bridge.agent_bridge import AgentLLMModel

        fragments = (
            "answer</arg_value></function_calls_output>",
            "<wechat-sticker-copied>https://example.com/a.png</wechat-sticker-copied>",
        )
        for fragment in fragments:
            with self.subTest(fragment=fragment):
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
                    "choices": [{"delta": {"content": fragment}, "finish_reason": "stop"}],
                }])
                backup = FakeBot(stream_chunks=[{
                    "choices": [{"delta": {"content": "backup safe"}, "finish_reason": "stop"}],
                }])

                with patch("bridge.agent_bridge.conf", return_value=config):
                    with patch(
                        "models.bot_factory.create_bot",
                        side_effect=[primary, backup],
                    ):
                        model = AgentLLMModel(bridge=None)
                        model.channel_type = "wechat_group"
                        chunks = list(model.call_stream(self._request()))

                self.assertEqual(1, len(chunks))
                self.assertEqual(
                    "backup safe",
                    chunks[0]["choices"][0]["delta"]["content"],
                )
                self.assertNotIn(fragment, str(chunks))

    def test_invalid_candidate_does_not_reach_agent_history(self):
        from agent.protocol.agent_stream import AgentStreamExecutor
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
            "choices": [{
                "delta": {"tool_calls": [{
                    "index": 0,
                    "id": "call-invalid",
                    "function": {"name": "", "arguments": "{}"},
                }]},
                "finish_reason": "tool_calls",
            }],
        }])
        backup = FakeBot(stream_chunks=[{
            "choices": [{"delta": {"content": "backup final"}, "finish_reason": "stop"}],
        }])
        events = []

        with patch("bridge.agent_bridge.conf", return_value=config):
            with patch("models.bot_factory.create_bot", side_effect=[primary, backup]):
                model = AgentLLMModel(bridge=None)
                model.channel_type = "wechat_group"
                executor = AgentStreamExecutor(
                    agent=None,
                    model=model,
                    system_prompt="",
                    tools=[],
                    messages=[],
                    on_event=events.append,
                    context={"channel_type": "wechat_group"},
                )
                content, tool_calls = executor._call_llm_stream(retry_on_empty=False)

        self.assertEqual("backup final", content)
        self.assertEqual([], tool_calls)
        self.assertNotIn("call-invalid", str(executor.messages))
        self.assertNotIn("tool_use", str(executor.messages))
        self.assertNotIn("call-invalid", str(events))
        self.assertEqual([], events[-1]["data"]["tool_calls"])

    def test_wechat_group_empty_response_falls_back(self):
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
            "choices": [{"delta": {}, "finish_reason": "stop"}],
        }])
        backup = FakeBot(stream_chunks=[{
            "choices": [{"delta": {"content": "backup final"}, "finish_reason": "stop"}],
        }])

        with patch("bridge.agent_bridge.conf", return_value=config):
            with patch("models.bot_factory.create_bot", side_effect=[primary, backup]):
                model = AgentLLMModel(bridge=None)
                model.channel_type = "wechat_group"
                chunks = list(model.call_stream(self._request()))

        self.assertEqual("backup final", chunks[0]["choices"][0]["delta"]["content"])
        self.assertEqual(1, len(backup.calls))

    def test_wechat_group_content_filter_does_not_use_fallback(self):
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
            "choices": [{
                "delta": {"content": "partial must not leak"},
                "finish_reason": "content_filter",
            }],
        }])
        backup = FakeBot(stream_chunks=[{
            "choices": [{"delta": {"content": "must not run"}, "finish_reason": "stop"}],
        }])

        with patch("bridge.agent_bridge.conf", return_value=config):
            with patch("models.bot_factory.create_bot", side_effect=[primary, backup]) as create_bot:
                model = AgentLLMModel(bridge=None)
                model.channel_type = "wechat_group"
                chunks = list(model.call_stream(self._request()))

        self.assertIn("无法协助", chunks[0]["choices"][0]["delta"]["content"])
        self.assertNotIn("partial must not leak", str(chunks))
        self.assertEqual(1, create_bot.call_count)
        self.assertEqual([], backup.calls)

    def test_wechat_group_all_invalid_candidates_return_safe_error(self):
        from bridge.agent_bridge import AgentLLMModel

        config = FakeConfig({
            "model": "primary-model",
            "bot_type": "openai",
            "model_fallbacks": [],
            "use_linkai": False,
            "linkai_api_key": "",
            "enable_thinking": False,
        })
        fragment = "secret</arg_value></function_calls_output>"
        primary = FakeBot(stream_chunks=[{
            "choices": [{"delta": {"content": fragment}, "finish_reason": "stop"}],
        }])

        with patch("bridge.agent_bridge.conf", return_value=config):
            with patch("models.bot_factory.create_bot", return_value=primary):
                model = AgentLLMModel(bridge=None)
                model.channel_type = "wechat_group"
                chunks = list(model.call_stream(self._request()))

        self.assertEqual(1, len(chunks))
        self.assertTrue(chunks[0]["protocol_error"])
        self.assertTrue(chunks[0]["model_fallback_exhausted"])
        self.assertNotIn(fragment, str(chunks))
        self.assertIn("无法安全处理", chunks[0]["message"])

    def test_wechat_group_buffer_honors_cancellation_without_fallback(self):
        from agent.protocol import AgentCancelledError
        from bridge.agent_bridge import AgentLLMModel

        cancel_event = threading.Event()

        class CancellingBot(FakeBot):
            def call_with_tools(self, **kwargs):
                self.calls.append(kwargs)

                def chunks():
                    yield {
                        "choices": [{
                            "delta": {"content": "partial"},
                            "finish_reason": None,
                        }],
                    }
                    cancel_event.set()
                    yield {
                        "choices": [{
                            "delta": {"content": "must not be delivered"},
                            "finish_reason": "stop",
                        }],
                    }

                return chunks()

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
        primary = CancellingBot()
        backup = FakeBot(stream_chunks=[{
            "choices": [{"delta": {"content": "must not run"}, "finish_reason": "stop"}],
        }])
        request = self._request()
        request._cancel_event = cancel_event

        with patch("bridge.agent_bridge.conf", return_value=config):
            with patch("models.bot_factory.create_bot", side_effect=[primary, backup]) as create_bot:
                model = AgentLLMModel(bridge=None)
                model.channel_type = "wechat_group"
                with self.assertRaises(AgentCancelledError):
                    list(model.call_stream(request))

        self.assertEqual(1, create_bot.call_count)
        self.assertEqual([], backup.calls)

    def test_request_source_snapshot_builds_independent_requests(self):
        from agent.protocol import LLMRequestSourceSnapshot

        source = LLMRequestSourceSnapshot(
            messages=[{"role": "user", "content": {"text": "original"}}],
            tools=[{"name": "read", "input_schema": {"type": "object"}}],
            system="system",
            request_options={"mode": {"value": "original"}},
        )

        first = source.build_request()
        first.messages[0]["content"]["text"] = "mutated"
        first.tools[0]["name"] = "mutated"
        first.request_options["mode"]["value"] = "mutated"
        second = source.build_request()

        self.assertEqual("original", second.messages[0]["content"]["text"])
        self.assertEqual("read", second.tools[0]["name"])
        self.assertEqual("original", second.request_options["mode"]["value"])
        self.assertIsNot(first.messages, second.messages)

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
