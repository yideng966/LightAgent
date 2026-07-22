import os
import tempfile
import unittest

from channel.wechat_group.wechat_group_profile_evolution_store import (
    WechatGroupProfileEvolutionStore,
)


class WechatGroupProfileEvolutionStoreTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self._tmp.name, "profiles.db")
        self.store = WechatGroupProfileEvolutionStore(self.db_path)

    def tearDown(self):
        self._tmp.cleanup()

    def test_store_records_run_and_diffs_for_room(self):
        run_id = self.store.create_run(
            room_id="wgr_a",
            trigger_source="manual",
            batch_start_row_id=1,
        )
        self.store.record_diff(
            run_id=run_id,
            room_id="wgr_a",
            sender_id="wgm_alice",
            before={"aliases": []},
            after={"aliases": ["Alice"]},
            evidence_message_ids=["m1", "m2"],
        )
        self.store.finish_run(
            run_id=run_id,
            status="success",
            batch_end_row_id=3,
            batch_message_count=2,
            analyzed_member_count=1,
            profile_update_count=1,
            alias_update_count=1,
            role_hint_update_count=0,
            failed_reason="",
        )

        runs = self.store.list_runs("wgr_a")
        diffs = self.store.list_diffs("wgr_a", sender_id="wgm_alice")

        self.assertEqual(1, len(runs))
        self.assertEqual(run_id, runs[0]["run_id"])
        self.assertEqual("success", runs[0]["status"])
        self.assertEqual(1, runs[0]["profile_update_count"])
        self.assertEqual(1, len(diffs))
        self.assertEqual({"aliases": []}, diffs[0]["before"])
        self.assertEqual({"aliases": ["Alice"]}, diffs[0]["after"])
        self.assertEqual(["m1", "m2"], diffs[0]["evidence_message_ids"])

    def test_status_tracks_room_cursor_and_failure_reason(self):
        self.store.update_status(
            room_id="wgr_a",
            last_archive_row_id=12,
            last_success_at=100,
            running=True,
            last_failed_reason="",
        )
        self.store.update_status(
            room_id="wgr_a",
            running=False,
            last_failed_reason="bad json",
        )

        status = self.store.get_status("wgr_a")

        self.assertEqual("wgr_a", status["room_id"])
        self.assertEqual(12, status["last_archive_row_id"])
        self.assertEqual(100, status["last_success_at"])
        self.assertFalse(status["running"])
        self.assertEqual("bad json", status["last_failed_reason"])


if __name__ == "__main__":
    unittest.main()
