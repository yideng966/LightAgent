import os
import tempfile
import unittest

from channel.wechat_group.wechat_group_archive import WechatGroupArchive
from channel.wechat_group.wechat_group_knowledge_store import WechatGroupKnowledgeStore


class WechatGroupKnowledgeStoreTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.knowledge_path = os.path.join(self._tmp.name, "knowledge.db")
        self.archive_path = os.path.join(self._tmp.name, "archive.db")
        self.store = WechatGroupKnowledgeStore(self.knowledge_path)

    def tearDown(self):
        self._tmp.cleanup()

    def test_group_memory_store_isolated_by_room_id(self):
        self.store.add_group_memory(room_id="room@@a", content="A群周六发布")
        self.store.add_group_memory(room_id="room@@b", content="B群周日发布")

        rows = self.store.list_group_memories("room@@a")

        self.assertEqual(1, len(rows))
        self.assertEqual("A群周六发布", rows[0]["content"])

    def test_learning_cursor_uses_archive_row_id(self):
        self.store.update_cursor("room@@a", 123)

        cursor = self.store.get_cursor("room@@a")

        self.assertEqual(123, cursor["last_archive_row_id"])

    def test_group_memory_pagination_returns_exact_count(self):
        for index in range(21):
            self.store.add_group_memory(
                room_id="room@@a",
                content=f"A群长期约定 {index:02d}",
                updated_at=100 + index,
            )
        self.store.add_group_memory(room_id="room@@b", content="B群约定")

        first = self.store.list_group_memories("room@@a", limit=20, offset=0)
        second = self.store.list_group_memories("room@@a", limit=20, offset=20)

        self.assertEqual(21, self.store.count_group_memories("room@@a"))
        self.assertEqual(20, len(first))
        self.assertEqual(1, len(second))
        self.assertEqual("A群长期约定 00", second[0]["content"])

    def test_scheduler_and_backfill_state_are_persistent_and_room_scoped(self):
        self.store.update_scheduler_state(
            "wgr_a",
            initialized_at=100,
            initialization_mode="from_now",
            latest_observed_row_id=50,
            next_retry_at=200,
        )
        self.store.update_backfill_state(
            "wgr_a",
            cursor_row_id=10,
            target_row_id=50,
            status="failed",
            completed_batches=2,
        )

        reopened = WechatGroupKnowledgeStore(self.knowledge_path)

        self.assertEqual(50, reopened.get_scheduler_state("wgr_a")["latest_observed_row_id"])
        self.assertEqual(200, reopened.get_scheduler_state("wgr_a")["next_retry_at"])
        self.assertEqual("failed", reopened.get_backfill_state("wgr_a")["status"])
        self.assertEqual(0, reopened.get_scheduler_state("wgr_b")["latest_observed_row_id"])
        self.assertEqual("idle", reopened.get_backfill_state("wgr_b")["status"])

    def test_running_learning_runs_are_marked_interrupted_on_recovery(self):
        run_id = self.store.create_learning_run("wgr_a", "memory", 10)
        self.store.update_backfill_state("wgr_a", status="running", target_row_id=100)

        changed = self.store.interrupt_running_learning_runs()
        run = self.store.list_learning_runs("wgr_a")[0]

        self.assertEqual(1, changed)
        self.assertEqual(run_id, run["run_id"])
        self.assertEqual("interrupted", run["status"])
        self.assertEqual("process_restarted", run["interrupted_reason"])
        self.assertEqual("interrupted", self.store.get_backfill_state("wgr_a")["status"])

    def test_archive_reads_messages_after_row_id_in_room_order(self):
        archive = WechatGroupArchive(self.archive_path)
        archive.record_message(
            message_id="m1",
            room_id="room@@a",
            sender_id="wxid_alice",
            text="第一条",
            created_at=100,
        )
        archive.record_message(
            message_id="m2",
            room_id="room@@b",
            sender_id="wxid_bob",
            text="其他群",
            created_at=101,
        )
        archive.record_message(
            message_id="m3",
            room_id="room@@a",
            sender_id="wxid_alice",
            text="第二条",
            created_at=102,
        )

        first_batch = archive.get_messages_after_row_id("room@@a", 0, limit=10)
        second_batch = archive.get_messages_after_row_id("room@@a", first_batch[0]["id"], limit=10)

        self.assertEqual(["m1", "m3"], [item["message_id"] for item in first_batch])
        self.assertEqual(["m3"], [item["message_id"] for item in second_batch])


if __name__ == "__main__":
    unittest.main()
