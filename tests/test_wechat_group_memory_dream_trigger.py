import tempfile
import unittest
from pathlib import Path

from channel.wechat_group.wechat_group_archive import WechatGroupArchive
from channel.wechat_group.wechat_group_knowledge_store import WechatGroupKnowledgeStore


class FakeDreamService:
    def __init__(self, results=None):
        self.results = list(results or [{"status": "success", "transient": False}])
        self.calls = []

    def run_once(self, room_id, trigger_source="manual", force=False):
        self.calls.append((room_id, trigger_source, force))
        return self.results.pop(0) if self.results else {"status": "success", "transient": False}


class WechatGroupMemoryDreamTriggerTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.archive = WechatGroupArchive(str(root / "archive.db"))
        self.store = WechatGroupKnowledgeStore(str(root / "knowledge.db"))
        self.config = {
            "wechat_group_learning_enabled": True,
            "wechat_group_learning_idle_minutes": 1,
            "wechat_group_learning_group_memory_min_messages": 2,
            "wechat_group_learning_batch_message_limit": 50,
            "wechat_group_learning_group_memory_window_minutes": 120,
            "wechat_group_learning_max_interval_minutes": 1440,
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def _record(self, message_id, ts):
        return self.archive.record_message(
            message_id=message_id,
            room_id="wgr_a",
            stable_room_id="wgr_a",
            sender_id="runtime",
            stable_member_id="member",
            message_type="text",
            text=f"durable fact {message_id}",
            created_at=ts,
        )

    def _trigger(self, service=None):
        from channel.wechat_group.wechat_group_memory_dream_trigger import WechatGroupMemoryDreamTrigger

        return WechatGroupMemoryDreamTrigger(
            archive=self.archive,
            knowledge_store=self.store,
            dream_service=service or FakeDreamService(),
            config_getter=lambda key, default=None: self.config.get(key, default),
        )

    def test_first_signal_sets_high_water_then_new_messages_trigger_once(self):
        service = FakeDreamService()
        trigger = self._trigger(service)
        old_row = self._record("old", 10)

        trigger.note_message("wgr_a", old_row, now=10)
        self.assertEqual(old_row, self.store.get_cursor("wgr_a")["last_archive_row_id"])
        trigger.scan_once(now=100)
        self.assertEqual([], service.calls)

        row_1 = self._record("new-1", 110)
        trigger.note_message("wgr_a", row_1, now=110)
        row_2 = self._record("new-2", 120)
        trigger.note_message("wgr_a", row_2, now=120)
        trigger.scan_once(now=181)
        trigger.scan_once(now=300)

        self.assertEqual([("wgr_a", "idle", False)], service.calls)

    def test_disabled_or_insufficient_messages_do_not_run(self):
        service = FakeDreamService()
        trigger = self._trigger(service)
        self.store.update_cursor("wgr_a", 0)
        row = self._record("one", 10)
        trigger.note_message("wgr_a", row, now=10)

        self.config["wechat_group_learning_enabled"] = False
        trigger.scan_once(now=100)
        self.config["wechat_group_learning_enabled"] = True
        trigger.scan_once(now=100)

        self.assertEqual([], service.calls)

    def test_transient_failure_enters_backoff_without_repeat(self):
        service = FakeDreamService([{
            "status": "failed",
            "transient": True,
            "llm_status_code": 503,
        }])
        trigger = self._trigger(service)
        self.store.update_cursor("wgr_a", 0)
        for index in range(2):
            row = self._record(f"m{index}", 10 + index)
            trigger.note_message("wgr_a", row, now=10 + index)

        trigger.scan_once(now=100)
        trigger.scan_once(now=120)

        self.assertEqual(1, len(service.calls))
        self.assertGreater(trigger.get_status("wgr_a")["backoff_until"], 120)
        self.assertEqual(0, self.store.get_cursor("wgr_a")["last_archive_row_id"])

    def test_failure_warning_includes_safe_run_and_phase_diagnostics(self):
        service = FakeDreamService([{
            "status": "failed",
            "run_id": "run-empty-1",
            "summary_status": "failed",
            "dream_status": "not_run",
            "transient": False,
            "llm_status_code": 0,
            "message": (
                "text model completion returned empty content "
                "api_key=super-secret\nforged-line"
            ),
        }])
        trigger = self._trigger(service)
        self.store.update_cursor("wgr_a", 0)
        for index in range(2):
            row = self._record(f"diagnostic-{index}", 10 + index)
            trigger.note_message("wgr_a", row, now=10 + index)

        with self.assertLogs("log", level="WARNING") as captured:
            trigger.scan_once(now=100)

        output = "\n".join(captured.output)
        self.assertIn("room=wgr_a", output)
        self.assertIn("run=run-empty-1", output)
        self.assertIn("status=failed", output)
        self.assertIn("summary=failed", output)
        self.assertIn("dream=not_run", output)
        self.assertIn("transient=False", output)
        self.assertIn("http=-", output)
        self.assertIn(
            "reason=text model completion returned empty content "
            "api_key=[redacted] forged-line",
            output,
        )
        self.assertNotIn("\nforged-line", output)
        self.assertNotIn("super-secret", output)
        self.assertEqual(0, self.store.get_cursor("wgr_a")["last_archive_row_id"])

    def test_fully_filtered_batch_runs_once_to_advance_the_cursor(self):
        service = FakeDreamService()
        trigger = self._trigger(service)
        self.store.update_cursor("wgr_a", 0)
        row = self.archive.record_message(
            message_id="secret",
            room_id="wgr_a",
            stable_room_id="wgr_a",
            sender_id="runtime",
            stable_member_id="member",
            message_type="text",
            text="api_key=must-not-enter-memory",
            created_at=10,
        )
        trigger.note_message("wgr_a", row, now=10)

        trigger.scan_once(now=100)

        self.assertEqual([("wgr_a", "idle", True)], service.calls)

    def test_missing_stable_room_is_ignored(self):
        service = FakeDreamService()
        trigger = self._trigger(service)

        trigger.note_message("", 1, now=10)
        trigger.scan_once(now=100)

        self.assertEqual([], service.calls)


if __name__ == "__main__":
    unittest.main()
