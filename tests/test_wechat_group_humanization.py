import os
import tempfile
import unittest

from channel.wechat_group.wechat_group_archive import WechatGroupArchive
from channel.wechat_group.wechat_group_archive_context import (
    build_archive_evidence_block,
)
from channel.wechat_group.wechat_group_context import build_safe_wechat_group_recent_context_block_from_rows
from channel.wechat_group.wechat_group_humanized_context import (
    WechatGroupHumanizedContextBuilder,
)
from channel.wechat_group.wechat_group_reply_cleanup import cleanup_wechat_group_reply_text
from channel.wechat_group.wechat_group_message import WechatGroupMessage
from channel.wechat_group.protocol import parse_sidecar_event
from config import conf


LONG_WECHAT_IMAGE_TRANSPORT_XML = """<?xml version="1.0"?>
<msg>
  <img aeskey="{}" cdnthumburl="masked" md5="masked" hevc_mid_size="31347" />
</msg>
""".format("a" * 240)

class WechatGroupHumanizationArchiveTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmpdir.name, "archive.db")
        self.archive = WechatGroupArchive(self.db_path)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _record(self, message_id, room_id="room@@a", text="", sender="Alice", ts=1000, message_type="text", media_path=""):
        self.archive.record_message(
            message_id=message_id,
            room_id=room_id,
            room_name="Room",
            sender_id="wxid_" + sender.lower(),
            sender_nickname=sender,
            message_type=message_type,
            text=text,
            media_path=media_path,
            created_at=ts,
        )

    def test_archive_search_filters_room_time_keywords_and_current_message(self):
        self._record("old", text="release window was yesterday", ts=100)
        self._record("match-1", text="release window is Friday", sender="Alice", ts=950)
        self._record("match-2", text="Bob owns release checklist", sender="Bob", ts=970)
        self._record("current", text="who owns release", sender="Carol", ts=980)
        self._record("other-room", room_id="room@@b", text="release secret in another room", ts=960)
        self._record("no-keyword", text="lunch order", sender="Dave", ts=965)

        rows = self.archive.search_messages(
            "room@@a",
            query="who owns release?",
            since_ts=900,
            until_ts=1000,
            limit=10,
            exclude_message_id="current",
        )

        self.assertEqual(["match-1", "match-2"], [row["message_id"] for row in rows])

    def test_archive_queries_use_stable_room_while_preserving_runtime_fields(self):
        self.archive.record_message(
            message_id="stable-msg",
            room_id="room@@runtime",
            room_name="Room",
            sender_id="wxid_runtime",
            sender_nickname="Alice",
            message_type="text",
            text="stable release discussion",
            stable_room_id="wgr_room",
            runtime_room_id="room@@runtime",
            stable_member_id="wgm_alice",
            runtime_sender_id="wxid_runtime",
            created_at=1000,
        )

        recent = self.archive.get_recent_messages("wgr_room", limit=10, minutes=10, now=1010)
        searched = self.archive.search_messages("wgr_room", query="release", since_ts=900, until_ts=1100)
        exact = self.archive.get_message_by_id("wgr_room", "stable-msg")

        self.assertEqual(["stable-msg"], [row["message_id"] for row in recent])
        self.assertEqual(["stable-msg"], [row["message_id"] for row in searched])
        self.assertEqual("stable-msg", exact["message_id"])
        self.assertEqual("wgr_room", exact["stable_room_id"])
        self.assertEqual("room@@runtime", exact["runtime_room_id"])
        self.assertEqual("wgm_alice", exact["stable_member_id"])
        self.assertEqual("wxid_runtime", exact["runtime_sender_id"])

    def test_distill_returns_latest_limit_in_chronological_order(self):
        for index in range(150):
            self._record(
                "message-{:03d}".format(index),
                text="message {}".format(index),
                ts=1000 + index,
            )

        rows = self.archive.get_messages_for_distill(
            "room@@a",
            since_ts=1000,
            until_ts=1200,
            limit=100,
        )

        self.assertEqual(100, len(rows))
        self.assertEqual("message-050", rows[0]["message_id"])
        self.assertEqual("message-149", rows[-1]["message_id"])
        self.assertEqual(
            sorted(row["created_at"] for row in rows),
            [row["created_at"] for row in rows],
        )

    def test_distill_honors_until_timestamp_when_newer_rows_exist(self):
        for index in range(6):
            self._record(
                "bounded-{}".format(index),
                text="bounded {}".format(index),
                ts=1000 + index,
            )

        rows = self.archive.get_messages_for_distill(
            "room@@a",
            since_ts=900,
            until_ts=1003,
            limit=10,
        )

        self.assertEqual(
            ["bounded-0", "bounded-1", "bounded-2", "bounded-3"],
            [row["message_id"] for row in rows],
        )

    def test_summary_archive_context_rejects_other_room_runtime_id_collision(self):
        self.archive.record_message(
            message_id="room-a-message",
            room_id="room@@a",
            room_name="A群",
            sender_id="wxid_alice",
            sender_nickname="Alice",
            message_type="text",
            text="A群昨天确认了发布计划",
            stable_room_id="wgr_room_a",
            runtime_room_id="room@@a",
            created_at=1000,
        )
        self.archive.record_message(
            message_id="room-b-collision",
            room_id="wgr_room_a",
            room_name="B群",
            sender_id="wxid_bob",
            sender_nickname="Bob",
            message_type="text",
            text="B群机密内容不得出现在A群总结",
            stable_room_id="wgr_room_b",
            runtime_room_id="wgr_room_a",
            created_at=1001,
        )
        self.archive.record_message(
            message_id="legacy-message",
            room_id="room@@legacy",
            room_name="旧群",
            sender_id="wxid_legacy",
            sender_nickname="Legacy",
            message_type="text",
            text="未绑定稳定身份的历史消息",
            created_at=1002,
        )

        recent = self.archive.get_recent_messages("wgr_room_a", limit=10, minutes=60, now=1010)
        searched = self.archive.search_messages(
            "wgr_room_a", since_ts=900, until_ts=1100, limit=10
        )
        distilled = self.archive.get_messages_for_distill(
            "wgr_room_a", since_ts=900, until_ts=1100, limit=10
        )
        evidence = build_archive_evidence_block(
            self.archive,
            room_id="wgr_room_a",
            query="",
            now=1010,
            days=1,
            limit=10,
        )

        for rows in (recent, searched, distilled):
            self.assertEqual(["room-a-message"], [row["message_id"] for row in rows])
        self.assertIn("A群昨天确认了发布计划", evidence)
        self.assertNotIn("B群机密内容", evidence)
        self.assertIsNone(self.archive.get_message_by_id("wgr_room_a", "room-b-collision"))
        self.assertEqual(
            ["legacy-message"],
            [
                row["message_id"]
                for row in self.archive.get_recent_messages(
                    "room@@legacy", limit=10, minutes=60, now=1010
                )
            ],
        )

    def test_safe_recent_formatter_omits_internal_identifiers_and_paths(self):
        rows = [
            {
                "message_id": "image-1",
                "created_at": 1000,
                "message_type": "image",
                "sender_nickname": "Alice",
                "text": "",
                "media_path": "D:/tmp/private/cat.jpg",
            },
            {
                "message_id": "text-1",
                "created_at": 1010,
                "message_type": "text",
                "sender_nickname": "Bob",
                "text": "<xml>hello</xml> C:/Users/me/secret.txt",
            },
        ]

        block = build_safe_wechat_group_recent_context_block_from_rows(rows)

        self.assertIn("<recent-wechat-group-transcript>", block)
        self.assertIn("[image message]", block)
        self.assertIn("Bob: hello [local-path]", block)
        self.assertNotIn("message_id", block)
        self.assertNotIn("image-1", block)
        self.assertNotIn("D:/tmp/private", block)
        self.assertNotIn("C:/Users", block)
        self.assertNotIn("<xml>", block)

    def test_archive_evidence_excludes_current_and_covered_source_events(self):
        self._record("prev-1", text="Alice said the launch is Friday", sender="Alice", ts=950)
        self._record("prev-2", text="Bob said QA owns the checklist", sender="Bob", ts=960)
        self._record("current", text="summarize the launch discussion", sender="Carol", ts=970)
        covered = self.archive.get_message_by_id("room@@a", "prev-1")

        evidence = build_archive_evidence_block(
            self.archive,
            room_id="room@@a",
            query="launch checklist",
            now=980,
            days=1,
            limit=10,
            exclude_message_id="current",
            exclude_source_event_ids=(
                "inbound:{}".format(covered["id"]),
            ),
        )

        self.assertIn("<wechat-group-archive-evidence>", evidence)
        self.assertNotIn("Alice said the launch is Friday", evidence)
        self.assertIn("Bob said QA owns the checklist", evidence)
        self.assertNotIn("current", evidence)

    def test_legacy_text_transport_xml_is_projected_from_all_prompt_contexts(self):
        self._record(
            "legacy-image-as-text",
            text=LONG_WECHAT_IMAGE_TRANSPORT_XML,
            sender="Alice",
            ts=950,
            message_type="text",
        )
        rows = self.archive.get_recent_messages("room@@a", limit=10, minutes=60, now=980)

        recent = build_safe_wechat_group_recent_context_block_from_rows(rows)
        evidence = build_archive_evidence_block(
            self.archive,
            room_id="room@@a",
            query="hevc_mid_size",
            now=980,
            days=1,
            limit=10,
        )

        self.assertIn("[image message]", recent)
        self.assertIn("[image message]", evidence)
        for transport_fragment in ("<?xml", "<img", "hevc_mid_size", "aeskey", "cdnthumburl"):
            self.assertNotIn(transport_fragment, recent)
            self.assertNotIn(transport_fragment, evidence)


