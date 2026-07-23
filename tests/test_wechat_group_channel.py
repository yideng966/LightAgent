import os
import sqlite3
import tempfile
import threading
import unittest
from contextlib import closing
from unittest.mock import Mock, call, patch

from agent.tools.base_tool import ToolResult
from bridge.context import Context, ContextType
from bridge.reply import Reply, ReplyType
from channel.channel_factory import create_channel
from channel.wechat_group.protocol import SidecarEventType, parse_sidecar_event
from channel.wechat_group.wechat_group_client import WechatGroupClient
from channel.wechat_group.wechat_group_channel import (
    WECHAT_GROUP_DEFAULT_IMAGE_REPLY_QUESTION,
    WechatGroupChannel,
)
from channel.wechat_group.wechat_group_archive import WechatGroupArchive
from channel.wechat_group.wechat_group_message import WechatGroupMessage
from common import const
from config import conf


WECHAT_IMAGE_TRANSPORT_XML = """<?xml version="1.0"?>
<msg>
  <img aeskey="masked" cdnthumburl="masked" md5="masked" hevc_mid_size="31347" />
</msg>
"""


class FakeClient:
    def __init__(self):
        self.commands = []
        self.started = False
        self.stopped = False
        self.force_rescanned = False
        self.force_rescan_error = None
        self.force_rescan_hook = None
        self.error = ""

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def force_rescan(self):
        self.force_rescanned = True
        if self.force_rescan_hook:
            self.force_rescan_hook()
        if self.force_rescan_error:
            raise self.force_rescan_error

    def poll_error(self):
        return self.error

    def send_text(self, room_id, text, mention_ids=None):
        self.commands.append(("send_text", room_id, text, mention_ids or []))

    def send_file(self, room_id, path):
        self.commands.append(("send_file", room_id, path))

    def send_image(self, room_id, path):
        self.commands.append(("send_image", room_id, path))

    def send_audio(self, room_id, path):
        self.commands.append(("send_audio", room_id, path))

    def list_rooms(self):
        self.commands.append(("list_rooms",))

    def list_room_members(self, room_id, request_id=None, query=""):
        self.commands.append(("list_room_members", room_id, request_id or "", query or ""))


class CapturingClient(WechatGroupClient):
    def __init__(self):
        super().__init__()
        self.sent = []

    def send_command(self, command):
        self.sent.append(command.to_json())


