import tempfile
import unittest
from pathlib import Path


class MemoryChannelRoutingTest(unittest.TestCase):
    def test_explicit_wechat_group_never_allows_shared_writes(self):
        from agent.memory.routing import resolve_memory_route

        route = resolve_memory_route(
            context={
                "channel_type": "wechat_group",
                "wechat_group_stable_room_id": "wgr_room",
            }
        )

        self.assertEqual("wechat_group", route.scope_type)
        self.assertEqual("wgr_room", route.scope_id)
        self.assertFalse(route.allow_shared_flush)
        self.assertFalse(route.allow_shared_evolution)

    def test_wechat_group_without_stable_room_fails_closed(self):
        from agent.memory.routing import resolve_memory_route

        route = resolve_memory_route(context={"channel_type": "wechat_group"})

        self.assertEqual("wechat_group", route.scope_type)
        self.assertEqual("", route.scope_id)
        self.assertFalse(route.allow_shared_flush)
        self.assertFalse(route.allow_shared_evolution)

    def test_legacy_wechat_group_session_id_is_safe_fallback(self):
        from agent.memory.routing import resolve_memory_route

        route = resolve_memory_route(session_id="wechat_group:wgr_room:wgm_member")

        self.assertEqual("wechat_group", route.scope_type)
        self.assertEqual("wgr_room", route.scope_id)
        self.assertFalse(route.allow_shared_flush)
        self.assertFalse(route.allow_shared_evolution)

    def test_other_channels_keep_shared_behavior(self):
        from agent.memory.routing import resolve_memory_route

        route = resolve_memory_route(
            context={"channel_type": "web"},
            session_id="web-user",
        )

        self.assertEqual("shared", route.scope_type)
        self.assertTrue(route.allow_shared_flush)
        self.assertTrue(route.allow_shared_evolution)

    def test_memory_manager_rejects_group_flush_as_second_line_of_defense(self):
        from agent.memory.manager import MemoryManager
        from agent.memory.routing import resolve_memory_route

        class FakeFlushManager:
            def __init__(self):
                self.called = False

            def flush_from_messages(self, **_kwargs):
                self.called = True
                return True

        manager = MemoryManager.__new__(MemoryManager)
        manager.flush_manager = FakeFlushManager()
        manager._dirty = False
        manager._memory_route = resolve_memory_route(channel_type="wechat_group")

        result = manager.flush_memory(
            [{"role": "user", "content": "group secret"}],
        )

        self.assertFalse(result)
        self.assertFalse(manager.flush_manager.called)
        self.assertFalse(manager._dirty)


if __name__ == "__main__":
    unittest.main()
