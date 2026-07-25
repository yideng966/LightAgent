import os
import tempfile
import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from channel.wechat_group.wechat_group_archive import WechatGroupArchive
from channel.wechat_group.wechat_group_statistics_service import WechatGroupStatisticsService


class _IdentityStore:
    def get_member(self, member_id):
        return {"display_name": ""}

    def get_room(self, room_id):
        return {"canonical_name": "稳定测试群"}


class _IdentityService:
    def __init__(self):
        self.store = _IdentityStore()

    def list_confirmed_room_scope_ids(self, stable_room_id):
        return ["room@@legacy"]

    def resolve_canonical_member_id(self, stable_room_id, stable_member_id):
        return {"wgm_old": "wgm_alice"}.get(stable_member_id, stable_member_id)


class WechatGroupStatisticsTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.archive = WechatGroupArchive(os.path.join(self.tempdir.name, "archive.db"))
        self.zone = ZoneInfo("Asia/Shanghai")
        self.start = datetime(2026, 7, 20, tzinfo=self.zone)
        self.end = self.start + timedelta(days=1)
        self.service = WechatGroupStatisticsService(
            archive=self.archive,
            identity_service=_IdentityService(),
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def _record(self, message_id, created_at, **kwargs):
        self.archive.record_message(
            message_id=message_id,
            room_id=kwargs.pop("room_id", "room@@current"),
            room_name="旧群名",
            sender_id=kwargs.pop("sender_id", "sender"),
            sender_nickname=kwargs.pop("sender_nickname", "Alice"),
            stable_room_id=kwargs.pop("stable_room_id", "wgr_room"),
            runtime_room_id=kwargs.pop("runtime_room_id", "room@@current"),
            stable_member_id=kwargs.pop("stable_member_id", "wgm_alice"),
            runtime_sender_id=kwargs.pop("runtime_sender_id", "sender"),
            created_at=int(created_at.timestamp()),
            text=kwargs.pop("text", "消息"),
            **kwargs,
        )

    def test_base_report_keeps_stable_scope_and_merges_renamed_members(self):
        self._record(
            "m1", self.start, stable_member_id="wgm_old", sender_nickname="旧昵称",
            text="看看 https://example.com/a#fragment",
        )
        self._record("m2", self.start + timedelta(minutes=5), sender_nickname="新昵称")
        self._record(
            "m3", self.start + timedelta(minutes=10), room_id="room@@legacy",
            stable_room_id="", runtime_room_id="room@@legacy", stable_member_id="wgm_bob",
            sender_nickname="Bob", text="legacy message",
        )
        self._record(
            "collision", self.start + timedelta(minutes=15), room_id="room@@legacy",
            stable_room_id="wgr_other", stable_member_id="wgm_other", sender_nickname="Other",
        )
        self._record("at-end", self.end, stable_member_id="wgm_late")
        self._record(
            "bot", self.start + timedelta(minutes=20), stable_member_id="wgm_bot",
            runtime_sender_id="bot", metadata={"self_id": "bot"}, sender_nickname="机器人",
        )

        report = self.service.build_base_report(
            "wgr_room", "custom", self.start, self.end, timezone_name="Asia/Shanghai",
        )

        self.assertEqual("稳定测试群", report["room_name"])
        self.assertEqual(3, report["total_messages"])
        self.assertEqual(2, report["active_speaker_count"])
        self.assertEqual("新昵称", report["top_speaker"]["display_name"])
        self.assertEqual(2, report["top_speaker"]["message_count"])
        self.assertEqual("https://example.com/a", report["links"][0]["url"])
        self.assertEqual(["新昵称"], report["links"][0]["provider_display_names"])
        self.assertEqual(0, report["unresolved_message_count"])

    def test_archive_page_does_not_use_runtime_alias_without_confirmation(self):
        self._record("stable", self.start)
        self._record(
            "legacy", self.start + timedelta(minutes=1), room_id="room@@legacy",
            stable_room_id="", runtime_room_id="room@@legacy", stable_member_id="wgm_bob",
        )

        rows = self.archive.get_report_messages_page(
            "wgr_room", int(self.start.timestamp()), int(self.end.timestamp()), legacy_room_ids=[],
        )

        self.assertEqual(["stable"], [row["message_id"] for row in rows])

    def test_weekly_period_uses_previous_natural_week(self):
        now = datetime(2026, 7, 22, 16, 30, tzinfo=self.zone)
        start, end = self.service.resolve_period("weekly", now=now)

        self.assertEqual(datetime(2026, 7, 13, tzinfo=self.zone), start)
        self.assertEqual(datetime(2026, 7, 20, tzinfo=self.zone), end)


if __name__ == "__main__":
    unittest.main()
