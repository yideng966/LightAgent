import os
import tempfile
import unittest

from channel.wechat_group.wechat_group_knowledge_service import WechatGroupKnowledgeService
from channel.wechat_group.wechat_group_knowledge_store import WechatGroupKnowledgeStore


class WechatGroupKnowledgeServiceTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store = WechatGroupKnowledgeStore(os.path.join(self._tmp.name, "knowledge.db"))
        self.service = WechatGroupKnowledgeService(self.store)

    def tearDown(self):
        self._tmp.cleanup()

    def test_search_group_memory_stays_in_current_room(self):
        self.service.add_group_memory("room@@a", "A群周六早上发布", ["m1"], "A群讨论", "manual")
        self.service.add_group_memory("room@@b", "B群周日晚上发布", ["m2"], "B群讨论", "manual")

        rows = self.service.search_group_memories("room@@a", "发布", limit=5)

        self.assertEqual(1, len(rows))
        self.assertEqual("A群周六早上发布", rows[0]["content"])

    def test_disable_group_memory_marks_status_inactive(self):
        memory = self.service.add_group_memory("room@@a", "临时规则", ["m3"], "管理员", "manual")

        disabled = self.service.disable_group_memory("room@@a", memory["memory_id"])

        self.assertTrue(disabled)
        self.assertEqual([], self.service.list_group_memories("room@@a"))

    def test_search_group_memory_falls_back_to_latest_active_rows(self):
        self.service.add_group_memory("room@@a", "A群固定每周复盘", ["m1"], "讨论", "manual")

        rows = self.service.search_group_memories("room@@a", "完全不相关", limit=5)

        self.assertEqual(1, len(rows))
        self.assertEqual("A群固定每周复盘", rows[0]["content"])


if __name__ == "__main__":
    unittest.main()
