import tempfile
import unittest
from datetime import datetime
from pathlib import Path


class FakeRouter:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def complete(self, messages, **kwargs):
        self.calls.append({"messages": messages, **kwargs})
        return self.responses.pop(0)


class MemoryDreamEngineTest(unittest.TestCase):
    def test_complete_uses_shared_router_with_purpose_and_temperature(self):
        from agent.memory.dream_engine import MemoryDreamEngine

        router = FakeRouter([{"success": True, "content": "distilled", "raw": {}}])
        engine = MemoryDreamEngine(router)

        result = engine.complete(
            system_prompt="system",
            user_prompt="material",
            purpose="memory_deep_dream",
            temperature=0.2,
        )

        self.assertEqual("distilled", result)
        self.assertEqual("memory_deep_dream", router.calls[0]["purpose"])
        self.assertEqual(0.2, router.calls[0]["temperature"])
        self.assertEqual("system", router.calls[0]["system"])

    def test_transient_error_envelope_is_classified(self):
        from agent.memory.dream_engine import MemoryDreamEngine, MemoryDreamError

        router = FakeRouter([{
            "success": False,
            "content": "service unavailable",
            "raw": {"error": True, "status_code": 503, "message": "upstream unavailable"},
        }])

        with self.assertRaises(MemoryDreamError) as captured:
            MemoryDreamEngine(router).complete(
                system_prompt="system",
                user_prompt="material",
                purpose="wechat_group_memory_deep_dream",
            )

        self.assertTrue(captured.exception.transient)
        self.assertEqual(503, captured.exception.status_code)
        self.assertIn("HTTP 503", str(captured.exception))

    def test_empty_completion_reports_bounded_metadata_without_reasoning_text(self):
        from agent.memory.dream_engine import MemoryDreamEngine, MemoryDreamError

        router = FakeRouter([{
            "success": False,
            "content": "",
            "raw": {
                "model": "reasoning-model",
                "choices": [{
                    "message": {
                        "content": "",
                        "reasoning_content": "PRIVATE REASONING MUST NOT LEAK",
                    },
                    "finish_reason": "length",
                }],
                "usage": {
                    "completion_tokens": 800,
                    "completion_tokens_details": {"reasoning_tokens": 800},
                },
            },
        }])

        with self.assertRaises(MemoryDreamError) as captured:
            MemoryDreamEngine(router).complete(
                system_prompt="system",
                user_prompt="material",
                purpose="wechat_group_memory_daily_summary",
            )

        message = str(captured.exception)
        self.assertIn("empty content", message)
        self.assertIn("model=reasoning-model", message)
        self.assertIn("finish_reason=length", message)
        self.assertIn("completion_tokens=800", message)
        self.assertIn("reasoning_tokens=800", message)
        self.assertNotIn("PRIVATE REASONING MUST NOT LEAK", message)
        self.assertEqual(0, captured.exception.status_code)
        self.assertFalse(captured.exception.transient)

    def test_empty_completion_diagnostics_tolerate_malformed_metadata(self):
        from agent.memory.dream_engine import MemoryDreamEngine, MemoryDreamError

        router = FakeRouter([{
            "success": False,
            "content": "",
            "raw": {
                "model": {"unexpected": "mapping"},
                "choices": "not-a-list",
                "usage": {
                    "completion_tokens": [800],
                    "completion_tokens_details": "not-a-mapping",
                },
            },
        }])

        with self.assertRaises(MemoryDreamError) as captured:
            MemoryDreamEngine(router).complete(
                system_prompt="system",
                user_prompt="material",
                purpose="wechat_group_memory_daily_summary",
            )

        self.assertEqual(
            "text model completion returned empty content",
            str(captured.exception),
        )

    def test_timeout_exception_without_status_is_transient(self):
        from agent.memory.dream_engine import MemoryDreamEngine, MemoryDreamError

        class TimeoutRouter:
            def complete(self, *_args, **_kwargs):
                raise TimeoutError("upstream timed out")

        with self.assertRaises(MemoryDreamError) as captured:
            MemoryDreamEngine(TimeoutRouter()).complete(
                system_prompt="system",
                user_prompt="material",
                purpose="memory_daily_summary",
            )

        self.assertTrue(captured.exception.transient)

    def test_exception_route_metadata_is_preserved_for_diagnostics(self):
        from agent.memory.dream_engine import MemoryDreamEngine, MemoryDreamError

        class FailedFallbackRouter:
            def complete(self, *_args, **_kwargs):
                error = RuntimeError("fallback timed out")
                error._lightagent_route_source = "fallback"
                error._lightagent_route_attempt_count = 3
                raise error

        engine = MemoryDreamEngine(FailedFallbackRouter())
        with self.assertRaises(MemoryDreamError):
            engine.complete(
                system_prompt="system",
                user_prompt="material",
                purpose="wechat_group_memory_daily_summary",
            )

        self.assertEqual(
            {"fallback_used": True, "attempt_count": 3},
            engine.last_completion_metadata,
        )

    def test_global_summary_and_dream_use_shared_engine(self):
        from agent.memory.summarizer import MemoryFlushManager

        responses = [
            {"success": True, "content": "- durable summary", "raw": {}},
            {
                "success": True,
                "content": "[MEMORY]\n- distilled memory\n\n[DREAM]\ncleaned",
                "raw": {},
            },
        ]
        router = FakeRouter(responses)
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            memory_dir = workspace / "memory"
            memory_dir.mkdir()
            (workspace / "MEMORY.md").write_text("- old memory\n", encoding="utf-8")
            today = datetime.now().strftime("%Y-%m-%d")
            (memory_dir / f"{today}.md").write_text("- daily fact\n", encoding="utf-8")
            manager = MemoryFlushManager(workspace, llm_model=router)

            summary = manager._summarize_messages([
                {"role": "user", "content": "remember this"},
                {"role": "assistant", "content": "noted"},
            ])
            dreamed = manager.deep_dream(force=True)

            self.assertEqual("- durable summary", summary)
            self.assertTrue(dreamed)
            self.assertEqual("memory_daily_summary", router.calls[0]["purpose"])
            self.assertEqual("memory_deep_dream", router.calls[1]["purpose"])
            self.assertIn("distilled memory", (workspace / "MEMORY.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
