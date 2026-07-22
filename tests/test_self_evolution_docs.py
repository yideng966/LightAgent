import ast
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

    def test_readme_documents_wechat_group_reuses_self_evolution(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        expected_terms = [
            "WechatGroupChannel",
            "ChatChannel",
            "Bridge.fetch_agent_reply",
            "AgentBridge.agent_reply",
            "wechat_group",
            "微信群",
            "复用自主进化",
            "不设置主动推送 receiver",
        ]
        for term in expected_terms:
            with self.subTest(term=term):
                self.assertIn(term, readme)

    def test_group_turns_are_recorded_without_proactive_receiver(self):
        agent_bridge = (ROOT / "bridge" / "agent_bridge.py").read_text(encoding="utf-8")
        bridge_tree = ast.parse(agent_bridge)
        self.assertTrue(
            self._has_group_safe_note_user_turn(bridge_tree),
            "AgentBridge must record group turns with an empty proactive receiver",
        )

        executor = (ROOT / "agent" / "evolution" / "executor.py").read_text(encoding="utf-8")
        executor_tree = ast.parse(executor)
        self.assertTrue(
            self._has_receiver_guarded_notify(executor_tree),
            "Evolution executor must notify only when both channel_type and receiver exist",
        )

    @staticmethod
    def _has_group_safe_note_user_turn(tree):
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Name) or node.func.id != "note_user_turn":
                continue
            receiver_kw = next((kw for kw in node.keywords if kw.arg == "receiver"), None)
            if not receiver_kw or not isinstance(receiver_kw.value, ast.IfExp):
                continue
            receiver_expr = receiver_kw.value
            if isinstance(receiver_expr.orelse, ast.Constant) and receiver_expr.orelse.value == "":
                return True
        return False

    @staticmethod
    def _has_receiver_guarded_notify(tree):
        for node in ast.walk(tree):
            if not isinstance(node, ast.If):
                continue
            test = node.test
            if not isinstance(test, ast.BoolOp) or not isinstance(test.op, ast.And):
                continue
            names = {value.id for value in test.values if isinstance(value, ast.Name)}
            if not {"channel_type", "receiver"}.issubset(names):
                continue
            for child in ast.walk(ast.Module(body=node.body, type_ignores=[])):
                if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
                    if child.func.id == "_notify_user":
                        return True
        return False


if __name__ == "__main__":
    unittest.main()
