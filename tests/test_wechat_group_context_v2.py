import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from agent.memory.conversation_store import ConversationStore
from channel.wechat_group.wechat_group_archive import WechatGroupArchive
from channel.wechat_group.wechat_group_context_policy import WechatGroupContextPolicy
from channel.wechat_group.wechat_group_humanized_context import (
    WechatGroupHumanizedContextBuilder,
)
from channel.wechat_group.wechat_group_request_snapshot import (
    WechatGroupRequestSnapshotFactory,
)
from config import conf


def make_message(now, message_id="current"):
    return SimpleNamespace(
        msg_id=message_id,
        create_time=now,
        message_type="text",
        text="这个怎么算",
        content="这个怎么算",
        is_at=True,
        is_quote_self=False,
        quote={},
        at_list=[],
        actual_user_id="runtime-alice",
        actual_user_nickname="Alice",
        other_user_id="runtime-room",
        other_user_nickname="Test Room",
        to_user_id="runtime-bot",
        self_display_name="LightAgent",
        wechat_group_stable_room_id="wgr_room",
        wechat_group_stable_member_id="wgm_alice",
        wechat_group_identity_requires_confirmation=False,
    )


class WechatGroupContextV2Test(unittest.TestCase):
    def setUp(self):
        self.original = {
            key: conf().get(key)
            for key in (
                "wechat_group_context_engine_mode",
                "wechat_group_recent_context_enabled",
                "wechat_group_archive_evidence_enabled",
                "wechat_group_local_summary_enabled",
                "wechat_group_reply_policy_enabled",
                "wechat_group_reference_policy_enabled",
                "wechat_group_link_policy_enabled",
            )
        }
        conf()["wechat_group_context_engine_mode"] = "v2"
        conf()["wechat_group_recent_context_enabled"] = True
        conf()["wechat_group_archive_evidence_enabled"] = True
        conf()["wechat_group_local_summary_enabled"] = True
        self.tempdir = tempfile.TemporaryDirectory()
        self.archive = WechatGroupArchive(
            str(Path(self.tempdir.name) / "archive.db")
        )
        self.store = ConversationStore(Path(self.tempdir.name) / "conversations.db")
        self.now = int(time.time())
        self.archive.record_message(
            "msg-1",
            "wgr_room",
            sender_nickname="Bob",
            text="月卡按自然月计算",
            created_at=self.now - 30,
            stable_room_id="wgr_room",
            stable_member_id="wgm_bob",
        )
        self.archive.record_assistant_reply(
            "wgr_room",
            content="我刚才回答过一次",
            created_at=self.now - 20,
            stable_room_id="wgr_room",
            thread_id="wgt_old",
        )
        self.archive.record_message(
            "current",
            "wgr_room",
            sender_nickname="Alice",
            text="这个怎么算",
            created_at=self.now,
            stable_room_id="wgr_room",
            stable_member_id="wgm_alice",
        )

    def tearDown(self):
        self.tempdir.cleanup()
        for key, value in self.original.items():
            if value is None:
                conf().pop(key, None)
            else:
                conf()[key] = value

    def test_default_direct_request_uses_bounded_recent_snapshot(self):
        snapshot = WechatGroupRequestSnapshotFactory(
            self.archive,
            store=self.store,
        ).build(
            make_message(self.now),
            "这个怎么算",
            trigger_source="direct_reply",
            is_free_reply=False,
            owner_session_id="wechat_group:wgr_room:wgm_alice",
            thread_id="wgt_new",
            thread_action="new_thread",
        )

        block = snapshot.recent_block()
        self.assertEqual("recent", snapshot.context_policy.mode)
        self.assertIn("月卡按自然月计算", block)
        self.assertIn("我刚才回答过一次", block)
        self.assertNotIn("这个怎么算", block)
        self.assertIn('untrusted="true"', block)
        self.assertEqual(2, snapshot.diagnostics["timeline_event_count"])

    def test_resume_thread_excludes_events_already_in_agent_history(self):
        session_id = "wechat_group:wgr_room:wgm_alice"
        self.store.create_thread(session_id, "wgt_old")
        self.store.append_messages(
            session_id,
            [{
                "role": "assistant",
                "content": "我刚才回答过一次",
                "extras": {"source_event_id": "assistant:1"},
            }],
            channel_type="wechat_group",
            thread_id="wgt_old",
        )

        snapshot = WechatGroupRequestSnapshotFactory(
            self.archive,
            store=self.store,
        ).build(
            make_message(self.now),
            "继续刚才你说的",
            trigger_source="direct_reply",
            is_free_reply=False,
            owner_session_id=session_id,
            thread_id="wgt_old",
            thread_action="resume_thread",
        )

        self.assertNotIn("我刚才回答过一次", snapshot.recent_block())
        self.assertIn("月卡按自然月计算", snapshot.recent_block())
        self.assertEqual(1, snapshot.diagnostics["excluded_thread_event_count"])

    def test_context_policy_only_enables_archive_for_explicit_recall(self):
        policy = WechatGroupContextPolicy()
        recent = policy.resolve("这个怎么算", trigger_source="direct_reply")
        recall = policy.resolve("总结一下昨天谁说过这个")

        self.assertFalse(recent.include_archive_evidence)
        self.assertEqual("recall", recall.mode)
        self.assertTrue(recall.include_archive_evidence)

    def test_intent_route_can_select_minimal_context(self):
        decision = WechatGroupContextPolicy().resolve(
            "每天九点提醒我开会",
            trigger_source="direct_reply",
            required_context_mode="minimal",
        )

        self.assertEqual("minimal", decision.mode)
        self.assertEqual("intent_route", decision.reason)
        self.assertEqual(4, decision.recent_limit)

    def test_humanized_builder_uses_snapshot_and_disables_extract_summary(self):
        channel = SimpleNamespace(
            archive=self.archive,
            _build_memory_context_block=Mock(return_value=""),
            _build_style_context_block=Mock(return_value=""),
            _build_emotion_context_block=Mock(return_value=""),
            _build_multimodal_context=Mock(return_value={"block": "", "diagnostics": {}}),
            _resolve_focus_context=Mock(return_value={}),
            _build_focus_context_block=Mock(return_value=""),
            _infer_multimodal_trigger_source=Mock(return_value="direct_reply"),
        )
        context = {
            "wechat_group_owner_session_id": "wechat_group:wgr_room:wgm_alice",
            "wechat_group_thread_id": "wgt_new",
            "wechat_group_session_action": "new_thread",
        }

        result = WechatGroupHumanizedContextBuilder(channel).build(
            make_message(self.now),
            "这个怎么算",
            trigger_source="direct_reply",
            request_context=context,
        )

        self.assertIn("<recent-wechat-group-transcript", result.content)
        self.assertIn("月卡按自然月计算", result.content)
        self.assertNotIn("<local-extractive-summary>", result.content)
        self.assertNotIn("<wechat-group-archive-evidence>", result.content)
        self.assertEqual("recent", result.metadata["wechat_group_context_mode"])
        self.assertEqual(
            self.archive.get_room_revision("wgr_room"),
            result.metadata["wechat_group_room_revision_before"],
        )


if __name__ == "__main__":
    unittest.main()
