import os
import tempfile
import threading
import unittest

from channel.wechat_group.wechat_group_client import WechatGroupClient
from channel.wechat_group.wechat_group_report_delivery_service import WechatGroupReportDeliveryService
from channel.wechat_group.wechat_group_report_store import WechatGroupReportStore


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
        "ranking": [], "topics": [], "highlights": [], "links": [],
        "archive_message_count": 1, "unresolved_message_count": 0,
        "generated_at": "2026-07-21T09:00:00+08:00",
    }


class _IdentityService:
    def get_active_runtime_room_id(self, stable_room_id):
        return "room@@runtime" if stable_room_id == "wgr_room" else ""


class _Client:
    def __init__(self, text_status="sent", image_status="sent"):
        self.text_status = text_status
        self.image_status = image_status
        self.text_calls = []
        self.image_calls = []

    def send_text_confirmed(self, room_id, text, mention_ids=None):
        self.text_calls.append((room_id, text, mention_ids or []))
        return self.text_status

    def send_image_confirmed(self, room_id, path):
        self.image_calls.append((room_id, path))
        return self.image_status


class _Channel:
    def __init__(self, client):
        self.client = client
        self.identity_service = _IdentityService()


class _Renderer:
    def __init__(self, image_error=None):
        self.image_error = image_error

    def render_images(self, report, output, report_id):
        if self.image_error:
            raise self.image_error
        return {"template_id": "test", "template_version": "1", "parts": []}

    def render_text(self, report, output):
        return {"parts": ["第一段", "第二段"]}

    def asset_absolute_path(self, relative_path):
        return __file__


class WechatGroupReportDeliveryTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.store = WechatGroupReportStore(os.path.join(self.tempdir.name, "reports.db"))
        self.report = self.store.create_report(
            "wgr_room", "daily", "start", "end", 1, "1", _payload(), force_regenerate=False,
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def _delivery_service(self, renderer, client):
        return WechatGroupReportDeliveryService(
            store=self.store,
            renderer=renderer,
            identity_service=_IdentityService(),
            channel_getter=lambda: _Channel(client),
        )

    def test_image_preferred_falls_back_when_rendering_failure_is_determinate(self):
        client = _Client()
        service = self._delivery_service(_Renderer(image_error=ValueError("broken template")), client)
        delivery = service.create_delivery(
            self.report["report_id"], "wgr_room", "test", {"mode": "image_preferred"},
        )

        service._process_delivery(delivery["delivery_id"], "wgr_room", retry_only=False)
        status = service.get_status(delivery["delivery_id"], "wgr_room")

        self.assertEqual("fallback_sent", status["state"])
        self.assertEqual("text", status["actual_output"])
        self.assertEqual(2, len(status["parts"]))
        self.assertEqual(2, len(client.text_calls))

    def test_image_only_does_not_send_text_when_rendering_fails(self):
        client = _Client()
        service = self._delivery_service(_Renderer(image_error=ValueError("broken template")), client)
        delivery = service.create_delivery(
            self.report["report_id"], "wgr_room", "test", {"mode": "image"},
        )

        service._process_delivery(delivery["delivery_id"], "wgr_room", retry_only=False)
        status = service.get_status(delivery["delivery_id"], "wgr_room")

        self.assertEqual("failed", status["state"])
        self.assertEqual([], client.text_calls)

    def test_unknown_text_result_does_not_retry_as_fallback(self):
        client = _Client(text_status="unknown")
        service = self._delivery_service(_Renderer(), client)
        delivery = service.create_delivery(
            self.report["report_id"], "wgr_room", "test", {"mode": "text"},
        )

        service._process_delivery(delivery["delivery_id"], "wgr_room", retry_only=False)
        status = service.get_status(delivery["delivery_id"], "wgr_room")

        self.assertEqual("delivery_unknown", status["state"])
        self.assertEqual("unknown", status["parts"][0]["state"])

    def test_delivery_reuses_completed_text_preview(self):
        client = _Client()
        service = self._delivery_service(_Renderer(), client)
        self.store.create_preview(
            "preview-1", "job-1", self.report["report_id"], "wgr_room", {"mode": "text"},
        )
        self.store.update_preview(
            "preview-1", "wgr_room", state="text_ready", actual_output="text",
            text_parts=["预览第一段", "预览第二段"],
        )
        delivery = service.create_delivery(
            self.report["report_id"], "wgr_room", "test",
            {"mode": "text", "_source_preview_id": "preview-1"},
        )

        service._process_delivery(delivery["delivery_id"], "wgr_room", retry_only=False)
        status = service.get_status(delivery["delivery_id"], "wgr_room")

        self.assertEqual("sent", status["state"])
        self.assertEqual(["预览第一段", "预览第二段"], [call[1] for call in client.text_calls])

    def test_delivery_keeps_completed_image_preview_without_unpreviewed_text_fallback(self):
        client = _Client(image_status="failed")
        renderer = _Renderer(image_error=ValueError("preview must be reused"))
        service = self._delivery_service(renderer, client)
        self.store.create_preview(
            "preview-image", "job-1", self.report["report_id"], "wgr_room", {"mode": "image_preferred"},
        )
        self.store.update_preview(
            "preview-image", "wgr_room", state="ready", actual_output="image",
        )
        self.store.replace_preview_parts(
            "preview-image", "wgr_room", [{"relative_path": "preview.png", "width": 941, "height": 200}],
        )
        delivery = service.create_delivery(
            self.report["report_id"], "wgr_room", "test",
            {"mode": "image_preferred", "_source_preview_id": "preview-image"},
        )

        service._process_delivery(delivery["delivery_id"], "wgr_room", retry_only=False)
        status = service.get_status(delivery["delivery_id"], "wgr_room")

        self.assertEqual("failed", status["state"])
        self.assertEqual([], client.text_calls)
        self.assertEqual(1, len(client.image_calls))

    def test_confirmed_client_correlates_only_its_request_id(self):
        client = WechatGroupClient()
        commands = []

        def send_command(command):
            commands.append(command)
            request_id = command.payload["request_id"]
            threading.Timer(
                0.01,
                lambda: client.consume_send_result({"request_id": request_id, "ok": True}),
            ).start()

        client.send_command = send_command
        self.assertFalse(client.consume_send_result({"request_id": "late", "ok": True}))

        result = client.send_text_confirmed("room@@runtime", "报告第一段", timeout=1)

        self.assertEqual("sent", result)
        self.assertEqual("send_text", commands[0].type)
        self.assertTrue(commands[0].payload["request_id"])
        self.assertFalse(client.consume_send_result({"request_id": commands[0].payload["request_id"], "ok": True}))


if __name__ == "__main__":
    unittest.main()
