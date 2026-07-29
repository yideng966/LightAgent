import threading
import unittest
from collections import OrderedDict
from types import SimpleNamespace

from bridge.agent_bridge import AgentBridge
from config import conf


class FakeInitializer:
    def __init__(self):
        self.calls = []

    def initialize_agent(self, session_id=None, history_thread_id=None):
        self.calls.append((session_id, history_thread_id))
        return SimpleNamespace(
            owner_session_id=session_id,
            history_thread_id=history_thread_id,
        )


class AgentBridgeThreadCacheTest(unittest.TestCase):
    def setUp(self):
        self.original_limit = conf().get(
            "wechat_group_thread_agent_cache_max_entries"
        )
        conf()["wechat_group_thread_agent_cache_max_entries"] = 8
        self.bridge = AgentBridge.__new__(AgentBridge)
        self.bridge.agents = OrderedDict()
        self.bridge._agents_lock = threading.RLock()
        self.bridge._active_agent_cache_keys = set()
        self.bridge.initializer = FakeInitializer()

    def tearDown(self):
        if self.original_limit is None:
            conf().pop("wechat_group_thread_agent_cache_max_entries", None)
        else:
            conf()["wechat_group_thread_agent_cache_max_entries"] = self.original_limit

    def test_thread_cache_is_bounded_lru_and_legacy_agent_is_preserved(self):
        legacy = self.bridge.get_agent("legacy-session")
        for index in range(10):
            self.bridge.get_agent("owner", thread_id="thread-{}".format(index))

        thread_keys = [key for key in self.bridge.agents if isinstance(key, tuple)]
        self.assertEqual(8, len(thread_keys))
        self.assertNotIn(("owner", "thread-0"), self.bridge.agents)
        self.assertNotIn(("owner", "thread-1"), self.bridge.agents)
        self.assertIs(legacy, self.bridge.agents["legacy-session"])

        self.bridge.get_agent("owner", thread_id="thread-2")
        self.bridge.get_agent("owner", thread_id="thread-10")

        self.assertIn(("owner", "thread-2"), self.bridge.agents)
        self.assertNotIn(("owner", "thread-3"), self.bridge.agents)

    def test_thread_initialization_passes_owner_and_history_thread(self):
        agent = self.bridge.get_agent("owner", thread_id="thread-a")

        self.assertEqual("owner", agent.owner_session_id)
        self.assertEqual("thread-a", agent.history_thread_id)
        self.assertEqual([("owner", "thread-a")], self.bridge.initializer.calls)


if __name__ == "__main__":
    unittest.main()
