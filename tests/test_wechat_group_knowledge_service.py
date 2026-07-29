import os
import tempfile
import unittest

from channel.wechat_group.wechat_group_archive import WechatGroupArchive
from channel.wechat_group.wechat_group_knowledge_service import WechatGroupKnowledgeService
from channel.wechat_group.wechat_group_knowledge_store import WechatGroupKnowledgeStore


class WechatGroupKnowledgeServiceTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store = WechatGroupKnowledgeStore(os.path.join(self._tmp.name, "knowledge.db"))
        self.archive = WechatGroupArchive(os.path.join(self._tmp.name, "archive.db"))
        self.service = WechatGroupKnowledgeService(self.store, archive=self.archive)

    def tearDown(self):
        self._tmp.cleanup()

    def test_search_group_memory_stays_in_current_room(self):
        self.service.add_group_memory("room@@a", "A群周六早上发布", evidence_text="A群讨论")
        self.service.add_group_memory("room@@b", "B群周日晚上发布", evidence_text="B群讨论")

        rows = self.service.search_group_memories("room@@a", "发布", limit=5)

        self.assertEqual(1, len(rows))
        self.assertEqual("A群周六早上发布", rows[0]["content"])

    def test_group_knowledge_query_api_isolated_by_room(self):
        self.service.add_group_memory("wgr_a", "A群发布窗口是周五晚上")
        self.service.add_group_memory("wgr_b", "B群发布窗口是周六早上")

        rows = self.service.search_group_knowledge("wgr_a", "发布窗口", limit=5)

        self.assertEqual(["A群发布窗口是周五晚上"], [item["content"] for item in rows])

    def test_disable_group_memory_marks_status_inactive(self):
        memory = self.service.add_group_memory("room@@a", "临时规则", evidence_text="管理员")

        disabled = self.service.disable_group_memory("room@@a", memory["memory_id"])

        self.assertTrue(disabled)
        self.assertEqual([], self.service.list_group_memories("room@@a"))

    def test_search_group_memory_returns_empty_for_unrelated_query(self):
        self.service.add_group_memory("room@@a", "A群固定每周复盘", evidence_text="讨论")

        rows = self.service.search_group_memories("room@@a", "完全不相关", limit=5)

        self.assertEqual([], rows)

    def test_search_group_memory_returns_score_and_respects_min_score(self):
        self.service.add_group_memory("room@@a", "发布窗口固定为周五晚上", evidence_text="项目发布讨论")
        self.service.add_group_memory("room@@a", "每月进行一次成本复盘", evidence_text="复盘")

        matched = self.service.search_group_memories("room@@a", "发布窗口", limit=5, min_score=0.5)
        filtered = self.service.search_group_memories("room@@a", "发布项目", limit=5, min_score=0.95)

        self.assertEqual(1, len(matched))
        self.assertEqual(1.0, matched[0]["score"])
        self.assertEqual("content_exact", matched[0]["match_reason"])
        self.assertEqual([], filtered)

    def test_recent_group_memories_is_explicit_and_room_scoped(self):
        self.service.add_group_memory("room@@a", "A群固定每周复盘")
        self.service.add_group_memory("room@@b", "B群固定每周例会")

        rows = self.service.list_recent_group_memories("room@@a", limit=5)

        self.assertEqual(["A群固定每周复盘"], [item["content"] for item in rows])

    def test_manual_evidence_is_validated_in_service_layer(self):
        self.archive.record_message(
            message_id="a1",
            room_id="wgr_a",
            stable_room_id="wgr_a",
            sender_id="runtime-a",
            stable_member_id="wgm_a",
            text="A群长期约定",
            message_type="text",
        )

        saved = self.service.add_group_memory(
            "wgr_a", "A群长期约定", evidence_message_ids=["a1"]
        )

        self.assertEqual(["a1"], saved["evidence_message_ids"])
        with self.assertRaisesRegex(ValueError, "must belong to the current group"):
            self.service.add_group_memory(
                "wgr_b", "错误跨群记忆", evidence_message_ids=["a1"]
            )


if __name__ == "__main__":
    unittest.main()
