import os
import sqlite3
import tempfile
import types
import unittest

from channel.wechat_group.wechat_group_archive import WechatGroupArchive
from config import conf


WECHAT_IMAGE_TRANSPORT_XML = """<?xml version="1.0"?>
<msg>
  <img aeskey="masked" cdnthumburl="masked" md5="masked" hevc_mid_size="31347" />
</msg>
"""


class WechatGroupFocusServiceTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.focus_db_path = os.path.join(self._tmp.name, "wechat_group_focus.db")
        self.archive_db_path = os.path.join(self._tmp.name, "wechat_group_archive.db")
        self._original_config = {
            "wechat_group_focus_recent_message_limit": conf().get("wechat_group_focus_recent_message_limit"),
            "wechat_group_focus_context_message_limit": conf().get("wechat_group_focus_context_message_limit"),
            "wechat_group_focus_stack_depth": conf().get("wechat_group_focus_stack_depth"),
            "wechat_group_focus_stale_rounds": conf().get("wechat_group_focus_stale_rounds"),
            "wechat_group_focus_min_keywords": conf().get("wechat_group_focus_min_keywords"),
        }
        conf()["wechat_group_focus_recent_message_limit"] = 20
        conf()["wechat_group_focus_context_message_limit"] = 8
        conf()["wechat_group_focus_stack_depth"] = 4
        conf()["wechat_group_focus_stale_rounds"] = 20
        conf()["wechat_group_focus_min_keywords"] = 2

    def tearDown(self):
        for key, value in self._original_config.items():
            if value is None:
                conf().pop(key, None)
            else:
                conf()[key] = value
        self._tmp.cleanup()

    def _msg(self, message_id, text, created_at=200, quote=None, is_quote_self=False):
        return types.SimpleNamespace(
            msg_id=message_id,
            other_user_id="room@@abc",
            other_user_nickname="测试群",
            actual_user_id="wxid_alice",
            actual_user_nickname="Alice",
            to_user_id="wxid_bot",
            message_type="text",
            text=text,
            content=text.replace("@LightBot", "").strip(),
            media_path="",
            is_at=True,
            quote=quote or {},
            is_quote_self=is_quote_self,
            create_time=created_at,
        )

    def test_focus_store_discards_legacy_topic_database(self):
        legacy_path = os.path.join(self._tmp.name, "wechat_group_topics.db")
        conn = sqlite3.connect(legacy_path)
        conn.execute("CREATE TABLE wechat_group_topic_threads (thread_id TEXT PRIMARY KEY, room_id TEXT)")
        conn.execute("INSERT INTO wechat_group_topic_threads VALUES ('topic-1', 'room@@abc')")
        conn.commit()
        conn.close()

        from channel.wechat_group.wechat_group_focus_store import discard_legacy_topic_data

        discarded = discard_legacy_topic_data(data_root=self._tmp.name)

        self.assertTrue(discarded)
        self.assertFalse(os.path.exists(legacy_path))

    def test_focus_stack_is_scoped_by_room(self):
        from channel.wechat_group.wechat_group_focus_store import WechatGroupFocusStore

        store = WechatGroupFocusStore(self.focus_db_path)
        store.save_stack("room@@a", [{"frame_id": "fa", "topic": ["发布"], "depth": 0, "last_row_id": 1}])
        store.save_stack("room@@b", [{"frame_id": "fb", "topic": ["团建"], "depth": 0, "last_row_id": 2}])

        self.assertEqual(["发布"], store.load_stack("room@@a")[0]["topic"])
        self.assertEqual(["团建"], store.load_stack("room@@b")[0]["topic"])

    def test_standalone_at_does_not_include_old_focus_messages(self):
        from channel.wechat_group.wechat_group_focus_service import WechatGroupFocusService
        from channel.wechat_group.wechat_group_focus_store import WechatGroupFocusStore

        archive = WechatGroupArchive(self.archive_db_path)
        archive.record_message("msg-old-1", "room@@abc", "测试群", "wxid_a", "A", "text", "难受 她不爱我了", created_at=100)
        archive.record_message("msg-old-2", "room@@abc", "测试群", "wxid_b", "B", "text", "xx不爱你了吗", created_at=101)
        archive.record_message("msg-old-3", "room@@abc", "测试群", "wxid_b", "B", "image", "[截图]", media_path="D:/tmp/a.jpg", created_at=102)
        archive.record_message("msg-current", "room@@abc", "测试群", "wxid_b", "B", "text", "@LightBot 让gpt来帮忙了", is_at=True, created_at=200)

        service = WechatGroupFocusService(store=WechatGroupFocusStore(self.focus_db_path))
        focus = service.resolve_reply_focus(archive, self._msg("msg-current", "@LightBot 让gpt来帮忙了"), "让gpt来帮忙了", now=200)

        texts = "\n".join(row.get("text", "") for row in focus["messages"])
        self.assertEqual("standalone", focus["mode"])
        self.assertNotIn("她不爱我了", texts)
        self.assertNotIn("不爱你了吗", texts)
        self.assertIn("让gpt来帮忙了", texts)

    def test_summary_request_keeps_recent_room_messages(self):
        from channel.wechat_group.wechat_group_focus_service import WechatGroupFocusService
        from channel.wechat_group.wechat_group_focus_store import WechatGroupFocusStore

        archive = WechatGroupArchive(self.archive_db_path)
        archive.record_message("msg-1", "room@@abc", "测试群", "wxid_a", "Alice", "text", "发布窗口是周五晚上", created_at=100)
        archive.record_message("msg-2", "room@@abc", "测试群", "wxid_b", "Bob", "text", "回归还没过", created_at=101)
        archive.record_message("msg-current", "room@@abc", "测试群", "wxid_a", "Alice", "text", "@LightBot 总结刚才", is_at=True, created_at=200)

        service = WechatGroupFocusService(store=WechatGroupFocusStore(self.focus_db_path))
        focus = service.resolve_reply_focus(archive, self._msg("msg-current", "@LightBot 总结刚才"), "总结刚才", now=200)

        texts = "\n".join(row.get("text", "") for row in focus["messages"])
        self.assertEqual("contextual", focus["mode"])
        self.assertIn("发布窗口", texts)
        self.assertIn("回归还没过", texts)

    def test_focus_summary_projects_legacy_text_image_xml(self):
        from channel.wechat_group.wechat_group_focus_service import WechatGroupFocusService
        from channel.wechat_group.wechat_group_focus_store import WechatGroupFocusStore

        archive = WechatGroupArchive(self.archive_db_path)
        archive.record_message(
            "legacy-image-as-text",
            "room@@abc",
            "测试群",
            "wxid_a",
            "Alice",
            "text",
            WECHAT_IMAGE_TRANSPORT_XML,
            media_path="",
            created_at=100,
        )
        archive.record_message(
            "msg-current",
            "room@@abc",
            "测试群",
            "wxid_b",
            "Bob",
            "text",
            "@LightBot 总结刚才",
            is_at=True,
            created_at=200,
        )

        service = WechatGroupFocusService(store=WechatGroupFocusStore(self.focus_db_path))
        focus = service.resolve_reply_focus(
            archive,
            self._msg("msg-current", "@LightBot 总结刚才"),
            "总结刚才",
            now=200,
        )
        block = service.build_prompt_block(focus)

        self.assertIn("[image message legacy-image-as-text]", block)
        for transport_fragment in ("<?xml", "<img", "hevc_mid_size", "aeskey", "cdnthumburl"):
            self.assertNotIn(transport_fragment, block)

    def test_focus_prompt_sanitizes_legacy_transport_xml_summary(self):
        from channel.wechat_group.wechat_group_focus_service import WechatGroupFocusService
        from channel.wechat_group.wechat_group_focus_store import WechatGroupFocusStore

        service = WechatGroupFocusService(store=WechatGroupFocusStore(self.focus_db_path))

        block = service.build_prompt_block({
            "event": "kept",
            "mode": "contextual",
            "frame": {
                "title": WECHAT_IMAGE_TRANSPORT_XML,
                "summary": WECHAT_IMAGE_TRANSPORT_XML,
                "topic": ["xml", "img", "aeskey", "cdnthumburl", "hevc_mid_size"],
            },
            "messages": [],
        })

        self.assertIn("[media message]", block)
        for transport_fragment in ("<?xml", "<img", "hevc_mid_size", "aeskey", "cdnthumburl"):
            self.assertNotIn(transport_fragment, block)

    def test_focus_prompt_filters_transport_metadata_from_legacy_topic(self):
        from channel.wechat_group.wechat_group_focus_service import WechatGroupFocusService
        from channel.wechat_group.wechat_group_focus_store import WechatGroupFocusStore

        service = WechatGroupFocusService(store=WechatGroupFocusStore(self.focus_db_path))

        block = service.build_prompt_block({
            "event": "kept",
            "mode": "contextual",
            "frame": {
                "title": "release checklist",
                "summary": "release checklist is ready",
                "topic": ["release", "aeskey", "cdnthumburl", "hevc_mid_size"],
            },
            "messages": [],
        })

        self.assertIn("keywords: release", block)
        for transport_fragment in ("hevc_mid_size", "aeskey", "cdnthumburl"):
            self.assertNotIn(transport_fragment, block)

    def test_focus_prompt_omits_values_from_legacy_transport_topic(self):
        from channel.wechat_group.wechat_group_focus_service import WechatGroupFocusService
        from channel.wechat_group.wechat_group_focus_store import WechatGroupFocusStore

        service = WechatGroupFocusService(store=WechatGroupFocusStore(self.focus_db_path))

        block = service.build_prompt_block({
            "event": "kept",
            "mode": "contextual",
            "frame": {
                "title": "xmlversion",
                "summary": "[image message]",
                "topic": [
                    "xml",
                    "msg",
                    "img",
                    "aeskey",
                    "maskedvalue",
                    "cdnthumburl",
                    "beef",
                ],
            },
            "messages": [],
        })

        self.assertIn("current_focus: [media message]", block)
        self.assertNotIn("xmlversion", block)
        self.assertNotIn("keywords:", block)
        for transport_fragment in ("aeskey", "maskedvalue", "cdnthumburl", "beef"):
            self.assertNotIn(transport_fragment, block)

    def test_focus_uses_stable_room_after_runtime_room_changes(self):
        from channel.wechat_group.wechat_group_focus_service import WechatGroupFocusService
        from channel.wechat_group.wechat_group_focus_store import WechatGroupFocusStore

        archive = WechatGroupArchive(self.archive_db_path)
        archive.record_message(
            "msg-old-runtime",
            "room@@old",
            "Stable Room",
            "wxid_alice_old",
            "Alice",
            "text",
            "release checklist is due Friday",
            stable_room_id="wgr_room",
            runtime_room_id="room@@old",
            stable_member_id="wgm_alice",
            runtime_sender_id="wxid_alice_old",
            created_at=100,
        )
        archive.record_message(
            "msg-current",
            "room@@new",
            "Stable Room",
            "wxid_alice_new",
            "Alice",
            "text",
            "@LightBot summarize above",
            stable_room_id="wgr_room",
            runtime_room_id="room@@new",
            stable_member_id="wgm_alice",
            runtime_sender_id="wxid_alice_new",
            is_at=True,
            created_at=200,
        )
        msg = self._msg("msg-current", "@LightBot summarize above")
        msg.other_user_id = "room@@new"
        msg.actual_user_id = "wxid_alice_new"
        msg.wechat_group_stable_room_id = "wgr_room"
        msg.wechat_group_stable_member_id = "wgm_alice"

        store = WechatGroupFocusStore(self.focus_db_path)
        service = WechatGroupFocusService(store=store)
        focus = service.resolve_reply_focus(archive, msg, "summarize above", now=200)

        texts = "\n".join(row.get("text", "") for row in focus["messages"])
        self.assertEqual("contextual", focus["mode"])
        self.assertIn("release checklist is due Friday", texts)
        self.assertEqual("wgr_room", focus["frame"]["room_id"])
        self.assertEqual(1, len(store.load_stack("wgr_room")))
        self.assertEqual([], store.load_stack("room@@new"))

    def test_returned_event_pops_to_matching_previous_focus(self):
        from channel.wechat_group.wechat_group_focus_service import WechatGroupFocusService
        from channel.wechat_group.wechat_group_focus_store import WechatGroupFocusStore

        archive = WechatGroupArchive(self.archive_db_path)
        archive.record_message("msg-release", "room@@abc", "测试群", "wxid_a", "Alice", "text", "发布排期周五", created_at=100)
        archive.record_message("msg-team", "room@@abc", "测试群", "wxid_b", "Bob", "text", "团建预算确认", created_at=101)
        archive.record_message("msg-current", "room@@abc", "测试群", "wxid_a", "Alice", "text", "@LightBot 回到之前发布排期", is_at=True, created_at=200)
        store = WechatGroupFocusStore(self.focus_db_path)
        store.save_stack("room@@abc", [
            {"frame_id": "focus-release", "room_id": "room@@abc", "depth": 0, "topic": ["发布", "排期"], "title": "发布排期", "last_row_id": 1},
            {"frame_id": "focus-team", "room_id": "room@@abc", "depth": 1, "topic": ["团建", "预算"], "title": "团建预算", "last_row_id": 2},
        ])

        service = WechatGroupFocusService(store=store)
        focus = service.resolve_reply_focus(archive, self._msg("msg-current", "@LightBot 回到之前发布排期"), "回到之前发布排期", now=200)

        self.assertEqual("returned", focus["event"])
        self.assertEqual("发布排期", focus["frame"]["title"])
        self.assertEqual(1, len(store.load_stack("room@@abc")))

    def test_focus_prompt_does_not_emit_legacy_topic_block(self):
        from channel.wechat_group.wechat_group_focus_service import WechatGroupFocusService
        from channel.wechat_group.wechat_group_focus_store import WechatGroupFocusStore

        service = WechatGroupFocusService(store=WechatGroupFocusStore(self.focus_db_path))
        block = service.build_prompt_block({
            "event": "kept",
            "mode": "contextual",
            "reason": "contextual_keyword",
            "frame": {
                "frame_id": "focus-release",
                "topic": ["发布", "排期"],
                "title": "发布排期",
                "summary": "最近围绕发布排期的群聊焦点",
                "participants": ["Alice", "Bob"],
                "hit_count": 2,
            },
            "messages": [{"message_id": "msg-1"}],
        })

        self.assertIn("<wechat-group-focus", block)
        self.assertIn("current_focus: 发布排期", block)
        self.assertNotIn("<wechat-group-topic>", block)


if __name__ == "__main__":
    unittest.main()
