import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from agent.tools.base_tool import ToolResult
from bridge.context import ContextType
from config import conf


WECHAT_STICKER_TRANSPORT_XML = """<?xml version="1.0"?>
<msg>
  <emoji aeskey="masked" cdnurl="masked" md5="masked" hevc_mid_size="31347" />
</msg>
"""


class WechatGroupMultimodalContextServiceTest(unittest.TestCase):
    def setUp(self):
        self._original_config = {
            "wechat_group_multimodal_context_enabled": conf().get("wechat_group_multimodal_context_enabled"),
            "wechat_group_multimodal_image_understanding_context_enabled": conf().get("wechat_group_multimodal_image_understanding_context_enabled"),
            "wechat_group_multimodal_free_reply_image_context_enabled": conf().get("wechat_group_multimodal_free_reply_image_context_enabled"),
            "wechat_group_multimodal_same_sender_window_seconds": conf().get("wechat_group_multimodal_same_sender_window_seconds"),
            "wechat_group_multimodal_unique_image_window_seconds": conf().get("wechat_group_multimodal_unique_image_window_seconds"),
            "wechat_group_multimodal_quote_sender_window_minutes": conf().get("wechat_group_multimodal_quote_sender_window_minutes"),
            "wechat_group_multimodal_max_recent_messages": conf().get("wechat_group_multimodal_max_recent_messages"),
            "wechat_group_image_understanding_enabled": conf().get("wechat_group_image_understanding_enabled"),
            "wechat_group_image_understanding_prompt": conf().get("wechat_group_image_understanding_prompt"),
            "wechat_group_image_understanding_cache_minutes": conf().get("wechat_group_image_understanding_cache_minutes"),
        }

    def tearDown(self):
        for key, value in self._original_config.items():
            if value is None:
                conf().pop(key, None)
            else:
                conf()[key] = value

    def _text_msg(self, text="这是真的吗", sender_id="wxid_alice", ts=100002, quote=None):
        return SimpleNamespace(
            ctype=ContextType.TEXT,
            content=text,
            text=text,
            other_user_id="room@@abc",
            other_user_nickname="Test Room",
            actual_user_id=sender_id,
            actual_user_nickname="Alice" if sender_id == "wxid_alice" else "Bob",
            to_user_id="wxid_bot",
            to_user_nickname="LightBot",
            is_at=False,
            is_quote_self=False,
            is_group=True,
            at_list=[],
            self_display_name="LightBot",
            create_time=ts,
            msg_id="msg-text",
            message_type="text",
            media_path="",
            quote=quote or {},
            forward={},
            raw_app_type="",
        )

    def _image_msg(self, media_path="D:/tmp/cat.jpg", ts=100000):
        return SimpleNamespace(
            ctype=ContextType.IMAGE,
            content=media_path,
            text="",
            other_user_id="room@@abc",
            other_user_nickname="Test Room",
            actual_user_id="wxid_alice",
            actual_user_nickname="Alice",
            to_user_id="wxid_bot",
            to_user_nickname="LightBot",
            is_at=True,
            is_quote_self=False,
            is_group=True,
            at_list=["wxid_bot"],
            self_display_name="LightBot",
            create_time=ts,
            msg_id="msg-image",
            message_type="image",
            media_path=media_path,
            quote={},
            forward={},
            raw_app_type="",
        )

    def _image_item(self, message_id, sender_id="wxid_alice", media_path="D:/tmp/fact.jpg", ts=100000):
        return {
            "message_id": message_id,
            "message_type": "image",
            "media_path": media_path,
            "sender_nickname": "Alice" if sender_id == "wxid_alice" else "Bob",
            "sender_id": sender_id,
            "created_at": ts,
        }

    def test_config_defaults_are_conservative_for_free_reply(self):
        from channel.wechat_group.wechat_group_multimodal_context_service import (
            get_wechat_group_multimodal_context_config,
        )

        cfg = get_wechat_group_multimodal_context_config()

        self.assertTrue(cfg["enabled"])
        self.assertTrue(cfg["image_understanding_enabled"])
        self.assertFalse(cfg["free_reply_image_context_enabled"])
        self.assertEqual(120, cfg["same_sender_window_seconds"])
        self.assertEqual(120, cfg["unique_image_window_seconds"])
        self.assertEqual(30, cfg["quote_sender_window_minutes"])
        self.assertEqual(20, cfg["max_recent_messages"])

    def test_image_summary_cache_is_owned_by_multimodal_service(self):
        from channel.wechat_group.wechat_group_multimodal_context_service import (
            WechatGroupMultimodalContextService,
        )

        conf()["wechat_group_image_understanding_prompt"] = "Describe this image"
        conf()["wechat_group_image_understanding_cache_minutes"] = 30
        service = WechatGroupMultimodalContextService(Mock())

        with patch(
            "agent.tools.vision.vision.Vision.execute",
            return_value=ToolResult.success({"content": "Cached cat summary."}),
        ) as execute:
            first = service.build_context(
                self._image_msg(),
                query="",
                trigger_source="image_message",
                now=100000,
            )
            second = service.build_context(
                self._image_msg(),
                query="",
                trigger_source="image_message",
                now=100000,
            )

        execute.assert_called_once_with({
            "image": "D:/tmp/cat.jpg",
            "question": "Describe this image",
        })
        self.assertIn("Cached cat summary.", first["block"])
        self.assertIn("Cached cat summary.", second["block"])
        self.assertNotIn("D:/tmp/cat.jpg", first["block"])
        self.assertNotIn("D:/tmp/cat.jpg", second["block"])

    def test_image_summary_failure_returns_diagnostic_text_without_path_leak(self):
        from channel.wechat_group.wechat_group_multimodal_context_service import (
            WechatGroupMultimodalContextService,
        )

        conf()["wechat_group_image_understanding_prompt"] = "Describe this image"
        service = WechatGroupMultimodalContextService(Mock())

        with patch(
            "agent.tools.vision.vision.Vision.execute",
            side_effect=RuntimeError("vision backend down"),
        ):
            result = service.build_context(
                self._image_msg(media_path="D:/tmp/private/cat.jpg"),
                query="",
                trigger_source="image_message",
                now=100000,
            )

        self.assertIn("<wechat-group-multimodal>", result["block"])
        self.assertIn("[image_understanding]", result["block"])
        self.assertIn("图片理解失败", result["block"])
        self.assertNotIn("D:/tmp/private/cat.jpg", result["block"])
        self.assertEqual("current_image", result["diagnostics"]["reason"])
        self.assertEqual("msg-image", result["diagnostics"].get("matched_image_message_id"))
        self.assertEqual("wxid_alice", result["diagnostics"].get("matched_image_sender_id"))
        self.assertFalse(result["diagnostics"].get("summary_generated"))
        self.assertNotIn("media_path", result["diagnostics"])
        for image in result["matched_images"]:
            self.assertNotIn("media_path", image)

    def test_image_summary_failure_sanitizes_exception_path(self):
        from channel.wechat_group.wechat_group_multimodal_context_service import (
            WechatGroupMultimodalContextService,
        )

        conf()["wechat_group_image_understanding_prompt"] = "Describe this image"
        service = WechatGroupMultimodalContextService(Mock())

        with patch(
            "agent.tools.vision.vision.Vision.execute",
            side_effect=FileNotFoundError("D:/tmp/private/cat.jpg"),
        ):
            result = service.build_context(
                self._image_msg(media_path="D:/tmp/private/cat.jpg"),
                query="",
                trigger_source="image_message",
                now=100000,
            )

        self.assertIn("图片理解失败", result["block"])
        self.assertNotIn("D:/tmp/private/cat.jpg", result["block"])
        self.assertFalse(result["diagnostics"].get("summary_generated"))

    def test_free_reply_text_binds_same_sender_recent_image_when_enabled(self):
        from channel.wechat_group.wechat_group_multimodal_context_service import (
            WechatGroupMultimodalContextService,
        )

        conf()["wechat_group_multimodal_free_reply_image_context_enabled"] = True
        conf()["wechat_group_image_understanding_prompt"] = "Describe this image"
        archive = Mock()
        archive.get_recent_messages.return_value = [
            self._image_item("image-before-question", sender_id="wxid_alice", media_path="D:/tmp/fact.jpg"),
        ]
        service = WechatGroupMultimodalContextService(archive)

        with patch(
            "agent.tools.vision.vision.Vision.execute",
            return_value=ToolResult.success({"content": "A screenshot of a transfer notice."}),
        ) as execute:
            result = service.build_context(
                self._text_msg(),
                query="这是真的吗",
                trigger_source="free_reply",
                now=100002,
            )

        execute.assert_called_once_with({
            "image": "D:/tmp/fact.jpg",
            "question": "Describe this image",
        })
        self.assertIn("<wechat-group-multimodal>", result["block"])
        self.assertIn("same_sender_recent_image", result["block"])
        self.assertIn("A screenshot of a transfer notice.", result["block"])
        self.assertNotIn("D:/tmp/fact.jpg", result["block"])

    def test_quoted_image_lookup_uses_stable_room_after_runtime_room_changes(self):
        from channel.wechat_group.wechat_group_multimodal_context_service import (
            WechatGroupMultimodalContextService,
        )

        conf()["wechat_group_image_understanding_enabled"] = True
        conf()["wechat_group_image_understanding_prompt"] = "Describe this image"
        archive = Mock()
        archive.get_message_by_id.return_value = self._image_item(
            "quoted-image",
            sender_id="wxid_old",
            media_path="D:/tmp/quoted.jpg",
        )
        service = WechatGroupMultimodalContextService(archive)
        msg = self._text_msg(
            text="@LightBot explain this",
            sender_id="wxid_new",
            quote={"message_id": "quoted-image"},
        )
        msg.wechat_group_stable_room_id = "wgr_room"
        msg.wechat_group_stable_member_id = "wgm_alice"

        with patch(
            "agent.tools.vision.vision.Vision.execute",
            return_value=ToolResult.success({"content": "Quoted image summary."}),
        ):
            result = service.build_context(
                msg,
                query="explain this",
                trigger_source="direct_reply",
                now=100002,
            )

        archive.get_message_by_id.assert_any_call("wgr_room", "quoted-image")
        archive.get_recent_messages.assert_not_called()
        self.assertIn("quoted_image", result["block"])
        self.assertIn("Quoted image summary.", result["block"])

    def test_quote_fallback_projects_sticker_xml_to_semantic_placeholder(self):
        from channel.wechat_group.wechat_group_multimodal_context_service import (
            WechatGroupMultimodalContextService,
        )

        archive = Mock()
        archive.get_message_by_id.return_value = None
        service = WechatGroupMultimodalContextService(archive)
        msg = self._text_msg(
            text="@LightBot explain this",
            quote={
                "message_id": "quoted-sticker",
                "type": "47",
                "content": WECHAT_STICKER_TRANSPORT_XML,
            },
        )

        result = service.build_context(
            msg,
            query="explain this",
            trigger_source="direct_reply",
            now=100002,
        )

        self.assertIn("message_type: sticker", result["block"])
        self.assertIn("content: [sticker]", result["block"])
        for transport_fragment in ("<?xml", "<emoji", "hevc_mid_size", "aeskey", "cdnurl"):
            self.assertNotIn(transport_fragment, result["block"])

    def test_same_sender_recent_image_matches_stable_member_after_runtime_sender_changes(self):
        from channel.wechat_group.wechat_group_multimodal_context_service import (
            WechatGroupMultimodalContextService,
        )

        conf()["wechat_group_image_understanding_enabled"] = True
        conf()["wechat_group_image_understanding_prompt"] = "Describe this image"
        archive = Mock()
        archive.get_recent_messages.return_value = [
            {
                "message_id": "alice-old-runtime-image",
                "message_type": "image",
                "media_path": "D:/tmp/alice.jpg",
                "sender_nickname": "Alice",
                "sender_id": "wxid_alice_old",
                "stable_member_id": "wgm_alice",
                "created_at": 100000,
            },
            {
                "message_id": "bob-image",
                "message_type": "image",
                "media_path": "D:/tmp/bob.jpg",
                "sender_nickname": "Bob",
                "sender_id": "wxid_bob",
                "stable_member_id": "wgm_bob",
                "created_at": 100001,
            },
        ]
        service = WechatGroupMultimodalContextService(archive)
        msg = self._text_msg(sender_id="wxid_alice_new", ts=100002)
        msg.wechat_group_stable_room_id = "wgr_room"
        msg.wechat_group_stable_member_id = "wgm_alice"

        with patch(
            "channel.wechat_group.wechat_group_multimodal_context_service._looks_like_image_reference_question",
            return_value=True,
        ):
            with patch(
                "agent.tools.vision.vision.Vision.execute",
                return_value=ToolResult.success({"content": "Alice old runtime image."}),
            ):
                result = service.build_context(
                    msg,
                    query="image question",
                    trigger_source="direct_reply",
                    now=100002,
                )

        archive.get_recent_messages.assert_any_call("wgr_room", limit=20, minutes=2, now=100002)
        self.assertIn("same_sender_recent_image", result["block"])
        self.assertIn("alice-old-runtime-image", result["block"])
        self.assertIn("Alice old runtime image.", result["block"])

    def test_direct_reply_text_binds_unique_recent_image(self):
        from channel.wechat_group.wechat_group_multimodal_context_service import (
            WechatGroupMultimodalContextService,
        )

        conf()["wechat_group_image_understanding_enabled"] = True
        archive = Mock()
        archive.get_recent_messages.return_value = [
            self._image_item("recent-image", sender_id="wxid_carol", media_path="D:/tmp/recent.jpg"),
        ]
        service = WechatGroupMultimodalContextService(archive)

        with patch(
            "agent.tools.vision.vision.Vision.execute",
            return_value=ToolResult.success({"content": "A suspicious payment screenshot."}),
        ):
            result = service.build_context(
                self._text_msg(text="@LightBot 这是真的吗", sender_id="wxid_bob", ts=100030),
                query="这是真的吗",
                trigger_source="direct_reply",
                now=100030,
            )

        self.assertIn("unique_recent_image", result["block"])
        self.assertIn("recent-image", result["block"])
        self.assertNotIn("D:/tmp/recent.jpg", result["block"])

    def test_direct_reply_text_asking_what_sender_posted_binds_unique_recent_image(self):
        from channel.wechat_group.wechat_group_multimodal_context_service import (
            WechatGroupMultimodalContextService,
        )

        conf()["wechat_group_image_understanding_enabled"] = True
        conf()["wechat_group_image_understanding_prompt"] = "Describe this image"
        archive = Mock()
        archive.get_recent_messages.return_value = [
            self._image_item("recent-image", sender_id="wxid_alice", media_path="D:/tmp/recent.jpg"),
        ]
        service = WechatGroupMultimodalContextService(archive)

        with patch(
            "agent.tools.vision.vision.Vision.execute",
            return_value=ToolResult.success({"content": "A screenshot shared by Alice."}),
        ) as execute:
            result = service.build_context(
                self._text_msg(text="@LightBot 海佬发的啥", sender_id="wxid_bob", ts=100030),
                query="海佬发的啥",
                trigger_source="direct_reply",
                now=100030,
            )

        execute.assert_called_once_with({
            "image": "D:/tmp/recent.jpg",
            "question": "Describe this image",
        })
        self.assertIn("unique_recent_image", result["block"])
        self.assertIn("recent-image", result["block"])
        self.assertIn("A screenshot shared by Alice.", result["block"])
        self.assertNotIn("D:/tmp/recent.jpg", result["block"])

    def test_free_reply_wechat_image_marker_question_binds_unique_recent_image(self):
        from channel.wechat_group.wechat_group_multimodal_context_service import (
            WechatGroupMultimodalContextService,
        )

        conf()["wechat_group_multimodal_free_reply_image_context_enabled"] = True
        conf()["wechat_group_image_understanding_enabled"] = True
        conf()["wechat_group_image_understanding_prompt"] = "Describe this image"
        archive = Mock()
        archive.get_recent_messages.return_value = [
            self._image_item("recent-image", sender_id="wxid_bob", media_path="D:/tmp/recent.jpg"),
        ]
        service = WechatGroupMultimodalContextService(archive)
        text = "「紫菜：[图片]」\n- - - - - - - - - - - - - - -\n这是哪个？"

        with patch(
            "agent.tools.vision.vision.Vision.execute",
            return_value=ToolResult.success({"content": "A screenshot of a router service."}),
        ) as execute:
            result = service.build_context(
                self._text_msg(text=text, sender_id="wxid_alice", ts=100030),
                query=text,
                trigger_source="free_reply",
                now=100030,
            )

        execute.assert_called_once_with({
            "image": "D:/tmp/recent.jpg",
            "question": "Describe this image",
        })
        self.assertIn("unique_recent_image", result["block"])
        self.assertIn("recent-image", result["block"])
        self.assertIn("A screenshot of a router service.", result["block"])
        self.assertNotIn("D:/tmp/recent.jpg", result["block"])

    def test_direct_reply_expanded_image_quote_asking_for_current_config_binds_same_sender_image(self):
        from channel.wechat_group.wechat_group_multimodal_context_service import (
            WechatGroupMultimodalContextService,
        )

        conf()["wechat_group_image_understanding_enabled"] = True
        conf()["wechat_group_image_understanding_prompt"] = "Describe this image"
        archive = Mock()
        archive.get_recent_messages.return_value = [
            self._image_item("quoted-config-image", sender_id="wxid_alice", media_path="D:/private/config.jpg"),
        ]
        service = WechatGroupMultimodalContextService(archive)
        text = "「Alice：[图片]」\n- - - - - - - - - - - - - - -\n@LightBot 看我当前配置"

        with patch(
            "agent.tools.vision.vision.Vision.execute",
            return_value=ToolResult.success({"content": "A PC hardware configuration screenshot."}),
        ) as execute:
            result = service.build_context(
                self._text_msg(text=text, sender_id="wxid_alice", ts=100030),
                query=text,
                trigger_source="direct_reply",
                now=100030,
            )

        execute.assert_called_once_with({
            "image": "D:/private/config.jpg",
            "question": "Describe this image",
        })
        self.assertIn("same_sender_recent_image", result["block"])
        self.assertIn("quoted-config-image", result["block"])
        self.assertIn("A PC hardware configuration screenshot.", result["block"])
        self.assertNotIn("D:/private/config.jpg", result["block"])
        self.assertNotIn("media_path", result["diagnostics"])

    def test_expanded_image_quote_prefers_latest_when_same_sender_has_multiple_recent_images(self):
        from channel.wechat_group.wechat_group_multimodal_context_service import (
            WechatGroupMultimodalContextService,
        )

        conf()["wechat_group_image_understanding_prompt"] = "Describe latest image"
        archive = Mock()
        archive.get_recent_messages.return_value = [
            self._image_item("intended-earlier-image", sender_id="wxid_alice", media_path="D:/private/intended.jpg"),
            self._image_item(
                "newer-black-image",
                sender_id="wxid_alice",
                media_path="D:/private/black.jpg",
                ts=100015,
            ),
        ]
        service = WechatGroupMultimodalContextService(archive)
        text = "「Alice：[图片]」\n- - - - - - - - - - - - - - -\n@LightBot 这图是啥意思啊"

        with patch(
            "agent.tools.vision.vision.Vision.execute",
            return_value=ToolResult.success({"content": "Latest image summary."}),
        ) as execute:
            result = service.build_context(
                self._text_msg(text=text, sender_id="wxid_alice", ts=100030),
                query=text,
                trigger_source="direct_reply",
                now=100030,
            )

        execute.assert_called_once_with({
            "image": "D:/private/black.jpg",
            "question": "Describe latest image",
        })
        self.assertIn("<wechat-group-multimodal>", result["block"])
        self.assertIn("same_sender_latest_image", result["block"])
        self.assertIn("newer-black-image", result["block"])
        self.assertIn("Latest image summary.", result["block"])
        self.assertNotIn("D:/private/intended.jpg", result["block"])
        self.assertNotIn("D:/private/black.jpg", result["block"])
        self.assertEqual("same_sender_latest_image", result["diagnostics"]["reason"])
        self.assertEqual("newer-black-image", result["diagnostics"]["matched_image_message_id"])
        self.assertEqual("", result["diagnostics"]["skipped_reason"])

    def test_ambiguous_multiple_recent_images_are_not_bound(self):
        from channel.wechat_group.wechat_group_multimodal_context_service import (
            WechatGroupMultimodalContextService,
        )

        conf()["wechat_group_multimodal_free_reply_image_context_enabled"] = True
        archive = Mock()
        archive.get_recent_messages.return_value = [
            self._image_item("image-a", sender_id="wxid_alice", media_path="D:/tmp/a.jpg"),
            self._image_item("image-b", sender_id="wxid_bob", media_path="D:/tmp/b.jpg", ts=100001),
        ]
        service = WechatGroupMultimodalContextService(archive)

        with patch("agent.tools.vision.vision.Vision.execute") as execute:
            result = service.build_context(
                self._text_msg(sender_id="wxid_carol", ts=100002),
                query="这是真的吗",
                trigger_source="free_reply",
                now=100002,
            )

        execute.assert_not_called()
        self.assertIn("<wechat-group-multimodal>", result["block"])
        self.assertIn("status: ambiguous_reference", result["block"])
        self.assertIn("不得猜测图片内容", result["block"])
        self.assertNotIn("D:/tmp/a.jpg", result["block"])
        self.assertNotIn("D:/tmp/b.jpg", result["block"])
        self.assertEqual("ambiguous_recent_images", result["diagnostics"]["skipped_reason"])


if __name__ == "__main__":
    unittest.main()
