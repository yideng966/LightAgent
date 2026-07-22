import time
import unittest

from bridge.context import ContextType
from channel.wechat_group.wechat_group_message import WechatGroupMessage
from channel.wechat_group.protocol import SidecarEventType, parse_sidecar_event


class WechatGroupMessageTest(unittest.TestCase):
    def test_parse_message_event_to_group_chat_message(self):
        raw = {
            "type": SidecarEventType.MESSAGE,
            "message_id": "msg-1",
            "timestamp": 1710000000,
            "room_id": "room@@abc",
            "room_name": "测试群",
            "sender_id": "wxid_alice",
            "sender_name": "Alice",
            "self_id": "wxid_bot",
            "self_name": "LightBot",
            "text": "@LightBot hello",
            "is_at": True,
            "at_list": ["wxid_bot"],
            "message_type": "text",
        }

        msg = WechatGroupMessage(parse_sidecar_event(raw))

        self.assertEqual("msg-1", msg.msg_id)
        self.assertEqual(ContextType.TEXT, msg.ctype)
        self.assertEqual("@LightBot hello", msg.content)
        self.assertTrue(msg.is_group)
        self.assertTrue(msg.is_at)
        self.assertEqual("room@@abc", msg.from_user_id)
        self.assertEqual("测试群", msg.from_user_nickname)
        self.assertEqual("wxid_bot", msg.to_user_id)
        self.assertEqual("LightBot", msg.to_user_nickname)
        self.assertEqual("room@@abc", msg.other_user_id)
        self.assertEqual("测试群", msg.other_user_nickname)
        self.assertEqual("wxid_alice", msg.actual_user_id)
        self.assertEqual("Alice", msg.actual_user_nickname)
        self.assertEqual(["wxid_bot"], msg.at_list)
        self.assertFalse(msg.my_msg)

    def test_parse_self_message_marks_my_msg(self):
        raw = {
            "type": "message",
            "message_id": "msg-2",
            "timestamp": int(time.time()),
            "room_id": "room@@abc",
            "room_name": "测试群",
            "sender_id": "wxid_bot",
            "sender_name": "LightBot",
            "self_id": "wxid_bot",
            "self_name": "LightBot",
            "text": "self message",
            "message_type": "text",
        }

        msg = WechatGroupMessage(parse_sidecar_event(raw))

        self.assertTrue(msg.my_msg)
        self.assertFalse(msg.is_at)

    def test_parse_quote_self_message_metadata(self):
        raw = {
            "type": "message",
            "message_id": "msg-quote",
            "timestamp": int(time.time()),
            "room_id": "room@@abc",
            "room_name": "Test Room",
            "sender_id": "wxid_alice",
            "sender_name": "Alice",
            "self_id": "@bot",
            "self_name": "LightBot",
            "text": "What about this?",
            "message_type": "text",
            "is_quote_self": True,
            "quote": {
                "sender_id": "@bot",
                "sender_name": "LightBot",
                "message_id": "123456",
                "type": "1",
                "content": "previous answer",
            },
            "quote_diagnostics": {
                "status": "resolved",
                "source": "puppet_cache",
                "method_error": "id_not_found",
                "has_content": True,
                "msg_type": "49",
                "parse_status": "quote_parsed",
                "xml_candidate_count": 2,
                "parsed_candidate_count": 1,
                "raw_xml": "<msg>secret</msg>",
                "media_path": "C:/private/quote.jpg",
            },
        }

        msg = WechatGroupMessage(parse_sidecar_event(raw))

        self.assertTrue(msg.is_quote_self)
        self.assertEqual("@bot", msg.quote["sender_id"])
        self.assertEqual("previous answer", msg.quote["content"])
        self.assertEqual(
            {
                "status": "resolved",
                "source": "puppet_cache",
                "method_error": "id_not_found",
                "parse_status": "quote_parsed",
                "has_content": True,
                "msg_type": "49",
                "xml_candidate_count": 2,
                "parsed_candidate_count": 1,
            },
            msg.quote_diagnostics,
        )
        self.assertNotIn("raw_xml", msg.quote_diagnostics)
        self.assertNotIn("media_path", msg.quote_diagnostics)

    def test_parse_pat_self_text_message_metadata(self):
        raw = {
            "type": SidecarEventType.MESSAGE,
            "message_id": "msg-pat-self",
            "timestamp": 1710000000,
            "room_id": "room@@abc",
            "room_name": "Test Room",
            "sender_id": "room@@abc",
            "sender_name": "Test Room",
            "self_id": "wxid_bot",
            "self_name": "LightBot",
            "text": "\"Alice\" 拍了拍我",
            "message_type": "text",
        }

        msg = WechatGroupMessage(parse_sidecar_event(raw))

        self.assertTrue(msg.is_pat_self)
        self.assertEqual("Alice", msg.pat_actor_name)
        self.assertEqual("我", msg.pat_target_name)
        self.assertEqual("\"Alice\" 拍了拍我", msg.content)

    def test_parse_forward_preview_metadata(self):
        raw = {
            "type": "message",
            "message_id": "msg-forward",
            "timestamp": int(time.time()),
            "room_id": "room@@abc",
            "room_name": "Test Room",
            "sender_id": "wxid_alice",
            "sender_name": "Alice",
            "self_id": "@bot",
            "self_name": "LightBot",
            "text": "[聊天记录]",
            "message_type": "text",
            "raw_app_type": "19",
            "forward": {
                "title": "聊天记录",
                "description": "Alice: 明天早上十点发版",
                "source": "Alice",
                "record_count_hint": 3,
            },
        }

        msg = WechatGroupMessage(parse_sidecar_event(raw))

        self.assertEqual("19", msg.raw_app_type)
        self.assertEqual("聊天记录", msg.forward["title"])
        self.assertEqual("Alice: 明天早上十点发版", msg.forward["description"])

    def test_parse_identity_fingerprint_metadata_without_changing_legacy_ids(self):
        raw = {
            "type": SidecarEventType.MESSAGE,
            "message_id": "msg-identity",
            "timestamp": 1710000000,
            "room_id": "room@@runtime",
            "room_name": "测试群",
            "sender_id": "wxid_runtime_alice",
            "sender_name": "Alice",
            "self_id": "wxid_runtime_bot",
            "self_name": "LightBot",
            "text": "hello",
            "message_type": "text",
            "runtime_room_id": "room@@runtime",
            "runtime_sender_id": "wxid_runtime_alice",
            "runtime_self_id": "wxid_runtime_bot",
            "account_fingerprint": {
                "runtime_self_id": "wxid_runtime_bot",
                "self_name": "LightBot",
            },
            "room_fingerprint": {
                "runtime_room_id": "room@@runtime",
                "room_name": "测试群",
                "self_runtime_id": "wxid_runtime_bot",
            },
            "member_fingerprint": {
                "runtime_sender_id": "wxid_runtime_alice",
                "display_name": "Alice",
                "room_alias": "阿狸",
                "wechat_id": "alice_wechat",
            },
        }

        msg = WechatGroupMessage(parse_sidecar_event(raw))

        self.assertEqual("room@@runtime", msg.other_user_id)
        self.assertEqual("wxid_runtime_alice", msg.actual_user_id)
        self.assertEqual("wxid_runtime_bot", msg.to_user_id)
        self.assertEqual("room@@runtime", msg.runtime_room_id)
        self.assertEqual("wxid_runtime_alice", msg.runtime_sender_id)
        self.assertEqual("wxid_runtime_bot", msg.runtime_self_id)
        self.assertEqual("alice_wechat", msg.member_fingerprint["wechat_id"])
        self.assertEqual("阿狸", msg.identity_fingerprint_metadata["member"]["room_alias"])


if __name__ == "__main__":
    unittest.main()
