import tempfile
import time
import unittest
from pathlib import Path

from channel.wechat_group.wechat_group_archive import WechatGroupArchive
from channel.wechat_group.wechat_group_request_snapshot import (
    WechatGroupRequestSnapshotFactory,
)
from channel.wechat_group.wechat_group_rolling_summary import (
    WechatGroupRollingSummaryService,
    WechatGroupRollingSummaryStore,
)


class FakeDreamEngine:
    def __init__(self, response="已压缩的群聊背景", error=None):
        self.response = response
        self.error = error
        self.calls = []

    def complete(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


class WechatGroupRollingSummaryTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        self.archive = WechatGroupArchive(str(root / "archive.db"))
        self.store = WechatGroupRollingSummaryStore(str(root / "summary.db"))
        self.now = int(time.time())

    def tearDown(self):
        self.tempdir.cleanup()

    def _record_events(self, start, count):
        for index in range(start, start + count):
            self.archive.record_message(
                "msg-{}".format(index),
                "wgr_room",
                sender_nickname="成员{}".format(index % 3),
                text="第{}条事实 token=secret{}".format(index, index),
                created_at=self.now + index,
                stable_room_id="wgr_room",
                stable_member_id="member-{}".format(index % 3),
            )

    def test_refresh_advances_dual_cursor_and_keeps_raw_tail(self):
        self._record_events(0, 20)
        engine = FakeDreamEngine()
        service = WechatGroupRollingSummaryService(
            self.archive,
            store=self.store,
            dream_engine=engine,
            retain_tail=12,
        )

        result = service.refresh_room("wgr_room")
        state = self.store.get("wgr_room")
        remaining = service.timeline_service.events_after_revision(
            "wgr_room",
            state.revision,
        )

        self.assertEqual("updated", result["status"])
        self.assertEqual(8, state.summarized_event_count)
        self.assertEqual(12, len(remaining))
        self.assertEqual(8, state.revision.inbound_cursor)
        self.assertEqual(0, state.revision.assistant_cursor)
        self.assertNotIn("secret0", engine.calls[0]["user_prompt"])
        self.assertIn("token=[redacted]", engine.calls[0]["user_prompt"])

    def test_model_failure_does_not_advance_cursor_or_replace_summary(self):
        self._record_events(0, 20)
        service = WechatGroupRollingSummaryService(
            self.archive,
            store=self.store,
            dream_engine=FakeDreamEngine("第一版摘要"),
            retain_tail=12,
        )
        service.refresh_room("wgr_room")
        before = self.store.get("wgr_room")
        self._record_events(20, 13)
        service.dream_engine = FakeDreamEngine(error=RuntimeError("503 unavailable"))

        with self.assertRaises(RuntimeError):
            service.refresh_room("wgr_room")

        after = self.store.get("wgr_room")
        self.assertEqual(before.summary, after.summary)
        self.assertEqual(before.revision, after.revision)
        self.assertEqual(before.summarized_event_count, after.summarized_event_count)

    def test_summary_revision_excludes_summarized_events_from_recent(self):
        self._record_events(0, 20)
        service = WechatGroupRollingSummaryService(
            self.archive,
            store=self.store,
            dream_engine=FakeDreamEngine(),
            retain_tail=12,
        )
        service.refresh_room("wgr_room")
        block, revision = service.get_prompt_context("wgr_room")
        message = type("Message", (), {
            "msg_id": "current",
            "create_time": self.now + 30,
            "message_type": "text",
            "is_quote_self": True,
            "wechat_group_stable_room_id": "wgr_room",
            "wechat_group_stable_member_id": "member-0",
            "other_user_id": "runtime-room",
            "actual_user_id": "runtime-member",
        })()
        snapshot = WechatGroupRequestSnapshotFactory(self.archive).build(
            message,
            "继续刚才",
            trigger_source="quote_self",
            is_free_reply=False,
        )
        recent = snapshot.recent_block(after_revision=revision)

        self.assertIn("wechat-group-rolling-summary", block)
        self.assertNotIn("第0条事实", recent)
        self.assertIn("第19条事实", recent)
        self.assertEqual(12, recent.count("[text]"))


if __name__ == "__main__":
    unittest.main()
