import unittest
from unittest.mock import Mock

from bridge.context import ContextType
from channel.wechat_group.protocol import parse_sidecar_event
from channel.wechat_group.wechat_group_channel import WechatGroupChannel
from channel.wechat_group.wechat_group_message import WechatGroupMessage
from channel.wechat_group.wechat_group_persona import (
    DEFAULT_WECHAT_GROUP_PERSONA_PROMPT,
    WECHAT_GROUP_PERSONA_MAX_LENGTH,
    WECHAT_GROUP_PERSONA_PRESETS,
    build_wechat_group_persona_block,
    get_wechat_group_persona_config,
    normalize_wechat_group_persona_prompt,
    resolve_wechat_group_persona_preset_id,
    should_skip_persona_for_message,
)
from config import conf


class WechatGroupPersonaTest(unittest.TestCase):
    def setUp(self):
        self._original_config = {
            "wechat_group_room_ids": conf().get("wechat_group_room_ids"),
            "wechat_group_persona_prompt": conf().get("wechat_group_persona_prompt"),
            "wechat_group_persona_preset_id": conf().get("wechat_group_persona_preset_id"),
            "wechat_group_admin_members": conf().get("wechat_group_admin_members"),
            "wechat_group_admin_sender_ids": conf().get("wechat_group_admin_sender_ids"),
        }

    def tearDown(self):
        for key, value in self._original_config.items():
            if value is None:
                conf().pop(key, None)
            else:
                conf()[key] = value

    def test_default_presets_use_bailongmapro_persona_data(self):
        preset_ids = [preset["id"] for preset in WECHAT_GROUP_PERSONA_PRESETS]

        self.assertEqual(
            ["owner-digital-twin", "tech-duty", "social-fun"],
            preset_ids,
        )
        self.assertIn("你是白龙马 / 小白龙", WECHAT_GROUP_PERSONA_PRESETS[0]["prompt"])
        self.assertIn("技术值班 AI 助手", WECHAT_GROUP_PERSONA_PRESETS[1]["prompt"])
        self.assertIn("轻松陪聊 AI 助手", WECHAT_GROUP_PERSONA_PRESETS[2]["prompt"])
        for preset in WECHAT_GROUP_PERSONA_PRESETS:
            self.assertIn("不要汇报内部工具过程", preset["prompt"])
            self.assertIn("不要使用 Markdown 展示格式", preset["prompt"])

    def test_normalize_prompt_trims_crlf_and_limits_length(self):
        prompt = "  hello\r\nworld  " + ("x" * (WECHAT_GROUP_PERSONA_MAX_LENGTH + 20))

        normalized = normalize_wechat_group_persona_prompt(prompt)

        self.assertNotIn("\r\n", normalized)
        self.assertTrue(normalized.startswith("hello\nworld"))
        self.assertLessEqual(len(normalized), WECHAT_GROUP_PERSONA_MAX_LENGTH)

    def test_resolve_preset_id_matches_builtin_or_custom(self):
        self.assertEqual(
            "tech-duty",
            resolve_wechat_group_persona_preset_id(WECHAT_GROUP_PERSONA_PRESETS[1]["prompt"]),
        )
        self.assertEqual(
            "owner-digital-twin",
            resolve_wechat_group_persona_preset_id(
                WECHAT_GROUP_PERSONA_PRESETS[0]["prompt"],
                preferred_id="owner-clone",
            ),
        )
        self.assertEqual(
            "custom",
            resolve_wechat_group_persona_preset_id("自定义微信群助手人设", preferred_id="tech-duty"),
        )

    def test_get_config_falls_back_to_default_prompt(self):
        conf()["wechat_group_persona_prompt"] = ""
        conf()["wechat_group_persona_preset_id"] = ""

        persona = get_wechat_group_persona_config()

        self.assertEqual("owner-digital-twin", persona["preset_id"])
        self.assertEqual(DEFAULT_WECHAT_GROUP_PERSONA_PROMPT, persona["prompt"])

    def test_default_persona_tells_model_not_to_use_markdown_display_format(self):
        persona = get_wechat_group_persona_config()

        self.assertIn("不要使用 Markdown 展示格式", persona["prompt"])

    def test_persona_block_uses_independent_wechat_group_tag(self):
        block = build_wechat_group_persona_block("  自定义人设\r\n第二行 ")

        self.assertEqual(
            "<wechat-group-persona>\n自定义人设\n第二行\n</wechat-group-persona>",
            block,
        )

    def test_channel_injects_persona_block_into_group_text(self):
        conf()["wechat_group_room_ids"] = ["room@@abc"]
        conf()["wechat_group_persona_prompt"] = "你是测试微信群助手"
        conf()["wechat_group_persona_preset_id"] = "custom"
        channel = WechatGroupChannel(client=Mock())
        msg = Mock(
            ctype=ContextType.TEXT,
            content="@LightBot 帮我总结一下",
            from_user_id="room@@abc",
            other_user_id="room@@abc",
            other_user_nickname="测试群",
            actual_user_id="wxid_alice",
            actual_user_nickname="Alice",
            to_user_id="wxid_bot",
            is_at=True,
            at_list=["wxid_bot"],
            self_display_name="LightBot",
        )

        context = channel._compose_context(ContextType.TEXT, msg.content, isgroup=True, msg=msg)

        self.assertIsNotNone(context)
        self.assertIn("<wechat-group-persona>", context.content)
        self.assertIn("你是测试微信群助手", context.content)
        self.assertTrue(context.content.rstrip().endswith("帮我总结一下"))

    def test_admin_config_request_skips_persona_block(self):
        conf()["wechat_group_admin_members"] = [{"room_id": "room@@abc", "sender_id": "wxid_admin"}]
        conf()["wechat_group_admin_sender_ids"] = []
        msg = WechatGroupMessage(parse_sidecar_event({
            "type": "message",
            "message_id": "msg-admin",
            "room_id": "room@@abc",
            "room_name": "测试群",
            "sender_id": "wxid_admin",
            "sender_name": "Admin",
            "self_id": "wxid_bot",
            "self_name": "LightBot",
            "text": "@LightBot 修改人设为技术值班助手",
            "is_at": True,
            "at_list": ["wxid_bot"],
        }))

        self.assertTrue(should_skip_persona_for_message(msg))

    def test_normal_member_config_request_does_not_skip_persona_block(self):
        conf()["wechat_group_admin_members"] = [{"room_id": "room@@abc", "sender_id": "wxid_admin"}]
        conf()["wechat_group_admin_sender_ids"] = []
        msg = WechatGroupMessage(parse_sidecar_event({
            "type": "message",
            "message_id": "msg-normal",
            "room_id": "room@@abc",
            "room_name": "测试群",
            "sender_id": "wxid_alice",
            "sender_name": "Alice",
            "self_id": "wxid_bot",
            "self_name": "LightBot",
            "text": "@LightBot 修改人设为技术值班助手",
            "is_at": True,
            "at_list": ["wxid_bot"],
        }))

        self.assertFalse(should_skip_persona_for_message(msg))

    def test_admin_identity_does_not_cross_rooms(self):
        conf()["wechat_group_admin_members"] = [{"room_id": "room@@abc", "sender_id": "wxid_admin"}]
        conf()["wechat_group_admin_sender_ids"] = []
        msg = WechatGroupMessage(parse_sidecar_event({
            "type": "message",
            "message_id": "msg-admin-other-room",
            "room_id": "room@@other",
            "room_name": "其他群",
            "sender_id": "wxid_admin",
            "sender_name": "Admin",
            "self_id": "wxid_bot",
            "self_name": "LightBot",
            "text": "@LightBot 修改人设为技术值班助手",
            "is_at": True,
            "at_list": ["wxid_bot"],
        }))

        self.assertFalse(should_skip_persona_for_message(msg))

    def test_stable_admin_config_request_skips_persona_only_after_alias_confirmation(self):
        conf()["wechat_group_admin_members"] = [{
            "stable_room_id": "wgr_room",
            "stable_member_id": "wgm_admin",
            "identity_status": "confirmed",
        }]
        conf()["wechat_group_admin_sender_ids"] = []
        msg = WechatGroupMessage(parse_sidecar_event({
            "type": "message",
            "message_id": "msg-stable-admin",
            "room_id": "room@@new",
            "room_name": "Test Room",
            "sender_id": "wxid_new",
            "sender_name": "Admin",
            "self_id": "wxid_bot",
            "self_name": "LightBot",
            "text": "@LightBot 修改人设为技术值班助手",
            "is_at": True,
            "at_list": ["wxid_bot"],
        }))
        msg.wechat_group_stable_room_id = "wgr_room"
        msg.wechat_group_stable_member_id = "wgm_admin"
        msg.wechat_group_identity_requires_confirmation = False

        self.assertTrue(should_skip_persona_for_message(msg))

        msg.wechat_group_identity_requires_confirmation = True
        self.assertFalse(should_skip_persona_for_message(msg))


if __name__ == "__main__":
    unittest.main()
