import types
import unittest
from unittest.mock import patch


class WechatGroupGlobalMemoryIsolationTest(unittest.TestCase):
    def test_group_turn_does_not_accumulate_global_evolution(self):
        from agent.evolution.trigger import note_user_turn

        agent = types.SimpleNamespace(
            _evo_turns=4,
            _evo_observed_messages=[{"role": "user", "content": "old"}],
            _evo_observed_scope={"stable_room_id": "old"},
        )

        note_user_turn(
            agent,
            channel_type="wechat_group",
            observed_messages=[{"role": "user", "content": "group secret"}],
            stable_room_id="wgr_room",
        )

        self.assertEqual(0, agent._evo_turns)
        self.assertEqual([], agent._evo_observed_messages)
        self.assertEqual({}, agent._evo_observed_scope)

    def test_evolution_scanner_skips_group_agent(self):
        from agent.evolution.trigger import _scan_once

        agent = types.SimpleNamespace(
            _evo_run_active=False,
            _evo_last_active=1,
            _evo_turns=10,
            _evo_channel_type="wechat_group",
            _evo_receiver="",
            _memory_route=None,
            messages_lock=types.SimpleNamespace(
                __enter__=lambda self: self,
                __exit__=lambda self, *_args: None,
            ),
            messages=[],
        )
        bridge = types.SimpleNamespace(agents={"wechat_group:wgr_room:wgm_member": agent})
        cfg = types.SimpleNamespace(min_turns=1, idle_seconds=0)

        with patch("agent.evolution.trigger.time.time", return_value=100), patch(
            "agent.evolution.trigger.run_evolution_for_session"
        ) as run:
            _scan_once(bridge, cfg)

        run.assert_not_called()

    def test_evolution_executor_rejects_direct_group_call(self):
        from agent.evolution.executor import run_evolution_for_session

        bridge = types.SimpleNamespace(agents={}, default_agent=None)
        with patch("agent.evolution.executor.get_evolution_config") as get_cfg:
            get_cfg.return_value = types.SimpleNamespace(enabled=True)
            result = run_evolution_for_session(
                bridge,
                session_id="wechat_group:wgr_room:wgm_member",
                channel_type="wechat_group",
            )

        self.assertFalse(result)

    def test_daily_flush_only_uses_non_group_agents(self):
        from agent.memory.routing import resolve_memory_route
        from bridge.agent_initializer import AgentInitializer

        class FakeFlushManager:
            def __init__(self):
                self.daily_calls = 0
                self.dream_calls = 0
                self._last_flush_thread = None

            def create_daily_summary(self, _messages):
                self.daily_calls += 1
                return False

            def deep_dream(self):
                self.dream_calls += 1
                return True

        def make_agent(route):
            flush = FakeFlushManager()
            agent = types.SimpleNamespace(
                memory_manager=types.SimpleNamespace(flush_manager=flush),
                messages=[{"role": "user", "content": "text"}],
                messages_lock=__import__("threading").RLock(),
                _memory_route=route,
            )
            return agent, flush

        group_agent, group_flush = make_agent(resolve_memory_route(channel_type="wechat_group"))
        web_agent, web_flush = make_agent(resolve_memory_route(channel_type="web"))
        initializer = AgentInitializer.__new__(AgentInitializer)
        initializer.agent_bridge = types.SimpleNamespace(
            default_agent=None,
            agents={
                "wechat_group:wgr_room:wgm_member": group_agent,
                "web-user": web_agent,
            },
        )

        initializer._flush_all_agents()

        self.assertEqual(0, group_flush.daily_calls)
        self.assertEqual(0, group_flush.dream_calls)
        self.assertEqual(1, web_flush.daily_calls)
        self.assertEqual(1, web_flush.dream_calls)


if __name__ == "__main__":
    unittest.main()
