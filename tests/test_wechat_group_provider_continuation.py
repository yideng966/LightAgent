import copy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from agent.protocol.agent_stream import AgentStreamExecutor
from agent.protocol.models import LLMModel, LLMRequest
from bridge.agent_bridge import TextModelRouter
from channel.wechat_group.wechat_group_provider_continuation import (
    CAPABILITY_IMMUTABLE_PARENT,
    ProviderContinuationScope,
    ProviderContinuationStore,
    endpoint_fingerprint,
    opaque_hash,
    permission_fingerprint,
)


class FakeBridge:
    def __init__(self):
        self._agent_model_failover_state = None
        self._text_model_sessions = None


class FakeContinuationBot:
    def __init__(self, responses, api_base="https://provider.example/v1"):
        self.responses = list(responses)
        self.api_base = api_base
        self.calls = []
        self.builds = []
        self.capability_error = None
        self.builder_error = None

    def get_api_config(self):
        return {"api_base": self.api_base}

    def get_provider_continuation_capability(self, model):
        if self.capability_error:
            raise self.capability_error
        return {
            "mode": CAPABILITY_IMMUTABLE_PARENT,
            "anchor_type": "response_id",
        }

    def build_provider_continuation_request(
        self,
        request_kwargs,
        committed_anchor,
        capability,
    ):
        if self.builder_error:
            raise self.builder_error
        prepared = copy.deepcopy(request_kwargs)
        prepared["provider_parent"] = committed_anchor
        self.builds.append({
            "committed_anchor": committed_anchor,
            "capability": dict(capability),
        })
        return prepared

    @staticmethod
    def extract_provider_continuation_anchor(payload, capability):
        if not isinstance(payload, dict):
            return ""
        return {
            "anchor_type": capability.get("anchor_type"),
            "anchor_value": payload.get("provider_anchor") or "",
        }

    @staticmethod
    def classify_provider_continuation_error(error, capability):
        if isinstance(error, dict):
            return error.get("anchor_error") or ""
        return getattr(error, "anchor_error", "")

    def call_with_tools(self, **kwargs):
        self.calls.append(copy.deepcopy(kwargs))
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        if kwargs.get("stream"):
            chunks = response if isinstance(response, list) else [response]
            return iter(chunks)
        return response


class CaptureStreamModel(LLMModel):
    def __init__(self):
        super().__init__(model="capture-model")
        self.requests = []

    def call_stream(self, request):
        self.requests.append(request)
        yield {
            "choices": [{
                "delta": {"content": "ok"},
                "finish_reason": "stop",
            }],
        }


class BrokenStageStore:
    def __init__(self, delegate):
        self.delegate = delegate

    def get_committed(self, scope):
        return self.delegate.get_committed(scope)

    def stage(self, *args, **kwargs):
        raise OSError("disk unavailable")

    def expire(self, row_id):
        return self.delegate.expire(row_id)


