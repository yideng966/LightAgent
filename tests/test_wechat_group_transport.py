import html
import unittest

from channel.wechat_group.wechat_group_transport import (
    detect_wechat_transport_message_type,
    is_wechat_transport_metadata_term,
    project_wechat_media_semantic_text,
)


WECHAT_IMAGE_TRANSPORT_XML = """<?xml version="1.0"?>
<msg>
  <img aeskey="masked" cdnthumburl="masked" md5="masked" hevc_mid_size="31347" />
</msg>
"""

WECHAT_STICKER_TRANSPORT_XML = """<?xml version="1.0"?>
<msg>
  <emoji aeskey="masked" cdnurl="masked" md5="masked" />
</msg>
"""


class WechatGroupTransportTest(unittest.TestCase):
    def test_detects_image_transport_xml(self):
        self.assertEqual(
            "image",
            detect_wechat_transport_message_type(WECHAT_IMAGE_TRANSPORT_XML),
        )

    def test_detects_sticker_transport_xml(self):
        self.assertEqual(
            "sticker",
            detect_wechat_transport_message_type(WECHAT_STICKER_TRANSPORT_XML),
        )

    def test_detects_double_html_escaped_transport_xml(self):
        encoded = html.escape(html.escape(WECHAT_IMAGE_TRANSPORT_XML))

        self.assertEqual("image", detect_wechat_transport_message_type(encoded))

    def test_ignores_plain_html_image_and_protocol_field_discussion(self):
        self.assertEqual(
            "",
            detect_wechat_transport_message_type('<img src="cat.png" alt="cat">'),
        )
        self.assertEqual(
            "",
            detect_wechat_transport_message_type("hevc_mid_size=31347 是微信图片协议字段"),
        )

    def test_identifies_transport_metadata_terms_only(self):
        for value in ("aeskey", "cdnthumburl=", "CDNURL", "hevc_mid_size", "encrypturl"):
            self.assertTrue(is_wechat_transport_metadata_term(value), value)
        for value in ("hevc", "image", "release", "讨论 hevc_mid_size 字段"):
            self.assertFalse(is_wechat_transport_metadata_term(value), value)

    def test_projects_only_explicit_safe_media_semantic_text(self):
        self.assertEqual(
            "[sticker: 小猫捂脸表示无奈]",
            project_wechat_media_semantic_text(
                "sticker",
                WECHAT_STICKER_TRANSPORT_XML,
                {"media_semantic_text": "小猫捂脸表示无奈"},
            ),
        )
        for semantic in (
            WECHAT_STICKER_TRANSPORT_XML,
            r"C:\private\sticker.gif",
            "https://example.test/private.png",
            "cdnurl=secret",
        ):
            self.assertEqual(
                "",
                project_wechat_media_semantic_text(
                    "sticker",
                    WECHAT_STICKER_TRANSPORT_XML,
                    {"media_semantic_text": semantic},
                ),
            )


if __name__ == "__main__":
    unittest.main()
