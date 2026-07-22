import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SchedulerUiTest(unittest.TestCase):
    def test_task_cards_show_receiver_name_as_target(self):
        console_js = (ROOT / "channel/web/static/js/console.js").read_text(encoding="utf-8")

        self.assertIn("const taskTarget = action.receiver_name || '--';", console_js)
        self.assertIn("目标", console_js)
        self.assertIn("${escapeHtml(taskTarget)}", console_js)

    def test_task_cards_show_waiting_identity_binding_status(self):
        console_js = (ROOT / "channel/web/static/js/console.js").read_text(encoding="utf-8")

        self.assertIn("waiting_identity_binding", console_js)
        self.assertIn("需要重新绑定", console_js)
        self.assertIn("deliveryStatusText", console_js)

    def test_task_edit_preserves_wechat_group_stable_receiver_fields(self):
        console_js = (ROOT / "channel/web/static/js/console.js").read_text(encoding="utf-8")

        self.assertIn("action.receiver_kind = currentEditingTask.action.receiver_kind || '';", console_js)
        self.assertIn("action.stable_receiver = currentEditingTask.action.stable_receiver || '';", console_js)
        self.assertIn("action.runtime_receiver = currentEditingTask.action.runtime_receiver || '';", console_js)


if __name__ == "__main__":
    unittest.main()