class WechatGroupChannelTest(unittest.TestCase):
    def setUp(self):
        self._original_config = {
            "wechat_group_room_ids": conf().get("wechat_group_room_ids"),
            "wechat_group_stable_room_ids": conf().get("wechat_group_stable_room_ids"),
            "wechat_group_names": conf().get("wechat_group_names"),
            "wechat_group_sidecar_memory_path": conf().get("wechat_group_sidecar_memory_path"),
            "wechat_group_admin_sender_ids": conf().get("wechat_group_admin_sender_ids"),
            "wechat_group_admin_members": conf().get("wechat_group_admin_members"),
            "wechat_group_admin_required_permissions": conf().get("wechat_group_admin_required_permissions"),
            "wechat_group_blacklist_members": conf().get("wechat_group_blacklist_members"),
            "wechat_group_alias_sync_cooldown_minutes": conf().get("wechat_group_alias_sync_cooldown_minutes"),
            "group_name_white_list": conf().get("group_name_white_list"),
            "group_shared_session": conf().get("group_shared_session"),
            "wechat_group_free_reply_enabled": conf().get("wechat_group_free_reply_enabled"),
            "wechat_group_voice_interaction_mode": conf().get("wechat_group_voice_interaction_mode"),
            "wechat_group_free_reply_room_ids": conf().get("wechat_group_free_reply_room_ids"),
            "wechat_group_free_reply_stable_room_ids": conf().get("wechat_group_free_reply_stable_room_ids"),
            "wechat_group_blocked_stable_member_ids": conf().get("wechat_group_blocked_stable_member_ids"),
            "wechat_group_blocked_sender_ids": conf().get("wechat_group_blocked_sender_ids"),
            "wechat_group_free_reply_names": conf().get("wechat_group_free_reply_names"),
            "wechat_group_free_reply_force_keywords": conf().get("wechat_group_free_reply_force_keywords"),
            "wechat_group_free_reply_activity_level": conf().get("wechat_group_free_reply_activity_level"),
            "wechat_group_free_reply_mute_minutes": conf().get("wechat_group_free_reply_mute_minutes"),
            "wechat_group_free_reply_mute_mentions_enabled": conf().get("wechat_group_free_reply_mute_mentions_enabled"),
            "wechat_group_recent_context_enabled": conf().get("wechat_group_recent_context_enabled"),
            "wechat_group_knowledge_enabled": conf().get("wechat_group_knowledge_enabled"),
            "wechat_group_profile_enabled": conf().get("wechat_group_profile_enabled"),
            "wechat_group_focus_enabled": conf().get("wechat_group_focus_enabled"),
            "wechat_group_focus_recent_message_limit": conf().get("wechat_group_focus_recent_message_limit"),
            "wechat_group_focus_context_message_limit": conf().get("wechat_group_focus_context_message_limit"),
            "wechat_group_focus_stack_depth": conf().get("wechat_group_focus_stack_depth"),
            "wechat_group_focus_stale_rounds": conf().get("wechat_group_focus_stale_rounds"),
            "wechat_group_focus_min_keywords": conf().get("wechat_group_focus_min_keywords"),
            "wechat_group_style_enabled": conf().get("wechat_group_style_enabled"),
            "wechat_group_emotion_enabled": conf().get("wechat_group_emotion_enabled"),
            "wechat_group_free_reply_typing_delay_enabled": conf().get("wechat_group_free_reply_typing_delay_enabled"),
            "wechat_group_free_reply_typing_chars_per_second": conf().get("wechat_group_free_reply_typing_chars_per_second"),
            "wechat_group_response_cleanup_enabled": conf().get("wechat_group_response_cleanup_enabled"),
            "wechat_group_response_cleanup_max_chars": conf().get("wechat_group_response_cleanup_max_chars"),
            "wechat_group_image_understanding_enabled": conf().get("wechat_group_image_understanding_enabled"),
            "wechat_group_image_understanding_comment_enabled": conf().get("wechat_group_image_understanding_comment_enabled"),
            "wechat_group_image_understanding_prompt": conf().get("wechat_group_image_understanding_prompt"),
            "wechat_group_image_understanding_cache_minutes": conf().get("wechat_group_image_understanding_cache_minutes"),
            "wechat_group_free_reply_image_understanding_enabled": conf().get("wechat_group_free_reply_image_understanding_enabled"),
            "wechat_group_multimodal_context_enabled": conf().get("wechat_group_multimodal_context_enabled"),
            "wechat_group_multimodal_image_understanding_context_enabled": conf().get("wechat_group_multimodal_image_understanding_context_enabled"),
            "wechat_group_multimodal_free_reply_image_context_enabled": conf().get("wechat_group_multimodal_free_reply_image_context_enabled"),
            "wechat_group_multimodal_same_sender_window_seconds": conf().get("wechat_group_multimodal_same_sender_window_seconds"),
            "wechat_group_multimodal_unique_image_window_seconds": conf().get("wechat_group_multimodal_unique_image_window_seconds"),
            "wechat_group_multimodal_quote_sender_window_minutes": conf().get("wechat_group_multimodal_quote_sender_window_minutes"),
            "wechat_group_multimodal_max_recent_messages": conf().get("wechat_group_multimodal_max_recent_messages"),
            "wechat_group_image_create_hourly_limit": conf().get("wechat_group_image_create_hourly_limit"),
            "wechat_group_video_understanding_enabled": conf().get("wechat_group_video_understanding_enabled"),
            "wechat_group_forward_preview_enabled": conf().get("wechat_group_forward_preview_enabled"),
            "wechat_group_quote_context_enabled": conf().get("wechat_group_quote_context_enabled"),
            "wechat_group_sticker_enabled": conf().get("wechat_group_sticker_enabled"),
            "wechat_group_sticker_auto_collect_enabled": conf().get("wechat_group_sticker_auto_collect_enabled"),
            "image_create_prefix": conf().get("image_create_prefix"),
            "agent": conf().get("agent"),
            "skills": conf().get("skills"),
            "tools": conf().get("tools"),
        }

    def tearDown(self):
        for key, value in self._original_config.items():
            if value is None:
                conf().pop(key, None)
            else:
                conf()[key] = value

    def test_factory_creates_wechat_group_channel(self):
        channel = create_channel(const.WECHAT_GROUP)

        self.assertIsInstance(channel, WechatGroupChannel)

    def test_record_inbound_message_notifies_profile_evolution_signal(self):
        conf()["wechat_group_record_messages"] = True
        with tempfile.TemporaryDirectory() as tmp:
            archive = WechatGroupArchive(os.path.join(tmp, "archive.db"))
            channel = WechatGroupChannel(client=Mock(), archive=archive)
            msg = WechatGroupMessage(parse_sidecar_event({
                "type": "message",
                "message_id": "profile-signal-1",
                "room_id": "room@@abc",
                "room_name": "Test Room",
                "sender_id": "wxid_alice",
                "sender_name": "Alice",
                "self_id": "wxid_bot",
                "self_name": "LightBot",
                "text": "hello",
                "timestamp": 1000,
            }))

            with patch("channel.wechat_group.wechat_group_profile_evolution_trigger.note_wechat_group_profile_signal") as note:
                channel._record_inbound_message(msg)

            row = archive.get_message_by_id("room@@abc", "profile-signal-1")
            self.assertIsNotNone(row)
            note.assert_called_once_with("room@@abc", archive_row_id=row["id"])
        self.assertEqual(const.WECHAT_GROUP, channel.channel_type)

    def test_record_inbound_message_keeps_runtime_media_path_metadata(self):
        conf()["wechat_group_record_messages"] = True
        with tempfile.TemporaryDirectory() as tmp:
            archive = WechatGroupArchive(os.path.join(tmp, "archive.db"))
            channel = WechatGroupChannel(client=Mock(), archive=archive)
            msg = WechatGroupMessage(parse_sidecar_event({
                "type": "message",
                "message_id": "media-metadata-1",
                "room_id": "room@@runtime",
                "room_name": "Test Room",
                "sender_id": "wxid_runtime",
                "sender_name": "Alice",
                "self_id": "wxid_bot",
                "self_name": "LightBot",
                "message_type": "image",
                "file_path": "D:/lightagent/wechat_group/media/room@@runtime/photo.jpg",
                "timestamp": 1000,
            }))
            msg.wechat_group_stable_room_id = "wgr_room"
            msg.wechat_group_stable_member_id = "wgm_alice"

            channel._record_inbound_message(msg)

            row = archive.get_message_by_id("wgr_room", "media-metadata-1")
            self.assertEqual("D:/lightagent/wechat_group/media/room@@runtime/photo.jpg", row["media_path"])
            self.assertEqual(
                "D:/lightagent/wechat_group/media/room@@runtime/photo.jpg",
                row["metadata"]["runtime_media_path"],
            )
            self.assertEqual("", row["metadata"]["stable_media_path"])
            self.assertEqual("runtime_legacy", row["metadata"]["media_path_storage"])

    def test_record_inbound_message_keeps_sanitized_quote_diagnostics(self):
        conf()["wechat_group_record_messages"] = True
        with tempfile.TemporaryDirectory() as tmp:
            archive = WechatGroupArchive(os.path.join(tmp, "archive.db"))
            channel = WechatGroupChannel(client=Mock(), archive=archive)
            msg = WechatGroupMessage(parse_sidecar_event({
                "type": "message",
                "message_id": "quote-diagnostics-1",
                "room_id": "room@@runtime",
                "room_name": "Test Room",
                "sender_id": "wxid_runtime",
                "sender_name": "Alice",
                "self_id": "wxid_bot",
                "self_name": "LightBot",
                "text": "What does this image mean?",
                "timestamp": 1000,
                "quote_diagnostics": {
                    "status": "resolved",
                    "source": "puppet_cache",
                    "parse_status": "quote_parsed",
                    "xml_candidate_count": 1,
                    "raw_xml": "<msg>secret</msg>",
                    "media_path": "C:/private/quote.jpg",
                },
            }))

            channel._record_inbound_message(msg)

            row = archive.get_message_by_id("room@@runtime", "quote-diagnostics-1")
            diagnostics = row["metadata"]["quote_diagnostics"]
            self.assertEqual("resolved", diagnostics["status"])
            self.assertEqual("puppet_cache", diagnostics["source"])
            self.assertEqual("quote_parsed", diagnostics["parse_status"])
            self.assertEqual(1, diagnostics["xml_candidate_count"])
            self.assertNotIn("raw_xml", diagnostics)
            self.assertNotIn("media_path", diagnostics)

    def test_assistant_reply_archive_keeps_stable_and_runtime_room(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = WechatGroupArchive(os.path.join(tmp, "archive.db"))

            archive.record_assistant_reply(
                room_id="wgr_room",
                room_name="Stable Room",
                content="hello",
                stable_room_id="wgr_room",
                runtime_room_id="room@@new",
            )

            self.assertEqual("Stable Room", archive.find_room_name("wgr_room"))
            with closing(sqlite3.connect(archive.db_path)) as conn:
                row = conn.execute(
                    "SELECT room_id, stable_room_id, runtime_room_id FROM wechat_group_assistant_replies"
                ).fetchone()
            self.assertEqual(("wgr_room", "wgr_room", "room@@new"), row)

    def test_channel_does_not_keep_legacy_image_understanding_builders(self):
        from channel.wechat_group.wechat_group_channel import WechatGroupChannel

        legacy_names = [
            name for name in (
                "_build_recent_image_understanding_content",
                "_build_image_understanding_content",
                "_build_multimodal_context_block",
                "_build_quote_multimodal_section",
                "_build_forward_multimodal_section",
                "_build_video_multimodal_section",
            )
            if hasattr(WechatGroupChannel, name)
        ]

        self.assertEqual([], legacy_names)

    def test_startup_reports_sidecar_error_without_login_success(self):
        client = FakeClient()
        client.error = "sidecar failed"
        channel = WechatGroupChannel(client=client)

        channel.startup()

        success, error = channel.wait_startup(timeout=0)
        self.assertTrue(client.started)
        self.assertFalse(success)
        self.assertEqual("sidecar failed", error)
        self.assertEqual(channel.STATUS_ERROR, channel.status)
        self.assertEqual("sidecar failed", channel.last_error)

    def test_startup_success_keeps_status_starting_before_qr_or_login(self):
        client = FakeClient()
        channel = WechatGroupChannel(client=client)

        channel.startup()

        success, error = channel.wait_startup(timeout=0)
        self.assertTrue(client.started)
        self.assertTrue(success)
        self.assertEqual("", error)
        self.assertEqual(channel.STATUS_STARTING, channel.status)

    def test_force_rescan_clears_runtime_login_state_before_client_restart(self):
        client = FakeClient()
        channel = WechatGroupChannel(client=client)
        channel.status = channel.STATUS_CONNECTED
        channel.last_error = "old error"
        channel.qr_code = "old qr"
        channel.rooms = [{"room_id": "room@@old"}]
        channel.user_id = "wxid_old"
        channel.name = "Old User"
        channel.room_members = {"room@@old": [{"sender_id": "wxid_member"}]}
        channel.report_startup_error("old startup error")
        observed = {}

        def capture_state_before_restart():
            observed.update({
                "status": channel.status,
                "last_error": channel.last_error,
                "qr_code": channel.qr_code,
                "rooms": list(channel.rooms),
                "user_id": channel.user_id,
                "name": channel.name,
                "room_members": dict(channel.room_members),
                "startup_event_set": channel._startup_event.is_set(),
                "startup_error": channel._startup_error,
            })

        client.force_rescan_hook = capture_state_before_restart

        channel.force_rescan()

        self.assertTrue(client.force_rescanned)
        self.assertEqual({
            "status": channel.STATUS_STARTING,
            "last_error": "",
            "qr_code": "",
            "rooms": [],
            "user_id": "",
            "name": "",
            "room_members": {},
            "startup_event_set": False,
            "startup_error": None,
        }, observed)
        self.assertEqual(channel.STATUS_STARTING, channel.status)
        success, error = channel.wait_startup(timeout=0)
        self.assertTrue(success)
        self.assertEqual("", error)

    def test_force_rescan_reports_error_and_reraises_client_failure(self):
        client = FakeClient()
        client.force_rescan_error = RuntimeError("login cache is locked")
        channel = WechatGroupChannel(client=client)
        channel.status = channel.STATUS_CONNECTED
        channel.qr_code = "old qr"
        channel.rooms = [{"room_id": "room@@old"}]
        channel.user_id = "wxid_old"
        channel.name = "Old User"
        channel.room_members = {"room@@old": [{"sender_id": "wxid_member"}]}
        channel.report_startup_success()

        with self.assertRaisesRegex(RuntimeError, "login cache is locked"):
            channel.force_rescan()

        self.assertTrue(client.force_rescanned)
        self.assertEqual(channel.STATUS_ERROR, channel.status)
        self.assertEqual("login cache is locked", channel.last_error)
        self.assertEqual("", channel.qr_code)
        self.assertEqual([], channel.rooms)
        self.assertEqual("", channel.user_id)
        self.assertEqual("", channel.name)
        self.assertEqual({}, channel.room_members)
        success, error = channel.wait_startup(timeout=0)
        self.assertFalse(success)
        self.assertEqual("login cache is locked", error)

    def test_sidecar_events_update_login_status(self):
        identity_service = Mock()
        identity_service.resolve_account.return_value = Mock(
            stable_id="wga_account",
            status="legacy_imported",
            requires_confirmation=True,
        )
        identity_service.resolve_room.return_value = Mock(
            stable_id="wgr_room",
            status="legacy_imported",
            confidence="candidate",
            requires_confirmation=True,
        )
        channel = WechatGroupChannel(client=FakeClient(), identity_service=identity_service)

        self.assertTrue(channel.consume_sidecar_event(parse_sidecar_event({
            "type": SidecarEventType.QR,
            "qrcode": "qr-data",
            "url": "https://example.test/qr",
        })))
        self.assertEqual(channel.STATUS_QR_READY, channel.status)
        self.assertEqual("qr-data", channel.qr_code)

        self.assertTrue(channel.consume_sidecar_event(parse_sidecar_event({
            "type": SidecarEventType.STATUS,
            "status": channel.STATUS_LOGGED_IN,
            "self_id": "wxid_bot",
            "self_name": "LightBot",
        })))
        self.assertEqual(channel.STATUS_LOGGED_IN, channel.status)

        self.assertTrue(channel.consume_sidecar_event(parse_sidecar_event({
            "type": SidecarEventType.ROOMS,
            "rooms": [{"room_id": "room@@abc", "name": "Test Room"}],
        })))
        self.assertEqual(channel.STATUS_CONNECTED, channel.status)
        self.assertEqual("room@@abc", channel.rooms[0]["runtime_room_id"])
        self.assertEqual("wgr_room", channel.rooms[0]["stable_room_id"])
        self.assertEqual("legacy_imported", channel.rooms[0]["binding_status"])
        self.assertTrue(channel.rooms[0]["identity_requires_confirmation"])

    @staticmethod
    def _build_identity_message(message_id, room_id, sender_id):
        return WechatGroupMessage(parse_sidecar_event({
            "type": SidecarEventType.MESSAGE,
            "message_id": message_id,
            "room_id": room_id,
            "room_name": "Same Room",
            "sender_id": sender_id,
            "sender_name": sender_id,
            "self_id": "self_a",
            "self_name": "LightBot",
            "text": "@LightBot hello",
            "message_type": "text",
            "is_at": True,
            "at_list": ["self_a"],
            "account_fingerprint": {"runtime_self_id": "self_a", "self_name": "LightBot"},
            "room_fingerprint": {"runtime_room_id": room_id, "room_name": "Same Room"},
            "member_fingerprint": {"runtime_sender_id": sender_id, "display_name": sender_id},
        }))

    def test_room_sync_isolates_duplicate_names_within_same_account(self):
        from channel.wechat_group.wechat_group_identity_service import WechatGroupIdentityService
        from channel.wechat_group.wechat_group_identity_store import WechatGroupIdentityStore

        with tempfile.TemporaryDirectory() as tmp:
            identity_service = WechatGroupIdentityService(
                WechatGroupIdentityStore(os.path.join(tmp, "identity.db"))
            )
            channel = WechatGroupChannel(client=FakeClient(), identity_service=identity_service)
            channel.user_id = "self_a"
            channel.name = "LightBot"

            rooms = channel._enrich_rooms_with_stable_identity([
                {"room_id": "room@@first", "name": "Same Room"},
                {"room_id": "room@@second", "name": "Same Room"},
            ])

        stable_room_ids = [room.get("stable_room_id") for room in rooms]
        self.assertTrue(all(str(room_id).startswith("wgr_") for room_id in stable_room_ids))
        self.assertEqual(2, len(set(stable_room_ids)))

    def test_room_sync_duplicate_rows_still_recover_unique_room_name(self):
        from channel.wechat_group.wechat_group_client import get_wechat_group_sidecar_memory_path
        from channel.wechat_group.wechat_group_identity_service import WechatGroupIdentityService
        from channel.wechat_group.wechat_group_identity_store import WechatGroupIdentityStore

        with tempfile.TemporaryDirectory() as tmp:
            identity_service = WechatGroupIdentityService(
                WechatGroupIdentityStore(os.path.join(tmp, "identity.db"))
            )
            account = identity_service.resolve_account(
                "self_a",
                "LightBot",
                get_wechat_group_sidecar_memory_path(),
                {},
            )
            previous = identity_service.resolve_room(
                account.stable_id,
                "room@@old",
                "Same Room",
                "self_a",
                {},
            )
            channel = WechatGroupChannel(client=FakeClient(), identity_service=identity_service)
            channel.user_id = "self_a"
            channel.name = "LightBot"

            rooms = channel._enrich_rooms_with_stable_identity([
                {"room_id": "room@@new", "name": "Same Room"},
                {"room_id": "room@@new", "name": "Same Room"},
            ])

        self.assertEqual(
            [previous.stable_id, previous.stable_id],
            [room.get("stable_room_id") for room in rooms],
        )

    def test_messages_before_room_sync_isolate_duplicate_names_in_current_session(self):
        from channel.wechat_group.wechat_group_identity_service import WechatGroupIdentityService
        from channel.wechat_group.wechat_group_identity_store import WechatGroupIdentityStore

        with tempfile.TemporaryDirectory() as tmp:
            identity_service = WechatGroupIdentityService(
                WechatGroupIdentityStore(os.path.join(tmp, "identity.db"))
            )
            channel = WechatGroupChannel(client=FakeClient(), identity_service=identity_service)

            first = channel._resolve_message_identity(
                self._build_identity_message("msg-1", "room@@first", "sender-1")
            )
            second = channel._resolve_message_identity(
                self._build_identity_message("msg-2", "room@@second", "sender-2")
            )

        self.assertNotEqual(
            first.get("wechat_group_stable_room_id"),
            second.get("wechat_group_stable_room_id"),
        )

    def test_failed_duplicate_room_resolution_retry_stays_isolated(self):
        from channel.wechat_group.wechat_group_identity_service import WechatGroupIdentityService
        from channel.wechat_group.wechat_group_identity_store import WechatGroupIdentityStore

        with tempfile.TemporaryDirectory() as tmp:
            identity_service = WechatGroupIdentityService(
                WechatGroupIdentityStore(os.path.join(tmp, "identity.db"))
            )
            real_resolve_room = identity_service.resolve_room
            failed_second_room_once = False

            def resolve_room_with_transient_failure(*args, **kwargs):
                nonlocal failed_second_room_once
                runtime_room_id = args[1]
                if runtime_room_id == "room@@second" and not failed_second_room_once:
                    failed_second_room_once = True
                    raise RuntimeError("transient room resolution failure")
                return real_resolve_room(*args, **kwargs)

            identity_service.resolve_room = resolve_room_with_transient_failure
            channel = WechatGroupChannel(client=FakeClient(), identity_service=identity_service)

            first = channel._resolve_message_identity(
                self._build_identity_message("msg-1", "room@@first", "sender-1")
            )
            failed = channel._resolve_message_identity(
                self._build_identity_message("msg-2", "room@@second", "sender-2")
            )
            retried = channel._resolve_message_identity(
                self._build_identity_message("msg-3", "room@@second", "sender-2")
            )

        self.assertEqual({}, failed)
        self.assertTrue(retried.get("wechat_group_stable_room_id"))
        self.assertNotEqual(
            first.get("wechat_group_stable_room_id"),
            retried.get("wechat_group_stable_room_id"),
        )

    def test_concurrent_duplicate_room_resolution_is_serialized(self):
        from channel.wechat_group.wechat_group_identity_service import WechatGroupIdentityService
        from channel.wechat_group.wechat_group_identity_store import WechatGroupIdentityStore

        with tempfile.TemporaryDirectory() as tmp:
            identity_service = WechatGroupIdentityService(
                WechatGroupIdentityStore(os.path.join(tmp, "identity.db"))
            )
            real_resolve_room = identity_service.resolve_room
            first_room_entered = threading.Event()
            release_first_room = threading.Event()
            second_worker_started = threading.Event()
            second_room_entered = threading.Event()
            results = {}
            errors = {}

            def controlled_resolve_room(*args, **kwargs):
                runtime_room_id = args[1]
                if runtime_room_id == "room@@first":
                    first_room_entered.set()
                    if not release_first_room.wait(5):
                        raise TimeoutError("first room resolution was not released")
                elif runtime_room_id == "room@@second":
                    second_room_entered.set()
                return real_resolve_room(*args, **kwargs)

            identity_service.resolve_room = controlled_resolve_room
            channel = WechatGroupChannel(client=FakeClient(), identity_service=identity_service)

            def resolve_message(key, message, started_event=None):
                if started_event is not None:
                    started_event.set()
                try:
                    results[key] = channel._resolve_message_identity(message)
                except BaseException as e:
                    errors[key] = e

            first_thread = threading.Thread(
                target=resolve_message,
                args=("first", self._build_identity_message("msg-1", "room@@first", "sender-1")),
            )
            second_thread = None
            second_entered_before_release = False
            try:
                first_thread.start()
                self.assertTrue(first_room_entered.wait(5), "first room did not enter resolve_room")
                second_thread = threading.Thread(
                    target=resolve_message,
                    args=(
                        "second",
                        self._build_identity_message("msg-2", "room@@second", "sender-2"),
                        second_worker_started,
                    ),
                )
                second_thread.start()
                self.assertTrue(second_worker_started.wait(5), "second worker did not start")
                second_entered_before_release = second_room_entered.wait(0.5)
            finally:
                release_first_room.set()
                first_thread.join(5)
                if second_thread is not None:
                    second_thread.join(5)

        self.assertFalse(first_thread.is_alive())
        self.assertIsNotNone(second_thread)
        self.assertFalse(second_thread.is_alive())
        self.assertEqual({}, errors)
        first_room_id = results.get("first", {}).get("wechat_group_stable_room_id")
        second_room_id = results.get("second", {}).get("wechat_group_stable_room_id")
        self.assertFalse(
            second_entered_before_release,
            "second room entered resolve_room before release: first={} second={}".format(
                first_room_id,
                second_room_id,
            ),
        )
        self.assertTrue(first_room_id)
        self.assertTrue(second_room_id)
        self.assertNotEqual(first_room_id, second_room_id)

    def test_new_logged_in_transition_clears_session_room_name_isolation(self):
        from channel.wechat_group.wechat_group_identity_service import WechatGroupIdentityService
        from channel.wechat_group.wechat_group_identity_store import WechatGroupIdentityStore

        with tempfile.TemporaryDirectory() as tmp:
            identity_service = WechatGroupIdentityService(
                WechatGroupIdentityStore(os.path.join(tmp, "identity.db"))
            )
            channel = WechatGroupChannel(client=FakeClient(), identity_service=identity_service)
            channel.status = channel.STATUS_CONNECTED

            first = channel._resolve_message_identity(
                self._build_identity_message("msg-1", "room@@first", "sender-1")
            )
            self.assertTrue(channel.consume_sidecar_event(parse_sidecar_event({
                "type": SidecarEventType.STATUS,
                "status": channel.STATUS_LOGGED_IN,
                "self_id": "self_a",
                "self_name": "LightBot",
            })))
            second = channel._resolve_message_identity(
                self._build_identity_message("msg-2", "room@@second", "sender-2")
            )

        self.assertEqual(
            first.get("wechat_group_stable_room_id"),
            second.get("wechat_group_stable_room_id"),
        )

    def test_repeated_logged_in_status_keeps_session_room_name_isolation(self):
        from channel.wechat_group.wechat_group_identity_service import WechatGroupIdentityService
        from channel.wechat_group.wechat_group_identity_store import WechatGroupIdentityStore

        with tempfile.TemporaryDirectory() as tmp:
            identity_service = WechatGroupIdentityService(
                WechatGroupIdentityStore(os.path.join(tmp, "identity.db"))
            )
            channel = WechatGroupChannel(client=FakeClient(), identity_service=identity_service)

            self.assertTrue(channel.consume_sidecar_event(parse_sidecar_event({
                "type": SidecarEventType.STATUS,
                "status": channel.STATUS_LOGGED_IN,
                "self_id": "self_a",
                "self_name": "LightBot",
            })))
            first = channel._resolve_message_identity(
                self._build_identity_message("msg-1", "room@@first", "sender-1")
            )
            self.assertTrue(channel.consume_sidecar_event(parse_sidecar_event({
                "type": SidecarEventType.STATUS,
                "status": channel.STATUS_LOGGED_IN,
                "self_id": "self_a",
                "self_name": "LightBot",
            })))
            second = channel._resolve_message_identity(
                self._build_identity_message("msg-2", "room@@second", "sender-2")
            )

        self.assertNotEqual(
            first.get("wechat_group_stable_room_id"),
            second.get("wechat_group_stable_room_id"),
        )

    def test_room_sync_uses_effective_default_sidecar_memory_path(self):
        conf()["wechat_group_sidecar_memory_path"] = ""
        identity_service = Mock()
        identity_service.resolve_account.return_value = Mock(
            stable_id="wga_account",
            status="confirmed",
            confidence="profile",
            requires_confirmation=False,
        )
        channel = WechatGroupChannel(client=FakeClient(), identity_service=identity_service)
        channel.user_id = "self_a"
        channel.name = "LightBot"

        channel._enrich_rooms_with_stable_identity([])

        expected_path = os.path.join(os.path.expanduser("~"), ".lightagent", "wechat_group")
        self.assertEqual(expected_path, identity_service.resolve_account.call_args.args[2])

    def test_rooms_event_does_not_mutate_profile_names(self):
        class FakeProfileService:
            def __init__(self):
                self.called = False

            def repair_historical_profile_names(self, room_name_by_id=None):
                self.called = True
                raise AssertionError("room sync must not rewrite profile names")

        service = FakeProfileService()
        channel = WechatGroupChannel(client=FakeClient(), profile_service=service)

        self.assertTrue(channel.consume_sidecar_event(parse_sidecar_event({
            "type": SidecarEventType.ROOMS,
            "rooms": [
                {"id": "room@@abc", "name": "Test Room"},
                {"room_id": "room@@legacy", "name": "Legacy Room"},
                {"id": "room@@blank", "name": ""},
            ],
        })))

        self.assertFalse(service.called)

    def test_rooms_event_keeps_connected_status_without_profile_repair(self):
        class FailingProfileService:
            def __init__(self):
                self.called = False

            def repair_historical_profile_names(self, room_name_by_id=None):
                self.called = True
                raise RuntimeError("repair failed")

        service = FailingProfileService()
        channel = WechatGroupChannel(client=FakeClient(), profile_service=service)
        channel.status = channel.STATUS_LOGGED_IN

        self.assertTrue(channel.consume_sidecar_event(parse_sidecar_event({
            "type": SidecarEventType.ROOMS,
            "rooms": [{"id": "room@@abc", "name": "Test Room"}],
        })))

        self.assertFalse(service.called)
        self.assertEqual(channel.STATUS_CONNECTED, channel.status)
        self.assertEqual([{"id": "room@@abc", "name": "Test Room"}], channel.rooms)

    def test_error_before_login_marks_channel_error(self):
        channel = WechatGroupChannel(client=FakeClient())
        channel.status = channel.STATUS_QR_READY

        self.assertTrue(channel.consume_sidecar_event(parse_sidecar_event({
            "type": SidecarEventType.ERROR,
            "message": "login failed",
        })))

        success, error = channel.wait_startup(timeout=0)
        self.assertFalse(success)
        self.assertEqual("login failed", error)
        self.assertEqual(channel.STATUS_ERROR, channel.status)
        self.assertEqual("login failed", channel.last_error)

    def test_error_after_connected_does_not_drop_login_status(self):
        channel = WechatGroupChannel(client=FakeClient())
        channel.status = channel.STATUS_LOGGED_IN

        self.assertTrue(channel.consume_sidecar_event(parse_sidecar_event({
            "type": SidecarEventType.ROOMS,
            "rooms": [{"room_id": "room@@abc", "name": "Test Room"}],
        })))
        self.assertEqual(channel.STATUS_CONNECTED, channel.status)

        self.assertTrue(channel.consume_sidecar_event(parse_sidecar_event({
            "type": SidecarEventType.ERROR,
            "message": "non fatal sidecar warning",
        })))

        self.assertEqual(channel.STATUS_CONNECTED, channel.status)
        self.assertEqual("non fatal sidecar warning", channel.last_error)

    def test_duplicate_and_self_messages_are_ignored(self):
        channel = WechatGroupChannel(client=FakeClient())
        channel.handle_text = Mock()
        event = parse_sidecar_event({
            "type": SidecarEventType.MESSAGE,
            "message_id": "msg-1",
            "room_id": "room@@abc",
            "room_name": "测试群",
            "sender_id": "wxid_alice",
            "sender_name": "Alice",
            "self_id": "wxid_bot",
            "self_name": "LightBot",
            "text": "@LightBot hello",
            "is_at": True,
            "at_list": ["wxid_bot"],
        })

        self.assertTrue(channel.consume_sidecar_event(event))
        self.assertFalse(channel.consume_sidecar_event(event))

        self_msg = parse_sidecar_event({
            "type": "message",
            "message_id": "msg-2",
            "room_id": "room@@abc",
            "room_name": "测试群",
            "sender_id": "wxid_bot",
            "sender_name": "LightBot",
            "self_id": "wxid_bot",
            "self_name": "LightBot",
            "text": "self",
        })
        self.assertFalse(channel.consume_sidecar_event(self_msg))
        self.assertEqual(1, channel.handle_text.call_count)

    def test_unselected_room_id_is_ignored_before_group_name_matching(self):
        conf()["wechat_group_room_ids"] = ["room@@allowed"]
        conf()["wechat_group_names"] = []
        channel = WechatGroupChannel(client=FakeClient())
        channel.handle_text = Mock()

        ignored = parse_sidecar_event({
            "type": "message",
            "message_id": "msg-3",
            "room_id": "room@@blocked",
            "room_name": "测试群",
            "sender_id": "wxid_alice",
            "sender_name": "Alice",
            "self_id": "wxid_bot",
            "self_name": "LightBot",
            "text": "@LightBot hello",
            "is_at": True,
            "at_list": ["wxid_bot"],
        })
        allowed = parse_sidecar_event({
            "type": "message",
            "message_id": "msg-4",
            "room_id": "room@@allowed",
            "room_name": "测试群",
            "sender_id": "wxid_alice",
            "sender_name": "Alice",
            "self_id": "wxid_bot",
            "self_name": "LightBot",
            "text": "@LightBot hello",
            "is_at": True,
            "at_list": ["wxid_bot"],
        })

        self.assertFalse(channel.consume_sidecar_event(ignored))
        self.assertTrue(channel.consume_sidecar_event(allowed))
        self.assertEqual(1, channel.handle_text.call_count)

    def test_unselected_room_logs_info_without_message_text(self):
        conf()["wechat_group_stable_room_ids"] = ["wgr_allowed"]
        conf()["wechat_group_room_ids"] = ["room@@allowed"]
        conf()["wechat_group_names"] = []
        channel = WechatGroupChannel(client=FakeClient())
        channel.handle_text = Mock()
        channel._resolve_message_identity = Mock(return_value={})
        event = parse_sidecar_event({
            "type": "message",
            "message_id": "msg-route-filtered",
            "room_id": "room@@blocked",
            "room_name": "Blocked Room",
            "sender_id": "sender-alice",
            "sender_name": "Alice",
            "self_id": "sender-bot",
            "self_name": "LightBot",
            "text": "TOP SECRET MESSAGE BODY",
            "is_at": True,
            "at_list": ["sender-bot"],
        })

        with self.assertLogs("log", level="INFO") as captured:
            accepted = channel.consume_sidecar_event(event)

        output = "\n".join(captured.output)
        self.assertFalse(accepted)
        self.assertIn("reason=unselected_room", output)
        self.assertIn("msg-route-filtered", output)
        self.assertIn("room@@blocked", output)
        self.assertNotIn("TOP SECRET MESSAGE BODY", output)
        channel.handle_text.assert_not_called()

    def test_selected_room_name_is_allowed_after_automatic_identity_resolution(self):
        conf()["wechat_group_room_ids"] = []
        conf()["wechat_group_stable_room_ids"] = []
        conf()["wechat_group_names"] = ["Trusted Room"]
        ignored = Mock(
            other_user_id="room@@other",
            other_user_nickname="Other Room",
            wechat_group_stable_room_id="wgr_other",
            wechat_group_room_identity_requires_confirmation=False,
        )
        allowed = Mock(
            other_user_id="room@@trusted",
            other_user_nickname="Trusted Room",
            wechat_group_stable_room_id="wgr_trusted",
            wechat_group_room_identity_requires_confirmation=False,
        )

        self.assertFalse(WechatGroupChannel._is_selected_room(ignored))
        self.assertTrue(WechatGroupChannel._is_selected_room(allowed))

    def test_unconfirmed_stable_room_is_blocked_until_binding_is_confirmed(self):
        conf()["wechat_group_stable_room_ids"] = ["wgr_room"]
        msg = Mock(
            other_user_id="room@@runtime",
            other_user_nickname="Test Room",
            wechat_group_stable_room_id="wgr_room",
            stable_room_id="wgr_room",
            wechat_group_room_identity_requires_confirmation=True,
        )

        self.assertFalse(WechatGroupChannel._is_selected_room(msg))

        msg.wechat_group_room_identity_requires_confirmation = False
        self.assertTrue(WechatGroupChannel._is_selected_room(msg))

    def test_selected_room_id_enters_group_context_without_group_name_whitelist(self):
        conf()["wechat_group_room_ids"] = ["room@@allowed"]
        conf()["group_name_white_list"] = []
        channel = WechatGroupChannel(client=FakeClient())
        msg = Mock(
            ctype=ContextType.TEXT,
            content="@LightBot hello",
            from_user_id="room@@allowed",
            other_user_id="room@@allowed",
            other_user_nickname="Not In Whitelist",
            actual_user_id="wxid_alice",
            actual_user_nickname="Alice",
            to_user_id="wxid_bot",
            is_at=True,
            at_list=["wxid_bot"],
            self_display_name="LightBot",
            quote={},
            forward={},
            raw_app_type="",
            media_path="",
            message_type="text",
            msg_id="msg-image-create-default-prefix",
        )

        context = channel._compose_context(
            ContextType.TEXT,
            msg.content,
            isgroup=True,
            msg=msg,
        )

        self.assertIsNotNone(context)
        self.assertEqual("room@@allowed", context["receiver"])

    def test_stable_room_selection_runs_before_runtime_room_whitelist(self):
        from channel.wechat_group.wechat_group_identity_service import WechatGroupIdentityService
        from channel.wechat_group.wechat_group_identity_store import WechatGroupIdentityStore

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        store = WechatGroupIdentityStore(os.path.join(tmp.name, "identity.db"))
        store.upsert_account("wga_account", display_name="Bot", status="confirmed", confidence="manual")
        store.upsert_room("wgr_room", "wga_account", canonical_name="测试群", status="confirmed", confidence="manual")
        store.upsert_member("wgm_alice", "wgr_room", "wga_account", display_name="Alice", status="confirmed", confidence="manual")
        store.activate_account_alias("wga_account", "wxid_bot", self_name="LightBot")
        store.activate_room_alias("wga_account", "wgr_room", "room@@new", room_name="测试群")
        store.activate_member_alias("wga_account", "wgr_room", "wgm_alice", "wxid_new", runtime_room_id="room@@new")
        conf()["wechat_group_room_ids"] = []
        conf()["wechat_group_stable_room_ids"] = ["wgr_room"]
        conf()["wechat_group_names"] = []
        conf()["group_name_white_list"] = []
        conf()["group_shared_session"] = True

        channel = WechatGroupChannel(
            client=FakeClient(),
            archive=WechatGroupArchive(os.path.join(tmp.name, "archive.db")),
            identity_service=WechatGroupIdentityService(store=store),
        )
        raw = {
            "type": SidecarEventType.MESSAGE,
            "message_id": "msg-stable",
            "room_id": "room@@new",
            "room_name": "测试群",
            "sender_id": "wxid_new",
            "sender_name": "Alice",
            "self_id": "wxid_bot",
            "self_name": "LightBot",
            "text": "@LightBot hello",
            "message_type": "text",
            "is_at": True,
            "at_list": ["wxid_bot"],
            "account_fingerprint": {"runtime_self_id": "wxid_bot", "self_name": "LightBot"},
            "room_fingerprint": {"runtime_room_id": "room@@new", "room_name": "测试群"},
            "member_fingerprint": {"runtime_sender_id": "wxid_new", "display_name": "Alice"},
        }
        msg = WechatGroupMessage(parse_sidecar_event(raw))

        with patch("channel.wechat_group.wechat_group_profile_evolution_trigger.note_wechat_group_profile_signal") as note_signal:
            context = channel._compose_context(ContextType.TEXT, msg.content, isgroup=True, msg=msg)

        self.assertIsNotNone(context)
        self.assertEqual("room@@new", context["receiver"])
        self.assertEqual("wgr_room", context["wechat_group_stable_receiver"])
        self.assertEqual("wechat_group:wgr_room", context["session_id"])
        self.assertEqual("room@@new", context["wechat_group_room_id"])
        self.assertEqual("wxid_new", context["wechat_group_sender_id"])
        self.assertEqual("wgr_room", context["wechat_group_stable_room_id"])
        self.assertEqual("wgm_alice", context["wechat_group_stable_member_id"])
        archived = channel.archive.get_message_by_id("wgr_room", "msg-stable")
        self.assertEqual("room@@new", archived["runtime_room_id"])
        self.assertEqual("wgr_room", archived["stable_room_id"])
        note_signal.assert_called_once()
        self.assertEqual("wgr_room", note_signal.call_args.args[0])

    def test_wechat_group_scheduler_request_sets_scheduler_intent(self):
        conf()["wechat_group_room_ids"] = ["room@@allowed"]
        conf()["group_name_white_list"] = []
        channel = WechatGroupChannel(client=FakeClient())
        msg = Mock(
            ctype=ContextType.TEXT,
            content="@LightBot 每天12点在本群里面播报世界杯比赛结果",
            from_user_id="room@@allowed",
            other_user_id="room@@allowed",
            other_user_nickname="Not In Whitelist",
            actual_user_id="wxid_alice",
            actual_user_nickname="Alice",
            to_user_id="wxid_bot",
            is_at=True,
            at_list=["wxid_bot"],
            self_display_name="LightBot",
        )

        context = channel._compose_context(
            ContextType.TEXT,
            msg.content,
            isgroup=True,
            msg=msg,
        )

        self.assertIsNotNone(context)
        self.assertTrue(context["intent_requires_scheduler"])

    def test_wechat_group_image_create_uses_builtin_prefix_when_config_missing(self):
        conf()["wechat_group_room_ids"] = ["room@@allowed"]
        conf()["group_name_white_list"] = []
        conf().pop("image_create_prefix", None)
        channel = WechatGroupChannel(client=FakeClient())
        msg = Mock(
            ctype=ContextType.TEXT,
            content="@LightBot \u753b\u4e2a\u5154\u5b50",
            from_user_id="room@@allowed",
            other_user_id="room@@allowed",
            other_user_nickname="Not In Whitelist",
            actual_user_id="wxid_alice",
            actual_user_nickname="Alice",
            to_user_id="wxid_bot",
            is_at=True,
            at_list=["wxid_bot"],
            self_display_name="LightBot",
        )

        context = channel._compose_context(
            ContextType.TEXT,
            msg.content,
            isgroup=True,
            msg=msg,
        )

        self.assertIsNotNone(context)
        self.assertEqual(ContextType.IMAGE_CREATE, context.type)
        self.assertEqual("\u4e2a\u5154\u5b50", context.content)

    def test_wechat_group_free_reply_text_starting_with_find_does_not_create_image(self):
        conf()["wechat_group_room_ids"] = ["room@@allowed"]
        conf()["group_name_white_list"] = []
        conf().pop("image_create_prefix", None)
        channel = WechatGroupChannel(client=FakeClient())
        msg = Mock(
            ctype=ContextType.TEXT,
            content="\u627e\u5230\u95ee\u9898\u6211\u5c31\u4e0d\u8bf4\u4e86 \u5173\u952e\u662f\u4ec0\u4e48\u90fd\u6ca1\u627e\u5230",
            from_user_id="room@@allowed",
            other_user_id="room@@allowed",
            other_user_nickname="Not In Whitelist",
            actual_user_id="wxid_alice",
            actual_user_nickname="Alice",
            to_user_id="wxid_bot",
            is_at=False,
            at_list=[],
            self_display_name="LightBot",
            is_group=True,
            quote={},
            forward={},
            raw_app_type="",
            media_path="",
            message_type="text",
            msg_id="msg-find-text",
        )

        context = channel._compose_context(
            ContextType.TEXT,
            msg.content,
            isgroup=True,
            msg=msg,
            wechat_group_force_reply=True,
        )

        self.assertIsNotNone(context)
        self.assertEqual(ContextType.TEXT, context.type)
        self.assertIn("\u627e\u5230\u95ee\u9898", context.content)

    def test_send_text_reply_to_original_room_with_sender_mention(self):
        client = FakeClient()
        channel = WechatGroupChannel(client=client)
        context = {
            "type": ContextType.TEXT,
            "receiver": "room@@abc",
            "msg": Mock(
                is_group=True,
                actual_user_id="wxid_alice",
                actual_user_nickname="Alice",
            ),
        }

        channel.send(Reply(ReplyType.TEXT, "hello"), context)

        self.assertEqual(
            [("send_text", "room@@abc", "hello", ["wxid_alice"])],
            client.commands,
        )

    def test_send_pat_self_reply_does_not_mention_room_sender(self):
        client = FakeClient()
        channel = WechatGroupChannel(client=client)
        context = {
            "type": ContextType.TEXT,
            "receiver": "room@@abc",
            "wechat_group_trigger_source": "pat_self",
            "msg": Mock(
                is_group=True,
                actual_user_id="room@@abc",
                actual_user_nickname="Test Room",
                is_pat_self=True,
            ),
        }

        channel.send(Reply(ReplyType.TEXT, "在"), context)

        self.assertEqual(
            [("send_text", "room@@abc", "在", [])],
            client.commands,
        )

    def test_pat_self_text_enters_forced_reply_context(self):
        conf()["wechat_group_room_ids"] = ["room@@abc"]
        conf()["group_name_white_list"] = []
        channel = WechatGroupChannel(client=FakeClient())
        channel.produce = Mock()
        channel.free_reply_worker.submit = Mock()
        context = {"receiver": "room@@abc", "msg": Mock()}
        channel._compose_context = Mock(return_value=context)
        msg = WechatGroupMessage(parse_sidecar_event({
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
        }))

        channel.handle_text(msg)

        channel.free_reply_worker.submit.assert_not_called()
        channel._compose_context.assert_called_once()
        _, content = channel._compose_context.call_args.args[:2]
        kwargs = channel._compose_context.call_args.kwargs
        self.assertEqual("\"Alice\" 拍了拍我", content)
        self.assertTrue(kwargs["wechat_group_force_reply"])
        self.assertEqual("pat_self", kwargs["wechat_group_trigger_source"])
        channel.produce.assert_called_once_with(context)

    def test_send_silent_reply_notice_is_not_sent_to_group(self):
        conf()["wechat_group_free_reply_typing_delay_enabled"] = False
        client = FakeClient()
        channel = WechatGroupChannel(client=client)
        context = {
            "type": ContextType.TEXT,
            "receiver": "room@@abc",
            "msg": Mock(is_group=True, actual_user_id="wxid_alice"),
        }

        channel.send(Reply(ReplyType.TEXT, "（没@我，不插嘴）"), context)

        self.assertEqual([], client.commands)

    def test_send_internal_non_reply_reason_is_not_sent_to_group(self):
        conf()["wechat_group_free_reply_typing_delay_enabled"] = False
        client = FakeClient()
        channel = WechatGroupChannel(client=client)
        context = {
            "type": ContextType.TEXT,
            "receiver": "room@@abc",
            "msg": Mock(is_group=True, actual_user_id="wxid_alice"),
        }

        channel.send(
            Reply(ReplyType.TEXT, "（这不是在问我，是Mr.J在回春希的图，我不用插嘴）"),
            context,
        )

        self.assertEqual([], client.commands)

    def test_send_long_text_containing_silent_phrase_is_not_suppressed(self):
        conf()["wechat_group_free_reply_typing_delay_enabled"] = False
        client = FakeClient()
        channel = WechatGroupChannel(client=client)
        context = {
            "type": ContextType.TEXT,
            "receiver": "room@@abc",
            "msg": Mock(is_group=True, actual_user_id="wxid_alice"),
        }

        channel.send(Reply(ReplyType.TEXT, "这句话的意思是：没@我，不插嘴，表示机器人不会主动接话。"), context)

        self.assertEqual(
            [("send_text", "room@@abc", "这句话的意思是：没@我，不插嘴，表示机器人不会主动接话。", ["wxid_alice"])],
            client.commands,
        )

    def test_send_business_error_reply_to_original_room_with_sender_mention(self):
        client = FakeClient()
        channel = WechatGroupChannel(client=client)
        context = {
            "type": ContextType.TEXT,
            "receiver": "room@@abc",
            "msg": Mock(
                is_group=True,
                actual_user_id="wxid_alice",
                actual_user_nickname="Alice",
            ),
        }

        channel.send(Reply(ReplyType.ERROR, "需要管理员权限执行"), context)

        self.assertEqual(
            [("send_text", "room@@abc", "需要管理员权限执行", ["wxid_alice"])],
            client.commands,
        )

    def test_send_non_agent_timeout_error_is_not_suppressed(self):
        client = FakeClient()
        channel = WechatGroupChannel(client=client)
        context = {
            "type": ContextType.TEXT,
            "receiver": "room@@abc",
            "msg": Mock(
                is_group=True,
                actual_user_id="wxid_alice",
                actual_user_nickname="Alice",
            ),
        }

        channel.send(
            Reply(ReplyType.ERROR, "Tool execution timeout, please retry."),
            context,
        )

        self.assertEqual(
            [("send_text", "room@@abc", "Tool execution timeout, please retry.", ["wxid_alice"])],
            client.commands,
        )

    def test_send_suppresses_transient_agent_error_when_not_forced(self):
        client = FakeClient()
        channel = WechatGroupChannel(client=client)
        context = {
            "type": ContextType.TEXT,
            "receiver": "room@@abc",
            "msg": Mock(
                is_group=True,
                actual_user_id="wxid_alice",
                actual_user_nickname="Alice",
            ),
        }

        channel.send(
            Reply(
                ReplyType.ERROR,
                "Agent error: Rate limit exceeded. Please try again later. "
                "(Status: 429, Code: , Type: FreeUsageLimitError)",
            ),
            context,
        )

        self.assertEqual([], client.commands)

    def test_send_forced_transient_agent_error_uses_token_exhausted_hint(self):
        client = FakeClient()
        channel = WechatGroupChannel(client=client)
        context = {
            "type": ContextType.TEXT,
            "receiver": "room@@abc",
            "wechat_group_force_reply": True,
            "msg": Mock(
                is_group=True,
                actual_user_id="wxid_alice",
                actual_user_nickname="Alice",
            ),
        }

        channel.send(
            Reply(
                ReplyType.ERROR,
                "Agent error: Rate limit exceeded. Please try again later. "
                "(Status: 429, Code: , Type: FreeUsageLimitError)",
            ),
            context,
        )

        self.assertEqual(
            [("send_text", "room@@abc", "别@我了哥，没Token了。", ["wxid_alice"])],
            client.commands,
        )

    def test_send_text_reply_can_simulate_typing_delay(self):
        conf()["wechat_group_free_reply_typing_delay_enabled"] = True
        conf()["wechat_group_free_reply_typing_chars_per_second"] = 7
        client = FakeClient()
        channel = WechatGroupChannel(client=client)
        context = {
            "type": ContextType.TEXT,
            "receiver": "room@@abc",
            "msg": Mock(
                is_group=True,
                actual_user_id="wxid_alice",
                actual_user_nickname="Alice",
            ),
        }

        with patch("channel.wechat_group.wechat_group_channel.time.sleep") as sleep:
            channel.send(Reply(ReplyType.TEXT, "1234567"), context)

        self.assertIn(call(1.0), sleep.call_args_list)
        self.assertEqual(
            [("send_text", "room@@abc", "1234567", ["wxid_alice"])],
            client.commands,
        )

    def test_send_cleans_text_before_typing_and_archive(self):
        conf()["wechat_group_response_cleanup_enabled"] = True
        conf()["wechat_group_response_cleanup_max_chars"] = 200
        conf()["wechat_group_free_reply_typing_delay_enabled"] = True
        conf()["wechat_group_free_reply_typing_chars_per_second"] = 7
        client = FakeClient()
        archive = Mock()
        channel = WechatGroupChannel(client=client, archive=archive)
        context = {
            "type": ContextType.TEXT,
            "receiver": "room@@abc",
            "msg": Mock(
                is_group=True,
                actual_user_id="wxid_alice",
                actual_user_nickname="Alice",
                other_user_nickname="Room",
            ),
        }
        content = "<wechat-group-reply-policy>\ninternal\n</wechat-group-reply-policy>\nI can help with that: ship Friday"

        with patch("channel.wechat_group.wechat_group_channel.time.sleep") as sleep:
            channel.send(Reply(ReplyType.TEXT, content), context)

        self.assertEqual(
            [("send_text", "room@@abc", "ship Friday", ["wxid_alice"])],
            client.commands,
        )
        self.assertIn(call(len("ship Friday") / 7.0), sleep.call_args_list)
        archive.record_assistant_reply.assert_called_once()
        self.assertEqual("ship Friday", archive.record_assistant_reply.call_args.kwargs["content"])

    def test_send_strips_markdown_before_wechat_group_delivery_and_archive(self):
        conf()["wechat_group_response_cleanup_enabled"] = True
        conf()["wechat_group_response_cleanup_max_chars"] = 800
        client = FakeClient()
        archive = Mock()
        channel = WechatGroupChannel(client=client, archive=archive)
        context = {
            "type": ContextType.TEXT,
            "receiver": "room@@abc",
            "msg": Mock(
                is_group=True,
                actual_user_id="wxid_alice",
                actual_user_nickname="Alice",
                other_user_nickname="Room",
            ),
        }

        channel.send(Reply(ReplyType.TEXT, "**结论**\n* 今天先别发版"), context)

        self.assertEqual(
            [("send_text", "room@@abc", "结论\n今天先别发版", ["wxid_alice"])],
            client.commands,
        )
        self.assertEqual(
            "结论\n今天先别发版",
            archive.record_assistant_reply.call_args.kwargs["content"],
        )

    def test_decorated_group_reply_does_not_prefix_plain_text_at(self):
        client = FakeClient()
        channel = WechatGroupChannel(client=client)
        context = {
            "isgroup": True,
            "receiver": "room@@abc",
            "msg": Mock(
                is_group=True,
                actual_user_id="wxid_alice",
                actual_user_nickname="Alice",
            ),
        }

        reply = channel._decorate_reply(context, Reply(ReplyType.TEXT, "hello"))
        channel.send(reply, context)

        self.assertEqual(
            [("send_text", "room@@abc", "hello", ["wxid_alice"])],
            client.commands,
        )

    def test_decorated_group_error_reply_does_not_include_error_prefix(self):
        channel = WechatGroupChannel(client=FakeClient())
        context = {
            "isgroup": True,
            "receiver": "room@@abc",
            "msg": Mock(
                is_group=True,
                actual_user_id="wxid_alice",
                actual_user_nickname="Alice",
            ),
        }

        reply = channel._decorate_reply(
            context,
            Reply(ReplyType.ERROR, "累了不想画了，你跪安吧。"),
        )

        self.assertEqual(ReplyType.ERROR, reply.type)
        self.assertEqual("累了不想画了，你跪安吧。", reply.content)

    def test_client_builds_media_send_commands(self):
        client = CapturingClient()

        client.send_image("room@@abc", "D:/tmp/a.png")
        client.send_file("room@@abc", "D:/tmp/a.txt")
        client.send_audio("room@@abc", "D:/tmp/a.mp3")

        self.assertEqual(
            [
                {"type": "send_image", "room_id": "room@@abc", "path": "D:/tmp/a.png"},
                {"type": "send_file", "room_id": "room@@abc", "path": "D:/tmp/a.txt"},
                {"type": "send_audio", "room_id": "room@@abc", "path": "D:/tmp/a.mp3"},
            ],
            client.sent,
        )

    def test_client_send_text_includes_alias_sync_cooldown_minutes(self):
        conf()["wechat_group_alias_sync_cooldown_minutes"] = 5
        client = CapturingClient()

        client.send_text("room@@abc", "hello", mention_ids=["wxid_alice"])

        self.assertEqual(
            [
                {
                    "type": "send_text",
                    "room_id": "room@@abc",
                    "text": "hello",
                    "mention_ids": ["wxid_alice"],
                    "alias_sync_cooldown_minutes": 5,
                }
            ],
            client.sent,
        )

    def test_client_list_room_members_includes_request_id_and_query(self):
        client = CapturingClient()

        client.list_room_members("room@@abc", request_id="req-1", query="yideng0803")

        self.assertEqual(
            [{"type": "list_room_members", "room_id": "room@@abc", "request_id": "req-1", "query": "yideng0803"}],
            client.sent,
        )

    def test_sticker_collection_skips_normal_images(self):
        conf()["wechat_group_sticker_enabled"] = True
        conf()["wechat_group_sticker_auto_collect_enabled"] = True
        sticker_service = Mock()
        channel = WechatGroupChannel(client=FakeClient(), sticker_service=sticker_service)

        msg = Mock(
            message_type="image",
            media_path="D:/tmp/photo.jpg",
            other_user_id="room@@abc",
            msg_id="msg-image",
            text="",
            create_time=100,
        )

        channel._collect_sticker_from_message(msg)

        sticker_service.collect_from_message.assert_not_called()

    def test_sticker_collection_accepts_sticker_messages(self):
        conf()["wechat_group_sticker_enabled"] = True
        conf()["wechat_group_sticker_auto_collect_enabled"] = True
        sticker_service = Mock()
        channel = WechatGroupChannel(client=FakeClient(), sticker_service=sticker_service)

        msg = Mock(
            message_type="sticker",
            media_path="D:/tmp/reaction.gif",
            other_user_id="room@@abc",
            msg_id="msg-sticker",
            text=WECHAT_IMAGE_TRANSPORT_XML,
            create_time=100,
        )

        channel._collect_sticker_from_message(msg)

        sticker_service.collect_from_message.assert_called_once_with(
            room_id="room@@abc",
            media_path="D:/tmp/reaction.gif",
            source_message_id="msg-sticker",
            description="reaction",
            now=100,
        )

    def test_send_voice_reply_uses_audio_command(self):
        client = FakeClient()
        channel = WechatGroupChannel(client=client)
        context = {
            "type": ContextType.TEXT,
            "receiver": "room@@abc",
            "msg": Mock(is_group=True, actual_user_id="wxid_alice"),
        }

        channel.send(Reply(ReplyType.VOICE, "D:/tmp/a.mp3"), context)

        self.assertEqual(
            [("send_audio", "room@@abc", "D:/tmp/a.mp3")],
            client.commands,
        )

    def test_image_create_limit_zero_blocks_wechat_group_generation(self):
        conf()["wechat_group_image_create_hourly_limit"] = 0
        channel = WechatGroupChannel(client=FakeClient())
        context = Context(ContextType.IMAGE_CREATE, "a cat")
        context["receiver"] = "room@@abc"
        context["msg"] = Mock(actual_user_id="wxid_alice")

        with patch("channel.channel.Channel.build_reply_content") as build_reply:
            reply = channel._generate_reply(context)

        build_reply.assert_not_called()
        self.assertEqual(ReplyType.ERROR, reply.type)
        self.assertIn("生图额度", reply.content)

    def test_non_admin_persistent_write_request_is_rejected_before_agent(self):
        conf()["wechat_group_admin_sender_ids"] = []
        conf()["wechat_group_admin_members"] = [{"room_id": "room@@abc", "sender_id": "wxid_admin"}]
        conf()["wechat_group_admin_required_permissions"] = {
            "knowledge_write": True,
            "memory_write": True,
            "workspace_write": True,
        }
        channel = WechatGroupChannel(client=FakeClient())
        context = Context(ContextType.TEXT, "整理成 md 文档存入永久记忆以及知识库中")
        context["channel_type"] = "wechat_group"
        context["wechat_group_room_id"] = "room@@abc"
        context["wechat_group_sender_id"] = "wxid_normal"
        context["msg"] = Mock(
            other_user_id="room@@abc",
            actual_user_id="wxid_normal",
            actual_user_nickname="Normal",
            to_user_id="wxid_bot",
            is_group=True,
        )

        with patch("channel.chat_channel.ChatChannel._generate_reply") as generate:
            reply = channel._generate_reply(context)

        generate.assert_not_called()
        self.assertEqual(ReplyType.ERROR, reply.type)
        self.assertIn("当前群管理员", reply.content)

    def test_admin_persistent_write_request_is_not_rejected_by_channel_guard(self):
        conf()["wechat_group_admin_members"] = [{"room_id": "room@@abc", "sender_id": "wxid_admin"}]
        channel = WechatGroupChannel(client=FakeClient())
        context = Context(ContextType.TEXT, "保存到知识库")
        context["channel_type"] = "wechat_group"
        context["wechat_group_room_id"] = "room@@abc"
        context["wechat_group_sender_id"] = "wxid_admin"
        context["msg"] = Mock(other_user_id="room@@abc", actual_user_id="wxid_admin", is_group=True)

        blocked = channel._check_admin_guard(context)

        self.assertIsNone(blocked)

    def test_stable_admin_after_runtime_switch_is_not_rejected_by_channel_guard(self):
        conf()["wechat_group_admin_members"] = [{
            "stable_room_id": "wgr_room",
            "stable_member_id": "wgm_admin",
            "identity_status": "confirmed",
            "legacy_room_id": "room@@old",
            "legacy_sender_id": "wxid_old",
        }]
        channel = WechatGroupChannel(client=FakeClient())
        context = Context(ContextType.TEXT, "保存到知识库")
        context["channel_type"] = "wechat_group"
        context["wechat_group_stable_room_id"] = "wgr_room"
        context["wechat_group_stable_member_id"] = "wgm_admin"
        context["wechat_group_room_id"] = "room@@new"
        context["wechat_group_sender_id"] = "wxid_new"

        self.assertIsNone(channel._check_admin_guard(context))

    def test_pending_runtime_alias_of_stable_admin_is_rejected_by_channel_guard(self):
        conf()["wechat_group_admin_members"] = [{
            "stable_room_id": "wgr_room",
            "stable_member_id": "wgm_admin",
            "identity_status": "confirmed",
        }]
        channel = WechatGroupChannel(client=FakeClient())
        context = Context(ContextType.TEXT, "保存到知识库")
        context["channel_type"] = "wechat_group"
        context["wechat_group_stable_room_id"] = "wgr_room"
        context["wechat_group_stable_member_id"] = "wgm_admin"
        context["wechat_group_identity_requires_confirmation"] = True

        blocked = channel._check_admin_guard(context)

        self.assertIsNotNone(blocked)
        self.assertEqual(ReplyType.ERROR, blocked.type)

    def test_legacy_recent_context_uses_stable_room_scope(self):
        archive = Mock()
        channel = WechatGroupChannel(client=FakeClient(), archive=archive)
        msg = Mock(
            wechat_group_stable_room_id="wgr_room",
            stable_room_id="",
            other_user_id="room@@new",
            create_time=100,
        )

        with patch(
            "channel.wechat_group.wechat_group_channel.build_wechat_group_recent_context_block",
            return_value="recent",
        ) as build_recent:
            result = channel._build_recent_context_block(msg)

        self.assertEqual("recent", result)
        self.assertEqual("wgr_room", build_recent.call_args.args[1])

    def test_non_admin_normal_message_with_admin_policy_context_is_not_rejected(self):
        conf()["wechat_group_room_ids"] = ["room@@abc"]
        conf()["group_name_white_list"] = []
        conf()["wechat_group_admin_members"] = [{"room_id": "room@@abc", "sender_id": "wxid_admin"}]
        channel = WechatGroupChannel(client=FakeClient())
        channel._build_recent_context_block = Mock(return_value="")
        channel._resolve_focus_context = Mock(return_value={})
        channel._build_focus_context_block = Mock(return_value="")
        channel._build_memory_context_block = Mock(return_value="")
        channel._build_style_context_block = Mock(return_value="")
        channel._build_emotion_context_block = Mock(return_value="")
        channel._build_multimodal_context = Mock(return_value={"block": "", "diagnostics": {}, "matched_images": []})
        channel._record_inbound_message = Mock()
        msg = Mock(
            ctype=ContextType.TEXT,
            content="@LightBot 今天下午发布窗口是谁负责？",
            text="@LightBot 今天下午发布窗口是谁负责？",
            from_user_id="room@@abc",
            other_user_id="room@@abc",
            other_user_nickname="Test Room",
            actual_user_id="wxid_normal",
            actual_user_nickname="Normal",
            to_user_id="wxid_bot",
            to_user_nickname="LightBot",
            is_at=True,
            is_group=True,
            at_list=["wxid_bot"],
            self_display_name="LightBot",
            msg_id="msg-normal-admin-policy",
            message_type="text",
            media_path="",
        )

        context = channel._compose_context(ContextType.TEXT, msg.content, isgroup=True, msg=msg)

        self.assertIn("<wechat-group-admin-policy>", context.content)
        self.assertIn("写入知识库", context.content)
        with patch(
            "channel.chat_channel.ChatChannel._generate_reply",
            return_value=Reply(ReplyType.TEXT, "ok"),
        ) as generate:
            reply = channel._generate_reply(context)

        generate.assert_called_once()
        self.assertEqual(ReplyType.TEXT, reply.type)
        self.assertEqual("ok", reply.content)

    def test_image_create_success_records_hourly_usage(self):
        conf()["wechat_group_image_create_hourly_limit"] = 5
        archive = Mock(
            count_image_create_usage=Mock(return_value=0),
            record_image_create_usage=Mock(),
        )
        channel = WechatGroupChannel(client=FakeClient(), archive=archive)
        context = Context(ContextType.IMAGE_CREATE, "a cat")
        context["receiver"] = "room@@abc"
        context["wechat_group_stable_room_id"] = "wgr_room"
        context["wechat_group_stable_member_id"] = "wgm_alice"
        context["wechat_group_runtime_room_id"] = "room@@abc"
        context["wechat_group_runtime_sender_id"] = "wxid_alice"
        context["msg"] = Mock(actual_user_id="wxid_alice")

        with patch(
            "channel.chat_channel.ChatChannel._generate_reply",
            return_value=Reply(ReplyType.IMAGE_URL, "D:/tmp/out.png"),
        ) as generate:
            reply = channel._generate_reply(context)

        generate.assert_called_once()
        self.assertEqual(ReplyType.IMAGE_URL, reply.type)
        archive.record_image_create_usage.assert_called_once_with(
            room_id="wgr_room",
            sender_id="wgm_alice",
            prompt="a cat",
            status="accepted",
            stable_room_id="wgr_room",
            runtime_room_id="room@@abc",
            stable_member_id="wgm_alice",
            runtime_sender_id="wxid_alice",
        )
        archive.count_image_create_usage.assert_called_once_with(room_id="wgr_room", window_seconds=3600)

    def test_image_create_in_agent_mode_uses_deterministic_script_runner(self):
        conf()["agent"] = True
        conf()["wechat_group_image_create_hourly_limit"] = 5
        archive = Mock(
            count_image_create_usage=Mock(return_value=0),
            record_image_create_usage=Mock(),
        )
        channel = WechatGroupChannel(client=FakeClient(), archive=archive)
        context = Context(ContextType.IMAGE_CREATE, "a rabbit")
        context["receiver"] = "room@@abc"
        context["msg"] = Mock(actual_user_id="wxid_alice")

        with patch("channel.channel.Channel._build_image_create_reply",
                   return_value=Reply(ReplyType.IMAGE, "D:/tmp/rabbit.png")) as image_reply:
            with patch("channel.channel.Bridge") as bridge_factory:
                reply = channel._generate_reply(context)

        image_reply.assert_called_once_with("a rabbit", context)
        bridge_factory.assert_not_called()
        self.assertEqual(ReplyType.IMAGE, reply.type)
        self.assertEqual("D:/tmp/rabbit.png", reply.content)

    def test_image_create_script_runner_uses_json_argument_without_shell(self):
        conf()["skills"] = {
            "image-generation": {
                "provider": "custom:img01",
                "model": "my-image-model",
                "proxy_enabled": True,
                "proxy_domains": ["assets.grok.com", "*.grok.com"],
            }
        }
        conf()["tools"] = {
            "web_fetch": {
                "proxy": "http://127.0.0.1:7890",
            }
        }
        channel = WechatGroupChannel(client=FakeClient())
        context = Context(ContextType.IMAGE_CREATE, "a rabbit")

        completed = Mock(
            returncode=0,
            stdout='{"images":[{"url":"D:/tmp/rabbit.png"}]}',
            stderr="",
        )
        with patch("channel.channel.subprocess.run", return_value=completed) as run:
            reply = channel._build_image_create_reply("a rabbit", context)

        self.assertEqual(ReplyType.IMAGE, reply.type)
        self.assertEqual("D:/tmp/rabbit.png", reply.content)
        args = run.call_args.args[0]
        self.assertIsInstance(args, list)
        self.assertIn("generate.py", args[1].replace("\\", "/"))
        self.assertIn('"provider": "custom:img01"', args[2])
        self.assertIn('"model": "my-image-model"', args[2])
        self.assertIn('"proxy": "http://127.0.0.1:7890"', args[2])
        self.assertIn('"proxy_enabled": true', args[2])
        self.assertIn('"proxy_domains": ["assets.grok.com", "*.grok.com"]', args[2])
        self.assertFalse(run.call_args.kwargs.get("shell", False))
        self.assertEqual("utf-8", run.call_args.kwargs.get("encoding"))
        self.assertEqual("replace", run.call_args.kwargs.get("errors"))
        self.assertEqual(
            "utf-8",
            run.call_args.kwargs.get("env", {}).get("PYTHONIOENCODING"),
        )

    def test_image_create_script_payload_preserves_empty_proxy_domains(self):
        conf()["skills"] = {
            "image-generation": {
                "proxy_enabled": True,
                "proxy_domains": [],
            }
        }
        conf()["tools"] = {"web_fetch": {"proxy": "http://127.0.0.1:7890"}}
        channel = WechatGroupChannel(client=FakeClient())
        context = Context(ContextType.IMAGE_CREATE, "a rabbit")

        completed = Mock(
            returncode=0,
            stdout='{"images":[{"url":"D:/tmp/rabbit.png"}]}',
            stderr="",
        )
        with patch("channel.channel.subprocess.run", return_value=completed) as run:
            reply = channel._build_image_create_reply("a rabbit", context)

        self.assertEqual(ReplyType.IMAGE, reply.type)
        args = run.call_args.args[0]
        self.assertIn('"proxy_domains": []', args[2])

    def test_image_create_script_payload_normalizes_string_false_proxy_enabled(self):
        conf()["skills"] = {
            "image-generation": {
                "proxy_enabled": "false",
                "proxy_domains": ["assets.grok.com"],
            }
        }
        conf()["tools"] = {"web_fetch": {"proxy": "http://127.0.0.1:7890"}}
        channel = WechatGroupChannel(client=FakeClient())
        context = Context(ContextType.IMAGE_CREATE, "a rabbit")

        completed = Mock(
            returncode=0,
            stdout='{"images":[{"url":"D:/tmp/rabbit.png"}]}',
            stderr="",
        )
        with patch("channel.channel.subprocess.run", return_value=completed) as run:
            reply = channel._build_image_create_reply("a rabbit", context)

        self.assertEqual(ReplyType.IMAGE, reply.type)
        args = run.call_args.args[0]
        self.assertIn('"proxy_enabled": false', args[2])

    def test_image_create_script_failure_returns_safe_user_message(self):
        channel = WechatGroupChannel(client=FakeClient())
        context = Context(ContextType.IMAGE_CREATE, "a rabbit")
        completed = Mock(
            returncode=1,
            stdout='{"error":"unknown custom provider id: img01"}',
            stderr="",
        )

        with patch("channel.channel.subprocess.run", return_value=completed):
            reply = channel._build_image_create_reply("a rabbit", context)

        self.assertEqual(ReplyType.ERROR, reply.type)
        self.assertNotIn("unknown custom provider id", reply.content)
        self.assertIn("累了不想画了，你跪安吧。", reply.content)

    def test_non_at_message_without_free_reply_enabled_is_ignored(self):
        conf()["wechat_group_free_reply_enabled"] = False
        channel = WechatGroupChannel(client=FakeClient())
        channel.produce = Mock()
        channel.free_reply_worker = Mock()
        msg = Mock(
            ctype=ContextType.TEXT,
            content="谁能帮我总结一下刚才群里讨论的方案？",
            text="谁能帮我总结一下刚才群里讨论的方案？",
            other_user_id="room@@abc",
            other_user_nickname="测试群",
            actual_user_id="wxid_alice",
            actual_user_nickname="Alice",
            is_at=False,
        )

        channel.handle_text(msg)

        channel.produce.assert_not_called()
        channel.free_reply_worker.submit.assert_not_called()

    def test_non_at_message_logs_inbound_message_and_free_reply_decision(self):
        conf()["wechat_group_free_reply_enabled"] = False
        channel = WechatGroupChannel(client=FakeClient())
        channel.produce = Mock()
        channel.free_reply_worker = Mock()
        msg = Mock(
            ctype=ContextType.TEXT,
            content="Can someone summarize the plan from the group discussion?",
            text="Can someone summarize the plan from the group discussion?",
            message_type="text",
            other_user_id="room@@abc",
            other_user_nickname="Test Room",
            actual_user_id="wxid_alice",
            actual_user_nickname="Alice",
            is_at=False,
        )

        with self.assertLogs("log", level="INFO") as captured:
            channel.handle_text(msg)

        logs = "\n".join(captured.output)
        self.assertIn("[wechat_group] inbound:", logs)
        self.assertIn('room="Test Room"', logs)
        self.assertIn('sender="Alice"', logs)
        self.assertIn("Can someone summarize the plan", logs)
        self.assertIn("[wechat_group] free reply skipped:", logs)
        self.assertIn("score=", logs)
        self.assertIn("threshold=", logs)
        self.assertIn("suppressions=disabled(自由回复未启用)", logs)

    def test_image_transport_xml_is_projected_in_inbound_log(self):
        channel = WechatGroupChannel(client=FakeClient())
        msg = Mock(
            ctype=ContextType.IMAGE,
            content="D:/tmp/cat.jpg",
            text=WECHAT_IMAGE_TRANSPORT_XML,
            message_type="image",
            other_user_id="room@@abc",
            other_user_nickname="Test Room",
            actual_user_id="wxid_alice",
            actual_user_nickname="Alice",
            is_at=True,
        )

        with self.assertLogs("log", level="INFO") as captured:
            channel._log_inbound_message(msg)

        logs = "\n".join(captured.output)
        self.assertIn('type=image', logs)
        self.assertIn('text="[image]"', logs)
        for transport_fragment in ("<?xml", "<img", "hevc_mid_size", "aeskey", "cdnthumburl"):
            self.assertNotIn(transport_fragment, logs)

    def test_image_media_path_is_projected_in_inbound_log(self):
        channel = WechatGroupChannel(client=FakeClient())
        msg = Mock(
            ctype=ContextType.IMAGE,
            content="D:/private/media/cat.jpg",
            text="",
            message_type="image",
            other_user_id="room@@abc",
            other_user_nickname="Test Room",
            actual_user_id="wxid_alice",
            actual_user_nickname="Alice",
            is_at=True,
        )

        with self.assertLogs("log", level="INFO") as captured:
            channel._log_inbound_message(msg)

        logs = "\n".join(captured.output)
        self.assertIn('text="[image]"', logs)
        self.assertNotIn("D:/private/media/cat.jpg", logs)

    def test_free_reply_scored_message_is_enqueued_not_produced_directly(self):
        conf()["wechat_group_room_ids"] = ["room@@abc"]
        conf()["wechat_group_free_reply_enabled"] = True
        conf()["wechat_group_free_reply_room_ids"] = ["room@@abc"]
        conf()["wechat_group_free_reply_activity_level"] = "normal"
        channel = WechatGroupChannel(client=FakeClient())
        channel.produce = Mock()
        channel.free_reply_worker = Mock()
        msg = Mock(
            ctype=ContextType.TEXT,
            content="谁能帮我总结一下刚才群里讨论的方案？",
            text="谁能帮我总结一下刚才群里讨论的方案？",
            other_user_id="room@@abc",
            other_user_nickname="测试群",
            actual_user_id="wxid_alice",
            actual_user_nickname="Alice",
            is_at=False,
        )

        channel.handle_text(msg)

        channel.free_reply_worker.submit.assert_called_once()
        channel.produce.assert_not_called()

    def test_free_reply_burst_keeps_latest_candidate_before_cooldown(self):
        conf()["wechat_group_room_ids"] = ["room@@abc"]
        conf()["wechat_group_free_reply_enabled"] = True
        conf()["wechat_group_free_reply_room_ids"] = ["room@@abc"]
        conf()["wechat_group_free_reply_activity_level"] = "normal"
        conf()["wechat_group_emotion_enabled"] = False
        archive = Mock(get_recent_messages=Mock(return_value=[]))
        channel = WechatGroupChannel(client=FakeClient(), archive=archive)
        channel.produce = Mock()
        channel.free_reply_worker = Mock(submit=Mock(return_value=True))
        channel._ensure_free_reply_worker_started = Mock()
        common_fields = {
            "ctype": ContextType.TEXT,
            "from_user_id": "room@@abc",
            "other_user_id": "room@@abc",
            "other_user_nickname": "Test Room",
            "actual_user_id": "wxid_alice",
            "actual_user_nickname": "Alice",
            "to_user_id": "wxid_bot",
            "to_user_nickname": "LightBot",
            "is_at": False,
            "is_quote_self": False,
            "is_group": True,
            "at_list": [],
            "self_display_name": "LightBot",
            "message_type": "text",
            "media_path": "",
            "my_msg": False,
        }
        msg1 = Mock(
            content="LightBot can you summarize the first proposal?",
            text="LightBot can you summarize the first proposal?",
            create_time=100000,
            msg_id="msg-free-reply-burst-1",
            **common_fields,
        )
        msg2 = Mock(
            content="LightBot can you summarize the latest proposal?",
            text="LightBot can you summarize the latest proposal?",
            create_time=100001,
            msg_id="msg-free-reply-burst-2",
            **common_fields,
        )

        channel.handle_text(msg1)
        channel.handle_text(msg2)

        self.assertEqual(2, channel.free_reply_worker.submit.call_count)
        submitted_messages = [
            call_args.args[0]["msg"] for call_args in channel.free_reply_worker.submit.call_args_list
        ]
        self.assertEqual([msg1, msg2], submitted_messages)
        self.assertEqual(0, channel.free_reply_state.get("room@@abc")["last_triggered_at"])

    def test_free_reply_cooldown_uses_stable_room_after_runtime_room_changes(self):
        conf()["wechat_group_room_ids"] = []
        conf()["wechat_group_stable_room_ids"] = ["wgr_room"]
        conf()["wechat_group_free_reply_enabled"] = True
        conf()["wechat_group_free_reply_room_ids"] = ["wgr_room"]
        conf()["wechat_group_free_reply_activity_level"] = "normal"
        conf()["wechat_group_emotion_enabled"] = False
        channel = WechatGroupChannel(client=FakeClient(), archive=Mock(get_recent_messages=Mock(return_value=[])))
        channel.free_reply_state.mark_triggered("wgr_room", now=1000)
        msg = Mock(
            ctype=ContextType.TEXT,
            content="LightBot can you help?",
            text="LightBot can you help?",
            from_user_id="room@@new",
            other_user_id="room@@new",
            other_user_nickname="Test Room",
            actual_user_id="wxid_alice_new",
            actual_user_nickname="Alice",
            to_user_id="wxid_bot",
            to_user_nickname="LightBot",
            is_at=False,
            is_quote_self=False,
            is_group=True,
            at_list=[],
            self_display_name="LightBot",
            message_type="text",
            media_path="",
            my_msg=False,
            create_time=1005,
            msg_id="msg-free-reply-stable-cooldown",
            wechat_group_stable_room_id="wgr_room",
            wechat_group_stable_member_id="wgm_alice",
        )

        with patch("time.time", return_value=1005):
            should_enqueue, decision = channel._should_enqueue_free_reply_message(msg)

        self.assertFalse(should_enqueue)
        self.assertIn("min_interval", decision["suppressions"])
        self.assertEqual("wgr_room", decision["room_id"])

    def test_free_reply_blocklist_uses_stable_member_after_runtime_sender_changes(self):
        conf()["wechat_group_room_ids"] = []
        conf()["wechat_group_stable_room_ids"] = ["wgr_room"]
        conf()["wechat_group_free_reply_enabled"] = True
        conf()["wechat_group_free_reply_stable_room_ids"] = ["wgr_room"]
        conf()["wechat_group_blocked_stable_member_ids"] = ["wgm_alice"]
        conf()["wechat_group_emotion_enabled"] = False
        channel = WechatGroupChannel(client=FakeClient(), archive=Mock(get_recent_messages=Mock(return_value=[])))
        msg = Mock(
            ctype=ContextType.TEXT,
            content="LightBot can you help?",
            text="LightBot can you help?",
            from_user_id="room@@new",
            other_user_id="room@@new",
            other_user_nickname="Test Room",
            actual_user_id="wxid_alice_new",
            actual_user_nickname="Alice",
            to_user_id="wxid_bot",
            to_user_nickname="LightBot",
            is_at=False,
            is_quote_self=False,
            is_group=True,
            at_list=[],
            self_display_name="LightBot",
            message_type="text",
            media_path="",
            my_msg=False,
            create_time=1005,
            msg_id="msg-free-reply-stable-blocked",
            wechat_group_stable_room_id="wgr_room",
            wechat_group_stable_member_id="wgm_alice",
        )

        should_enqueue, decision = channel._should_enqueue_free_reply_message(msg)

        self.assertFalse(should_enqueue)
        self.assertIn("blocked_sender", decision["suppressions"])
        self.assertEqual("wgm_alice", decision["sender_id"])

    def test_direct_reply_from_blacklist_member_is_silently_skipped(self):
        conf()["wechat_group_room_ids"] = []
        conf()["wechat_group_stable_room_ids"] = ["wgr_room"]
        conf()["wechat_group_blacklist_members"] = [{
            "stable_room_id": "wgr_room",
            "stable_member_id": "wgm_alice",
            "identity_status": "confirmed",
        }]
        conf()["wechat_group_emotion_enabled"] = False
        channel = WechatGroupChannel(client=FakeClient(), archive=Mock(get_recent_messages=Mock(return_value=[])))
        channel.produce = Mock()
        msg = Mock(
            ctype=ContextType.TEXT,
            content="@LightBot ping",
            text="@LightBot ping",
            from_user_id="room@@new",
            other_user_id="room@@new",
            other_user_nickname="Test Room",
            actual_user_id="wxid_alice_new",
            actual_user_nickname="Alice",
            to_user_id="wxid_bot",
            to_user_nickname="LightBot",
            is_at=True,
            is_quote_self=False,
            is_group=True,
            is_pat_self=False,
            at_list=["wxid_bot"],
            self_display_name="LightBot",
            message_type="text",
            media_path="",
            my_msg=False,
            create_time=1005,
            msg_id="msg-direct-blacklist",
            wechat_group_stable_room_id="wgr_room",
            wechat_group_stable_member_id="wgm_alice",
        )

        channel.handle_text(msg)

        channel.produce.assert_not_called()

    def test_free_reply_blocklist_uses_structured_blacklist_member(self):
        conf()["wechat_group_room_ids"] = []
        conf()["wechat_group_stable_room_ids"] = ["wgr_room"]
        conf()["wechat_group_free_reply_enabled"] = True
        conf()["wechat_group_free_reply_stable_room_ids"] = ["wgr_room"]
        conf()["wechat_group_blacklist_members"] = [{
            "stable_room_id": "wgr_room",
            "stable_member_id": "wgm_alice",
            "identity_status": "confirmed",
        }]
        conf()["wechat_group_emotion_enabled"] = False
        channel = WechatGroupChannel(client=FakeClient(), archive=Mock(get_recent_messages=Mock(return_value=[])))
        msg = Mock(
            ctype=ContextType.TEXT,
            content="LightBot can you help?",
            text="LightBot can you help?",
            from_user_id="room@@new",
            other_user_id="room@@new",
            other_user_nickname="Test Room",
            actual_user_id="wxid_alice_new",
            actual_user_nickname="Alice",
            to_user_id="wxid_bot",
            to_user_nickname="LightBot",
            is_at=False,
            is_quote_self=False,
            is_group=True,
            at_list=[],
            self_display_name="LightBot",
            message_type="text",
            media_path="",
            my_msg=False,
            create_time=1005,
            msg_id="msg-free-reply-structured-blocked",
            wechat_group_stable_room_id="wgr_room",
            wechat_group_stable_member_id="wgm_alice",
        )

        should_enqueue, decision = channel._should_enqueue_free_reply_message(msg)

        self.assertFalse(should_enqueue)
        self.assertIn("blocked_sender", decision["suppressions"])
        self.assertEqual("wgm_alice", decision["sender_id"])

    def test_free_reply_blocklist_still_supports_legacy_runtime_sender(self):
        conf()["wechat_group_room_ids"] = []
        conf()["wechat_group_stable_room_ids"] = ["wgr_room"]
        conf()["wechat_group_free_reply_enabled"] = True
        conf()["wechat_group_free_reply_stable_room_ids"] = ["wgr_room"]
        conf()["wechat_group_blocked_sender_ids"] = ["wxid_alice_old"]
        conf()["wechat_group_emotion_enabled"] = False
        channel = WechatGroupChannel(client=FakeClient(), archive=Mock(get_recent_messages=Mock(return_value=[])))
        msg = Mock(
            ctype=ContextType.TEXT,
            content="LightBot can you help?",
            text="LightBot can you help?",
            from_user_id="room@@new",
            other_user_id="room@@new",
            other_user_nickname="Test Room",
            actual_user_id="wxid_alice_old",
            actual_user_nickname="Alice",
            to_user_id="wxid_bot",
            to_user_nickname="LightBot",
            is_at=False,
            is_quote_self=False,
            is_group=True,
            at_list=[],
            self_display_name="LightBot",
            message_type="text",
            media_path="",
            my_msg=False,
            create_time=1005,
            msg_id="msg-free-reply-legacy-blocked",
            wechat_group_stable_room_id="wgr_room",
            wechat_group_stable_member_id="wgm_alice",
        )

        should_enqueue, decision = channel._should_enqueue_free_reply_message(msg)

        self.assertFalse(should_enqueue)
        self.assertIn("blocked_sender", decision["suppressions"])

    def test_free_reply_image_question_is_suppressed_without_image_context(self):
        conf()["wechat_group_room_ids"] = ["room@@abc"]
        conf()["wechat_group_free_reply_enabled"] = True
        conf()["wechat_group_free_reply_room_ids"] = ["room@@abc"]
        conf()["wechat_group_free_reply_force_keywords"] = ["小风"]
        conf()["wechat_group_free_reply_activity_level"] = "normal"
        conf()["wechat_group_multimodal_context_enabled"] = True
        conf()["wechat_group_multimodal_image_understanding_context_enabled"] = True
        conf()["wechat_group_multimodal_free_reply_image_context_enabled"] = False
        conf()["wechat_group_recent_context_enabled"] = False
        conf()["wechat_group_knowledge_enabled"] = False
        conf()["wechat_group_profile_enabled"] = False
        conf()["wechat_group_focus_enabled"] = False
        conf()["wechat_group_style_enabled"] = False
        conf()["wechat_group_emotion_enabled"] = False
        archive = Mock()
        archive.get_recent_messages.return_value = [
            {"message_type": "image", "media_path": "D:/tmp/cat.jpg", "sender_id": "wxid_alice"},
            {"message_type": "text", "text": "小风 这是真的吗", "sender_id": "wxid_alice"},
        ]
        channel = WechatGroupChannel(
            client=FakeClient(),
            archive=archive,
            memory_service=Mock(preview_prompt_memories_sync=Mock(return_value={})),
        )
        channel.produce = Mock()
        channel.free_reply_worker = Mock(submit=Mock(return_value=True))
        channel._ensure_free_reply_worker_started = Mock()
        msg = Mock(
            ctype=ContextType.TEXT,
            content="小风 这是真的吗",
            text="小风 这是真的吗",
            from_user_id="room@@abc",
            other_user_id="room@@abc",
            other_user_nickname="Test Room",
            actual_user_id="wxid_alice",
            actual_user_nickname="Alice",
            to_user_id="wxid_bot",
            to_user_nickname="LightBot",
            is_at=False,
            is_quote_self=False,
            is_group=True,
            at_list=[],
            self_display_name="LightBot",
            create_time=100002,
            msg_id="msg-free-reply-image-question-no-context",
            message_type="text",
            media_path="",
            my_msg=False,
        )

        channel.handle_text(msg)

        channel.produce.assert_not_called()
        channel._ensure_free_reply_worker_started.assert_not_called()
        channel.free_reply_worker.submit.assert_not_called()
        decision = channel.free_reply_state.last_decision()
        self.assertFalse(decision["triggered"])
        self.assertIn("force_keyword_match", decision["reasons"])
        self.assertIn("image_context_unavailable", decision["suppressions"])

    def test_free_reply_is_suppressed_when_emotion_service_blocks(self):
        class FakeEmotionService:
            def observe_message(self, room_id, text, is_at=False, now=None):
                return {"room_id": room_id}

            def adjust_free_reply_decision(self, decision, room_id, now=None):
                adjusted = dict(decision)
                adjusted["triggered"] = False
                adjusted["suppressions"] = list(adjusted.get("suppressions") or []) + ["emotion_low_sociability"]
                adjusted["emotion"] = {"interpreted_state": "withdrawn"}
                return adjusted

        conf()["wechat_group_room_ids"] = ["room@@abc"]
        conf()["wechat_group_free_reply_enabled"] = True
        conf()["wechat_group_free_reply_room_ids"] = ["room@@abc"]
        conf()["wechat_group_emotion_enabled"] = True
        channel = WechatGroupChannel(client=FakeClient(), emotion_service=FakeEmotionService())
        channel.produce = Mock()
        channel.free_reply_worker = Mock()
        msg = Mock(
            ctype=ContextType.TEXT,
            content="谁能帮我总结一下刚才群里讨论的方案？",
            text="谁能帮我总结一下刚才群里讨论的方案？",
            message_type="text",
            other_user_id="room@@abc",
            other_user_nickname="测试群",
            actual_user_id="wxid_alice",
            actual_user_nickname="Alice",
            is_at=False,
            create_time=100000,
        )

        channel.handle_text(msg)

        channel.free_reply_worker.submit.assert_not_called()
        channel.produce.assert_not_called()

    def test_at_message_does_not_enter_free_reply_worker(self):
        channel = WechatGroupChannel(client=FakeClient())
        channel.free_reply_worker = Mock()
        channel.produce = Mock()
        channel._compose_context = Mock(return_value={"receiver": "room@@abc", "msg": Mock()})
        msg = Mock(
            ctype=ContextType.TEXT,
            content="@LightBot hello",
            is_at=True,
        )

        channel.handle_text(msg)

        channel.free_reply_worker.submit.assert_not_called()
        channel.produce.assert_called_once()

    def test_exact_at_mute_command_silently_mutes_current_stable_room(self):
        conf()["wechat_group_free_reply_mute_minutes"] = 15
        conf()["wechat_group_free_reply_mute_mentions_enabled"] = True
        conf()["wechat_group_emotion_enabled"] = False
        channel = WechatGroupChannel(client=FakeClient())
        channel.produce = Mock()
        channel.free_reply_worker = Mock()
        channel.free_reply_state.mute("wgr_room", 15, now=900)
        msg = WechatGroupMessage(parse_sidecar_event({
            "type": SidecarEventType.MESSAGE,
            "message_id": "mute-command-1",
            "room_id": "room@@runtime",
            "room_name": "测试群",
            "sender_id": "wxid_alice",
            "sender_name": "Alice",
            "self_id": "wxid_bot",
            "self_name": "LightBot",
            "self_display_name": "LightBot",
            "text": "@LightBot\u2005闭嘴",
            "message_type": "text",
            "is_at": True,
            "at_list": ["wxid_bot"],
        }))
        msg.wechat_group_stable_room_id = "wgr_room"

        with patch("channel.wechat_group.wechat_group_channel.time.time", return_value=1000):
            channel.handle_text(msg)

        self.assertEqual(1900, channel.free_reply_state.get("wgr_room")["muted_until"])
        self.assertFalse(channel.free_reply_state.is_muted("room@@runtime", now=1001))
        channel.produce.assert_not_called()
        channel.free_reply_worker.submit.assert_not_called()

    def test_mute_command_requires_exact_text_and_real_at(self):
        channel = WechatGroupChannel(client=FakeClient())

        def message(text, is_at=True):
            return Mock(
                ctype=ContextType.TEXT,
                is_at=is_at,
                text=text,
                content=text,
                self_display_name="LightBot",
                to_user_nickname="LightBot",
                to_user_id="wxid_bot",
                runtime_self_id="wxid_bot",
            )

        self.assertTrue(channel._is_free_reply_mute_command(message("@LightBot\u2005闭嘴")))
        self.assertTrue(channel._is_free_reply_mute_command(message("闭嘴")))
        self.assertFalse(channel._is_free_reply_mute_command(message("@LightBot\u2005请闭嘴")))
        self.assertFalse(channel._is_free_reply_mute_command(message("@LightBot\u2005闭嘴一下")))
        self.assertFalse(channel._is_free_reply_mute_command(message("闭嘴", is_at=False)))

    def test_mute_mentions_switch_suppresses_at_in_current_room(self):
        conf()["wechat_group_free_reply_mute_mentions_enabled"] = True
        conf()["wechat_group_emotion_enabled"] = False
        channel = WechatGroupChannel(client=FakeClient())
        channel._compose_context = Mock()
        channel.produce = Mock()
        channel.free_reply_worker = Mock()
        channel.free_reply_state.mute("wgr_room", 10)
        msg = Mock(
            ctype=ContextType.TEXT,
            content="@LightBot hello",
            text="@LightBot hello",
            message_type="text",
            is_at=True,
            is_quote_self=False,
            is_pat_self=False,
            wechat_group_stable_room_id="wgr_room",
            stable_room_id="wgr_room",
            other_user_id="room@@runtime",
            other_user_nickname="测试群",
            actual_user_id="wxid_alice",
            actual_user_nickname="Alice",
            self_display_name="LightBot",
            to_user_nickname="LightBot",
            to_user_id="wxid_bot",
            runtime_self_id="wxid_bot",
        )

        channel.handle_text(msg)

        channel._compose_context.assert_not_called()
        channel.produce.assert_not_called()
        channel.free_reply_worker.submit.assert_not_called()

    def test_mute_mentions_switch_off_keeps_at_reply_behavior(self):
        conf()["wechat_group_free_reply_mute_mentions_enabled"] = False
        conf()["wechat_group_emotion_enabled"] = False
        channel = WechatGroupChannel(client=FakeClient())
        channel._compose_context = Mock(return_value={"receiver": "room@@runtime", "msg": Mock()})
        channel.produce = Mock()
        channel.free_reply_state.mute("wgr_room", 10)
        msg = Mock(
            ctype=ContextType.TEXT,
            content="@LightBot hello",
            text="@LightBot hello",
            message_type="text",
            is_at=True,
            is_quote_self=False,
            is_pat_self=False,
            wechat_group_stable_room_id="wgr_room",
            stable_room_id="wgr_room",
            other_user_id="room@@runtime",
            other_user_nickname="测试群",
            actual_user_id="wxid_alice",
            actual_user_nickname="Alice",
            self_display_name="LightBot",
            to_user_nickname="LightBot",
            to_user_id="wxid_bot",
            runtime_self_id="wxid_bot",
        )

        channel.handle_text(msg)

        channel._compose_context.assert_called_once()
        channel.produce.assert_called_once()

    def test_mute_mentions_does_not_cross_rooms_or_suppress_quote_only(self):
        conf()["wechat_group_free_reply_mute_mentions_enabled"] = True
        channel = WechatGroupChannel(client=FakeClient())
        channel.free_reply_state.mute("wgr_room_a", 10)
        other_room_at = Mock(
            is_at=True,
            wechat_group_stable_room_id="wgr_room_b",
            stable_room_id="wgr_room_b",
            other_user_id="room@@b",
        )
        quote_only = Mock(
            is_at=False,
            is_quote_self=True,
            wechat_group_stable_room_id="wgr_room_a",
            stable_room_id="wgr_room_a",
            other_user_id="room@@a",
        )
        channel.free_reply_state.mute("wgr_expired", 10, now=1)
        expired_at = Mock(
            is_at=True,
            wechat_group_stable_room_id="wgr_expired",
            stable_room_id="wgr_expired",
            other_user_id="room@@expired",
        )

        self.assertFalse(channel._should_suppress_at_during_free_reply_mute(other_room_at))
        self.assertFalse(channel._should_suppress_at_during_free_reply_mute(quote_only))
        self.assertFalse(channel._should_suppress_at_during_free_reply_mute(expired_at))

    def test_queued_free_reply_is_discarded_when_room_is_muted(self):
        channel = WechatGroupChannel(client=FakeClient())
        channel._compose_context = Mock()
        channel.free_reply_state.mute("wgr_room", 10)
        msg = Mock(
            ctype=ContextType.TEXT,
            content="谁能总结一下？",
            other_user_id="room@@runtime",
        )
        task = {
            "room_id": "wgr_room",
            "msg": msg,
            "local_decision": {
                "triggered": True,
                "suppressions": [],
                "room_id": "wgr_room",
                "room_name": "测试群",
                "sender_id": "wgm_alice",
                "sender_name": "Alice",
                "score": 60,
                "threshold": 50,
            },
        }

        channel._submit_free_reply_after_judge(task, {"approved": True})

        channel._compose_context.assert_not_called()
        self.assertIn(
            "muted_by_command",
            channel.free_reply_state.last_decision()["suppressions"],
        )

    def test_at_image_message_injects_vision_summary_as_text_context(self):
        conf()["wechat_group_room_ids"] = ["room@@abc"]
        conf()["group_name_white_list"] = []
        conf()["wechat_group_image_understanding_enabled"] = True
        conf()["wechat_group_image_understanding_comment_enabled"] = True
        conf()["wechat_group_image_understanding_prompt"] = "Describe this image"
        channel = WechatGroupChannel(
            client=FakeClient(),
            memory_service=Mock(preview_prompt_memories_sync=Mock(return_value={})),
        )
        channel.produce = Mock()
        msg = Mock(
            ctype=ContextType.IMAGE,
            content="D:/tmp/cat.jpg",
            text="",
            from_user_id="room@@abc",
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
            create_time=100000,
            msg_id="msg-image",
            message_type="image",
            media_path="D:/tmp/cat.jpg",
        )

        with patch(
            "agent.tools.vision.vision.Vision.execute",
            return_value=ToolResult.success({"content": "A cat sitting on a desk."}),
        ) as execute:
            channel.handle_text(msg)

        execute.assert_called_once_with({
            "image": "D:/tmp/cat.jpg",
            "question": "Describe this image",
        })
        channel.produce.assert_called_once()
        context = channel.produce.call_args.args[0]
        self.assertEqual(ContextType.TEXT, context.type)
        self.assertIn("<wechat-group-multimodal>", context.content)
        self.assertIn("[image_understanding]", context.content)
        self.assertIn("current_image", context.content)
        self.assertNotIn("D:/tmp/cat.jpg", context.content)
        self.assertIn("A cat sitting on a desk.", context.content)

    def test_at_image_message_uses_readable_default_question(self):
        import channel.wechat_group.wechat_group_channel as wechat_group_channel

        conf()["wechat_group_room_ids"] = ["room@@abc"]
        conf()["group_name_white_list"] = []
        conf()["wechat_group_image_understanding_enabled"] = True
        conf()["wechat_group_image_understanding_comment_enabled"] = True
        conf()["wechat_group_image_understanding_prompt"] = "Describe this image"
        conf()["wechat_group_recent_context_enabled"] = False
        conf()["wechat_group_knowledge_enabled"] = False
        conf()["wechat_group_profile_enabled"] = False
        conf()["wechat_group_focus_enabled"] = False
        conf()["wechat_group_style_enabled"] = False
        conf()["wechat_group_emotion_enabled"] = False
        channel = WechatGroupChannel(
            client=FakeClient(),
            memory_service=Mock(preview_prompt_memories_sync=Mock(return_value={})),
        )
        channel.produce = Mock()
        msg = Mock(
            ctype=ContextType.IMAGE,
            content="D:/tmp/cat.jpg",
            text=WECHAT_IMAGE_TRANSPORT_XML,
            from_user_id="room@@abc",
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
            create_time=100000,
            msg_id="msg-image-readable-question",
            message_type="image",
            media_path="D:/tmp/cat.jpg",
        )

        with patch(
            "agent.tools.vision.vision.Vision.execute",
            return_value=ToolResult.success({"content": "A cat sitting on a desk."}),
        ):
            channel.handle_text(msg)

        context = channel.produce.call_args.args[0]
        default_question = getattr(
            wechat_group_channel,
            "WECHAT_GROUP_DEFAULT_IMAGE_REPLY_QUESTION",
            None,
        )
        self.assertEqual("请根据这张图片作出简短回应。", default_question)
        self.assertEqual(
            WECHAT_GROUP_DEFAULT_IMAGE_REPLY_QUESTION,
            context["wechat_group_user_content"],
        )
        self.assertIn(default_question, context.content)
        self.assertIn("A cat sitting on a desk.", context.content)
        for transport_fragment in ("<?xml", "<img", "hevc_mid_size", "aeskey", "cdnthumburl"):
            self.assertNotIn(transport_fragment, context.content)
        self.assertNotIn("鐠", context.content)
        self.assertNotIn("閸", context.content)

    def test_at_image_transport_xml_does_not_bypass_comment_disabled(self):
        conf()["wechat_group_room_ids"] = ["room@@abc"]
        conf()["group_name_white_list"] = []
        conf()["wechat_group_image_understanding_enabled"] = True
        conf()["wechat_group_image_understanding_comment_enabled"] = False
        channel = WechatGroupChannel(client=FakeClient())
        channel.produce = Mock()
        msg = Mock(
            ctype=ContextType.IMAGE,
            content="D:/tmp/cat.jpg",
            text=WECHAT_IMAGE_TRANSPORT_XML,
            from_user_id="room@@abc",
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
            create_time=100000,
            msg_id="msg-image-comment-disabled",
            message_type="image",
            media_path="D:/tmp/cat.jpg",
        )

        with patch(
            "agent.tools.vision.vision.Vision.execute",
            return_value=ToolResult.success({"content": "A cat sitting on a desk."}),
        ) as execute:
            channel.handle_text(msg)

        execute.assert_not_called()
        channel.produce.assert_not_called()

    def test_non_at_image_message_is_archived_without_reply_context(self):
        conf()["wechat_group_room_ids"] = ["room@@abc"]
        conf()["group_name_white_list"] = []
        conf()["wechat_group_image_understanding_enabled"] = True
        conf()["wechat_group_free_reply_image_understanding_enabled"] = False
        channel = WechatGroupChannel(client=FakeClient())
        channel.produce = Mock()
        channel.free_reply_worker = Mock()
        msg = Mock(
            ctype=ContextType.IMAGE,
            content="D:/tmp/cat.jpg",
            text="",
            from_user_id="room@@abc",
            other_user_id="room@@abc",
            other_user_nickname="Test Room",
            actual_user_id="wxid_alice",
            actual_user_nickname="Alice",
            to_user_id="wxid_bot",
            is_at=False,
            is_quote_self=False,
            is_group=True,
            at_list=[],
            self_display_name="LightBot",
            create_time=100000,
            msg_id="msg-image-2",
            message_type="image",
            media_path="D:/tmp/cat.jpg",
        )

        channel.handle_text(msg)

        channel.produce.assert_not_called()
        channel.free_reply_worker.submit.assert_not_called()

    def test_non_at_image_message_queues_free_reply_when_image_switch_enabled(self):
        conf()["wechat_group_room_ids"] = ["room@@abc"]
        conf()["group_name_white_list"] = []
        conf()["wechat_group_free_reply_enabled"] = True
        conf()["wechat_group_free_reply_room_ids"] = ["room@@abc"]
        conf()["wechat_group_free_reply_activity_level"] = "normal"
        conf()["wechat_group_emotion_enabled"] = False
        conf()["wechat_group_image_understanding_enabled"] = True
        conf()["wechat_group_free_reply_image_understanding_enabled"] = True
        archive = Mock(get_recent_messages=Mock(return_value=[]))
        channel = WechatGroupChannel(client=FakeClient(), archive=archive)
        channel.produce = Mock()
        channel.free_reply_worker = Mock(submit=Mock(return_value=True))
        channel._ensure_free_reply_worker_started = Mock()
        msg = Mock(
            ctype=ContextType.IMAGE,
            content="D:/tmp/cat.jpg",
            text="",
            from_user_id="room@@abc",
            other_user_id="room@@abc",
            other_user_nickname="Test Room",
            actual_user_id="wxid_alice",
            actual_user_nickname="Alice",
            to_user_id="wxid_bot",
            is_at=False,
            is_quote_self=False,
            is_group=True,
            at_list=[],
            self_display_name="LightBot",
            create_time=100000,
            msg_id="msg-image-free-reply",
            message_type="image",
            media_path="D:/tmp/cat.jpg",
            my_msg=False,
        )

        with patch("agent.tools.vision.vision.Vision.execute") as execute:
            channel.handle_text(msg)

        execute.assert_not_called()
        channel.produce.assert_not_called()
        channel._ensure_free_reply_worker_started.assert_called_once()
        channel.free_reply_worker.submit.assert_called_once()
        task = channel.free_reply_worker.submit.call_args.args[0]
        self.assertIs(task["msg"], msg)
        self.assertEqual("[image]", task["text"])
        self.assertNotIn("D:/tmp/cat.jpg", task["text"])
        self.assertTrue(task["local_decision"]["triggered"])
        self.assertIn("media_payload_allowed", task["local_decision"]["reasons"])

    def test_non_at_image_free_reply_does_not_treat_windows_media_path_as_sensitive(self):
        conf()["wechat_group_room_ids"] = ["room@@abc"]
        conf()["group_name_white_list"] = []
        conf()["wechat_group_free_reply_enabled"] = True
        conf()["wechat_group_free_reply_room_ids"] = ["room@@abc"]
        conf()["wechat_group_free_reply_activity_level"] = "normal"
        conf()["wechat_group_emotion_enabled"] = False
        conf()["wechat_group_image_understanding_enabled"] = True
        conf()["wechat_group_free_reply_image_understanding_enabled"] = True
        archive = Mock(get_recent_messages=Mock(return_value=[]))
        channel = WechatGroupChannel(client=FakeClient(), archive=archive)
        channel.produce = Mock()
        channel.free_reply_worker = Mock(submit=Mock(return_value=True))
        channel._ensure_free_reply_worker_started = Mock()
        media_path = r"C:\Users\clancy\.lightagent\wechat_group\media\room@@abc\42628335"
        msg = Mock(
            ctype=ContextType.IMAGE,
            content=media_path,
            text="",
            from_user_id="room@@abc",
            other_user_id="room@@abc",
            other_user_nickname="Test Room",
            actual_user_id="wxid_alice",
            actual_user_nickname="Alice",
            to_user_id="wxid_bot",
            is_at=False,
            is_quote_self=False,
            is_group=True,
            at_list=[],
            self_display_name="LightBot",
            create_time=100000,
            msg_id="msg-image-windows-path",
            message_type="image",
            media_path=media_path,
            my_msg=False,
        )

        channel.handle_text(msg)

        channel.free_reply_worker.submit.assert_called_once()
        task = channel.free_reply_worker.submit.call_args.args[0]
        self.assertEqual("[image]", task["text"])
        self.assertNotIn(media_path, task["text"])
        self.assertTrue(task["local_decision"]["triggered"])
        self.assertIn("media_payload_allowed", task["local_decision"]["reasons"])
        self.assertNotIn("sensitive_or_dangerous", task["local_decision"]["suppressions"])

    def test_at_text_image_request_uses_recent_group_image(self):
        conf()["wechat_group_room_ids"] = ["room@@abc"]
        conf()["group_name_white_list"] = []
        conf()["wechat_group_image_understanding_enabled"] = True
        conf()["wechat_group_image_understanding_comment_enabled"] = True
        conf()["wechat_group_image_understanding_prompt"] = "Describe this image"
        archive = Mock(
            get_recent_messages=Mock(return_value=[
                {
                    "message_type": "image",
                    "media_path": "D:/tmp/recent.jpg",
                    "sender_nickname": "Alice",
                    "sender_id": "wxid_alice",
                    "created_at": 100000,
                }
            ])
        )
        channel = WechatGroupChannel(
            client=FakeClient(),
            archive=archive,
            memory_service=Mock(preview_prompt_memories_sync=Mock(return_value={})),
        )
        channel.produce = Mock()
        msg = Mock(
            ctype=ContextType.TEXT,
            content="@LightBot 识别这张图",
            text="@LightBot 识别这张图",
            from_user_id="room@@abc",
            other_user_id="room@@abc",
            other_user_nickname="Test Room",
            actual_user_id="wxid_bob",
            actual_user_nickname="Bob",
            to_user_id="wxid_bot",
            to_user_nickname="LightBot",
            is_at=True,
            is_quote_self=False,
            is_group=True,
            at_list=["wxid_bot"],
            self_display_name="LightBot",
            create_time=100030,
            msg_id="msg-text-image-request",
            message_type="text",
            media_path="",
        )

        with patch(
            "agent.tools.vision.vision.Vision.execute",
            return_value=ToolResult.success({"content": "A chart about revenue."}),
        ) as execute:
            channel.handle_text(msg)

        archive.get_recent_messages.assert_any_call(
            "room@@abc",
            limit=20,
            minutes=2,
            now=100030,
        )
        execute.assert_called_once_with({
            "image": "D:/tmp/recent.jpg",
            "question": "Describe this image",
        })
        channel.produce.assert_called_once()
        context = channel.produce.call_args.args[0]
        self.assertEqual(ContextType.TEXT, context.type)
        self.assertIn("<wechat-group-multimodal>", context.content)
        self.assertIn("[image_understanding]", context.content)
        self.assertIn("unique_recent_image", context.content)
        self.assertNotIn("D:/tmp/recent.jpg", context.content)
        self.assertIn("A chart about revenue.", context.content)
        self.assertIn("识别这张图", context.content)

    def test_at_text_ambiguous_image_question_uses_recent_group_image(self):
        conf()["wechat_group_room_ids"] = ["room@@abc"]
        conf()["group_name_white_list"] = []
        conf()["wechat_group_image_understanding_enabled"] = True
        conf()["wechat_group_image_understanding_comment_enabled"] = True
        conf()["wechat_group_image_understanding_prompt"] = "Describe this image"
        archive = Mock(
            get_recent_messages=Mock(return_value=[
                {
                    "message_type": "image",
                    "media_path": "D:/tmp/recent.jpg",
                    "sender_nickname": "Alice",
                    "sender_id": "wxid_alice",
                    "created_at": 100000,
                }
            ])
        )
        channel = WechatGroupChannel(
            client=FakeClient(),
            archive=archive,
            memory_service=Mock(preview_prompt_memories_sync=Mock(return_value={})),
        )
        channel.produce = Mock()
        msg = Mock(
            ctype=ContextType.TEXT,
            content="@LightBot 啥意思",
            text="@LightBot 啥意思",
            from_user_id="room@@abc",
            other_user_id="room@@abc",
            other_user_nickname="Test Room",
            actual_user_id="wxid_bob",
            actual_user_nickname="Bob",
            to_user_id="wxid_bot",
            to_user_nickname="LightBot",
            is_at=True,
            is_quote_self=False,
            is_group=True,
            at_list=["wxid_bot"],
            self_display_name="LightBot",
            create_time=100030,
            msg_id="msg-text-ambiguous-image-question",
            message_type="text",
            media_path="",
        )

        with patch(
            "agent.tools.vision.vision.Vision.execute",
            return_value=ToolResult.success({"content": "A confusing screenshot."}),
        ) as execute:
            channel.handle_text(msg)

        execute.assert_called_once_with({
            "image": "D:/tmp/recent.jpg",
            "question": "Describe this image",
        })
        channel.produce.assert_called_once()
        context = channel.produce.call_args.args[0]
        self.assertEqual(ContextType.TEXT, context.type)
        self.assertIn("<wechat-group-multimodal>", context.content)
        self.assertIn("[image_understanding]", context.content)
        self.assertIn("unique_recent_image", context.content)
        self.assertNotIn("D:/tmp/recent.jpg", context.content)
        self.assertIn("A confusing screenshot.", context.content)
        self.assertIn("啥意思", context.content)

    def test_at_text_image_request_prefers_quoted_image(self):
        conf()["wechat_group_room_ids"] = ["room@@abc"]
        conf()["group_name_white_list"] = []
        conf()["wechat_group_image_understanding_enabled"] = True
        conf()["wechat_group_image_understanding_comment_enabled"] = True
        conf()["wechat_group_image_understanding_prompt"] = "Describe this image"
        archive = Mock(
            get_message_by_id=Mock(return_value={
                "message_id": "quoted-image",
                "message_type": "text",
                "text": WECHAT_IMAGE_TRANSPORT_XML,
                "media_path": "D:/tmp/quoted.jpg",
                "sender_nickname": "Alice",
                "sender_id": "wxid_alice",
                "created_at": 100000,
            }),
            get_recent_messages=Mock(return_value=[
                {
                    "message_type": "image",
                    "media_path": "D:/tmp/recent.jpg",
                    "sender_nickname": "Carol",
                    "sender_id": "wxid_carol",
                    "created_at": 100020,
                }
            ]),
        )
        channel = WechatGroupChannel(
            client=FakeClient(),
            archive=archive,
            memory_service=Mock(preview_prompt_memories_sync=Mock(return_value={})),
        )
        channel.produce = Mock()
        msg = Mock(
            ctype=ContextType.TEXT,
            content="@LightBot 识别这张图",
            text="@LightBot 识别这张图",
            from_user_id="room@@abc",
            other_user_id="room@@abc",
            other_user_nickname="Test Room",
            actual_user_id="wxid_bob",
            actual_user_nickname="Bob",
            to_user_id="wxid_bot",
            to_user_nickname="LightBot",
            is_at=True,
            is_quote_self=False,
            quote={"message_id": "quoted-image", "type": "3", "content": "[图片]"},
            is_group=True,
            at_list=["wxid_bot"],
            self_display_name="LightBot",
            create_time=100030,
            msg_id="msg-text-image-request",
            message_type="text",
            media_path="",
        )

        with patch(
            "agent.tools.vision.vision.Vision.execute",
            return_value=ToolResult.success({"content": "Quoted image summary."}),
        ) as execute:
            channel.handle_text(msg)

        archive.get_message_by_id.assert_any_call("room@@abc", "quoted-image")
        self.assertNotIn(
            call("room@@abc", limit=10, minutes=10, now=100030),
            archive.get_recent_messages.call_args_list,
        )
        execute.assert_called_once_with({
            "image": "D:/tmp/quoted.jpg",
            "question": "Describe this image",
        })
        context = channel.produce.call_args.args[0]
        self.assertIn("quoted_image", context.content)
        self.assertIn("quoted-image", context.content)
        self.assertIn("Quoted image summary.", context.content)
        self.assertIn("content: [image]", context.content)
        self.assertNotIn("D:/tmp/quoted.jpg", context.content)
        for transport_fragment in ("<?xml", "<img", "hevc_mid_size", "aeskey", "cdnthumburl"):
            self.assertNotIn(transport_fragment, context.content)

    def test_at_text_image_request_uses_quoted_sender_when_quote_id_missing(self):
        conf()["wechat_group_room_ids"] = ["room@@abc"]
        conf()["group_name_white_list"] = []
        conf()["wechat_group_image_understanding_enabled"] = True
        conf()["wechat_group_image_understanding_comment_enabled"] = True
        conf()["wechat_group_image_understanding_prompt"] = "Describe this image"
        archive = Mock(
            get_message_by_id=Mock(return_value=None),
            get_recent_messages=Mock(return_value=[
                {
                    "message_type": "image",
                    "media_path": "D:/tmp/quoted-sender.jpg",
                    "sender_nickname": "Alice",
                    "sender_id": "wxid_alice",
                    "created_at": 100000,
                },
                {
                    "message_type": "image",
                    "media_path": "D:/tmp/newer-other.jpg",
                    "sender_nickname": "Carol",
                    "sender_id": "wxid_carol",
                    "created_at": 100020,
                },
            ]),
        )
        channel = WechatGroupChannel(
            client=FakeClient(),
            archive=archive,
            memory_service=Mock(preview_prompt_memories_sync=Mock(return_value={})),
        )
        channel.produce = Mock()
        msg = Mock(
            ctype=ContextType.TEXT,
            content="@LightBot 识别这张图",
            text="@LightBot 识别这张图",
            from_user_id="room@@abc",
            other_user_id="room@@abc",
            other_user_nickname="Test Room",
            actual_user_id="wxid_bob",
            actual_user_nickname="Bob",
            to_user_id="wxid_bot",
            to_user_nickname="LightBot",
            is_at=True,
            is_quote_self=False,
            quote={
                "message_id": "missing-id",
                "sender_id": "wxid_alice",
                "sender_name": "Alice",
                "type": "1",
                "content": WECHAT_IMAGE_TRANSPORT_XML,
            },
            is_group=True,
            at_list=["wxid_bot"],
            self_display_name="LightBot",
            create_time=100030,
            msg_id="msg-text-image-request",
            message_type="text",
            media_path="",
        )

        with patch(
            "agent.tools.vision.vision.Vision.execute",
            return_value=ToolResult.success({"content": "Quoted sender image summary."}),
        ) as execute:
            channel.handle_text(msg)

        execute.assert_called_once_with({
            "image": "D:/tmp/quoted-sender.jpg",
            "question": "Describe this image",
        })
        content = channel.produce.call_args.args[0].content
        self.assertIn("quoted_sender_recent_image", content)
        self.assertIn("Quoted sender image summary.", content)
        self.assertIn("content: [image]", content)
        self.assertNotIn("D:/tmp/quoted-sender.jpg", content)
        for transport_fragment in ("<?xml", "<img", "hevc_mid_size", "aeskey", "cdnthumburl"):
            self.assertNotIn(transport_fragment, content)

    def test_quote_self_message_does_not_enter_free_reply_worker(self):
        channel = WechatGroupChannel(client=FakeClient())
        channel.free_reply_worker = Mock()
        channel.produce = Mock()
        channel._compose_context = Mock(return_value={"receiver": "room@@abc", "msg": Mock()})
        msg = Mock(
            ctype=ContextType.TEXT,
            content="What about this?",
            is_at=False,
            is_quote_self=True,
        )

        channel.handle_text(msg)

        channel.free_reply_worker.submit.assert_not_called()
        channel.produce.assert_called_once()

    def test_quote_self_message_with_refer_text_enters_reply_context(self):
        conf()["wechat_group_room_ids"] = ["room@@abc"]
        conf()["group_name_white_list"] = []
        channel = WechatGroupChannel(
            client=FakeClient(),
            memory_service=Mock(preview_prompt_memories_sync=Mock(return_value={})),
        )
        channel.produce = Mock()
        content = "「LightBot：previous answer」\n- - - - - - - - - - - - - - -\nWhat about this?"
        msg = Mock(
            ctype=ContextType.TEXT,
            content=content,
            text=content,
            from_user_id="room@@abc",
            other_user_id="room@@abc",
            other_user_nickname="Test Room",
            actual_user_id="wxid_alice",
            actual_user_nickname="Alice",
            to_user_id="@bot",
            to_user_nickname="LightBot",
            is_at=False,
            is_quote_self=True,
            is_group=True,
            at_list=[],
            self_display_name="LightBot",
            create_time=100000,
            msg_id="msg-quote-self",
            message_type="text",
            media_path="",
        )

        channel.handle_text(msg)

        channel.produce.assert_called_once()
        context = channel.produce.call_args.args[0]
        self.assertEqual("room@@abc", context["receiver"])
        self.assertTrue(context["wechat_group_quote_self_triggered"])

    def test_at_reference_text_enters_direct_reply_context(self):
        conf()["wechat_group_room_ids"] = ["room@@abc"]
        conf()["group_name_white_list"] = []
        channel = WechatGroupChannel(
            client=FakeClient(),
            memory_service=Mock(preview_prompt_memories_sync=Mock(return_value={})),
        )
        channel.produce = Mock()
        channel._record_inbound_message = Mock()
        content = "「Bob：[动画表情]」\n- - - - - - - - - - - - - - -\n@LightBot 你知道这图什么意思不"
        msg = Mock(
            ctype=ContextType.TEXT,
            content=content,
            text=content,
            from_user_id="room@@abc",
            other_user_id="room@@abc",
            other_user_nickname="Test Room",
            actual_user_id="wxid_alice",
            actual_user_nickname="Alice",
            to_user_id="@bot",
            to_user_nickname="LightBot",
            is_at=True,
            is_quote_self=False,
            is_group=True,
            at_list=["LightBot"],
            self_display_name="LightBot",
            create_time=100000,
            msg_id="msg-at-reference",
            message_type="text",
            media_path="",
        )

        channel.handle_text(msg)

        channel.produce.assert_called_once()
        context = channel.produce.call_args.args[0]
        self.assertEqual("direct_reply", context["wechat_group_trigger_source"])
        self.assertNotIn("wechat_group_quote_self_triggered", context)

    def test_voice_transcription_force_mode_enters_reply_context(self):
        conf()["wechat_group_voice_interaction_mode"] = "force_reply"
        channel = WechatGroupChannel(client=FakeClient())
        expected = Context(ContextType.TEXT, "reply context")
        channel._compose_context = Mock(return_value=expected)
        msg = Mock()
        context = Context(
            ContextType.VOICE,
            "D:/tmp/voice.mp3",
            {
                "msg": msg,
                "isgroup": True,
                "desire_rtype": ReplyType.VOICE,
            },
        )

        result = channel._handle_voice_transcription(context, "请总结一下")

        self.assertIs(expected, result)
        channel._compose_context.assert_called_once()
        args = channel._compose_context.call_args.args
        kwargs = channel._compose_context.call_args.kwargs
        self.assertEqual((ContextType.TEXT, "请总结一下"), args)
        self.assertTrue(kwargs["wechat_group_force_reply"])
        self.assertEqual("voice_message", kwargs["wechat_group_trigger_source"])
        self.assertEqual(ContextType.VOICE, kwargs["origin_ctype"])
        self.assertEqual(ReplyType.VOICE, kwargs["desire_rtype"])

    def test_voice_transcription_free_reply_mode_queues_text_candidate(self):
        conf()["wechat_group_voice_interaction_mode"] = "free_reply"
        channel = WechatGroupChannel(client=FakeClient())
        channel._should_enqueue_free_reply_message = Mock(
            return_value=(True, {"triggered": True, "reasons": []})
        )
        channel._ensure_free_reply_worker_started = Mock()
        channel.free_reply_worker = Mock()
        channel.free_reply_worker.submit.return_value = True
        channel._log_free_reply_decision = Mock()
        msg = Mock(
            ctype=ContextType.VOICE,
            content="D:/tmp/voice.mp3",
            text="",
            message_type="voice",
            other_user_id="room@@abc",
            other_user_nickname="Test Room",
            actual_user_id="wxid_alice",
            actual_user_nickname="Alice",
        )
        context = Context(
            ContextType.VOICE,
            msg.content,
            {"msg": msg, "desire_rtype": ReplyType.VOICE},
        )

        result = channel._handle_voice_transcription(context, "谁能帮我总结一下？")

        self.assertIsNone(result)
        channel._should_enqueue_free_reply_message.assert_called_once_with(
            msg,
            text_override="谁能帮我总结一下？",
            message_type_override="text",
        )
        channel._ensure_free_reply_worker_started.assert_called_once_with()
        task = channel.free_reply_worker.submit.call_args.args[0]
        self.assertEqual("谁能帮我总结一下？", task["text"])
        self.assertEqual("谁能帮我总结一下？", task["voice_transcription"])
        self.assertEqual(ReplyType.VOICE, task["desire_rtype"])
        channel._log_free_reply_decision.assert_called_once_with(
            {"triggered": True, "reasons": []},
            "queued",
        )

    def test_approved_voice_free_reply_uses_transcript_and_keeps_voice_output(self):
        channel = WechatGroupChannel(client=FakeClient())
        channel._compose_context = Mock(
            return_value=Context(ContextType.TEXT, "enhanced transcript")
        )
        channel.produce = Mock()
        channel.free_reply_state = Mock()
        msg = Mock(
            ctype=ContextType.VOICE,
            content="D:/tmp/voice.mp3",
            other_user_id="room@@abc",
        )
        task = {
            "msg": msg,
            "room_id": "wgr_room",
            "text": "谁能帮我总结一下？",
            "voice_transcription": "谁能帮我总结一下？",
            "desire_rtype": ReplyType.VOICE,
            "local_decision": {"triggered": True, "reasons": []},
        }

        channel._submit_free_reply_after_judge(task, {"approved": True})

        channel._compose_context.assert_called_once()
        args = channel._compose_context.call_args.args
        kwargs = channel._compose_context.call_args.kwargs
        self.assertEqual((ContextType.TEXT, "谁能帮我总结一下？"), args)
        self.assertTrue(kwargs["wechat_group_force_reply"])
        self.assertTrue(kwargs["wechat_group_is_free_reply"])
        self.assertTrue(kwargs["wechat_group_voice_interaction"])
        self.assertEqual("free_reply", kwargs["wechat_group_trigger_source"])
        self.assertEqual(ContextType.VOICE, kwargs["origin_ctype"])
        self.assertEqual(ReplyType.VOICE, kwargs["desire_rtype"])
        produced = channel.produce.call_args.args[0]
        self.assertTrue(produced["suppress_mention"])
        self.assertTrue(produced["no_need_at"])

    def test_approved_three_sender_repeater_sends_original_text_without_agent(self):
        channel = WechatGroupChannel(client=FakeClient())
        context = Context(ContextType.TEXT, "enhanced repeater context")
        channel._compose_context = Mock(return_value=context)
        channel._send_reply = Mock()
        channel.produce = Mock()
        channel.free_reply_state = Mock()
        msg = Mock(
            ctype=ContextType.TEXT,
            content="same meme line",
            other_user_id="room@@abc",
        )
        task = {
            "msg": msg,
            "room_id": "wgr_room",
            "text": "same meme line",
            "local_decision": {
                "triggered": True,
                "reasons": ["repeater_message"],
                "suppressions": [],
            },
        }

        channel._submit_free_reply_after_judge(
            task,
            {"approved": True, "reason": "repeater_message", "source": "local"},
        )

        channel.produce.assert_not_called()
        channel._send_reply.assert_called_once()
        sent_context, sent_reply = channel._send_reply.call_args.args
        self.assertIs(context, sent_context)
        self.assertEqual(ReplyType.TEXT, sent_reply.type)
        self.assertEqual("same meme line", sent_reply.content)
        self.assertTrue(sent_context["suppress_mention"])
        self.assertTrue(sent_context["no_need_at"])
        channel.free_reply_state.mark_triggered.assert_called_once()

    def test_compose_context_injects_multimodal_quote_and_forward_block(self):
        conf()["wechat_group_room_ids"] = ["room@@abc"]
        conf()["group_name_white_list"] = []
        conf()["wechat_group_quote_context_enabled"] = True
        conf()["wechat_group_forward_preview_enabled"] = True
        channel = WechatGroupChannel(
            client=FakeClient(),
            memory_service=Mock(preview_context=Mock(return_value={})),
        )
        channel._build_recent_context_block = Mock(return_value="")
        channel._resolve_focus_context = Mock(return_value={})
        channel._build_focus_context_block = Mock(return_value="")
        channel._build_memory_context_block = Mock(return_value="")
        channel._build_style_context_block = Mock(return_value="")
        channel._build_emotion_context_block = Mock(return_value="")
        channel.archive.get_message_by_id = Mock(return_value={
            "message_id": "quoted-1",
            "message_type": "text",
            "text": "上条消息说要先回归。",
            "media_path": "",
            "sender_id": "wxid_bob",
            "sender_nickname": "Bob",
            "created_at": 99990,
        })
        msg = Mock(
            ctype=ContextType.TEXT,
            content="这段转发你怎么看？",
            text="这段转发你怎么看？",
            from_user_id="room@@abc",
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
            create_time=100000,
            msg_id="msg-multi",
            message_type="text",
            media_path="",
            quote={"message_id": "quoted-1", "sender_id": "wxid_bob", "sender_name": "Bob", "type": "1", "content": "上条消息说要先回归。"},
            forward={"title": "聊天记录", "description": "Alice：明天早上十点发版", "source": "Alice", "record_count_hint": 3},
            raw_app_type="19",
        )

        context = channel._compose_context(ContextType.TEXT, msg.content, isgroup=True, msg=msg)

        self.assertTrue(context["wechat_group_multimodal_injected"])
        self.assertIn("<wechat-group-multimodal>", context.content)
        self.assertIn("[quoted_message]", context.content)
        self.assertIn("上条消息说要先回归。", context.content)
        self.assertIn("[forward_preview]", context.content)
        self.assertIn("聊天记录", context.content)

    def test_handle_text_video_message_builds_text_context_when_video_understanding_enabled(self):
        conf()["wechat_group_room_ids"] = ["room@@abc"]
        conf()["group_name_white_list"] = []
        conf()["wechat_group_video_understanding_enabled"] = True
        channel = WechatGroupChannel(
            client=FakeClient(),
            memory_service=Mock(preview_context=Mock(return_value={})),
        )
        channel.produce = Mock()
        channel._build_recent_context_block = Mock(return_value="")
        channel._resolve_focus_context = Mock(return_value={})
        channel._build_focus_context_block = Mock(return_value="")
        channel._build_memory_context_block = Mock(return_value="")
        channel._build_style_context_block = Mock(return_value="")
        channel._build_emotion_context_block = Mock(return_value="")
        msg = Mock(
            ctype=ContextType.FILE,
            content="D:/tmp/demo.mp4",
            text="",
            from_user_id="room@@abc",
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
            create_time=100000,
            msg_id="msg-video",
            message_type="video",
            media_path="D:/tmp/demo.mp4",
            quote={},
            forward={},
            raw_app_type="",
        )

        channel.handle_text(msg)

        context = channel.produce.call_args.args[0]
        self.assertEqual(ContextType.TEXT, context.type)
        self.assertTrue(context["wechat_group_video_understanding_triggered"])
        self.assertTrue(context["wechat_group_multimodal_injected"])
        self.assertIn("<wechat-group-multimodal>", context.content)
        self.assertIn("[video_message]", context.content)
        self.assertIn("msg-video", context.content)
        self.assertNotIn("D:/tmp/demo.mp4", context.content)

    def test_worker_approved_task_enters_reply_context(self):
        channel = WechatGroupChannel(client=FakeClient())
        channel.produce = Mock()
        msg = Mock(
            ctype=ContextType.TEXT,
            content="谁能总结一下？",
            other_user_id="room@@abc",
            other_user_nickname="测试群",
            actual_user_id="wxid_alice",
            actual_user_nickname="Alice",
            is_at=False,
        )
        channel._compose_context = Mock(return_value={"receiver": "room@@abc", "msg": msg})
        task = {"msg": msg, "local_decision": {"triggered": True, "score": 55}}

        channel._submit_free_reply_after_judge(task, {"approved": True, "confidence": 0.9})

        context = channel.produce.call_args.args[0]
        self.assertTrue(context["wechat_group_free_reply_triggered"])
        self.assertTrue(context["suppress_mention"])
        self.assertTrue(context["no_need_at"])

    def test_worker_approved_image_free_reply_injects_vision_summary(self):
        conf()["wechat_group_room_ids"] = ["room@@abc"]
        conf()["wechat_group_free_reply_enabled"] = True
        conf()["wechat_group_free_reply_room_ids"] = ["room@@abc"]
        conf()["wechat_group_image_understanding_enabled"] = True
        conf()["wechat_group_image_understanding_comment_enabled"] = True
        conf()["wechat_group_free_reply_image_understanding_enabled"] = True
        conf()["wechat_group_image_understanding_prompt"] = "Describe this image"
        channel = WechatGroupChannel(
            client=FakeClient(),
            memory_service=Mock(preview_prompt_memories_sync=Mock(return_value={})),
        )
        channel.produce = Mock()
        msg = Mock(
            ctype=ContextType.IMAGE,
            content="D:/tmp/cat.jpg",
            text=WECHAT_IMAGE_TRANSPORT_XML,
            from_user_id="room@@abc",
            other_user_id="room@@abc",
            other_user_nickname="Test Room",
            actual_user_id="wxid_alice",
            actual_user_nickname="Alice",
            to_user_id="wxid_bot",
            to_user_nickname="LightBot",
            is_at=False,
            is_group=True,
            at_list=[],
            self_display_name="LightBot",
            create_time=100000,
            msg_id="msg-image-free-reply-approved",
            message_type="image",
            media_path="D:/tmp/cat.jpg",
        )
        task = {"msg": msg, "text": "[图片] D:/tmp/cat.jpg", "local_decision": {"triggered": True, "score": 50}}

        with patch(
            "agent.tools.vision.vision.Vision.execute",
            return_value=ToolResult.success({"content": "A cat on the sofa."}),
        ) as execute:
            channel._submit_free_reply_after_judge(task, {"approved": True, "confidence": 0.9})

        execute.assert_called_once_with({
            "image": "D:/tmp/cat.jpg",
            "question": "Describe this image",
        })
        channel.produce.assert_called_once()
        context = channel.produce.call_args.args[0]
        self.assertEqual(ContextType.TEXT, context.type)
        self.assertTrue(context["wechat_group_free_reply_triggered"])
        self.assertTrue(context["wechat_group_image_understanding_triggered"])
        self.assertTrue(context["suppress_mention"])
        self.assertEqual(
            WECHAT_GROUP_DEFAULT_IMAGE_REPLY_QUESTION,
            context["wechat_group_user_content"],
        )
        self.assertIn("<wechat-group-multimodal>", context.content)
        self.assertIn("[image_understanding]", context.content)
        self.assertIn("A cat on the sofa.", context.content)
        self.assertNotIn("D:/tmp/cat.jpg", context.content)
        for transport_fragment in ("<?xml", "<img", "hevc_mid_size", "aeskey", "cdnthumburl"):
            self.assertNotIn(transport_fragment, context.content)

    def test_worker_approved_text_free_reply_injects_recent_image_via_global_multimodal_context(self):
        conf()["wechat_group_room_ids"] = ["room@@abc"]
        conf()["wechat_group_free_reply_enabled"] = True
        conf()["wechat_group_free_reply_room_ids"] = ["room@@abc"]
        conf()["wechat_group_multimodal_context_enabled"] = True
        conf()["wechat_group_multimodal_image_understanding_context_enabled"] = True
        conf()["wechat_group_multimodal_free_reply_image_context_enabled"] = True
        conf()["wechat_group_multimodal_same_sender_window_seconds"] = 120
        conf()["wechat_group_image_understanding_prompt"] = "Describe this image"
        conf()["wechat_group_recent_context_enabled"] = False
        conf()["wechat_group_knowledge_enabled"] = False
        conf()["wechat_group_profile_enabled"] = False
        conf()["wechat_group_focus_enabled"] = False
        conf()["wechat_group_style_enabled"] = False
        conf()["wechat_group_emotion_enabled"] = False
        archive = Mock()
        archive.get_recent_messages.return_value = [
            {
                "message_id": "image-before-question",
                "message_type": "image",
                "media_path": "D:/tmp/fact.jpg",
                "sender_nickname": "Alice",
                "sender_id": "wxid_alice",
                "created_at": 100000,
            }
        ]
        channel = WechatGroupChannel(
            client=FakeClient(),
            archive=archive,
            memory_service=Mock(preview_prompt_memories_sync=Mock(return_value={})),
        )
        channel.produce = Mock()
        msg = Mock(
            ctype=ContextType.TEXT,
            content="这是真的吗",
            text="这是真的吗",
            from_user_id="room@@abc",
            other_user_id="room@@abc",
            other_user_nickname="Test Room",
            actual_user_id="wxid_alice",
            actual_user_nickname="Alice",
            to_user_id="wxid_bot",
            to_user_nickname="LightBot",
            is_at=False,
            is_quote_self=False,
            is_group=True,
            at_list=[],
            self_display_name="LightBot",
            create_time=100002,
            msg_id="msg-free-reply-text-image-question",
            message_type="text",
            media_path="",
        )
        task = {"msg": msg, "text": "这是真的吗", "local_decision": {"triggered": True, "score": 60}}

        with patch(
            "agent.tools.vision.vision.Vision.execute",
            return_value=ToolResult.success({"content": "A screenshot of a transfer notice."}),
        ) as execute:
            channel._submit_free_reply_after_judge(task, {"approved": True, "confidence": 0.9})

        execute.assert_called_once_with({
            "image": "D:/tmp/fact.jpg",
            "question": "Describe this image",
        })
        channel.produce.assert_called_once()
        context = channel.produce.call_args.args[0]
        self.assertTrue(context["wechat_group_free_reply_triggered"])
        self.assertTrue(context["wechat_group_multimodal_injected"])
        self.assertIn("<wechat-group-multimodal>", context.content)
        self.assertIn("[image_understanding]", context.content)
        self.assertIn("same_sender_recent_image", context.content)
        self.assertIn("A screenshot of a transfer notice.", context.content)
        self.assertIn("这是真的吗", context.content)
        self.assertNotIn("D:/tmp/fact.jpg", context.content)

    def test_at_text_image_question_injects_recent_image_via_global_multimodal_context(self):
        conf()["wechat_group_room_ids"] = ["room@@abc"]
        conf()["group_name_white_list"] = []
        conf()["wechat_group_image_understanding_enabled"] = True
        conf()["wechat_group_multimodal_context_enabled"] = True
        conf()["wechat_group_multimodal_image_understanding_context_enabled"] = True
        conf()["wechat_group_multimodal_unique_image_window_seconds"] = 120
        conf()["wechat_group_image_understanding_prompt"] = "Describe this image"
        conf()["wechat_group_recent_context_enabled"] = False
        conf()["wechat_group_knowledge_enabled"] = False
        conf()["wechat_group_profile_enabled"] = False
        conf()["wechat_group_focus_enabled"] = False
        conf()["wechat_group_style_enabled"] = False
        conf()["wechat_group_emotion_enabled"] = False
        archive = Mock()
        archive.get_recent_messages.return_value = [
            {
                "message_id": "recent-image",
                "message_type": "image",
                "media_path": "D:/tmp/recent.jpg",
                "sender_nickname": "Alice",
                "sender_id": "wxid_alice",
                "created_at": 100000,
            }
        ]
        channel = WechatGroupChannel(
            client=FakeClient(),
            archive=archive,
            memory_service=Mock(preview_prompt_memories_sync=Mock(return_value={})),
        )
        channel.produce = Mock()
        msg = Mock(
            ctype=ContextType.TEXT,
            content="@LightBot 这是真的吗",
            text="@LightBot 这是真的吗",
            from_user_id="room@@abc",
            other_user_id="room@@abc",
            other_user_nickname="Test Room",
            actual_user_id="wxid_bob",
            actual_user_nickname="Bob",
            to_user_id="wxid_bot",
            to_user_nickname="LightBot",
            is_at=True,
            is_quote_self=False,
            is_group=True,
            at_list=["wxid_bot"],
            self_display_name="LightBot",
            create_time=100030,
            msg_id="msg-at-text-image-question",
            message_type="text",
            media_path="",
        )

        with patch(
            "agent.tools.vision.vision.Vision.execute",
            return_value=ToolResult.success({"content": "A suspicious payment screenshot."}),
        ) as execute:
            channel.handle_text(msg)

        execute.assert_called_once_with({
            "image": "D:/tmp/recent.jpg",
            "question": "Describe this image",
        })
        channel.produce.assert_called_once()
        context = channel.produce.call_args.args[0]
        self.assertTrue(context["wechat_group_multimodal_injected"])
        self.assertIn("<wechat-group-multimodal>", context.content)
        self.assertIn("unique_recent_image", context.content)
        self.assertIn("A suspicious payment screenshot.", context.content)
        self.assertNotIn("D:/tmp/recent.jpg", context.content)

    def test_worker_approved_free_reply_bypasses_group_at_filter(self):
        conf()["wechat_group_room_ids"] = ["room@@abc"]
        conf()["wechat_group_free_reply_enabled"] = True
        conf()["wechat_group_free_reply_room_ids"] = ["room@@abc"]
        channel = WechatGroupChannel(client=FakeClient(), memory_service=Mock(preview_prompt_memories_sync=Mock(return_value={})))
        channel.produce = Mock()
        msg = Mock(
            ctype=ContextType.TEXT,
            content="哪里的用户名",
            text="哪里的用户名",
            from_user_id="room@@abc",
            other_user_id="room@@abc",
            other_user_nickname="测试群",
            actual_user_id="wxid_alice",
            actual_user_nickname="Alice",
            to_user_id="wxid_bot",
            to_user_nickname="LightBot",
            is_at=False,
            is_group=True,
            at_list=[],
            self_display_name="LightBot",
            create_time=100000,
            msg_id="msg-free-reply",
            message_type="text",
            media_path="",
        )
        task = {"msg": msg, "local_decision": {"triggered": True, "score": 55}}

        channel._submit_free_reply_after_judge(task, {"approved": True, "confidence": 0.9})

        channel.produce.assert_called_once()
        context = channel.produce.call_args.args[0]
        self.assertEqual("room@@abc", context["receiver"])
        self.assertEqual("room@@abc", context["session_id"])
        self.assertTrue(context.content.endswith("哪里的用户名"))
        self.assertTrue(context["wechat_group_free_reply_triggered"])

    def test_free_reply_does_not_mention_sender(self):
        mentions = WechatGroupChannel._build_reply_mentions({
            "suppress_mention": True,
            "msg": Mock(is_group=True, actual_user_id="wxid_alice"),
        })

        self.assertEqual([], mentions)

    def test_free_reply_status_returns_config_decision_and_worker_status(self):
        channel = WechatGroupChannel(client=FakeClient())
        channel.free_reply_worker = Mock(status=Mock(return_value={"running": False}))

        status = channel.free_reply_status()

        self.assertIn("config", status)
        self.assertIn("last_decision", status)
        self.assertIn("worker", status)

    def test_memory_service_uses_configured_embedding_provider(self):
        from agent.memory.config import MemoryConfig, get_default_memory_config, set_global_memory_config
        from unittest.mock import patch

        original_config = get_default_memory_config()
        provider = object()
        channel = WechatGroupChannel(client=FakeClient())

        with tempfile.TemporaryDirectory() as tmpdir:
            set_global_memory_config(MemoryConfig(workspace_root=tmpdir))
            with patch(
                "agent.memory.create_default_embedding_provider",
                return_value=provider,
                create=True,
            ):
                service = channel._get_memory_service()
            try:
                self.assertIs(service.memory_manager.embedding_provider, provider)
            finally:
                service.memory_manager.close()
                set_global_memory_config(original_config)

    def test_profile_service_uses_channel_identity_service(self):
        identity = object()
        profile_service = object()
        channel = WechatGroupChannel(client=FakeClient(), identity_service=identity)

        with patch(
            "channel.wechat_group.wechat_group_profile_service.WechatGroupProfileService",
            return_value=profile_service,
        ) as service_class:
            result = channel._get_profile_service()

        self.assertIs(profile_service, result)
        service_class.assert_called_once_with(identity_service=identity)

    def test_memory_context_reuses_identity_aware_profile_service(self):
        profile_service = object()
        context_service = Mock()
        channel = WechatGroupChannel(client=FakeClient(), profile_service=profile_service)

        with patch(
            "channel.wechat_group.wechat_group_channel.WechatGroupContextService",
            return_value=context_service,
        ) as context_service_class, patch(
            "agent.memory.manager.MemoryManager",
            return_value=object(),
        ), patch(
            "agent.memory.create_default_embedding_provider",
            return_value=object(),
            create=True,
        ):
            result = channel._get_memory_service()

        self.assertIs(context_service, result)
        context_service_class.assert_called_once_with(profile_service=profile_service)

    def test_channel_caches_full_room_members_from_sidecar_event(self):
        channel = WechatGroupChannel(client=FakeClient())

        event = parse_sidecar_event({
            "type": "room_members",
            "room_id": "room@@abc",
            "members": [
                {
                    "sender_id": "wxid_alice",
                    "sender_nickname": "Alice",
                    "wechat_id": "alice_wechat",
                },
                {
                    "sender_id": "wxid_bob",
                    "sender_nickname": "Bob",
                    "wechat_id": "bob_wechat",
                },
            ],
        })

        self.assertTrue(channel.consume_sidecar_event(event))

        members = channel.get_room_members("room@@abc", query="bob", limit=20, refresh=False)
        self.assertEqual(1, len(members))
        self.assertEqual("wxid_bob", members[0]["sender_id"])
        self.assertEqual("Bob", members[0]["sender_nickname"])

    def test_channel_enriches_sidecar_members_with_stable_identity(self):
        identity_service = Mock()
        identity_service.resolve_legacy_room_id.return_value = "wgr_room"
        identity_service.resolve_member.return_value = Mock(
            stable_id="wgm_alice",
            status="confirmed",
            confidence="manual",
            requires_confirmation=False,
        )
        channel = WechatGroupChannel(client=FakeClient(), identity_service=identity_service)

        self.assertTrue(channel.consume_sidecar_event(parse_sidecar_event({
            "type": "room_members",
            "room_id": "room@@abc",
            "members": [{"sender_id": "wxid_alice", "sender_nickname": "Alice"}],
        })))

        member = channel.get_room_members("room@@abc", limit=20, refresh=False)[0]
        self.assertEqual("wgm_alice", member["stable_member_id"])
        self.assertEqual("wxid_alice", member["runtime_sender_id"])
        self.assertEqual("confirmed", member["identity_status"])
        self.assertFalse(member["identity_requires_confirmation"])
        identity_service.resolve_member.assert_called_once_with(
            "wgr_room",
            "wxid_alice",
            "Alice",
            "Alice",
            {"wechat_id": ""},
        )

    def test_channel_member_identity_prefers_current_room_mapping(self):
        identity_service = Mock()
        identity_service.resolve_legacy_room_id.return_value = "wgr_wrong_account"
        identity_service.resolve_member.return_value = Mock(
            stable_id="wgm_alice",
            status="confirmed",
            confidence="manual",
            requires_confirmation=False,
        )
        channel = WechatGroupChannel(client=FakeClient(), identity_service=identity_service)
        channel.rooms = [{
            "runtime_room_id": "room@@same",
            "stable_room_id": "wgr_current_account",
            "binding_status": "confirmed",
        }]

        channel.consume_sidecar_event(parse_sidecar_event({
            "type": "room_members",
            "room_id": "room@@same",
            "members": [{"sender_id": "wxid_alice", "sender_nickname": "Alice"}],
        }))

        identity_service.resolve_member.assert_called_once_with(
            "wgr_current_account",
            "wxid_alice",
            "Alice",
            "Alice",
            {"wechat_id": ""},
        )
        identity_service.resolve_legacy_room_id.assert_not_called()

    def test_channel_filters_room_members_by_profile_nickname_for_runtime_member(self):
        class FakeProfileService:
            def get_profile(self, sender_id, room_id=""):
                if sender_id != "@raw_sender":
                    return None
                return {
                    "sender_id": sender_id,
                    "primary_nickname": "一灯（无情的复读机）",
                    "aliases": ["一灯"],
                }

        identity_service = Mock()
        identity_service.resolve_legacy_room_id.return_value = "wgr_room"
        channel = WechatGroupChannel(client=FakeClient(), identity_service=identity_service)
        channel.profile_service = FakeProfileService()
        channel.room_members["room@@abc"] = [{
            "sender_id": "@raw_sender",
            "sender_nickname": "@raw_sender",
            "wechat_id": "",
            "last_seen_at": 0,
            "message_count": 0,
        }]

        members = channel.get_room_members("room@@abc", query="一灯", limit=20, refresh=False)

        self.assertEqual(1, len(members))
        self.assertEqual("@raw_sender", members[0]["sender_id"])
        self.assertEqual("一灯（无情的复读机）", members[0]["sender_nickname"])
        self.assertEqual("一灯（无情的复读机）", members[0]["profile_nickname"])
        self.assertEqual(["一灯"], members[0]["profile_aliases"])

    def test_channel_refresh_room_members_sends_sidecar_command(self):
        client = FakeClient()
        channel = WechatGroupChannel(client=client)

        channel.refresh_room_members("room@@abc", wait=False, query="yideng0803")

        self.assertEqual("list_room_members", client.commands[0][0])
        self.assertEqual("room@@abc", client.commands[0][1])
        self.assertEqual("yideng0803", client.commands[0][3])


if __name__ == "__main__":
    unittest.main()
