import os
import tempfile
import unittest

from channel.wechat_group.wechat_group_profile_evolution_store import (
    WechatGroupProfileEvolutionStore,
)
from channel.wechat_group.wechat_group_profile_evolution_trigger import (
    WechatGroupProfileEvolutionTrigger,
)


class FakeExecutor:
    def __init__(self):
        self.calls = []

    def run_once(self, room_id, trigger_source="idle"):
        self.calls.append((room_id, trigger_source))
        return {"status": "success", "run_id": "run1"}


class WechatGroupProfileEvolutionTriggerTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store = WechatGroupProfileEvolutionStore(os.path.join(self._tmp.name, "profiles.db"))
        self.executor = FakeExecutor()
        self.config = {
            "wechat_group_profile_evolution_enabled": True,
            "wechat_group_profile_evolution_idle_minutes": 1,
            "wechat_group_profile_evolution_min_messages": 2,
            "wechat_group_profile_evolution_max_interval_minutes": 1440,
        }
        self.trigger = WechatGroupProfileEvolutionTrigger(
            evolution_store=self.store,
            executor=self.executor,
            config_getter=lambda key, default=None: self.config.get(key, default),
        )
        self.store.update_status("wgr_a", last_archive_row_id=0, latest_observed_row_id=0)

    def tearDown(self):
        self._tmp.cleanup()

    def test_scan_does_not_run_when_disabled(self):
        self.config["wechat_group_profile_evolution_enabled"] = False
        self.trigger.note_message("wgr_a", archive_row_id=1, now=100)
        self.trigger.note_message("wgr_a", archive_row_id=2, now=101)

        self.trigger.scan_once(now=500)

        self.assertEqual([], self.executor.calls)

    def test_scan_waits_for_idle_and_message_threshold(self):
        self.trigger.note_message("wgr_a", archive_row_id=1, now=100)

        self.trigger.scan_once(now=500)

        self.assertEqual([], self.executor.calls)

    def test_scan_runs_once_when_room_is_idle_and_threshold_reached(self):
        self.trigger.note_message("wgr_a", archive_row_id=1, now=100)
        self.trigger.note_message("wgr_a", archive_row_id=2, now=101)

        self.trigger.scan_once(now=500)
        self.trigger.scan_once(now=501)

        self.assertEqual([("wgr_a", "idle")], self.executor.calls)

    def test_first_signal_initializes_baseline_without_pending_history(self):
        self.trigger.note_message("wgr_new", archive_row_id=50, now=100)

        status = self.store.get_status("wgr_new")

        self.assertEqual(50, status["last_archive_row_id"])
        self.assertEqual(50, status["latest_observed_row_id"])

    def test_scan_backs_off_after_transient_llm_failure(self):
        from channel.wechat_group.wechat_group_profile_llm_extractor import (
            WechatGroupProfileExtractionError,
        )

        class FailingExecutor:
            def __init__(self):
                self.calls = []
                self.batch_message_limit = 20

            def run_once(self, room_id, trigger_source="idle"):
                self.calls.append((room_id, trigger_source))
                raise WechatGroupProfileExtractionError(
                    "LLM provider temporarily unavailable (HTTP 503): Inference is temporarily unavailable",
                    status_code=503,
                    transient=True,
                )

        executor = FailingExecutor()
        trigger = WechatGroupProfileEvolutionTrigger(
            evolution_store=self.store,
            executor=executor,
            config_getter=lambda key, default=None: self.config.get(key, default),
        )
        trigger.note_message("wgr_a", archive_row_id=1, now=100)
        trigger.note_message("wgr_a", archive_row_id=2, now=101)

        trigger.scan_once(now=500)
        trigger.scan_once(now=501)

        self.assertEqual([("wgr_a", "idle")], executor.calls)
        status = self.store.get_status("wgr_a")
        self.assertEqual(500, status["last_signal_at"])
        self.assertIn("LLM provider temporarily unavailable", status["last_failed_reason"])


if __name__ == "__main__":
    unittest.main()