class WechatGroupHumanizedContextBuilderTest(unittest.TestCase):
    def setUp(self):
        self._original_config = {
            "wechat_group_archive_evidence_enabled": conf().get("wechat_group_archive_evidence_enabled"),
            "wechat_group_rolling_summary_enabled": conf().get("wechat_group_rolling_summary_enabled"),
        }
        conf()["wechat_group_archive_evidence_enabled"] = True
        conf()["wechat_group_rolling_summary_enabled"] = False
        self.tmpdir = tempfile.TemporaryDirectory()
        self.archive = WechatGroupArchive(os.path.join(self.tmpdir.name, "archive.db"))

    def tearDown(self):
        for key, value in self._original_config.items():
            if value is None:
                conf().pop(key, None)
            else:
                conf()[key] = value
        self.tmpdir.cleanup()

    def _msg(self, text="@LightBot summarize above", message_id="current", ts=1010, is_at=True):
        return WechatGroupMessage(parse_sidecar_event({
            "type": "message",
            "message_id": message_id,
            "room_id": "room@@a",
            "room_name": "Room",
            "sender_id": "wxid_alice",
            "sender_name": "Alice",
            "self_id": "wxid_bot",
            "self_name": "LightBot",
            "text": text,
            "is_at": is_at,
            "at_list": ["wxid_bot"] if is_at else [],
            "timestamp": ts,
        }))

    def _stable_msg(self, text="@LightBot summarize above", message_id="current", ts=1010):
        msg = WechatGroupMessage(parse_sidecar_event({
            "type": "message",
            "message_id": message_id,
            "room_id": "room@@new",
            "room_name": "Room",
            "sender_id": "wxid_alice_new",
            "sender_name": "Alice",
            "self_id": "wxid_bot_new",
            "self_name": "LightBot",
            "text": text,
            "is_at": True,
            "at_list": ["wxid_bot_new"],
            "timestamp": ts,
        }))
        msg.wechat_group_stable_room_id = "wgr_room"
        msg.wechat_group_stable_member_id = "wgm_alice"
        return msg

    def test_builder_orders_policy_recent_evidence_focus_memory_and_raw_user_text(self):
        class FakeChannel:
            def __init__(self, archive):
                self.archive = archive

            def _resolve_focus_context(self, msg, query):
                return {"messages": [], "event": "kept"}

            def _build_focus_context_block(self, focus):
                return "<wechat-group-focus>\nfocus\n</wechat-group-focus>"

            def _build_memory_context_block(self, msg, query):
                return "<wechat-group-knowledge>\n[group_memory]\nship Friday\n</wechat-group-knowledge>"

            def _build_style_context_block(self, msg):
                return "<wechat-group-style>\nconcise\n</wechat-group-style>"

            def _build_emotion_context_block(self, msg):
                return "<wechat-group-emotion>\ncalm\n</wechat-group-emotion>"

            def _build_multimodal_context(self, msg, query, trigger_source, include_quote=True):
                return {"block": "", "diagnostics": {}, "matched_images": []}

            def _infer_multimodal_trigger_source(self, msg):
                return "direct_reply"

        self.archive.record_message(
            message_id="old-evidence",
            room_id="room@@a",
            sender_nickname="Bob",
            text="Bob said ship Friday",
            created_at=1000,
        )
        self.archive.record_message(
            message_id="recent",
            room_id="room@@a",
            sender_nickname="Carol",
            text="Carol confirmed the deployment owner",
            created_at=199990,
        )
        channel = FakeChannel(self.archive)
        msg = self._msg(ts=200000)
        result = WechatGroupHumanizedContextBuilder(channel).build(
            msg=msg,
            user_content="总结昨天的 ship plan",
            trigger_source="direct_reply",
        )

        content = result.content
        self.assertIn("<wechat-group-mention-verification>", content)
        self.assertIn("<wechat-group-reply-policy>", content)
        self.assertIn("<wechat-group-archive-evidence>", content)
        self.assertNotIn("<local-extractive-summary>", content)
        self.assertIn("<recent-wechat-group-transcript", content)
        self.assertIn("<wechat-group-focus>", content)
        self.assertIn("<wechat-group-memory>", content)
        self.assertNotIn("<wechat-group-knowledge>", content)
        self.assertTrue(content.rstrip().endswith("总结昨天的 ship plan"))
        self.assertLess(content.index("<wechat-group-reply-policy>"), content.index("<wechat-group-archive-evidence>"))
        self.assertLess(content.index("<recent-wechat-group-transcript"), content.index("<wechat-group-archive-evidence>"))
        self.assertLess(content.index("<wechat-group-archive-evidence>"), content.index("<wechat-group-focus>"))
        self.assertLess(content.index("<wechat-group-focus>"), content.index("<wechat-group-memory>"))

    def test_builder_falls_back_to_recent_rows_when_focus_only_has_current_message(self):
        class FakeChannel:
            def __init__(self, archive):
                self.archive = archive

            def _resolve_focus_context(self, msg, query):
                current = self.archive.get_message_by_id(msg.other_user_id, msg.msg_id)
                return {
                    "messages": [current],
                    "event": "kept",
                    "mode": "contextual",
                    "frame": {"title": "current request"},
                }

            def _build_focus_context_block(self, focus):
                return "<wechat-group-focus>\nfocus\n</wechat-group-focus>"

            def _build_memory_context_block(self, msg, query):
                return ""

            def _build_style_context_block(self, msg):
                return ""

            def _build_emotion_context_block(self, msg):
                return ""

            def _build_multimodal_context(self, msg, query, trigger_source, include_quote=True):
                return {"block": "", "diagnostics": {}, "matched_images": []}

            def _infer_multimodal_trigger_source(self, msg):
                return "direct_reply"

        self.archive.record_message(
            message_id="prev",
            room_id="room@@a",
            sender_nickname="Bob",
            text="release window is Friday",
            created_at=1000,
        )
        self.archive.record_message(
            message_id="current",
            room_id="room@@a",
            sender_nickname="Alice",
            text="@LightBot summarize above",
            created_at=1010,
        )

        result = WechatGroupHumanizedContextBuilder(FakeChannel(self.archive)).build(
            msg=self._msg(message_id="current"),
            user_content="summarize above",
            trigger_source="direct_reply",
        )

        self.assertIn("<recent-wechat-group-transcript", result.content)
        start = result.content.index("<recent-wechat-group-transcript")
        end = result.content.index("</recent-wechat-group-transcript>")
        transcript = result.content[start:end]
        self.assertIn("release window is Friday", transcript)
        self.assertNotIn("@LightBot summarize above", transcript)

    def test_builder_uses_stable_room_for_history_after_runtime_room_changes(self):
        class FakeChannel:
            def __init__(self, archive):
                self.archive = archive

            def _resolve_focus_context(self, msg, query):
                return {}

            def _build_focus_context_block(self, focus):
                return ""

            def _build_memory_context_block(self, msg, query):
                return ""

            def _build_style_context_block(self, msg):
                return ""

            def _build_emotion_context_block(self, msg):
                return ""

            def _build_multimodal_context(self, msg, query, trigger_source, include_quote=True):
                return {"block": "", "diagnostics": {}, "matched_images": []}

            def _infer_multimodal_trigger_source(self, msg):
                return "direct_reply"

        self.archive.record_message(
            message_id="prev-old-runtime",
            room_id="room@@old",
            room_name="Room",
            sender_id="wxid_bob_old",
            sender_nickname="Bob",
            message_type="text",
            text="release window is Friday",
            stable_room_id="wgr_room",
            runtime_room_id="room@@old",
            stable_member_id="wgm_bob",
            runtime_sender_id="wxid_bob_old",
            created_at=1000,
        )

        result = WechatGroupHumanizedContextBuilder(FakeChannel(self.archive)).build(
            msg=self._stable_msg(message_id="current"),
            user_content="summarize above",
            trigger_source="direct_reply",
        )

        self.assertNotIn("<wechat-group-archive-evidence>", result.content)
        self.assertNotIn("<local-extractive-summary>", result.content)
        self.assertIn("<recent-wechat-group-transcript", result.content)
        self.assertIn("release window is Friday", result.content)

    def test_builder_injects_configured_context_for_direct_reply(self):
        class FakeChannel:
            def __init__(self, archive):
                self.archive = archive

            def _resolve_focus_context(self, msg, query):
                return {}

            def _build_focus_context_block(self, focus):
                return ""

            def _build_memory_context_block(self, msg, query):
                return ""

            def _build_style_context_block(self, msg):
                return ""

            def _build_emotion_context_block(self, msg):
                return ""

            def _build_multimodal_context(self, msg, query, trigger_source, include_quote=True):
                return {"block": "", "diagnostics": {}, "matched_images": []}

            def _infer_multimodal_trigger_source(self, msg):
                return "direct_reply"

        self.archive.record_message(
            message_id="prev",
            room_id="room@@a",
            sender_nickname="Bob",
            text="都是算30天又不是自然月",
            created_at=1000,
        )
        result = WechatGroupHumanizedContextBuilder(FakeChannel(self.archive)).build(
            msg=self._msg(text="@LightBot 你说说是自然月吗"),
            user_content="你说说是自然月吗",
            trigger_source="direct_reply",
        )

        self.assertIn("<recent-wechat-group-transcript", result.content)
        self.assertIn("都是算30天又不是自然月", result.content)
        self.assertNotIn("<wechat-group-archive-evidence>", result.content)
        self.assertIn("<wechat-group-reply-policy>", result.content)

    def test_free_reply_uses_recent_member_conversation_only(self):
        class FakeChannel:
            def __init__(self, archive):
                self.archive = archive

            def _resolve_focus_context(self, msg, query):
                raise AssertionError("free reply must not resolve old focus")

            def _build_focus_context_block(self, focus):
                return ""

            def _build_memory_context_block(self, msg, query):
                return ""

            def _build_style_context_block(self, msg):
                return ""

            def _build_emotion_context_block(self, msg):
                return ""

            def _build_multimodal_context(self, msg, query, trigger_source, include_quote=True):
                return {"block": "", "diagnostics": {}, "matched_images": []}

            def _infer_multimodal_trigger_source(self, msg):
                return "free_reply"

        self.archive.record_message(
            message_id="old-topic",
            room_id="room@@a",
            sender_nickname="Alice",
            text="旧投屏话题",
            created_at=1000,
        )
        self.archive.record_message(
            message_id="recent-human",
            room_id="room@@a",
            sender_nickname="Bob",
            text="我弄好了",
            created_at=9900,
        )
        self.archive.record_assistant_reply(
            room_id="room@@a",
            room_name="Room",
            content="刚才机器人真实发出的消息",
            created_at=9950,
        )
        self.archive.record_message(
            message_id="current",
            room_id="room@@a",
            sender_nickname="Alice",
            text="有用吗",
            created_at=10000,
        )

        result = WechatGroupHumanizedContextBuilder(FakeChannel(self.archive)).build(
            msg=self._msg(text="有用吗", message_id="current", ts=10000, is_at=False),
            user_content="有用吗",
            trigger_source="free_reply",
            is_free_reply=True,
        )

        self.assertIn("<recent-wechat-group-transcript", result.content)
        self.assertIn("我弄好了", result.content)
        self.assertNotIn("刚才机器人真实发出的消息", result.content)
        self.assertNotIn("旧投屏话题", result.content)
        self.assertNotIn("<wechat-group-archive-evidence>", result.content)
        self.assertNotIn("<local-extractive-summary>", result.content)
        self.assertNotIn("<wechat-group-focus>", result.content)

    def test_builder_always_keeps_reference_policy(self):
        class FakeChannel:
            def __init__(self, archive):
                self.archive = archive

            def _resolve_focus_context(self, msg, query):
                return {}

            def _build_focus_context_block(self, focus):
                return ""

            def _build_memory_context_block(self, msg, query):
                return ""

            def _build_style_context_block(self, msg):
                return ""

            def _build_emotion_context_block(self, msg):
                return ""

            def _build_multimodal_context(self, msg, query, trigger_source, include_quote=True):
                return {"block": "", "diagnostics": {}, "matched_images": []}

            def _infer_multimodal_trigger_source(self, msg):
                return "direct_reply"

        result = WechatGroupHumanizedContextBuilder(FakeChannel(self.archive)).build(
            msg=self._msg(text="@LightBot read https://example.test"),
            user_content="read https://example.test",
            trigger_source="direct_reply",
        )

        self.assertIn("<wechat-group-reference-policy>", result.content)


