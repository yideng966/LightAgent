import os
import tempfile
import unittest
import warnings
from unittest.mock import Mock

from bridge.context import ContextType
from channel.wechat_group.protocol import parse_sidecar_event
from channel.wechat_group.wechat_group_archive import WechatGroupArchive
from channel.wechat_group.wechat_group_channel import WechatGroupChannel
from channel.wechat_group.wechat_group_context_service import WechatGroupContextService
from channel.wechat_group.wechat_group_context import (
    build_wechat_group_recent_context_block,
    build_wechat_group_recent_context_block_from_rows,
)
from channel.wechat_group.wechat_group_identity_service import WechatGroupIdentityService
from channel.wechat_group.wechat_group_identity_store import WechatGroupIdentityStore
from channel.wechat_group.wechat_group_knowledge_service import WechatGroupKnowledgeService
from channel.wechat_group.wechat_group_knowledge_store import WechatGroupKnowledgeStore
from channel.wechat_group.wechat_group_message import WechatGroupMessage
from channel.wechat_group.wechat_group_profile_service import WechatGroupProfileService
from channel.wechat_group.wechat_group_profile_store import WechatGroupProfileStore
from channel.wechat_group.wechat_group_reply_policy import build_wechat_group_reply_policy_block
from config import conf


WECHAT_IMAGE_TRANSPORT_XML = """<?xml version="1.0"?>
<msg>
  <img aeskey="masked" cdnthumburl="masked" md5="masked" hevc_mid_size="31347" />
</msg>
"""


