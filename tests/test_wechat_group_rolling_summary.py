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
from channel.wechat_group.wechat_group_timeline_service import RoomRevision


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
                created_at=self.now - 100 + index,
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

    def test_summary_rebuild_uses_all_room_members_and_drops_expired_events(self):
        self.archive.record_message(
            "expired",
            "wgr_room",
            sender_nickname="过期成员",
            text="两天前的旧事实",
            created_at=self.now - 25 * 60 * 60,
            stable_room_id="wgr_room",
            stable_member_id="member-expired",
        )
        self._record_events(0, 20)
        engine = FakeDreamEngine()
        service = WechatGroupRollingSummaryService(
            self.archive,
            store=self.store,
            dream_engine=engine,
            retain_tail=12,
        )

        result = service.refresh_room("wgr_room", now=self.now)
        prompt = engine.calls[0]["user_prompt"]

        self.assertEqual("updated", result["status"])
        self.assertIn("成员0", prompt)
        self.assertIn("成员1", prompt)
        self.assertIn("成员2", prompt)
        self.assertNotIn("两天前的旧事实", prompt)
        self.assertEqual(self.now - 24 * 60 * 60, result["window_start_at"])
        self.assertEqual(self.now, result["window_end_at"])

    def test_rebuild_does_not_merge_previous_summary_text(self):
        self._record_events(0, 20)
        engine = FakeDreamEngine("第一版摘要中的旧内容")
        service = WechatGroupRollingSummaryService(
            self.archive,
            store=self.store,
            dream_engine=engine,
            retain_tail=12,
        )
        service.refresh_room("wgr_room", now=self.now)
        self.archive.record_message(
            "new-message",
            "wgr_room",
            sender_nickname="新成员",
            text="新的群聊事实",
            created_at=self.now + 1,
            stable_room_id="wgr_room",
            stable_member_id="member-new",
        )
        engine.response = "第二版摘要"

        service.refresh_room("wgr_room", now=self.now + 1)

        self.assertNotIn("第一版摘要中的旧内容", engine.calls[-1]["user_prompt"])

    def test_summary_source_ids_survive_store_reopen_and_expire_when_stale(self):
        self._record_events(0, 20)
        service = WechatGroupRollingSummaryService(
            self.archive,
            store=self.store,
            dream_engine=FakeDreamEngine(),
            retain_tail=12,
        )

        service.refresh_room("wgr_room", now=self.now)
        state = self.store.get("wgr_room")
        reopened = WechatGroupRollingSummaryStore(self.store.db_path).get("wgr_room")

        self.assertEqual(8, len(state.source_event_ids))
        self.assertEqual(state.source_event_ids, reopened.source_event_ids)
        self.assertEqual(
            tuple("inbound:{}".format(index) for index in range(1, 9)),
            reopened.source_event_ids,
        )
        block, fresh = service.get_prompt_context_state(
            "wgr_room",
            now=state.updated_at + 3600,
        )
        self.assertIn("wechat-group-rolling-summary", block)
        self.assertIsNotNone(fresh)
        stale_block, stale = service.get_prompt_context_state(
            "wgr_room",
            now=state.updated_at + 3601,
        )
        self.assertEqual("", stale_block)
        self.assertIsNone(stale)

    def test_summary_with_assistant_sources_is_not_injected(self):
        self.store.save(
            "wgr_room",
            "包含旧机器人回复的摘要",
            RoomRevision(inbound_cursor=3, assistant_cursor=2),
            summarized_event_count=5,
            source_event_ids=["inbound:1", "assistant:2"],
        )
        service = WechatGroupRollingSummaryService(
            self.archive,
            store=self.store,
            dream_engine=FakeDreamEngine(),
        )

        block, state = service.get_prompt_context_state("wgr_room")

        self.assertEqual("", block)
        self.assertIsNone(state)

    def test_refresh_excludes_assistant_replies_from_summary_input(self):
        self._record_events(0, 20)
        self.archive.record_assistant_reply(
            "wgr_room",
            content="INTERNAL_ASSISTANT_TEXT_MUST_NOT_BE_SUMMARIZED",
            created_at=self.now - 95,
            stable_room_id="wgr_room",
        )
        engine = FakeDreamEngine()
        service = WechatGroupRollingSummaryService(
            self.archive,
            store=self.store,
            dream_engine=engine,
            retain_tail=12,
        )

        result = service.refresh_room("wgr_room", now=self.now)

        self.assertEqual("updated", result["status"])
        self.assertNotIn(
            "INTERNAL_ASSISTANT_TEXT_MUST_NOT_BE_SUMMARIZED",
            engine.calls[0]["user_prompt"],
        )
        self.assertEqual(0, result["revision"]["assistant_cursor"])


if __name__ == "__main__":
    unittest.main()
