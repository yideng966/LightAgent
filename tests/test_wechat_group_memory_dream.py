import json
import tempfile
import threading
import unittest
from pathlib import Path

from channel.wechat_group.wechat_group_archive import WechatGroupArchive
from channel.wechat_group.wechat_group_knowledge_service import WechatGroupKnowledgeService
from channel.wechat_group.wechat_group_knowledge_store import WechatGroupKnowledgeStore


class FakeDreamEngine:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def complete(self, **kwargs):
        self.calls.append(kwargs)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class WechatGroupMemoryDreamTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.archive = WechatGroupArchive(str(root / "archive.db"))
        self.store = WechatGroupKnowledgeStore(str(root / "knowledge.db"))
        self.service = WechatGroupKnowledgeService(self.store, archive=self.archive)
        self.config = {
            "wechat_group_learning_batch_message_limit": 50,
            "wechat_group_learning_group_memory_min_messages": 1,
            "wechat_group_learning_group_memory_window_minutes": 120,
            "wechat_group_learning_auto_apply_threshold": 0.9,
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def _record(self, message_id, room_id, text, ts=100):
        self.archive.record_message(
            message_id=message_id,
            room_id=room_id,
            stable_room_id=room_id,
            sender_id="runtime-member",
            stable_member_id="stable-member",
            text=text,
            message_type="text",
            created_at=ts,
        )

    def _dream_service(self, engine):
        from channel.wechat_group.wechat_group_memory_dream import WechatGroupMemoryDreamService

        return WechatGroupMemoryDreamService(
            archive=self.archive,
            knowledge_service=self.service,
            dream_engine=engine,
            config_getter=lambda key, default=None: self.config.get(key, default),
        )

    def test_two_stage_dream_adds_only_current_room_memory(self):
        self._record("a1", "wgr_a", "Deployments happen every Friday")
        self._record("b1", "wgr_b", "B room private rule")
        engine = FakeDreamEngine([
            json.dumps({"summary": "Friday deployment agreement", "evidence_message_ids": ["a1"]}),
            json.dumps({
                "memories": [{
                    "action": "add",
                    "target_memory_token": "",
                    "content": "The group deploys every Friday.",
                    "confidence": 0.98,
                    "evidence_message_ids": ["a1"],
                }],
                "dream_summary": "Added one durable agreement",
            }),
        ])

        result = self._dream_service(engine).run_once("wgr_a", trigger_source="manual")

        self.assertEqual("success", result["status"])
        self.assertEqual(1, result["group_memory_upsert_count"])
        self.assertEqual(
            ["wechat_group_memory_daily_summary", "wechat_group_memory_deep_dream"],
            [call["purpose"] for call in engine.calls],
        )
        self.assertEqual(1, len(self.store.list_group_memories("wgr_a")))
        self.assertEqual([], self.store.list_group_memories("wgr_b"))
        self.assertEqual(self.archive.get_max_row_id("wgr_a"), self.store.get_cursor("wgr_a")["last_archive_row_id"])
        self.assertEqual("", self.store.list_learning_runs("wgr_a", limit=1)[0]["dream_summary"])

    def test_cross_room_evidence_is_rejected_without_advancing_cursor(self):
        self._record("a1", "wgr_a", "A room agreement")
        self._record("b1", "wgr_b", "B room secret")
        engine = FakeDreamEngine([
            json.dumps({"summary": "A agreement", "evidence_message_ids": ["a1"]}),
            json.dumps({
                "memories": [{
                    "action": "add",
                    "content": "Leaked B rule",
                    "confidence": 0.99,
                    "evidence_message_ids": ["b1"],
                }],
                "dream_summary": "invalid",
            }),
        ])

        result = self._dream_service(engine).run_once("wgr_a")

        self.assertEqual("failed", result["status"])
        self.assertEqual("success", result["summary_status"])
        self.assertEqual("failed", result["dream_status"])
        self.assertEqual(0, self.store.get_cursor("wgr_a")["last_archive_row_id"])
        self.assertEqual([], self.store.list_group_memories("wgr_a"))

    def test_invalid_json_and_transient_failure_do_not_advance_cursor(self):
        from agent.memory.dream_engine import MemoryDreamError

        self._record("a1", "wgr_a", "A room agreement")
        invalid = self._dream_service(FakeDreamEngine(["not-json"])).run_once("wgr_a")
        self.assertEqual("failed", invalid["status"])
        self.assertEqual(0, self.store.get_cursor("wgr_a")["last_archive_row_id"])

        transient_engine = FakeDreamEngine([
            MemoryDreamError("HTTP 503", status_code=503, transient=True),
        ])
        transient = self._dream_service(transient_engine).run_once("wgr_a")
        self.assertEqual("failed", transient["status"])
        self.assertEqual("failed", transient["summary_status"])
        self.assertEqual("not_run", transient["dream_status"])
        self.assertTrue(transient["transient"])
        self.assertEqual(503, transient["llm_status_code"])
        self.assertEqual(0, self.store.get_cursor("wgr_a")["last_archive_row_id"])

    def test_empty_summary_advances_successful_cursor_without_writing(self):
        self._record("a1", "wgr_a", "casual chat")
        engine = FakeDreamEngine(["[EMPTY]"])

        result = self._dream_service(engine).run_once("wgr_a")

        self.assertEqual("success", result["status"])
        self.assertEqual("empty", result["summary_status"])
        self.assertEqual(1, len(engine.calls))
        self.assertEqual([], self.store.list_group_memories("wgr_a"))
        self.assertGreater(self.store.get_cursor("wgr_a")["last_archive_row_id"], 0)

    def test_fully_filtered_batch_advances_without_calling_llm(self):
        self._record("a1", "wgr_a", "api_key=must-not-enter-memory")
        engine = FakeDreamEngine([])

        result = self._dream_service(engine).run_once("wgr_a")

        self.assertEqual("success", result["status"])
        self.assertEqual("filtered", result["summary_status"])
        self.assertEqual("skipped", result["dream_status"])
        self.assertEqual([], engine.calls)
        self.assertEqual(
            self.archive.get_max_row_id("wgr_a"),
            self.store.get_cursor("wgr_a")["last_archive_row_id"],
        )

    def test_update_requires_server_provided_memory_token(self):
        self._record("a1", "wgr_a", "Friday changed to Thursday")
        self.service.add_group_memory("wgr_a", "Deploy Friday", ["a1"])
        engine = FakeDreamEngine([
            json.dumps({"summary": "Changed to Thursday", "evidence_message_ids": ["a1"]}),
            json.dumps({
                "memories": [{
                    "action": "update",
                    "target_memory_token": "M999",
                    "content": "Deploy Thursday",
                    "confidence": 0.99,
                    "evidence_message_ids": ["a1"],
                }],
                "dream_summary": "invalid token",
            }),
        ])

        result = self._dream_service(engine).run_once("wgr_a")

        self.assertEqual("failed", result["status"])
        self.assertEqual("Deploy Friday", self.store.list_group_memories("wgr_a")[0]["content"])

    def test_invalid_json_is_repaired_once_with_original_safe_material(self):
        self._record("a1", "wgr_a", "The group deploys on Friday")
        engine = FakeDreamEngine([
            "not-json",
            json.dumps({"summary": "Friday deployment", "evidence_message_ids": ["a1"]}),
            json.dumps({"memories": [], "dream_summary": "No write"}),
        ])

        result = self._dream_service(engine).run_once("wgr_a")

        self.assertEqual("success", result["status"])
        self.assertEqual(3, result["attempt_count"])
        self.assertEqual(
            "wechat_group_memory_daily_summary_repair",
            engine.calls[1]["purpose"],
        )
        repair_payload = json.loads(engine.calls[1]["user_prompt"])
        self.assertEqual(["a1"], repair_payload["allowed_evidence_message_ids"])
        self.assertNotIn("not-json", engine.calls[1]["user_prompt"])
        run = self.store.list_learning_runs("wgr_a", limit=1)[0]
        self.assertEqual(3, run["attempt_count"])
        self.assertEqual(result["cursor_after"], run["cursor_after"])

    def test_invalid_json_after_one_repair_fails_without_advancing_cursor(self):
        self._record("a1", "wgr_a", "The group deploys on Friday")
        engine = FakeDreamEngine(["not-json", "still-not-json"])

        result = self._dream_service(engine).run_once("wgr_a")

        self.assertEqual("failed", result["status"])
        self.assertEqual("invalid_json", result["failure_code"])
        self.assertEqual(2, result["attempt_count"])
        self.assertEqual(0, self.store.get_cursor("wgr_a")["last_archive_row_id"])
        self.assertEqual(2, len(engine.calls))

    def test_failed_completion_persists_router_attempt_metadata(self):
        from agent.memory.dream_engine import MemoryDreamError

        self._record("a1", "wgr_a", "The group deploys on Friday")

        class FailedFallbackEngine(FakeDreamEngine):
            def __init__(self):
                super().__init__([])
                self.last_completion_metadata = {
                    "fallback_used": True,
                    "attempt_count": 3,
                }

            def complete(self, **kwargs):
                self.calls.append(kwargs)
                raise MemoryDreamError(
                    "HTTP 503",
                    status_code=503,
                    transient=True,
                )

        result = self._dream_service(FailedFallbackEngine()).run_once("wgr_a")

        self.assertEqual("failed", result["status"])
        self.assertEqual(3, result["attempt_count"])
        self.assertTrue(result["fallback_used"])
        run = self.store.list_learning_runs("wgr_a", limit=1)[0]
        self.assertEqual(3, run["attempt_count"])
        self.assertEqual(1, run["fallback_used"])

    def test_same_room_runs_are_serialized_across_service_instances(self):
        self._record("a1", "wgr_a", "The release window is Friday")
        first_started = threading.Event()
        release_first = threading.Event()

        class BlockingDreamEngine(FakeDreamEngine):
            def complete(self, **kwargs):
                if not self.calls:
                    first_started.set()
                    if not release_first.wait(timeout=2):
                        raise RuntimeError("test timed out waiting to release first Dream")
                return super().complete(**kwargs)

        first_engine = BlockingDreamEngine([
            json.dumps({"summary": "Friday release window", "evidence_message_ids": ["a1"]}),
            json.dumps({
                "memories": [{
                    "action": "add",
                    "target_memory_token": "",
                    "content": "The group releases on Friday.",
                    "confidence": 0.99,
                    "evidence_message_ids": ["a1"],
                }],
                "dream_summary": "Added release window",
            }),
        ])
        second_engine = FakeDreamEngine([
            json.dumps({"summary": "duplicate", "evidence_message_ids": ["a1"]}),
        ])
        results = {}
        first_thread = threading.Thread(
            target=lambda: results.setdefault("first", self._dream_service(first_engine).run_once("wgr_a")),
        )
        second_thread = threading.Thread(
            target=lambda: results.setdefault("second", self._dream_service(second_engine).run_once("wgr_a")),
        )

        first_thread.start()
        self.assertTrue(first_started.wait(timeout=1))
        second_thread.start()
        second_thread.join(timeout=0.1)
        self.assertTrue(second_thread.is_alive())
        self.assertEqual([], second_engine.calls)
        release_first.set()
        first_thread.join(timeout=2)
        second_thread.join(timeout=2)

        self.assertFalse(first_thread.is_alive())
        self.assertFalse(second_thread.is_alive())
        self.assertEqual("success", results["first"]["status"])
        self.assertEqual("success", results["second"]["status"])
        self.assertEqual([], second_engine.calls)
        self.assertEqual(1, len(self.store.list_group_memories("wgr_a")))

    def test_different_room_runs_share_the_global_dream_lock(self):
        self._record("a1", "wgr_a", "Room A releases on Friday")
        self._record("b1", "wgr_b", "Room B releases on Saturday")
        first_started = threading.Event()
        release_first = threading.Event()

        class BlockingDreamEngine(FakeDreamEngine):
            def complete(self, **kwargs):
                if not self.calls:
                    first_started.set()
                    if not release_first.wait(timeout=2):
                        raise RuntimeError("test timed out waiting to release first Dream")
                return super().complete(**kwargs)

        first_engine = BlockingDreamEngine([
            json.dumps({"summary": "A Friday release", "evidence_message_ids": ["a1"]}),
            json.dumps({"memories": [], "dream_summary": "No write"}),
        ])
        second_engine = FakeDreamEngine([
            json.dumps({"summary": "B Saturday release", "evidence_message_ids": ["b1"]}),
            json.dumps({"memories": [], "dream_summary": "No write"}),
        ])
        results = {}
        first_thread = threading.Thread(
            target=lambda: results.setdefault("first", self._dream_service(first_engine).run_once("wgr_a")),
        )
        second_thread = threading.Thread(
            target=lambda: results.setdefault("second", self._dream_service(second_engine).run_once("wgr_b")),
        )

        first_thread.start()
        self.assertTrue(first_started.wait(timeout=1))
        second_thread.start()
        second_thread.join(timeout=0.1)
        self.assertTrue(second_thread.is_alive())
        self.assertEqual([], second_engine.calls)
        release_first.set()
        first_thread.join(timeout=2)
        second_thread.join(timeout=2)

        self.assertFalse(first_thread.is_alive())
        self.assertFalse(second_thread.is_alive())
        self.assertEqual("success", results["first"]["status"])
        self.assertEqual("success", results["second"]["status"])
        self.assertEqual(2, len(second_engine.calls))

    def test_history_uses_independent_cursor_and_continues_after_failure(self):
        self.config["wechat_group_learning_batch_message_limit"] = 1
        self._record("a1", "wgr_a", "First durable agreement", ts=100)
        self._record("a2", "wgr_a", "Second durable agreement", ts=1000)
        self.store.update_cursor("wgr_a", self.archive.get_max_row_id("wgr_a"))
        failing_engine = FakeDreamEngine([
            json.dumps({"summary": "First", "evidence_message_ids": ["a1"]}),
            json.dumps({"memories": [], "dream_summary": "No write"}),
            "not-json",
        ])
        dream = self._dream_service(failing_engine)

        first = dream.run_history("wgr_a", max_batches=2, operation="restart")

        self.assertEqual("failed", first["status"])
        self.assertGreater(first["backfill_cursor"], 0)
        self.assertEqual(
            self.archive.get_max_row_id("wgr_a"),
            self.store.get_cursor("wgr_a")["last_archive_row_id"],
        )
        failed_cursor = self.store.get_backfill_state("wgr_a")["cursor_row_id"]

        continuing = self._dream_service(FakeDreamEngine([
            json.dumps({"summary": "Second", "evidence_message_ids": ["a2"]}),
            json.dumps({"memories": [], "dream_summary": "No write"}),
        ])).run_history("wgr_a", max_batches=2, operation="continue")

        self.assertEqual("success", continuing["status"])
        self.assertEqual(failed_cursor, continuing["runs"][0]["cursor_before"])
        self.assertEqual("completed", self.store.get_backfill_state("wgr_a")["status"])

    def test_history_preview_freezes_current_high_watermark(self):
        self._record("a1", "wgr_a", "First durable agreement")
        dream = self._dream_service(FakeDreamEngine([]))

        preview = dream.preview_history("wgr_a")

        self.assertEqual(0, preview["cursor_start"])
        self.assertEqual(self.archive.get_max_row_id("wgr_a"), preview["frozen_high_watermark"])
        self.assertEqual(1, preview["pending_count"])

    def test_completed_history_continue_only_processes_new_archive_rows(self):
        self.config["wechat_group_learning_batch_message_limit"] = 1
        self._record("a1", "wgr_a", "First durable agreement", ts=100)
        first = self._dream_service(FakeDreamEngine([
            json.dumps({"summary": "First", "evidence_message_ids": ["a1"]}),
            json.dumps({"memories": [], "dream_summary": "No write"}),
        ])).run_history("wgr_a", max_batches=1, operation="restart")
        first_target = first["backfill_target_row_id"]
        self.assertEqual("completed", self.store.get_backfill_state("wgr_a")["status"])

        self._record("a2", "wgr_a", "Second durable agreement", ts=200)
        dream = self._dream_service(FakeDreamEngine([
            json.dumps({"summary": "Second", "evidence_message_ids": ["a2"]}),
            json.dumps({"memories": [], "dream_summary": "No write"}),
        ]))
        preview = dream.preview_history("wgr_a", operation="continue")
        continued = dream.run_history("wgr_a", max_batches=1, operation="continue")

        self.assertEqual(first_target, preview["cursor_start"])
        self.assertEqual(first_target, continued["runs"][0]["cursor_before"])
        self.assertEqual("completed", self.store.get_backfill_state("wgr_a")["status"])

    def test_history_restart_preview_always_starts_from_zero(self):
        self._record("a1", "wgr_a", "First durable agreement", ts=100)
        target = self.archive.get_max_row_id("wgr_a")
        self.store.update_backfill_state(
            "wgr_a",
            cursor_row_id=target,
            target_row_id=target,
            status="completed",
        )

        preview = self._dream_service(FakeDreamEngine([])).preview_history(
            "wgr_a",
            operation="restart",
        )

        self.assertEqual(0, preview["cursor_start"])
        self.assertEqual(target, preview["frozen_high_watermark"])
        self.assertEqual(1, preview["pending_count"])


if __name__ == "__main__":
    unittest.main()
