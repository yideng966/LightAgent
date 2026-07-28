# encoding:utf-8
import json
import os
import tempfile
import unittest
from pathlib import Path

from channel.wechat_group.wechat_group_membership_notice import (
    WechatGroupMembershipNoticeConfigError,
    build_membership_notice_template_values,
    membership_notice_placeholders,
    normalize_membership_notice_image_path,
    normalize_wechat_group_membership_notice_config,
    render_membership_notice_template,
    resolve_membership_notice_image_path,
    resolve_wechat_group_membership_notice,
    validate_membership_notice_image_bytes,
    validate_membership_notice_template,
)


class WechatGroupMembershipNoticeTest(unittest.TestCase):
    def test_defaults_are_enabled_and_keep_expected_templates(self):
        result = normalize_wechat_group_membership_notice_config({}, selected_room_ids=[])

        self.assertTrue(result["wechat_group_join_welcome_enabled"])
        self.assertEqual(result["wechat_group_join_welcome_text"], "欢迎加入群聊！")
        self.assertTrue(result["wechat_group_leave_notice_enabled"])
        self.assertEqual(result["wechat_group_leave_notice_text"], "{member_names} 已离开群聊。")

    def test_explicit_disabled_config_stays_disabled(self):
        result = normalize_wechat_group_membership_notice_config({
            "wechat_group_join_welcome_enabled": False,
            "wechat_group_leave_notice_enabled": False,
        }, selected_room_ids=[])

        self.assertFalse(result["wechat_group_join_welcome_enabled"])
        self.assertFalse(result["wechat_group_leave_notice_enabled"])

    def test_default_config_and_template_enable_both_notices(self):
        from config import available_setting

        template = json.loads(Path("config-template.json").read_text(encoding="utf-8"))

        for key in (
            "wechat_group_join_welcome_enabled",
            "wechat_group_leave_notice_enabled",
        ):
            with self.subTest(key=key):
                self.assertTrue(available_setting[key])
                self.assertTrue(template[key])

    def test_room_custom_and_disabled_override_global_independently(self):
        config = {
            "wechat_group_stable_room_ids": ["wgr_a", "wgr_b", "wgr_c"],
            "wechat_group_join_welcome_enabled": True,
            "wechat_group_join_welcome_text": "欢迎 {member_names}",
            "wechat_group_join_welcome_room_overrides": [
                {
                    "stable_room_id": "wgr_a",
                    "policy": "custom",
                    "content_type": "text",
                    "text": "欢迎加入 {room_name}，邀请人：{inviter_name}",
                },
                {"stable_room_id": "wgr_b", "policy": "disabled"},
            ],
        }

        room_custom = resolve_wechat_group_membership_notice("join", "wgr_a", config)
        room_disabled = resolve_wechat_group_membership_notice("join", "wgr_b", config)
        inherited = resolve_wechat_group_membership_notice("join", "wgr_c", config)

        self.assertEqual(room_custom["source"], "room")
        self.assertIn("{inviter_name}", room_custom["text"])
        self.assertIsNone(room_disabled)
        self.assertEqual(inherited["source"], "global")

    def test_room_custom_can_enable_notice_when_global_is_disabled(self):
        config = {
            "wechat_group_stable_room_ids": ["wgr_a"],
            "wechat_group_leave_notice_enabled": False,
            "wechat_group_leave_notice_room_overrides": [{
                "stable_room_id": "wgr_a",
                "policy": "custom",
                "content_type": "text",
                "text": "{member_names} 已离群，由 {remover_name} 操作",
            }],
        }

        result = resolve_wechat_group_membership_notice("leave", "wgr_a", config)

        self.assertEqual(result["source"], "room")

    def test_resolver_rejects_room_outside_selected_stable_scope(self):
        result = resolve_wechat_group_membership_notice("join", "wgr_other", {
            "wechat_group_stable_room_ids": ["wgr_selected"],
            "wechat_group_join_welcome_enabled": True,
            "wechat_group_join_welcome_text": "欢迎加入群聊！",
        })

        self.assertIsNone(result)

    def test_strict_config_rejects_unselected_or_runtime_room_override(self):
        for room_id in ("room@@runtime", "wgr_unselected"):
            with self.subTest(room_id=room_id):
                with self.assertRaises(WechatGroupMembershipNoticeConfigError):
                    normalize_wechat_group_membership_notice_config({
                        "wechat_group_join_welcome_room_overrides": [{
                            "stable_room_id": room_id,
                            "policy": "disabled",
                        }],
                    }, selected_room_ids=["wgr_selected"], strict=True)

    def test_event_placeholders_are_separate_and_unknown_expressions_are_rejected(self):
        self.assertIn("{inviter_name}", membership_notice_placeholders("join"))
        self.assertNotIn("{remover_name}", membership_notice_placeholders("join"))
        self.assertIn("{remover_name}", membership_notice_placeholders("leave"))
        self.assertEqual(
            validate_membership_notice_template("欢迎 {member_names}", "join"),
            "欢迎 {member_names}",
        )
        for text in ("{remover_name}", "{member.name}", "{unknown}", "{member_name"):
            with self.subTest(text=text):
                with self.assertRaises(WechatGroupMembershipNoticeConfigError):
                    validate_membership_notice_template(text, "join")

    def test_template_values_use_readable_names_and_fallbacks_without_runtime_ids(self):
        values = build_membership_notice_template_values("leave", {
            "room_name": "测试群",
            "self_name": "LightBot",
            "timestamp": 0,
            "members": [
                {"sender_id": "wxid_raw", "sender_nickname": "wxid_raw"},
                {"sender_id": "wxid_bob", "room_alias": "小波"},
            ],
            "remover": {"sender_id": "wxid_admin", "sender_nickname": "管理员小王"},
        }, now=1785217200)

        self.assertEqual(values["member_names"], "群成员、小波")
        self.assertEqual(values["member_count"], "2")
        self.assertEqual(values["remover_name"], "管理员小王")
        self.assertNotIn("wxid_", " ".join(values.values()))
        rendered = render_membership_notice_template(
            "{member_names} 已离开 {room_name}，操作人：{remover_name}",
            "leave",
            values,
        )
        self.assertEqual(rendered, "群成员、小波 已离开 测试群，操作人：管理员小王")

    def test_image_path_rejects_url_absolute_and_traversal(self):
        valid = "images/wechat_group_membership/example.png"
        self.assertEqual(normalize_membership_notice_image_path(valid), valid)
        for path in (
            "https://example.test/image.png",
            "C:\\temp\\image.png",
            "../images/wechat_group_membership/image.png",
            "images/wechat_group_membership/../../secret.png",
            "....//images/wechat_group_membership/image.png",
            "images/wechat_group_membership/image.svg",
        ):
            with self.subTest(path=path):
                with self.assertRaises(WechatGroupMembershipNoticeConfigError):
                    normalize_membership_notice_image_path(path, required=True)

    def test_resolve_image_path_stays_in_membership_directory(self):
        with tempfile.TemporaryDirectory() as workspace:
            relative = "images/wechat_group_membership/example.png"
            absolute = os.path.join(workspace, *relative.split("/"))
            os.makedirs(os.path.dirname(absolute), exist_ok=True)
            with open(absolute, "wb") as file_obj:
                file_obj.write(b"png")

            self.assertEqual(
                resolve_membership_notice_image_path(workspace, relative),
                os.path.realpath(absolute),
            )

    def test_image_content_uses_decoded_format_and_rejects_fake_image(self):
        from io import BytesIO
        from PIL import Image

        output = BytesIO()
        Image.new("RGB", (2, 2), "white").save(output, format="PNG")

        self.assertEqual(validate_membership_notice_image_bytes(output.getvalue()), ".png")
        with self.assertRaises(WechatGroupMembershipNoticeConfigError):
            validate_membership_notice_image_bytes(output.getvalue(), "fake.jpg")
        with self.assertRaises(WechatGroupMembershipNoticeConfigError):
            validate_membership_notice_image_bytes(b"<svg></svg>")


if __name__ == "__main__":
    unittest.main()
