import tempfile
import unittest
from pathlib import Path

from agent.memory.config import MemoryConfig
from agent.memory.manager import MemoryManager
from agent.memory.scope import MemoryScope
from agent.memory.storage import MemoryChunk, MemoryStorage


class MemoryScopeStorageTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.storage = MemoryStorage(Path(self._tmp.name) / "memory.db")

    def tearDown(self):
        self.storage.close()
        self._tmp.cleanup()

    def _save_text(self, chunk_id, text, scope=None, **kwargs):
        scope = scope or "shared"
        self.storage.save_chunk(MemoryChunk(
            id=chunk_id,
            user_id=kwargs.pop("user_id", None),
            scope=scope,
            source="memory",
            path=f"{chunk_id}.md",
            start_line=1,
            end_line=1,
            text=text,
            embedding=None,
            hash=MemoryStorage.compute_hash(text),
            **kwargs,
        ))

    def test_legacy_shared_chunk_backfills_scope_fields(self):
        self._save_text("legacy-shared", "stable shared memory")

        chunk = self.storage.get_chunk("legacy-shared")

        self.assertEqual("shared", chunk.scope)
        self.assertEqual("shared", chunk.scope_type)
        self.assertEqual("", chunk.scope_id)
        self.assertEqual("", chunk.channel_type)
        self.assertEqual("", chunk.subject_id)
        self.assertEqual("active", chunk.status)

    def test_search_keyword_filters_by_wechat_group_scope(self):
        room_a = MemoryScope.wechat_group("room@@a")
        room_b = MemoryScope.wechat_group("room@@b")
        self._save_text("room-a", "发布窗口是周五晚上", memory_scope=room_a)
        self._save_text("room-b", "发布窗口是周六早上", memory_scope=room_b)

        results = self.storage.search_keyword(
            "发布窗口",
            memory_scope=room_a,
            limit=10,
        )

        self.assertEqual(["room-a.md"], [item.path for item in results])

    def test_member_profile_scope_requires_room_and_sender(self):
        alice_room_a = MemoryScope.wechat_group_member_profile("room@@a", "wxid_alice")
        alice_room_b = MemoryScope.wechat_group_member_profile("room@@b", "wxid_alice")
        bob_room_a = MemoryScope.wechat_group_member_profile("room@@a", "wxid_bob")
        self._save_text("alice-a", "画像 Alice 喜欢简洁结论", memory_scope=alice_room_a)
        self._save_text("alice-b", "画像 Alice 在 B 群关注预算", memory_scope=alice_room_b)
        self._save_text("bob-a", "画像 Bob 关注测试覆盖", memory_scope=bob_room_a)

        results = self.storage.search_keyword(
            "画像",
            memory_scope=alice_room_a,
            limit=10,
        )

        self.assertEqual(["alice-a.md"], [item.path for item in results])

    def test_disabled_chunks_are_excluded_from_scoped_search(self):
        scope = MemoryScope.wechat_group("room@@a")
        self._save_text("active", "群规 使用中文回复", memory_scope=scope)
        self._save_text("disabled", "群规 使用英文回复", memory_scope=scope, status="disabled")

        results = self.storage.search_keyword(
            "群规",
            memory_scope=scope,
            limit=10,
        )

        self.assertEqual(["active.md"], [item.path for item in results])


class MemoryScopeManagerTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.manager = MemoryManager(MemoryConfig(workspace_root=self._tmp.name))

    async def asyncTearDown(self):
        self.manager.close()
        self._tmp.cleanup()

    async def test_manager_adds_and_searches_scoped_memories(self):
        room_a = MemoryScope.wechat_group("room@@a")
        room_b = MemoryScope.wechat_group("room@@b")
        await self.manager.add_memory("发布窗口是周五晚上", memory_scope=room_a)
        await self.manager.add_memory("发布窗口是周六早上", memory_scope=room_b)

        results = await self.manager.search("发布窗口", memory_scope=room_a)

        self.assertEqual(1, len(results))
        self.assertIn("周五", results[0].snippet)


if __name__ == "__main__":
    unittest.main()
