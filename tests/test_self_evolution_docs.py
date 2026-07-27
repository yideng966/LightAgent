import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SelfEvolutionDocsTest(unittest.TestCase):
    def test_readme_documents_self_evolution_runtime_chain(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        expected_terms = [
            "self_evolution_enabled",
            "self_evolution_idle_minutes",
            "self_evolution_min_turns",
            "未配置时的 fallback 默认值是关闭",
            "空闲 10 分钟",
            "至少 6 个真实用户轮次",
            "agent=false",
            "AgentBridge.agent_reply",
            "agent.chat.service",
            "agent.evolution.trigger",
            "agent.evolution.executor",
            "note_user_turn",
            "mark_run_active",
            "run_evolution_for_session",
            "remember_scheduled_output",
            "evolution_undo",
        ]
        for term in expected_terms:
            with self.subTest(term=term):
                self.assertIn(term, readme)

    def test_readme_documents_wechat_group_memory_isolation(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        expected_terms = [
            "WechatGroupChannel",
            "ChatChannel",
            "Bridge.fetch_agent_reply",
            "AgentBridge.agent_reply",
            "wechat_group",
            "微信群",
            "不参与 shared Daily Summary",
            "全局 Deep Dream",
            "Self-Evolution",
            "TextModelRouter.complete()",
            "stable_room_id",
        ]
        for term in expected_terms:
            with self.subTest(term=term):
                self.assertIn(term, readme)

        self.assertNotIn("微信群与群聊复用自主进化", readme)

    def test_group_turns_are_rejected_by_all_evolution_layers(self):
        agent_bridge = (ROOT / "bridge" / "agent_bridge.py").read_text(encoding="utf-8")
        trigger = (ROOT / "agent" / "evolution" / "trigger.py").read_text(encoding="utf-8")
        executor = (ROOT / "agent" / "evolution" / "executor.py").read_text(encoding="utf-8")
        self.assertIn("memory_route.allow_shared_evolution", agent_bridge)
        self.assertIn("route.allow_shared_evolution", trigger)
        self.assertIn("route.allow_shared_evolution", executor)


if __name__ == "__main__":
    unittest.main()