class WechatGroupProviderContinuationTest(unittest.TestCase):
    @staticmethod
    def _config(fallbacks=None):
        return {
            "model": "primary-model",
            "bot_type": "openai",
            "model_fallbacks": list(fallbacks or []),
            "model_failover_failure_threshold": 3,
            "model_failover_cooldown_seconds": 300,
            "enable_thinking": False,
            "wechat_group_provider_continuation_enabled": True,
            "wechat_group_admin_required_permissions": {
                "memory_write": True,
            },
        }

    @staticmethod
    def _context(request_id, action="resume_thread", member="wgm_alice"):
        return {
            "stable_account_scope": "wga_account",
            "stable_room_id": "wgr_room",
            "stable_member_id": member,
            "owner_session_id": "wechat_group:wgr_room:{}".format(member),
            "thread_id": "wgt_thread",
            "provider_key": "",
            "model": "",
            "endpoint_fingerprint": "",
            "permission_fingerprint": "",
            "thread_action": action,
            "request_id": request_id,
            "ttl_seconds": 900,
            "identity_status": "confirmed",
            "identity_confirmed": True,
            "is_admin": False,
        }

    @classmethod
    def _request(cls, request_id, action="resume_thread", messages=None):
        return LLMRequest(
            messages=messages or [{"role": "user", "content": "question"}],
            provider_continuation_context=cls._context(request_id, action=action),
        )

    @staticmethod
    def _scope(context, provider_key, model, api_base):
        return ProviderContinuationScope(
            stable_account_scope=context["stable_account_scope"],
            stable_room_id=context["stable_room_id"],
            stable_member_id=context["stable_member_id"],
            owner_session_id=context["owner_session_id"],
            thread_id=context["thread_id"],
            provider_key=provider_key,
            model=model,
            endpoint_fingerprint=endpoint_fingerprint(provider_key, api_base),
            permission_fingerprint=permission_fingerprint(context),
        )

    def test_store_keeps_pending_invisible_and_isolates_member_scope(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProviderContinuationStore(str(Path(tmpdir) / "anchors.db"))
            alice = ProviderContinuationScope(
                "account", "room", "alice", "owner-alice", "thread",
                "provider", "model", "endpoint", "permission",
            )
            bob = ProviderContinuationScope(
                "account", "room", "bob", "owner-bob", "thread",
                "provider", "model", "endpoint", "permission",
            )

            pending = store.stage(
                alice,
                "response_id",
                "anchor-a",
                "request-a",
                900,
                now=100,
            )

            self.assertIsNone(store.get_committed(alice, now=101))
            self.assertIsNone(store.get_committed(bob, now=101))
            self.assertEqual("pending", pending.status)
            self.assertTrue(store.commit("request-a", now=101))
            self.assertEqual("anchor-a", store.get_committed(alice, now=101).anchor_value)
            self.assertIsNone(store.get_committed(bob, now=101))

            store.stage(
                alice,
                "response_id",
                "anchor-b",
                "request-b",
                900,
                parent_anchor_value="anchor-a",
                now=102,
            )
            self.assertEqual(1, store.discard("request-b"))
            self.assertEqual("anchor-a", store.get_committed(alice, now=103).anchor_value)
            discarded = store.list_for_request("request-b")[0]
            self.assertEqual("discarded", discarded.status)
            self.assertEqual(opaque_hash("anchor-a"), discarded.parent_anchor_hash)

    def test_router_reuses_only_committed_anchor_and_stages_next_candidate(self):
        config = self._config()
        bot = FakeContinuationBot([
            {"choices": [{"message": {"content": "first"}}], "provider_anchor": "anchor-a"},
            {"choices": [{"message": {"content": "second"}}], "provider_anchor": "anchor-b"},
        ])
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProviderContinuationStore(str(Path(tmpdir) / "anchors.db"))
            with patch("bridge.agent_bridge.conf", return_value=config), \
                    patch("config.conf", return_value=config), \
                    patch("models.bot_factory.create_bot", return_value=bot):
                router = TextModelRouter(FakeBridge())
                router._provider_continuation_store = store
                router.call(self._request("request-a", action="new_thread"))

                self.assertIsNone(store.get_committed(
                    self._scope(self._context("request-a"), "openai", "primary-model", bot.api_base)
                ))
                self.assertTrue(store.commit("request-a"))
                router.call(self._request("request-b", action="resume_thread"))

            self.assertEqual("", bot.calls[0]["provider_parent"])
            self.assertEqual("anchor-a", bot.calls[1]["provider_parent"])
            pending = store.list_for_request("request-b")[0]
            self.assertEqual("pending", pending.status)
            self.assertEqual(opaque_hash("anchor-a"), pending.parent_anchor_hash)
            self.assertEqual("anchor-a", store.get_committed(pending.scope).anchor_value)
            self.assertTrue(store.commit("request-b"))
            self.assertEqual("anchor-b", store.get_committed(pending.scope).anchor_value)

    def test_tool_history_and_tool_call_do_not_create_anchor(self):
        config = self._config()
        bot = FakeContinuationBot([
            {"choices": [{"message": {"content": "local replay"}}], "provider_anchor": "ignored-a"},
            {
                "choices": [{"message": {
                    "content": None,
                    "tool_calls": [{"id": "call-1", "function": {"name": "read"}}],
                }}],
                "provider_anchor": "ignored-b",
            },
        ])
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProviderContinuationStore(str(Path(tmpdir) / "anchors.db"))
            with patch("bridge.agent_bridge.conf", return_value=config), \
                    patch("config.conf", return_value=config), \
                    patch("models.bot_factory.create_bot", return_value=bot):
                router = TextModelRouter(FakeBridge())
                router._provider_continuation_store = store
                router.call(self._request(
                    "request-tool-history",
                    messages=[
                        {"role": "user", "content": "read"},
                        {"role": "tool", "content": "raw result"},
                    ],
                ))
                router.call(self._request("request-tool-call"))

            self.assertNotIn("provider_parent", bot.calls[0])
            self.assertEqual([], store.list_for_request("request-tool-history"))
            self.assertEqual([], store.list_for_request("request-tool-call"))

    def test_expired_anchor_replays_same_candidate_once_without_anchor(self):
        config = self._config()
        bot = FakeContinuationBot([
            {"error": True, "anchor_error": "not_found"},
            {"choices": [{"message": {"content": "replayed"}}], "provider_anchor": "anchor-new"},
        ])
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProviderContinuationStore(str(Path(tmpdir) / "anchors.db"))
            context = self._context("request-new")
            with patch("bridge.agent_bridge.conf", return_value=config), \
                    patch("config.conf", return_value=config), \
                    patch("models.bot_factory.create_bot", return_value=bot):
                scope = self._scope(context, "openai", "primary-model", bot.api_base)
                store.stage(scope, "response_id", "anchor-old", "request-old", 900)
                store.commit("request-old")
                router = TextModelRouter(FakeBridge())
                router._provider_continuation_store = store
                response = router.call(self._request("request-new"))

            self.assertEqual("replayed", response["choices"][0]["message"]["content"])
            self.assertEqual(["anchor-old", ""], [call["provider_parent"] for call in bot.calls])
            self.assertEqual("expired", store.list_for_request("request-old")[0].status)
            self.assertEqual("pending", store.list_for_request("request-new")[0].status)

    def test_fallback_candidate_uses_only_its_own_provider_anchor(self):
        config = self._config([
            {"bot_type": "deepseek", "model": "backup-model"},
        ])
        primary = FakeContinuationBot([
            {"error": True, "message": "rate limit", "status_code": 429},
        ], api_base="https://primary.example/v1")
        backup = FakeContinuationBot([
            {"choices": [{"message": {"content": "backup"}}], "provider_anchor": "backup-new"},
        ], api_base="https://backup.example/v1")
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProviderContinuationStore(str(Path(tmpdir) / "anchors.db"))
            context = self._context("request-route")
            with patch("bridge.agent_bridge.conf", return_value=config), \
                    patch("config.conf", return_value=config), \
                    patch(
                        "models.bot_factory.create_bot",
                        side_effect=[primary, backup],
                    ):
                primary_scope = self._scope(
                    context, "openai", "primary-model", primary.api_base
                )
                backup_scope = self._scope(
                    context, "deepseek", "backup-model", backup.api_base
                )
                store.stage(
                    primary_scope, "response_id", "primary-old",
                    "request-primary", 900,
                )
                store.commit("request-primary")
                store.stage(
                    backup_scope, "response_id", "backup-old",
                    "request-backup", 900,
                )
                store.commit("request-backup")
                router = TextModelRouter(FakeBridge())
                router._provider_continuation_store = store
                response = router.call(self._request("request-route"))

            self.assertEqual("backup", response["choices"][0]["message"]["content"])
            self.assertEqual("primary-old", primary.calls[0]["provider_parent"])
            self.assertEqual("backup-old", backup.calls[0]["provider_parent"])
            pending = store.list_for_request("request-route")
            self.assertEqual(1, len(pending))
            self.assertEqual("deepseek", pending[0].scope.provider_key)

    def test_optional_adapter_and_store_failures_preserve_model_reply(self):
        config = self._config()
        capability_bot = FakeContinuationBot([
            {"choices": [{"message": {"content": "capability fallback"}}]},
        ])
        capability_bot.capability_error = RuntimeError("probe failed")
        stage_bot = FakeContinuationBot([
            {"choices": [{"message": {"content": "stage fallback"}}], "provider_anchor": "anchor"},
        ])
        with tempfile.TemporaryDirectory() as tmpdir:
            delegate = ProviderContinuationStore(str(Path(tmpdir) / "anchors.db"))
            with patch("bridge.agent_bridge.conf", return_value=config), \
                    patch("config.conf", return_value=config), \
                    patch("models.bot_factory.create_bot", return_value=capability_bot):
                router = TextModelRouter(FakeBridge())
                router._provider_continuation_store = delegate
                first = router.call(self._request("request-capability"))
            with patch("bridge.agent_bridge.conf", return_value=config), \
                    patch("config.conf", return_value=config), \
                    patch("models.bot_factory.create_bot", return_value=stage_bot):
                router = TextModelRouter(FakeBridge())
                router._provider_continuation_store = BrokenStageStore(delegate)
                second = router.call(self._request("request-stage", action="new_thread"))

            self.assertEqual(
                "capability fallback",
                first["choices"][0]["message"]["content"],
            )
            self.assertNotIn("provider_parent", capability_bot.calls[0])
            self.assertEqual(
                "stage fallback",
                second["choices"][0]["message"]["content"],
            )

    def test_stream_stages_anchor_only_after_stream_is_consumed(self):
        config = self._config()
        bot = FakeContinuationBot([[
            {"choices": [{"delta": {"content": "hello"}}]},
            {
                "choices": [{"delta": {}, "finish_reason": "stop"}],
                "provider_anchor": "stream-anchor",
            },
        ]])
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProviderContinuationStore(str(Path(tmpdir) / "anchors.db"))
            with patch("bridge.agent_bridge.conf", return_value=config), \
                    patch("config.conf", return_value=config), \
                    patch("models.bot_factory.create_bot", return_value=bot):
                router = TextModelRouter(FakeBridge())
                router._provider_continuation_store = store
                stream = router.call_stream(self._request("request-stream", action="new_thread"))
                self.assertEqual([], store.list_for_request("request-stream"))
                chunks = list(stream)

            self.assertEqual(2, len(chunks))
            self.assertEqual(
                "pending",
                store.list_for_request("request-stream")[0].status,
            )

    def test_agent_stream_attaches_confirmed_wechat_scope_only(self):
        model = CaptureStreamModel()
        context = {
            "channel_type": "wechat_group",
            "wechat_group_stable_account_id": "wga_account",
            "wechat_group_stable_room_id": "wgr_room",
            "wechat_group_stable_member_id": "wgm_alice",
            "wechat_group_owner_session_id": "owner",
            "wechat_group_thread_id": "thread",
            "wechat_group_session_action": "resume_thread",
            "wechat_group_thread_ttl_seconds": 900,
            "wechat_group_identity_status": "confirmed",
            "wechat_group_is_admin": True,
            "request_id": "request-stream-scope",
        }
        executor = AgentStreamExecutor(
            agent=SimpleNamespace(_current_session_id="fallback-owner"),
            model=model,
            system_prompt="",
            tools=[],
            messages=[],
            context=context,
        )

        with patch("config.conf", return_value={"enable_thinking": False}):
            content, _ = executor._call_llm_stream(retry_on_empty=False)

        scope = model.requests[0].provider_continuation_context
        self.assertEqual("ok", content)
        self.assertEqual("wga_account", scope["stable_account_scope"])
        self.assertEqual("wgr_room", scope["stable_room_id"])
        self.assertEqual("wgm_alice", scope["stable_member_id"])
        self.assertEqual("request-stream-scope", scope["request_id"])

        context["wechat_group_identity_requires_confirmation"] = True
        self.assertEqual({}, executor._provider_continuation_context())


if __name__ == "__main__":
    unittest.main()
