import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from agent.memory.conversation_store import ConversationStore
from bridge.reply import Reply, ReplyType
from channel.wechat_group.wechat_group_channel import WechatGroupChannel
from channel.wechat_group.wechat_group_continuation_store import (
    WechatGroupContinuationStore,
)
from config import conf


class FakeClient:
    def __init__(self, status):
        self.status = status
        self.confirmed_calls = []
        self.legacy_calls = []

    def send_text_confirmed(self, room_id, text, mention_ids=None):
        self.confirmed_calls.append((room_id, text, list(mention_ids or [])))
        return self.status

    def send_text(self, room_id, text, mention_ids=None):
        self.legacy_calls.append((room_id, text, list(mention_ids or [])))


class WechatGroupConfirmedSendTest(unittest.TestCase):
    def setUp(self):
        self.original = {
            "wechat_group_context_engine_mode": conf().get(
                "wechat_group_context_engine_mode"
            ),
            "wechat_group_response_cleanup_enabled": conf().get(
                "wechat_group_response_cleanup_enabled"
            ),
            "wechat_group_record_messages": conf().get(
                "wechat_group_record_messages"
            ),
        }
        conf()["wechat_group_context_engine_mode"] = "v2"
        conf()["wechat_group_response_cleanup_enabled"] = False
        conf()["wechat_group_record_messages"] = True

    def tearDown(self):
        for key, value in self.original.items():
            if value is None:
                conf().pop(key, None)
            else:
                conf()[key] = value

    @staticmethod
    def _channel(status):
        channel = WechatGroupChannel.__new__(WechatGroupChannel)
        channel.client = FakeClient(status)
        channel.archive = Mock()
        channel.archive.record_assistant_reply.return_value = 1
        channel._simulate_typing_delay_if_needed = lambda _reply: None
        channel._build_reply_mentions = lambda _context: ["runtime-member"]
        channel._record_emotion_reply = lambda _context: None
        channel._record_sticker_reply = lambda _reply, _context: None
        channel._wechat_group_rolling_summary_service = None
        channel._sync_cached_agent_thread = lambda _session_id, _thread_id: 0
        return channel

    @staticmethod
    def _context():
        return {
            "receiver": "runtime-room",
            "wechat_group_stable_room_id": "wgr_room",
            "wechat_group_runtime_room_id": "runtime-room",
            "wechat_group_thread_id": "wgt_thread",
            "request_id": "request-1",
            "isgroup": True,
        }

    @classmethod
    def _pending_context(cls):
        context = cls._context()
        context["session_id"] = "wechat_group:wgr_room:wgm_alice"
        context["wechat_group_pending_agent_delivery"] = {
            "state": "pending",
            "owner_session_id": context["session_id"],
            "thread_id": context["wechat_group_thread_id"],
            "request_id": context["request_id"],
            "action": "new_thread",
            "stable_room_id": "wgr_room",
            "stable_member_id": "wgm_alice",
            "message_id": "inbound-message-1",
            "ttl_seconds": 900,
            "reason": "independent_request",
            "continuation_capsule": {
                "tool_name": "web_fetch",
                "argument_summary": "{\"url\": \"https://example.com\"}",
                "result_summary": "public result",
                "status": "success",
            },
            "continuation_ttl_seconds": 600,
        }
        return context

    @staticmethod
    def _stage_pending_turn(store, context):
        store.append_messages(
            context["session_id"],
            [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": "question"}],
                    "extras": {
                        "delivery_state": "pending",
                        "delivery_request_id": context["request_id"],
                        "source_event_id": "inbound:7",
                    },
                },
                {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "raw answer"}],
                    "extras": {
                        "delivery_state": "pending",
                        "delivery_request_id": context["request_id"],
                    },
                },
            ],
            channel_type="wechat_group",
            thread_id=context["wechat_group_thread_id"],
        )

    def test_failed_or_unknown_send_is_not_archived(self):
        for status in ("failed", "unknown"):
            with self.subTest(status=status):
                channel = self._channel(status)

                channel.send(Reply(ReplyType.TEXT, "answer"), self._context())

                self.assertEqual(1, len(channel.client.confirmed_calls))
                channel.archive.record_assistant_reply.assert_not_called()

    def test_confirmed_send_is_archived_after_ack(self):
        channel = self._channel("sent")

        channel.send(Reply(ReplyType.TEXT, "answer"), self._context())

        channel.archive.record_assistant_reply.assert_called_once()
        kwargs = channel.archive.record_assistant_reply.call_args.kwargs
        self.assertEqual("wgt_thread", kwargs["thread_id"])
        self.assertEqual("request-1", kwargs["request_id"])

    def test_pending_turn_is_hidden_then_discarded_when_send_is_not_confirmed(self):
        for status in ("failed", "unknown"):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as tmpdir:
                store = ConversationStore(Path(tmpdir) / "conversations.db")
                continuation = WechatGroupContinuationStore(
                    str(Path(tmpdir) / "continuations.db")
                )
                context = self._pending_context()
                self._stage_pending_turn(store, context)
                channel = self._channel(status)

                self.assertEqual(
                    [],
                    store.load_messages(
                        context["session_id"],
                        thread_id=context["wechat_group_thread_id"],
                    ),
                )
                self.assertEqual(
                    [],
                    store.load_history_page(context["session_id"])["messages"],
                )

                with patch(
                    "agent.memory.get_conversation_store",
                    return_value=store,
                ), patch(
                    "channel.wechat_group.wechat_group_continuation_store."
                    "WechatGroupContinuationStore",
                    return_value=continuation,
                ):
                    channel.send(Reply(ReplyType.TEXT, "sent answer"), context)

                self.assertEqual(
                    [],
                    store.load_messages(
                        context["session_id"],
                        thread_id=context["wechat_group_thread_id"],
                    ),
                )
                self.assertIsNone(
                    store.get_thread(
                        context["session_id"],
                        context["wechat_group_thread_id"],
                    )
                )
                self.assertEqual("discarded", context[
                    "wechat_group_pending_agent_delivery"
                ]["state"])
                self.assertEqual(
                    "",
                    continuation.get_prompt_block(
                        context["session_id"],
                        context["wechat_group_thread_id"],
                        "wgr_room",
                        "wgm_alice",
                    ),
                )

    def test_confirmed_send_commits_clean_text_thread_and_continuation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ConversationStore(Path(tmpdir) / "conversations.db")
            continuation = WechatGroupContinuationStore(
                str(Path(tmpdir) / "continuations.db")
            )
            context = self._pending_context()
            self._stage_pending_turn(store, context)
            channel = self._channel("sent")
            channel.archive.record_assistant_reply.return_value = 11

            with patch(
                "agent.memory.get_conversation_store",
                return_value=store,
            ), patch(
                "channel.wechat_group.wechat_group_continuation_store."
                "WechatGroupContinuationStore",
                return_value=continuation,
            ):
                channel.send(Reply(ReplyType.TEXT, "cleaned answer"), context)

            messages = store.load_messages(
                context["session_id"],
                thread_id=context["wechat_group_thread_id"],
            )
            self.assertEqual(
                ["question", "cleaned answer"],
                [item["content"][0]["text"] for item in messages],
            )
            self.assertEqual(
                ["inbound:7", "assistant:11"],
                store.get_thread_source_event_ids(
                    context["session_id"],
                    context["wechat_group_thread_id"],
                ),
            )
            self.assertEqual(
                context["wechat_group_thread_id"],
                store.get_active_thread(context["session_id"])["thread_id"],
            )
            self.assertEqual("committed", context[
                "wechat_group_pending_agent_delivery"
            ]["state"])
            self.assertIn(
                "public result",
                continuation.get_prompt_block(
                    context["session_id"],
                    context["wechat_group_thread_id"],
                    "wgr_room",
                    "wgm_alice",
                ),
            )


if __name__ == "__main__":
    unittest.main()
