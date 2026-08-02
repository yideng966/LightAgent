import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch


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

    def test_task_edit_supports_wechat_group_target_selection(self):
        chat_html = (ROOT / "channel/web/chat.html").read_text(encoding="utf-8")
        console_js = (ROOT / "channel/web/static/js/console.js").read_text(encoding="utf-8")

        self.assertIn('id="task-edit-target-group-wrap"', chat_html)
        self.assertIn('id="task-edit-target-group"', chat_html)
        self.assertIn("function populateTaskWechatGroupTargets", console_js)
        self.assertIn("const isWechatGroupTask = channelType === 'wechat_group';", console_js)
        self.assertIn("extra.stable_selected_room_ids", console_js)
        self.assertIn("action.stable_receiver = stableReceiver;", console_js)
        self.assertIn("action.notify_session_id = `wechat_group:${stableReceiver}`;", console_js)

    def test_scheduler_update_accepts_stable_wechat_group_without_runtime_snapshot(self):
        from agent.tools.scheduler.task_store import TaskStore
        from channel.web import web_channel

        with tempfile.TemporaryDirectory() as workspace:
            store_path = Path(workspace) / "scheduler" / "tasks.json"
            store = TaskStore(str(store_path))
            store.add_task({
                "id": "task-room",
                "name": "群提醒",
                "enabled": True,
                "schedule": {"type": "interval", "seconds": 3600},
                "action": {
                    "type": "send_message",
                    "content": "提醒内容",
                    "channel_type": "wechat_group",
                    "receiver": "room@@old",
                    "receiver_kind": "wechat_group",
                    "stable_receiver": "wgr_old",
                },
            })
            payload = {
                "task_id": "task-room",
                "action": {
                    "type": "send_message",
                    "content": "提醒内容",
                    "channel_type": "wechat_group",
                    "receiver": "",
                    "receiver_name": "新目标群",
                    "receiver_kind": "wechat_group",
                    "stable_receiver": "wgr_new",
                    "runtime_receiver": "",
                    "notify_session_id": "wechat_group:wgr_new",
                    "is_group": True,
                },
            }
            with patch.object(web_channel, "_require_auth"), \
                    patch.object(web_channel, "_get_workspace_root", return_value=workspace), \
                    patch.object(web_channel, "conf", return_value={"wechat_group_stable_room_ids": ["wgr_new"]}), \
                    patch.object(web_channel.web, "header"), \
                    patch.object(web_channel.web, "data", return_value=json.dumps(payload).encode("utf-8")):
                result = json.loads(web_channel.SchedulerUpdateHandler().POST())

            self.assertEqual("success", result["status"])
            self.assertEqual("wgr_new", result["task"]["action"]["stable_receiver"])
            self.assertEqual("", result["task"]["action"]["runtime_receiver"])
            self.assertEqual("", result["task"]["delivery_status"])

            payload["action"]["stable_receiver"] = "wgr_unselected"
            with patch.object(web_channel, "_require_auth"), \
                    patch.object(web_channel, "_get_workspace_root", return_value=workspace), \
                    patch.object(web_channel, "conf", return_value={"wechat_group_stable_room_ids": ["wgr_new"]}), \
                    patch.object(web_channel.web, "header"), \
                    patch.object(web_channel.web, "data", return_value=json.dumps(payload).encode("utf-8")):
                rejected = json.loads(web_channel.SchedulerUpdateHandler().POST())

            self.assertEqual("error", rejected["status"])
            self.assertIn("not selected", rejected["message"])


if __name__ == "__main__":
    unittest.main()
