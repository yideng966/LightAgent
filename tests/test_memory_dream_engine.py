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
