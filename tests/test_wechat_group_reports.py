import os
import tempfile
import unittest
from unittest.mock import patch

from channel.wechat_group.wechat_group_report_store import (
    ReportVersionConflict,
    WechatGroupReportStore,
    normalize_report_settings,
)


def _payload():
    return {
        "room_name": "测试群",
        "report_type": "daily",
        "period_start": "2026-07-20T00:00:00+08:00",
        "period_end": "2026-07-21T00:00:00+08:00",
        "timezone": "Asia/Shanghai",
        "active_speaker_count": 1,
        "total_messages": 1,
        "top_speaker": {"display_name": "Alice", "message_count": 1},
        "topic_count": 0,
        "ranking": [],
        "topics": [],
        "highlights": [],
        "links": [],
        "archive_message_count": 1,
        "unresolved_message_count": 0,
        "generated_at": "2026-07-21T09:00:00+08:00",
    }


class WechatGroupReportStoreTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.store = WechatGroupReportStore(os.path.join(self.tempdir.name, "reports.db"))

    def tearDown(self):
        self.tempdir.cleanup()

    def test_settings_use_optimistic_lock_and_validate_schema(self):
        settings = self.store.get_settings("wgr_room")
        saved = self.store.save_settings("wgr_room", settings, expected_version=0, actor="test")

        self.assertEqual(1, saved["version"])
        with self.assertRaises(ReportVersionConflict):
            self.store.save_settings("wgr_room", settings, expected_version=0)
        with self.assertRaisesRegex(ValueError, "unsupported report settings schema version"):
            normalize_report_settings({"schema_version": 2})
        with self.assertRaisesRegex(ValueError, "invalid report timezone"):
            normalize_report_settings({"timezone": "Invalid/Timezone"})

    def test_ready_revision_is_immutable_and_force_creates_new_revision(self):
        first = self.store.create_report(
            "wgr_room", "daily", "start", "end", 9, "1", _payload(), force_regenerate=False,
        )
        reusable = self.store.create_report(
            "wgr_room", "daily", "start", "end", 9, "1", {"room_name": "changed"}, force_regenerate=False,
        )
        refreshed = self.store.create_report(
            "wgr_room", "daily", "start", "end", 9, "1", _payload(), force_regenerate=True,
        )

        self.assertEqual(first["report_id"], reusable["report_id"])
        self.assertEqual(1, first["revision"])
        self.assertEqual(2, refreshed["revision"])
        self.assertEqual(first["report_id"], refreshed["supersedes_report_id"])

    def test_preview_assets_are_scoped_to_their_stable_room(self):
        report = self.store.create_report(
            "wgr_room", "daily", "start", "end", 1, "1", _payload(), force_regenerate=False,
        )
        self.store.create_preview(
            "preview-1", "job-1", report["report_id"], "wgr_room", {"mode": "image"},
        )
        self.store.replace_preview_parts(
            "preview-1", "wgr_room", [{
                "relative_path": "images/wechat_group_reports/preview.png", "width": 941, "height": 100,
            }],
        )
        self.store.update_preview("preview-1", "wgr_room", state="ready", actual_output="image")

        self.assertEqual(
            "images/wechat_group_reports/preview.png",
            self.store.get_preview_asset_path("preview-1", "wgr_room", 0),
        )
        self.assertIsNone(self.store.get_preview("preview-1", "wgr_other"))
        self.assertEqual("", self.store.get_preview_asset_path("preview-1", "wgr_other", 0))

    def test_group_tool_queues_current_scope_delivery_after_generation(self):
        from channel.wechat_group.wechat_group_report_tools import WechatGroupReportTool

        class FakeRunner:
            def __init__(self):
                self.store = self
                self.submit_args = None

            def get_settings(self, room_id):
                return {"enabled": True, "output": {"mode": "text"}}

            def submit_generation(self, **kwargs):
                self.submit_args = kwargs
                kwargs["ready_callback"]({"report_id": "report-1"}, {"job_id": "job-1"})
                return {"job_id": "job-1", "state": "queued"}

        class FakeDelivery:
            def __init__(self):
                self.created = []
                self.submitted = []

            def create_delivery(self, **kwargs):
                self.created.append(kwargs)
                return {"delivery_id": "delivery-1"}

            def submit_delivery(self, delivery_id, stable_room_id):
                self.submitted.append((delivery_id, stable_room_id))

        runner = FakeRunner()
        delivery = FakeDelivery()
        tool = WechatGroupReportTool("wgr_room", "wgm_admin")
        with patch(
            "channel.wechat_group.wechat_group_report_tools.can_generate_wechat_group_report",
            return_value=(True, ""),
        ), patch(
            "agent.tools.scheduler.integration.get_wechat_group_report_runtime",
            return_value=(runner, delivery),
        ):
            result = tool.execute({"action": "generate", "report_type": "daily"})

        self.assertEqual("success", result.status)
        self.assertEqual("wgr_room", runner.submit_args["stable_room_id"])
        self.assertEqual("group_member", delivery.created[0]["actor"])
        self.assertEqual([("delivery-1", "wgr_room")], delivery.submitted)


if __name__ == "__main__":
    unittest.main()
