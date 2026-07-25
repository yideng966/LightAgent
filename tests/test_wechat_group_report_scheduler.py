import os
import tempfile
import unittest

from channel.wechat_group.wechat_group_report_scheduler import (
    WechatGroupReportScheduler,
    report_task_id,
)
from channel.wechat_group.wechat_group_report_store import WechatGroupReportStore


class _IdentityService:
    def get_active_runtime_room_id(self, stable_room_id):
        return "room@@runtime" if stable_room_id == "wgr_room" else ""


class _TaskStore:
    def __init__(self):
        self.tasks = []

    def upsert_task(self, task):
        self.tasks.append(task)
        return task


class WechatGroupReportSchedulerTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.store = WechatGroupReportStore(os.path.join(self.tempdir.name, "reports.db"))
        settings = self.store.get_settings("wgr_room")
        settings["enabled"] = True
        settings["schedules"]["daily"] = {"enabled": True, "send_time": "08:30"}
        self.settings = self.store.save_settings("wgr_room", settings, expected_version=0)
        self.task_store = _TaskStore()
        self.scheduler = WechatGroupReportScheduler(
            store=self.store,
            identity_service=_IdentityService(),
            task_store=self.task_store,
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def test_reconcile_upserts_all_stable_scope_tasks(self):
        result = self.scheduler.reconcile("wgr_room", self.settings)

        self.assertEqual("synced", result["status"])
        self.assertEqual(3, len(self.task_store.tasks))
        daily = self.task_store.tasks[0]
        self.assertEqual(report_task_id("wgr_room", "daily"), daily["id"])
        self.assertTrue(daily["enabled"])
        self.assertEqual("30 8 * * *", daily["schedule"]["expression"])
        self.assertEqual("Asia/Shanghai", daily["schedule"]["timezone"])
        self.assertEqual("wgr_room", daily["action"]["stable_receiver"])
        self.assertEqual("room@@runtime", daily["action"]["runtime_receiver"])
        self.assertFalse(self.task_store.tasks[1]["enabled"])
        self.assertFalse(self.task_store.tasks[2]["enabled"])

    def test_report_task_id_rejects_invalid_type(self):
        with self.assertRaises(ValueError):
            report_task_id("wgr_room", "custom")


if __name__ == "__main__":
    unittest.main()