class WechatGroupReplyCleanupTest(unittest.TestCase):
    def test_cleanup_removes_prompt_tags_prefaces_tail_questions_and_limits_length(self):
        text = (
            "<wechat-group-reply-policy>\ninternal\n</wechat-group-reply-policy>\n"
            "我来整理一下：Bob said ship Friday。\n"
            "如果你还想了解更多，我可以继续说明。"
        )

        cleaned = cleanup_wechat_group_reply_text(text, max_chars=24)

        self.assertEqual("Bob said ship Friday。", cleaned)

    def test_cleanup_removes_consultative_followup_tail_question(self):
        text = (
            "整体来说就是 **“大车好开、空间灵活、智驾强”**，30万级别里产品力确实挺能打。"
            "你想了解具体的哪方面？配置对比、还是跟其他车比比？"
        )

        cleaned = cleanup_wechat_group_reply_text(text, max_chars=800)

        self.assertEqual(
            "整体来说就是 “大车好开、空间灵活、智驾强”，30万级别里产品力确实挺能打。",
            cleaned,
        )

    def test_cleanup_strips_markdown_display_markers_for_wechat(self):
        text = (
            "### 结论\n"
            "**核心就是续航够、空间大**。\n"
            "* 先看预算\n"
            "- 再看充电条件\n"
            "> 不建议只看参数。"
        )

        cleaned = cleanup_wechat_group_reply_text(text, max_chars=800)

        self.assertEqual(
            "结论\n核心就是续航够、空间大。\n先看预算\n再看充电条件\n不建议只看参数。",
            cleaned,
        )

    def test_cleanup_strips_code_fences_inline_code_and_markdown_links(self):
        text = (
            "可以看 `config.py` 里的配置。\n"
            "```powershell\n"
            "python -m unittest tests.test_wechat_group_humanization\n"
            "```\n"
            "参考 [官方文档](https://example.com/docs)。"
        )

        cleaned = cleanup_wechat_group_reply_text(text, max_chars=800)

        self.assertEqual(
            "可以看 config.py 里的配置。\n"
            "python -m unittest tests.test_wechat_group_humanization\n"
            "参考 官方文档 https://example.com/docs。",
            cleaned,
        )

    def test_cleanup_keeps_plain_symbols_identifiers_urls_and_wechat_emojis(self):
        text = (
            "2*3=6，配置项 wechat_group_response_cleanup_enabled 不变。\n"
            "链接 https://example.com/a_b?x=1*2 也别动[捂脸]"
        )

        cleaned = cleanup_wechat_group_reply_text(text, max_chars=800)

        self.assertEqual(text, cleaned)

    def test_cleanup_removes_unreadable_leading_member_id_but_keeps_readable_mention(self):
        raw_member_id = "@62c6151697e24a21de9f36dee37b0e1961028c6abf7d480dfa00069f884fc9ff"
        body = "所以是要再买张电信卡才能转进去？这门槛有点高啊[捂脸]"

        self.assertEqual(
            body,
            cleanup_wechat_group_reply_text("{} {}".format(raw_member_id, body)),
        )
        self.assertEqual(
            "@小明 {}".format(body),
            cleanup_wechat_group_reply_text("@小明 {}".format(body)),
        )


if __name__ == "__main__":
    unittest.main()
