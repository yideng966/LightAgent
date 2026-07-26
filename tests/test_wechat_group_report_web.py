import json
import os
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from channel.wechat_group.wechat_group_report_preview_service import WechatGroupReportPreviewService
from channel.wechat_group.wechat_group_report_store import WechatGroupReportStore


ROOT = Path(__file__).resolve().parents[1]


def _payload():
    return {
        "room_name": "测试群", "report_type": "daily",
        "period_start": "2026-07-20T00:00:00+08:00",
        "period_end": "2026-07-21T00:00:00+08:00",
        "timezone": "Asia/Shanghai", "active_speaker_count": 1,
        "total_messages": 1, "top_speaker": {"display_name": "Alice", "message_count": 1},
        "topic_count": 0, "ranking": [], "topics": [], "highlights": [], "links": [],
        "archive_message_count": 1, "unresolved_message_count": 0,
        "generated_at": "2026-07-21T09:00:00+08:00",
    }


class _TextRenderer:
    def render_text(self, report, output):
        return {"parts": ["报告第一段", "报告第二段"]}


class _ArchiveStats:
    def get_archive_bounds(self, room_id):
        return {"message_count": 0, "first_created_at": 0, "last_created_at": 0}


class _Store:
    def get_settings(self, room_id):
        return {"version": 0, "enabled": False, "output": {"mode": "text"}}

    def get_room_overview(self, room_id):
        return {"latest_report": None, "latest_delivery": None}


class WechatGroupReportWebTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.store = WechatGroupReportStore(os.path.join(self.tempdir.name, "reports.db"))
        self.report = self.store.create_report(
            "wgr_room", "daily", "start", "end", 1, "1", _payload(), force_regenerate=False,
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def test_text_preview_is_asynchronous_and_room_scoped(self):
        service = WechatGroupReportPreviewService(store=self.store, renderer=_TextRenderer())
        service.submit(
            "preview-1", "job-1", "wgr_room", self.report, {"mode": "text"},
        )
        service.shutdown(wait=True)
        preview = service.get_status("preview-1", "wgr_room")

        self.assertEqual("text_ready", preview["state"])
        self.assertEqual(["报告第一段", "报告第二段"], preview["text_parts"])
        self.assertIsNone(service.get_status("preview-1", "wgr_other"))

    def test_public_preview_strips_stable_room_id_and_uses_asset_endpoint(self):
        from channel.web.web_channel import WechatGroupReportsHandler

        handler = WechatGroupReportsHandler()
        public = handler._public_preview({
            "preview_id": "preview-1", "job_id": "job-1", "report_id": "report-1",
            "stable_room_id": "wgr_room", "state": "ready", "actual_output": "image",
            "parts": [{"part_index": 0, "width": 941, "height": 300, "relative_path": "hidden.png"}],
        })

        self.assertNotIn("stable_room_id", public)
        self.assertNotIn("relative_path", public["parts"][0])
        self.assertIn("preview_id=preview-1", public["parts"][0]["asset_url"])
        self.assertIn("stable_room_id=wgr_room", public["parts"][0]["asset_url"])

    def test_settings_endpoint_requires_authentication_before_scoped_lookup(self):
        from channel.web.web_channel import WechatGroupReportsHandler

        handler = WechatGroupReportsHandler()
        params = types.SimpleNamespace(
            stable_room_id="wgr_room", runtime_room_id="", room_id="", job_id="",
            delivery_id="", preview_id="", part_index="", skill_name="",
        )
        with patch("channel.web.web_channel._require_auth") as require_auth, \
                patch("channel.web.web_channel.web.input", return_value=params), \
                patch.object(WechatGroupReportsHandler, "_selected_stable_room_id", return_value="wgr_room"), \
                patch.object(WechatGroupReportsHandler, "_get_store", return_value=_Store()), \
                patch.object(WechatGroupReportsHandler, "_statistics_service", return_value=_ArchiveStats()), \
                patch.object(WechatGroupReportsHandler, "_serialize_templates", return_value=[]), \
                patch.object(WechatGroupReportsHandler, "_connection_status", return_value={"ready": False, "status": "idle"}), \
                patch.object(WechatGroupReportsHandler, "_json", side_effect=lambda payload, status=200: json.dumps(payload)):
            result = json.loads(handler.GET("settings"))

        require_auth.assert_called_once()
        self.assertEqual("success", result["status"])
        self.assertEqual(0, result["settings"]["version"])

    def test_send_reuses_completed_preview_snapshot(self):
        from channel.web.web_channel import WechatGroupReportsHandler

        class PreviewService:
            def get_status(self, preview_id, room_id):
                self.preview_id = preview_id
                self.room_id = room_id
                return {
                    "preview_id": preview_id,
                    "report_id": self_report_id,
                    "state": "text_ready",
                    "actual_output": "text",
                    "output_settings": {"mode": "image_preferred", "builtin_text_template_id": "compact_text"},
                }

        class Store:
            def consume_send_confirmation(self, token, report_id, room_id):
                self.called = (token, report_id, room_id)
                return True

        class DeliveryService:
            def __init__(self):
                self.created = None
                self.submitted = None

            def create_delivery(self, report_id, room_id, actor, output_settings, confirmation_token):
                self.created = (report_id, room_id, actor, output_settings, confirmation_token)
                return {"delivery_id": "delivery-1"}

            def submit_delivery(self, delivery_id, room_id):
                self.submitted = (delivery_id, room_id)

        self_report_id = self.report["report_id"]
        preview_service = PreviewService()
        store = Store()
        delivery_service = DeliveryService()
        handler = WechatGroupReportsHandler()
        body = {
            "report_id": self_report_id,
            "preview_id": "preview-1",
            "confirmation_token": "confirm-1",
            "draft_settings": {"output": {"mode": "image"}},
        }
        with patch.object(WechatGroupReportsHandler, "_get_preview_service", return_value=preview_service), \
                patch.object(WechatGroupReportsHandler, "_get_store", return_value=store), \
                patch.object(WechatGroupReportsHandler, "_connection_status", return_value={"ready": True, "status": "connected"}), \
                patch("agent.tools.scheduler.integration.get_wechat_group_report_runtime", return_value=(None, delivery_service)), \
                patch.object(handler, "_json", side_effect=lambda payload, status=200: payload):
            result = handler._send("wgr_room", body)

        self.assertEqual("accepted", result["status"])
        self.assertEqual(("confirm-1", self_report_id, "wgr_room"), store.called)
        self.assertEqual("text", delivery_service.created[3]["mode"])
        self.assertEqual("compact_text", delivery_service.created[3]["builtin_text_template_id"])
        self.assertEqual("preview-1", delivery_service.created[3]["_source_preview_id"])
        self.assertEqual(("delivery-1", "wgr_room"), delivery_service.submitted)

    def test_console_report_ui_keeps_scroll_and_selects_builtin_text_templates(self):
        console_js = (ROOT / "channel/web/static/js/console.js").read_text(encoding="utf-8")
        render_start = console_js.index("function renderGroupsReportView")
        render_end = console_js.index("function syncGroupsPrimarySaveButton", render_start)
        render_block = console_js[render_start:render_end]
        send_start = console_js.index("function sendGroupsReport()")
        send_end = console_js.index("function pollGroupsReportDelivery", send_start)
        send_block = console_js[send_start:send_end]
        manual_start = console_js.index("function buildGroupsReportManualPanel")
        manual_end = console_js.index("function changeGroupsReportPeriod", manual_start)
        manual_block = console_js[manual_start:manual_end]

        self.assertIn("renderGroupsView({ preserveScroll: true })", render_block)
        self.assertIn('id="groups-report-builtin-text-template"', console_js)
        self.assertIn("compact_text", console_js)
        self.assertIn("preview_id: previewId", send_block)
        self.assertNotIn("draft_settings", send_block)
        self.assertIn("const offline = groupsReportState.connection?.ready === false", manual_block)
        self.assertIn("${previewReady ? '' : 'disabled'}", manual_block)


if __name__ == "__main__":
    unittest.main()