class WechatGroupRecentContextTest(unittest.TestCase):
    def setUp(self):
        self._original_config = {
            "wechat_group_room_ids": conf().get("wechat_group_room_ids"),
            "wechat_group_recent_context_enabled": conf().get("wechat_group_recent_context_enabled"),
            "wechat_group_recent_context_limit": conf().get("wechat_group_recent_context_limit"),
            "wechat_group_recent_context_minutes": conf().get("wechat_group_recent_context_minutes"),
            "wechat_group_record_messages": conf().get("wechat_group_record_messages"),
            "wechat_group_persona_prompt": conf().get("wechat_group_persona_prompt"),
            "wechat_group_persona_preset_id": conf().get("wechat_group_persona_preset_id"),
            "wechat_group_memory_enabled": conf().get("wechat_group_memory_enabled"),
            "wechat_group_member_memory_enabled": conf().get("wechat_group_member_memory_enabled"),
            "wechat_group_knowledge_enabled": conf().get("wechat_group_knowledge_enabled"),
            "wechat_group_profile_enabled": conf().get("wechat_group_profile_enabled"),
            "wechat_group_profile_context_limit": conf().get("wechat_group_profile_context_limit"),
            "wechat_group_group_memory_context_limit": conf().get("wechat_group_group_memory_context_limit"),
            "wechat_group_focus_enabled": conf().get("wechat_group_focus_enabled"),
            "wechat_group_focus_recent_message_limit": conf().get("wechat_group_focus_recent_message_limit"),
            "wechat_group_focus_context_message_limit": conf().get("wechat_group_focus_context_message_limit"),
            "wechat_group_focus_stack_depth": conf().get("wechat_group_focus_stack_depth"),
            "wechat_group_focus_stale_rounds": conf().get("wechat_group_focus_stale_rounds"),
            "wechat_group_focus_min_keywords": conf().get("wechat_group_focus_min_keywords"),
            "wechat_group_style_enabled": conf().get("wechat_group_style_enabled"),
            "wechat_group_emotion_enabled": conf().get("wechat_group_emotion_enabled"),
        }
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self._tmp.name, "wechat_group_archive.db")
        self.profile_db_path = os.path.join(self._tmp.name, "profiles.db")
        self.knowledge_db_path = os.path.join(self._tmp.name, "knowledge.db")

    def tearDown(self):
        for key, value in self._original_config.items():
            if value is None:
                conf().pop(key, None)
            else:
                conf()[key] = value
        self._tmp.cleanup()

    def _create_profile_scope(self, member_specs):
        identity = WechatGroupIdentityService(
            WechatGroupIdentityStore(os.path.join(self._tmp.name, "identity.db"))
        )
        account = identity.resolve_account("self-a", "Bot", "profile-a", {})
        identity.confirm_account_binding(account.stable_id, "self-a", actor="test", reason="account")
        room = identity.resolve_room(account.stable_id, "room@@abc", "Test Group", "self-a", {})
        identity.confirm_room_binding(room.stable_id, "room@@abc", actor="test", reason="room")
        members = {}
        for runtime_id, nickname in member_specs:
            member = identity.resolve_member(
                room.stable_id,
                runtime_id,
                nickname,
                nickname,
                {"wechat_id": "{}-wechat".format(runtime_id)},
            )
            identity.confirm_member_binding(
                room.stable_id,
                member.stable_id,
                runtime_id,
                actor="test",
                reason="member",
            )
            members[runtime_id] = member.stable_id
        service = WechatGroupProfileService(
            WechatGroupProfileStore(self.profile_db_path),
            identity_service=identity,
        )
        return room.stable_id, members, service

    def test_archive_queries_recent_messages_by_room_only(self):
        archive = WechatGroupArchive(self.db_path)
        archive.record_message(
            message_id="room-a-1",
            room_id="room@@a",
            room_name="A群",
            sender_id="wxid_alice",
            sender_nickname="Alice",
            message_type="text",
            text="A 群消息",
            is_at=True,
            created_at=1000,
        )
        archive.record_message(
            message_id="room-b-1",
            room_id="room@@b",
            room_name="B群",
            sender_id="wxid_bob",
            sender_nickname="Bob",
            message_type="text",
            text="B 群消息",
            is_at=True,
            created_at=1001,
        )

        rows = archive.get_recent_messages("room@@a", limit=10, minutes=60, now=2000)

        self.assertEqual(1, len(rows))
        self.assertEqual("room@@a", rows[0]["room_id"])
        self.assertEqual("A 群消息", rows[0]["text"])

    def test_recent_context_block_can_render_focus_rows(self):
        rows = [{
            "created_at": 100,
            "message_type": "text",
            "sender_nickname": "Alice",
            "text": "发布窗口是周五",
        }]

        block = build_wechat_group_recent_context_block_from_rows(rows)

        self.assertIn("<recent-wechat-group-transcript>", block)
        self.assertIn("发布窗口是周五", block)

    def test_recent_context_treats_missing_message_type_as_text(self):
        rows = [{
            "created_at": 100,
            "sender_nickname": "Alice",
            "text": "发布窗口是周五",
        }]

        block = build_wechat_group_recent_context_block_from_rows(rows)

        self.assertIn("[text] Alice: 发布窗口是周五", block)
        self.assertNotIn("[unknown message]", block)

    def test_archive_recent_messages_include_parsed_metadata(self):
        archive = WechatGroupArchive(self.db_path)
        archive.record_message(
            message_id="room-a-meta",
            room_id="room@@a",
            room_name="A群",
            sender_id="wxid_alice",
            sender_nickname="Alice",
            message_type="text",
            text="引用消息",
            is_at=True,
            metadata={
                "at_list": ["wxid_bot"],
                "quote": {"message_id": "quoted-1", "content": "上一条"},
                "forward": {"title": "聊天记录"},
                "raw_app_type": "19",
            },
            created_at=1000,
        )

        rows = archive.get_recent_messages("room@@a", limit=10, minutes=60, now=2000)

        self.assertEqual(1, len(rows))
        self.assertEqual(["wxid_bot"], rows[0]["at_list"])
        self.assertEqual("quoted-1", rows[0]["metadata"]["quote"]["message_id"])
        self.assertEqual("聊天记录", rows[0]["metadata"]["forward"]["title"])
        self.assertEqual("19", rows[0]["metadata"]["raw_app_type"])

    def test_archive_get_message_by_id_scopes_to_room(self):
        archive = WechatGroupArchive(self.db_path)
        archive.record_message(
            message_id="quoted-image",
            room_id="room@@a",
            room_name="A群",
            sender_id="wxid_alice",
            sender_nickname="Alice",
            message_type="image",
            text="[图片]",
            media_path="D:/tmp/quoted.jpg",
            created_at=1000,
        )
        archive.record_message(
            message_id="quoted-image",
            room_id="room@@b",
            room_name="B群",
            sender_id="wxid_bob",
            sender_nickname="Bob",
            message_type="image",
            text="[图片]",
            media_path="D:/tmp/other.jpg",
            created_at=1001,
        )

        row = archive.get_message_by_id("room@@a", "quoted-image")

        self.assertIsNotNone(row)
        self.assertEqual("room@@a", row["room_id"])
        self.assertEqual("image", row["message_type"])
        self.assertEqual("D:/tmp/quoted.jpg", row["media_path"])
        self.assertIsNone(archive.get_message_by_id("room@@missing", "quoted-image"))

    def test_archive_lists_members_by_room_and_query(self):
        archive = WechatGroupArchive(self.db_path)
        archive.record_message(
            message_id="room-a-1",
            room_id="room@@a",
            room_name="room a",
            sender_id="wxid_alice",
            sender_nickname="Alice",
            message_type="text",
            text="hello",
            created_at=1000,
        )
        archive.record_message(
            message_id="room-a-2",
            room_id="room@@a",
            room_name="room a",
            sender_id="wxid_alice",
            sender_nickname="Alice New",
            message_type="text",
            text="hello again",
            created_at=1010,
        )
        archive.record_message(
            message_id="room-a-3",
            room_id="room@@a",
            room_name="room a",
            sender_id="wxid_bob",
            sender_nickname="Bob",
            message_type="text",
            text="hello",
            created_at=1005,
        )
        archive.record_message(
            message_id="room-b-1",
            room_id="room@@b",
            room_name="room b",
            sender_id="wxid_alice_other",
            sender_nickname="Alice Other",
            message_type="text",
            text="other room",
            created_at=1020,
        )

        rows = archive.list_members("room@@a", query="alice", limit=10)

        self.assertEqual(1, len(rows))
        self.assertEqual("wxid_alice", rows[0]["sender_id"])
        self.assertEqual("Alice New", rows[0]["sender_nickname"])
        self.assertEqual(2, rows[0]["message_count"])
        self.assertEqual(1010, rows[0]["last_seen_at"])

    def test_wechat_group_channel_import_does_not_require_audio_converter(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            __import__("channel.wechat_group.wechat_group_channel")

        self.assertFalse(
            [item for item in caught if "ffmpeg or avconv" in str(item.message)]
        )

    def test_recent_context_block_is_compact_and_omits_other_rooms(self):
        archive = WechatGroupArchive(self.db_path)
        archive.record_message(
            message_id="msg-old",
            room_id="room@@a",
            room_name="A群",
            sender_id="wxid_alice",
            sender_nickname="Alice",
            message_type="text",
            text="第一条消息需要被摘要",
            created_at=1000,
        )
        archive.record_message(
            message_id="msg-other",
            room_id="room@@b",
            room_name="B群",
            sender_id="wxid_bob",
            sender_nickname="Bob",
            message_type="text",
            text="其他群消息不应该出现",
            created_at=1001,
        )

        block = build_wechat_group_recent_context_block(archive, "room@@a", limit=5, minutes=60, now=2000)

        self.assertIn("<recent-wechat-group-transcript>", block)
        self.assertIn("[text] Alice", block)
        self.assertIn("第一条消息需要被摘要", block)
        self.assertNotIn("其他群消息", block)

    def test_recent_context_block_does_not_expose_media_paths_or_transport_xml(self):
        archive = WechatGroupArchive(self.db_path)
        archive.record_message(
            message_id="image-1",
            room_id="room@@a",
            room_name="A群",
            sender_id="wxid_alice",
            sender_nickname="Alice",
            message_type="image",
            text="",
            media_path="D:/tmp/private/image-1.jpg",
            created_at=1000,
        )
        archive.record_message(
            message_id="file-1",
            room_id="room@@a",
            room_name="A群",
            sender_id="wxid_bob",
            sender_nickname="Bob",
            message_type="file",
            text="",
            media_path="C:/Users/clancy/.lightagent/private/report.pdf",
            created_at=1001,
        )
        archive.record_message(
            message_id="legacy-image-as-text",
            room_id="room@@a",
            room_name="A群",
            sender_id="wxid_carol",
            sender_nickname="Carol",
            message_type="text",
            text=WECHAT_IMAGE_TRANSPORT_XML,
            media_path="",
            created_at=1002,
        )

        block = build_wechat_group_recent_context_block(archive, "room@@a", limit=5, minutes=60, now=2000)

        self.assertIn("[image message_id=image-1]", block)
        self.assertIn("[file message_id=file-1]", block)
        self.assertIn("[image message_id=legacy-image-as-text]", block)
        self.assertNotIn("D:/tmp/private/image-1.jpg", block)
        self.assertNotIn("C:/Users/clancy/.lightagent/private/report.pdf", block)
        for transport_fragment in ("<?xml", "<img", "hevc_mid_size", "aeskey", "cdnthumburl"):
            self.assertNotIn(transport_fragment, block)

    def test_channel_records_message_and_injects_recent_context_before_request(self):
        conf()["wechat_group_room_ids"] = ["room@@abc"]
        conf()["wechat_group_record_messages"] = True
        conf()["wechat_group_recent_context_enabled"] = True
        conf()["wechat_group_recent_context_limit"] = 5
        conf()["wechat_group_recent_context_minutes"] = 60
        conf()["wechat_group_persona_prompt"] = ""
        conf()["wechat_group_persona_preset_id"] = ""
        archive = WechatGroupArchive(self.db_path)
        archive.record_message(
            message_id="msg-prev",
            room_id="room@@abc",
            room_name="测试群",
            sender_id="wxid_bob",
            sender_nickname="Bob",
            message_type="text",
            text="刚才讨论了发布窗口",
            created_at=1000,
        )
        channel = WechatGroupChannel(client=Mock(), archive=archive)
        msg = WechatGroupMessage(parse_sidecar_event({
            "type": "message",
            "message_id": "msg-current",
            "room_id": "room@@abc",
            "room_name": "测试群",
            "sender_id": "wxid_alice",
            "sender_name": "Alice",
            "self_id": "wxid_bot",
            "self_name": "LightBot",
            "text": "@LightBot 总结一下",
            "is_at": True,
            "at_list": ["wxid_bot"],
            "timestamp": 1010,
        }))

        context = channel._compose_context(ContextType.TEXT, msg.content, isgroup=True, msg=msg)

        self.assertIsNotNone(context)
        self.assertIn("<recent-wechat-group-transcript>", context.content)
        self.assertIn("刚才讨论了发布窗口", context.content)
        self.assertIn("Alice", context.content)
        self.assertTrue(context.content.rstrip().endswith("总结一下"))
        rows = archive.get_recent_messages("room@@abc", limit=10, minutes=60, now=1010)
        self.assertEqual(["msg-prev", "msg-current"], [row["message_id"] for row in rows])

    def test_context_service_builds_wechat_group_knowledge_block(self):
        room_id, members, profile_service = self._create_profile_scope([
            ("alice-runtime", "Alice"),
            ("bob-runtime", "Bob"),
        ])
        knowledge_service = WechatGroupKnowledgeService(WechatGroupKnowledgeStore(self.knowledge_db_path))
        knowledge_service.add_group_memory(room_id, "发布窗口是周五晚上", ["m1"], "讨论结果", "manual")
        profile_service.upsert_manual_profile(
            sender_id=members["alice-runtime"],
            primary_nickname="Alice",
            speak_style="直接给结论",
            interests=["发布"],
            common_words=["安排"],
            aliases=[],
            room_id=room_id,
        )
        profile_service.upsert_manual_profile(
            sender_id=members["bob-runtime"],
            primary_nickname="Bob",
            speak_style="喜欢列清单",
            interests=["测试"],
            common_words=["收到"],
            aliases=[],
            room_id=room_id,
        )
        service = WechatGroupContextService(
            profile_service=profile_service,
            knowledge_service=knowledge_service,
        )

        preview = service.preview_context(
            room_id=room_id,
            sender_id="alice-runtime",
            query="总结一下",
            mentioned_sender_ids=["bob-runtime"],
        )

        self.assertIn("<wechat-group-memory>", preview["content"])
        self.assertIn("[group_memory]", preview["content"])
        self.assertIn('[speaker_profile sender_id="{}"]'.format(members["alice-runtime"]), preview["content"])
        self.assertIn('[mentioned_profile sender_id="{}"]'.format(members["bob-runtime"]), preview["content"])

    def test_context_service_adds_reply_name_policy_for_member_aliases(self):
        room_id, members, profile_service = self._create_profile_scope([
            ("alice-runtime", "Alice"),
            ("xuxu-runtime", "徐徐图之"),
        ])
        knowledge_service = WechatGroupKnowledgeService(WechatGroupKnowledgeStore(self.knowledge_db_path))
        profile_service.upsert_manual_profile(
            sender_id=members["xuxu-runtime"],
            primary_nickname="\u5f90\u5f90\u56fe\u4e4b",
            speak_style="",
            interests=[],
            common_words=[],
            aliases=["\u56fe\u603b"],
            room_id=room_id,
        )
        service = WechatGroupContextService(
            profile_service=profile_service,
            knowledge_service=knowledge_service,
        )

        preview = service.preview_context(
            room_id=room_id,
            sender_id="alice-runtime",
            query="",
            mentioned_sender_ids=["xuxu-runtime"],
        )

        self.assertIn("[naming_policy]", preview["content"])
        self.assertIn("reply_name: \u5f90\u5f90\u56fe\u4e4b", preview["content"])

    def test_channel_injects_memory_after_recent_context_before_request(self):
        class FakeContextService:
            def preview_context(self, **kwargs):
                return {
                    "content": (
                        "<wechat-group-knowledge>\n"
                        "[group_memory]\n发布窗口是周五晚上\n"
                        '[speaker_profile sender_id="wxid_alice"]\n直接给结论\n'
                        "</wechat-group-knowledge>"
                    ),
                    "filtered_reasons": [],
                }

        conf()["wechat_group_room_ids"] = ["room@@abc"]
        conf()["wechat_group_record_messages"] = True
        conf()["wechat_group_recent_context_enabled"] = True
        conf()["wechat_group_knowledge_enabled"] = True
        conf()["wechat_group_profile_enabled"] = True
        archive = WechatGroupArchive(self.db_path)
        archive.record_message(
            message_id="msg-prev",
            room_id="room@@abc",
            room_name="测试群",
            sender_id="wxid_bob",
            sender_nickname="Bob",
            message_type="text",
            text="刚才讨论了发布窗口",
            created_at=1000,
        )
        channel = WechatGroupChannel(client=Mock(), archive=archive, memory_service=FakeContextService())
        msg = WechatGroupMessage(parse_sidecar_event({
            "type": "message",
            "message_id": "msg-current",
            "room_id": "room@@abc",
            "room_name": "测试群",
            "sender_id": "wxid_alice",
            "sender_name": "Alice",
            "self_id": "wxid_bot",
            "self_name": "LightBot",
            "text": "@LightBot 总结一下",
            "is_at": True,
            "at_list": ["wxid_bot", "wxid_bob"],
            "timestamp": 1010,
        }))

        context = channel._compose_context(ContextType.TEXT, msg.content, isgroup=True, msg=msg)

        recent_index = context.content.index("<recent-wechat-group-transcript>")
        memory_index = context.content.index("<wechat-group-memory>")
        request_index = context.content.rindex("总结一下")
        self.assertLess(recent_index, memory_index)
        self.assertLess(memory_index, request_index)
        self.assertIn("发布窗口是周五晚上", context.content)

    def test_channel_injects_focus_after_recent_context_before_memory(self):
        class FakeContextService:
            def preview_context(self, **kwargs):
                return {
                    "content": (
                        "<wechat-group-knowledge>\n"
                        "[group_memory]\n发布窗口是周五晚上\n"
                        "</wechat-group-knowledge>"
                    ),
                    "filtered_reasons": [],
                }

        class FakeFocusService:
            def resolve_reply_focus(self, archive, msg, query, now=None):
                self.args = (archive, msg.other_user_id, query, now)
                return {
                    "event": "kept",
                    "mode": "contextual",
                    "reason": "contextual_keyword",
                    "frame": {
                        "frame_id": "focus-release",
                        "topic": ["发布", "排期"],
                        "title": "发布排期",
                        "summary": "讨论本周五是否上线",
                    },
                    "messages": archive.get_recent_messages(msg.other_user_id, limit=20, minutes=60, now=now),
                }

            def build_prompt_block(self, focus):
                return (
                    "<wechat-group-focus event=\"kept\" mode=\"contextual\">\n"
                    "current_focus: 发布排期\n"
                    "summary: 讨论本周五是否上线\n"
                    "</wechat-group-focus>"
                )

        conf()["wechat_group_room_ids"] = ["room@@abc"]
        conf()["wechat_group_record_messages"] = True
        conf()["wechat_group_recent_context_enabled"] = True
        conf()["wechat_group_knowledge_enabled"] = True
        conf()["wechat_group_profile_enabled"] = True
        conf()["wechat_group_focus_enabled"] = True
        archive = WechatGroupArchive(self.db_path)
        archive.record_message(
            message_id="msg-prev",
            room_id="room@@abc",
            room_name="测试群",
            sender_id="wxid_bob",
            sender_nickname="Bob",
            message_type="text",
            text="刚才讨论了发布窗口",
            created_at=1000,
        )
        focus_service = FakeFocusService()
        channel = WechatGroupChannel(
            client=Mock(),
            archive=archive,
            memory_service=FakeContextService(),
            focus_service=focus_service,
        )
        msg = WechatGroupMessage(parse_sidecar_event({
            "type": "message",
            "message_id": "msg-current",
            "room_id": "room@@abc",
            "room_name": "测试群",
            "sender_id": "wxid_alice",
            "sender_name": "Alice",
            "self_id": "wxid_bot",
            "self_name": "LightBot",
            "text": "@LightBot 总结一下",
            "is_at": True,
            "at_list": ["wxid_bot", "wxid_bob"],
            "timestamp": 1010,
        }))

        context = channel._compose_context(ContextType.TEXT, msg.content, isgroup=True, msg=msg)

        recent_index = context.content.index("<recent-wechat-group-transcript>")
        focus_index = context.content.index("<wechat-group-focus")
        memory_index = context.content.index("<wechat-group-memory>")
        request_index = context.content.rindex("总结一下")
        self.assertLess(recent_index, focus_index)
        self.assertLess(focus_index, memory_index)
        self.assertLess(memory_index, request_index)
        self.assertNotIn("<wechat-group-topic>", context.content)
        self.assertEqual("room@@abc", focus_service.args[1])

    def test_channel_does_not_inject_old_focus_for_standalone_at(self):
        conf()["wechat_group_room_ids"] = ["room@@abc"]
        conf()["wechat_group_record_messages"] = True
        conf()["wechat_group_recent_context_enabled"] = True
        conf()["wechat_group_focus_enabled"] = True
        conf()["wechat_group_knowledge_enabled"] = False
        conf()["wechat_group_profile_enabled"] = False
        conf()["wechat_group_style_enabled"] = False
        conf()["wechat_group_emotion_enabled"] = False
        archive = WechatGroupArchive(self.db_path)
        archive.record_message("msg-old-1", "room@@abc", "测试群", "wxid_a", "A", "text", "难受 她不爱我了", created_at=1000)
        archive.record_message("msg-old-2", "room@@abc", "测试群", "wxid_b", "B", "text", "xx不爱你了吗", created_at=1001)
        archive.record_message("msg-old-3", "room@@abc", "测试群", "wxid_b", "B", "image", "[截图]", media_path="D:/tmp/a.jpg", created_at=1002)
        channel = WechatGroupChannel(client=Mock(), archive=archive)
        msg = WechatGroupMessage(parse_sidecar_event({
            "type": "message",
            "message_id": "msg-current",
            "room_id": "room@@abc",
            "room_name": "测试群",
            "sender_id": "wxid_b",
            "sender_name": "B",
            "self_id": "wxid_bot",
            "self_name": "LightBot",
            "text": "@LightBot 让gpt来帮忙了",
            "is_at": True,
            "at_list": ["wxid_bot"],
            "timestamp": 1010,
        }))

        context = channel._compose_context(ContextType.TEXT, msg.content, isgroup=True, msg=msg)

        self.assertIn("让gpt来帮忙了", context.content)
        self.assertNotIn("她不爱我了", context.content)
        self.assertNotIn("不爱你了吗", context.content)
        self.assertNotIn("<wechat-group-topic>", context.content)

    def test_channel_keeps_focus_messages_for_summary_request(self):
        conf()["wechat_group_room_ids"] = ["room@@abc"]
        conf()["wechat_group_record_messages"] = True
        conf()["wechat_group_recent_context_enabled"] = True
        conf()["wechat_group_focus_enabled"] = True
        conf()["wechat_group_knowledge_enabled"] = False
        conf()["wechat_group_profile_enabled"] = False
        conf()["wechat_group_style_enabled"] = False
        conf()["wechat_group_emotion_enabled"] = False
        archive = WechatGroupArchive(self.db_path)
        archive.record_message("msg-prev-1", "room@@abc", "测试群", "wxid_bob", "Bob", "text", "发布窗口是周五晚上", created_at=1000)
        archive.record_message("msg-prev-2", "room@@abc", "测试群", "wxid_alice", "Alice", "text", "回归还没过", created_at=1001)
        channel = WechatGroupChannel(client=Mock(), archive=archive)
        msg = WechatGroupMessage(parse_sidecar_event({
            "type": "message",
            "message_id": "msg-current",
            "room_id": "room@@abc",
            "room_name": "测试群",
            "sender_id": "wxid_alice",
            "sender_name": "Alice",
            "self_id": "wxid_bot",
            "self_name": "LightBot",
            "text": "@LightBot 总结刚才",
            "is_at": True,
            "at_list": ["wxid_bot"],
            "timestamp": 1010,
        }))

        context = channel._compose_context(ContextType.TEXT, msg.content, isgroup=True, msg=msg)

        self.assertIn("<wechat-group-focus", context.content)
        self.assertIn("<recent-wechat-group-transcript>", context.content)
        self.assertIn("发布窗口是周五晚上", context.content)
        self.assertIn("回归还没过", context.content)
        self.assertNotIn("<wechat-group-topic>", context.content)

    def test_channel_omits_memory_block_when_memory_config_disabled(self):
        class FakeContextService:
            def preview_context(self, **kwargs):
                raise AssertionError("context service should not be called")

        conf()["wechat_group_room_ids"] = ["room@@abc"]
        conf()["wechat_group_knowledge_enabled"] = False
        conf()["wechat_group_profile_enabled"] = False
        channel = WechatGroupChannel(client=Mock(), archive=WechatGroupArchive(self.db_path), memory_service=FakeContextService())
        msg = WechatGroupMessage(parse_sidecar_event({
            "type": "message",
            "message_id": "msg-current",
            "room_id": "room@@abc",
            "room_name": "测试群",
            "sender_id": "wxid_alice",
            "sender_name": "Alice",
            "self_id": "wxid_bot",
            "self_name": "LightBot",
            "text": "@LightBot 总结一下",
            "is_at": True,
            "at_list": ["wxid_bot"],
            "timestamp": 1010,
        }))

        context = channel._compose_context(ContextType.TEXT, msg.content, isgroup=True, msg=msg)

        self.assertNotIn("<wechat-group-memory>", context.content)

    def test_channel_injects_emotion_block_before_request(self):
        class FakeEmotionService:
            def build_prompt_block(self, room_id, now=None):
                return (
                    "<wechat-group-emotion>\n"
                    "valence: 0.1\n"
                    "energy: 0.7\n"
                    "sociability: 0.8\n"
                    "interpreted_state: engaged\n"
                    "</wechat-group-emotion>"
                )

            def observe_message(self, room_id, text, is_at=False, now=None):
                return {}

        conf()["wechat_group_room_ids"] = ["room@@abc"]
        conf()["wechat_group_emotion_enabled"] = True
        channel = WechatGroupChannel(
            client=Mock(),
            archive=WechatGroupArchive(self.db_path),
            emotion_service=FakeEmotionService(),
        )
        msg = WechatGroupMessage(parse_sidecar_event({
            "type": "message",
            "message_id": "msg-current",
            "room_id": "room@@abc",
            "room_name": "测试群",
            "sender_id": "wxid_alice",
            "sender_name": "Alice",
            "self_id": "wxid_bot",
            "self_name": "LightBot",
            "text": "@LightBot 总结一下",
            "is_at": True,
            "at_list": ["wxid_bot"],
            "timestamp": 1010,
        }))

        context = channel._compose_context(ContextType.TEXT, msg.content, isgroup=True, msg=msg)

        emotion_index = context.content.index("<wechat-group-emotion>")
        request_index = context.content.rindex("总结一下")
        self.assertLess(emotion_index, request_index)

    def test_channel_injects_style_between_memory_and_emotion(self):
        class FakeContextService:
            def preview_context(self, **kwargs):
                return {
                    "content": (
                        "<wechat-group-knowledge>\n"
                        "[group_memory]\n本群喜欢先给结论\n"
                        "</wechat-group-knowledge>"
                    ),
                    "filtered_reasons": [],
                }

        class FakeStyleService:
            def build_prompt_block_from_archive(self, archive, room_id, now=None):
                self.args = (archive, room_id, now)
                return (
                    "<wechat-group-style>\n"
                    "[style_card]\n"
                    "intent: coordination\n"
                    "tone: direct\n"
                    "</wechat-group-style>"
                )

        class FakeEmotionService:
            def build_prompt_block(self, room_id, now=None):
                return (
                    "<wechat-group-emotion>\n"
                    "valence: 0.1\n"
                    "energy: 0.7\n"
                    "sociability: 0.8\n"
                    "interpreted_state: engaged\n"
                    "</wechat-group-emotion>"
                )

            def observe_message(self, room_id, text, is_at=False, now=None):
                return {}

        conf()["wechat_group_room_ids"] = ["room@@abc"]
        conf()["wechat_group_style_enabled"] = True
        conf()["wechat_group_emotion_enabled"] = True
        style_service = FakeStyleService()
        channel = WechatGroupChannel(
            client=Mock(),
            archive=WechatGroupArchive(self.db_path),
            memory_service=FakeContextService(),
            emotion_service=FakeEmotionService(),
        )
        channel.style_service = style_service
        msg = WechatGroupMessage(parse_sidecar_event({
            "type": "message",
            "message_id": "msg-current",
            "room_id": "room@@abc",
            "room_name": "测试群",
            "sender_id": "wxid_alice",
            "sender_name": "Alice",
            "self_id": "wxid_bot",
            "self_name": "LightBot",
            "text": "@LightBot 总结一下",
            "is_at": True,
            "at_list": ["wxid_bot"],
            "timestamp": 1010,
        }))

        context = channel._compose_context(ContextType.TEXT, msg.content, isgroup=True, msg=msg)

        memory_index = context.content.index("<wechat-group-memory>")
        style_index = context.content.index("<wechat-group-style>")
        emotion_index = context.content.index("<wechat-group-emotion>")
        request_index = context.content.rindex("总结一下")
        self.assertLess(memory_index, style_index)
        self.assertLess(style_index, emotion_index)
        self.assertLess(emotion_index, request_index)
        self.assertEqual("room@@abc", style_service.args[1])

    def test_channel_sets_wechat_group_memory_tool_metadata(self):
        conf()["wechat_group_room_ids"] = ["room@@abc"]
        conf()["wechat_group_memory_enabled"] = False
        conf()["wechat_group_member_memory_enabled"] = False
        channel = WechatGroupChannel(client=Mock(), archive=WechatGroupArchive(self.db_path))
        msg = WechatGroupMessage(parse_sidecar_event({
            "type": "message",
            "message_id": "msg-current",
            "room_id": "room@@abc",
            "room_name": "Test Room",
            "sender_id": "wxid_alice",
            "sender_name": "Alice",
            "self_id": "wxid_bot",
            "self_name": "LightBot",
            "text": "@LightBot summarize",
            "is_at": True,
            "at_list": ["wxid_bot"],
            "timestamp": 1010,
        }))

        context = channel._compose_context(ContextType.TEXT, msg.content, isgroup=True, msg=msg)

        self.assertEqual("room@@abc", context.get("wechat_group_room_id"))
        self.assertEqual("wxid_alice", context.get("wechat_group_sender_id"))
        self.assertEqual("wxid_bot", context.get("wechat_group_bot_sender_id"))


class WechatGroupReplyPolicyTest(unittest.TestCase):
    def setUp(self):
        self._sticker_enabled = conf().get("wechat_group_sticker_enabled")
        self._sticker_reply_percent = conf().get("wechat_group_sticker_reply_percent")

    def tearDown(self):
        conf()["wechat_group_sticker_enabled"] = self._sticker_enabled
        conf()["wechat_group_sticker_reply_percent"] = self._sticker_reply_percent

    def test_free_reply_policy_mentions_banter_and_sticker_tools(self):
        conf()["wechat_group_sticker_enabled"] = True
        conf()["wechat_group_sticker_reply_percent"] = 20
        block = build_wechat_group_reply_policy_block("free_reply")

        self.assertIn("free_reply", block)
        self.assertIn("自然接梗", block)
        self.assertIn("wechat_group_sticker_search", block)
        self.assertIn("wechat_group_sticker_send", block)
        self.assertIn("目标频率约为 20%", block)

    def test_direct_reply_policy_requires_compact_answer_without_tail_question(self):
        conf()["wechat_group_sticker_enabled"] = True
        conf()["wechat_group_sticker_reply_percent"] = 20
        block = build_wechat_group_reply_policy_block("direct_reply")

        self.assertIn("direct_reply", block)
        self.assertIn("紧凑", block)
        self.assertIn("不要用追问收尾", block)
        self.assertIn("不要使用 Markdown 展示格式", block)
        self.assertIn("wechat_group_sticker_search", block)
        self.assertIn("目标频率约为 20%", block)

    def test_zero_sticker_reply_percent_only_allows_explicit_requests(self):
        conf()["wechat_group_sticker_enabled"] = True
        conf()["wechat_group_sticker_reply_percent"] = 0

        block = build_wechat_group_reply_policy_block("quote_self")

        self.assertIn("不要主动发送表情包", block)
        self.assertIn("用户明确要求", block)


if __name__ == "__main__":
    unittest.main()
