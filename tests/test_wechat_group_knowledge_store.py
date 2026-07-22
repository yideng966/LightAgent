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
