import json
import os
import sys
import tempfile
import types
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

if "web" not in sys.modules:
    web_stub = types.ModuleType("web")
    web_stub.HTTPError = type("HTTPError", (Exception,), {})
    web_stub.cookies = lambda: {}
    web_stub.header = lambda *args, **kwargs: None
    web_stub.data = lambda: b"{}"
    web_stub.input = lambda **kwargs: types.SimpleNamespace(**kwargs)
    web_stub.setcookie = lambda *args, **kwargs: None
    web_stub.seeother = lambda *args, **kwargs: Exception("seeother")
    web_stub.notfound = lambda *args, **kwargs: Exception("notfound")
    web_stub.badrequest = lambda *args, **kwargs: Exception("badrequest")
    web_stub.application = lambda *args, **kwargs: types.SimpleNamespace(wsgifunc=lambda: None)
    web_stub.httpserver = types.SimpleNamespace(
        LogMiddleware=type("LogMiddleware", (), {"log": lambda *args, **kwargs: None}),
        StaticMiddleware=lambda app: app,
        WSGIServer=lambda *args, **kwargs: types.SimpleNamespace(serve_forever=lambda: None),
    )
    sys.modules["web"] = web_stub


class WechatGroupWebTest(unittest.TestCase):
    def setUp(self):
        from config import conf

        self._original_config = {
            "channel_type": conf().get("channel_type"),
            "wechat_group_room_ids": conf().get("wechat_group_room_ids"),
            "wechat_group_stable_room_ids": conf().get("wechat_group_stable_room_ids"),
            "wechat_group_join_welcome_enabled": conf().get("wechat_group_join_welcome_enabled"),
            "wechat_group_join_welcome_content_type": conf().get("wechat_group_join_welcome_content_type"),
            "wechat_group_join_welcome_text": conf().get("wechat_group_join_welcome_text"),
            "wechat_group_join_welcome_image_path": conf().get("wechat_group_join_welcome_image_path"),
            "wechat_group_join_welcome_room_overrides": conf().get("wechat_group_join_welcome_room_overrides"),
            "wechat_group_leave_notice_enabled": conf().get("wechat_group_leave_notice_enabled"),
            "wechat_group_leave_notice_content_type": conf().get("wechat_group_leave_notice_content_type"),
            "wechat_group_leave_notice_text": conf().get("wechat_group_leave_notice_text"),
            "wechat_group_leave_notice_image_path": conf().get("wechat_group_leave_notice_image_path"),
            "wechat_group_leave_notice_room_overrides": conf().get("wechat_group_leave_notice_room_overrides"),
            "wechat_group_names": conf().get("wechat_group_names"),
            "github_commit_notify_enabled": conf().get("github_commit_notify_enabled"),
            "github_commit_notify_repository": conf().get("github_commit_notify_repository"),
            "github_commit_notify_branches": conf().get("github_commit_notify_branches"),
            "github_commit_notify_event_mode": conf().get("github_commit_notify_event_mode"),
            "github_commit_notify_events": conf().get("github_commit_notify_events"),
            "github_commit_notify_event_actions": conf().get("github_commit_notify_event_actions"),
            "github_commit_notify_stable_room_id": conf().get("github_commit_notify_stable_room_id"),
            "github_commit_notify_max_commits": conf().get("github_commit_notify_max_commits"),
            "github_commit_notify_retry_hours": conf().get("github_commit_notify_retry_hours"),
            "github_commit_notify_delivery_retention_days": conf().get("github_commit_notify_delivery_retention_days"),
            "github_commit_notify_webhook_secret": conf().get("github_commit_notify_webhook_secret"),
            "wechat_group_admin_members": conf().get("wechat_group_admin_members"),
            "wechat_group_admin_required_permissions": conf().get("wechat_group_admin_required_permissions"),
            "wechat_group_blacklist_members": conf().get("wechat_group_blacklist_members"),
            "wechat_group_alias_sync_cooldown_minutes": conf().get("wechat_group_alias_sync_cooldown_minutes"),
            "wechat_group_persona_prompt": conf().get("wechat_group_persona_prompt"),
            "wechat_group_persona_preset_id": conf().get("wechat_group_persona_preset_id"),
            "wechat_group_session_scope": conf().get("wechat_group_session_scope"),
            "wechat_group_thread_followup_ttl_minutes": conf().get("wechat_group_thread_followup_ttl_minutes"),
            "wechat_group_rolling_summary_enabled": conf().get("wechat_group_rolling_summary_enabled"),
            "wechat_group_tool_continuation_enabled": conf().get("wechat_group_tool_continuation_enabled"),
            "wechat_group_provider_continuation_enabled": conf().get("wechat_group_provider_continuation_enabled"),
            "wechat_group_archive_evidence_enabled": conf().get("wechat_group_archive_evidence_enabled"),
            "wechat_group_archive_evidence_days": conf().get("wechat_group_archive_evidence_days"),
            "wechat_group_response_cleanup_max_chars": conf().get("wechat_group_response_cleanup_max_chars"),
            "wechat_group_knowledge_enabled": conf().get("wechat_group_knowledge_enabled"),
            "wechat_group_profile_enabled": conf().get("wechat_group_profile_enabled"),
            "wechat_group_profile_context_limit": conf().get("wechat_group_profile_context_limit"),
            "wechat_group_group_memory_context_limit": conf().get("wechat_group_group_memory_context_limit"),
            "wechat_group_learning_enabled": conf().get("wechat_group_learning_enabled"),
            "wechat_group_learning_batch_message_limit": conf().get("wechat_group_learning_batch_message_limit"),
            "wechat_group_learning_profile_min_messages": conf().get("wechat_group_learning_profile_min_messages"),
            "wechat_group_learning_profile_sample_limit": conf().get("wechat_group_learning_profile_sample_limit"),
            "wechat_group_learning_group_memory_min_messages": conf().get("wechat_group_learning_group_memory_min_messages"),
            "wechat_group_learning_group_memory_window_minutes": conf().get("wechat_group_learning_group_memory_window_minutes"),
            "wechat_group_learning_idle_minutes": conf().get("wechat_group_learning_idle_minutes"),
            "wechat_group_learning_auto_apply_threshold": conf().get("wechat_group_learning_auto_apply_threshold"),
            "wechat_group_learning_max_interval_minutes": conf().get("wechat_group_learning_max_interval_minutes"),
            "wechat_group_learning_history_max_batches": conf().get("wechat_group_learning_history_max_batches"),
            "wechat_group_profile_evolution_enabled": conf().get("wechat_group_profile_evolution_enabled"),
            "wechat_group_profile_evolution_idle_minutes": conf().get("wechat_group_profile_evolution_idle_minutes"),
            "wechat_group_profile_evolution_min_messages": conf().get("wechat_group_profile_evolution_min_messages"),
            "wechat_group_profile_evolution_max_interval_minutes": conf().get("wechat_group_profile_evolution_max_interval_minutes"),
            "wechat_group_profile_evolution_batch_message_limit": conf().get("wechat_group_profile_evolution_batch_message_limit"),
            "wechat_group_free_reply_enabled": conf().get("wechat_group_free_reply_enabled"),
            "wechat_group_voice_interaction_mode": conf().get("wechat_group_voice_interaction_mode"),
            "wechat_group_free_reply_room_ids": conf().get("wechat_group_free_reply_room_ids"),
            "wechat_group_free_reply_stable_room_ids": conf().get("wechat_group_free_reply_stable_room_ids"),
            "wechat_group_blocked_stable_member_ids": conf().get("wechat_group_blocked_stable_member_ids"),
            "wechat_group_blocked_sender_ids": conf().get("wechat_group_blocked_sender_ids"),
            "wechat_group_free_reply_names": conf().get("wechat_group_free_reply_names"),
            "wechat_group_free_reply_activity_level": conf().get("wechat_group_free_reply_activity_level"),
            "wechat_group_free_reply_stable_room_activity_levels": conf().get("wechat_group_free_reply_stable_room_activity_levels"),
            "wechat_group_free_reply_mute_minutes": conf().get("wechat_group_free_reply_mute_minutes"),
            "wechat_group_free_reply_mute_mentions_enabled": conf().get("wechat_group_free_reply_mute_mentions_enabled"),
            "wechat_group_free_reply_queue_ttl_seconds": conf().get("wechat_group_free_reply_queue_ttl_seconds"),
            "wechat_group_free_reply_stale_message_tolerance": conf().get("wechat_group_free_reply_stale_message_tolerance"),
            "wechat_group_free_reply_worker_max_workers": conf().get("wechat_group_free_reply_worker_max_workers"),
            "wechat_group_free_reply_worker_queue_size": conf().get("wechat_group_free_reply_worker_queue_size"),
            "wechat_group_free_reply_llm_judge_enabled": conf().get("wechat_group_free_reply_llm_judge_enabled"),
            "wechat_group_free_reply_llm_judge_timeout_seconds": conf().get("wechat_group_free_reply_llm_judge_timeout_seconds"),
            "wechat_group_free_reply_llm_judge_min_confidence": conf().get("wechat_group_free_reply_llm_judge_min_confidence"),
            "wechat_group_free_reply_scorer_enabled": conf().get("wechat_group_free_reply_scorer_enabled"),
            "wechat_group_free_reply_scorer_provider": conf().get("wechat_group_free_reply_scorer_provider"),
            "wechat_group_free_reply_scorer_model": conf().get("wechat_group_free_reply_scorer_model"),
            "wechat_group_free_reply_scorer_context_limit": conf().get("wechat_group_free_reply_scorer_context_limit"),
            "wechat_group_free_reply_scorer_reply_threshold": conf().get("wechat_group_free_reply_scorer_reply_threshold"),
            "wechat_group_free_reply_scorer_soft_reply_threshold": conf().get("wechat_group_free_reply_scorer_soft_reply_threshold"),
            "wechat_group_free_reply_scorer_max_tokens": conf().get("wechat_group_free_reply_scorer_max_tokens"),
            "wechat_group_free_reply_scorer_fallback_to_rules": conf().get("wechat_group_free_reply_scorer_fallback_to_rules"),
            "wechat_group_free_reply_profiles": conf().get("wechat_group_free_reply_profiles"),
            "wechat_group_free_reply_rule_scores": conf().get("wechat_group_free_reply_rule_scores"),
            "wechat_group_free_reply_rule_enabled": conf().get("wechat_group_free_reply_rule_enabled"),
            "wechat_group_free_reply_force_keywords": conf().get("wechat_group_free_reply_force_keywords"),
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
            "wechat_group_focus_enabled": conf().get("wechat_group_focus_enabled"),
            "wechat_group_focus_recent_message_limit": conf().get("wechat_group_focus_recent_message_limit"),
            "wechat_group_focus_context_message_limit": conf().get("wechat_group_focus_context_message_limit"),
            "wechat_group_focus_stack_depth": conf().get("wechat_group_focus_stack_depth"),
            "wechat_group_focus_stale_rounds": conf().get("wechat_group_focus_stale_rounds"),
            "wechat_group_focus_min_keywords": conf().get("wechat_group_focus_min_keywords"),
            "wechat_group_focus_archive_recall_limit": conf().get("wechat_group_focus_archive_recall_limit"),
            "wechat_group_style_enabled": conf().get("wechat_group_style_enabled"),
            "wechat_group_style_learning_enabled": conf().get("wechat_group_style_learning_enabled"),
            "wechat_group_style_context_limit": conf().get("wechat_group_style_context_limit"),
            "wechat_group_style_candidate_min_evidence": conf().get("wechat_group_style_candidate_min_evidence"),
            "wechat_group_style_learning_batch_limit": conf().get("wechat_group_style_learning_batch_limit"),
            "wechat_group_style_auto_apply_enabled": conf().get("wechat_group_style_auto_apply_enabled"),
            "wechat_group_sticker_enabled": conf().get("wechat_group_sticker_enabled"),
            "wechat_group_sticker_auto_collect_enabled": conf().get("wechat_group_sticker_auto_collect_enabled"),
            "wechat_group_sticker_context_limit": conf().get("wechat_group_sticker_context_limit"),
            "wechat_group_sticker_reply_percent": conf().get("wechat_group_sticker_reply_percent"),
            "wechat_group_sticker_max_size_mb": conf().get("wechat_group_sticker_max_size_mb"),
            "wechat_group_sticker_daily_send_limit": conf().get("wechat_group_sticker_daily_send_limit"),
            "wechat_group_sticker_storage_dir": conf().get("wechat_group_sticker_storage_dir"),
            "wechat_group_sticker_online_search_enabled": conf().get("wechat_group_sticker_online_search_enabled"),
            "wechat_group_sticker_online_provider": conf().get("wechat_group_sticker_online_provider"),
            "wechat_group_sticker_online_endpoint": conf().get("wechat_group_sticker_online_endpoint"),
            "wechat_group_sticker_online_allowed_domains": conf().get("wechat_group_sticker_online_allowed_domains"),
            "wechat_group_sticker_online_allow_gif": conf().get("wechat_group_sticker_online_allow_gif"),
            "wechat_group_sticker_online_search_count": conf().get("wechat_group_sticker_online_search_count"),
            "wechat_group_sticker_cooldown_seconds": conf().get("wechat_group_sticker_cooldown_seconds"),
            "tools": conf().get("tools"),
            "skills": conf().get("skills"),
            "agent_workspace": conf().get("agent_workspace"),
        }

    def tearDown(self):
        from config import conf

        for key, value in self._original_config.items():
            if value is None:
                conf().pop(key, None)
            else:
                conf()[key] = value

    class FakeRunningWechatGroupChannel:
        def __init__(self, status="qr_ready", message="", qr_code="", rooms=None):
            self.status = status
            self.last_error = message
            self.qr_code = qr_code
            self.rooms = rooms or []
            self.login_status_calls = 0

        def get_login_status(self):
            self.login_status_calls += 1
            return self.status

    @staticmethod
    def _wechat_group_item(result):
        return next(channel for channel in result["channels"] if channel["name"] == "wechat_group")

    def test_channels_api_lists_wechat_group_as_qr_channel(self):
        from channel.web.web_channel import ChannelsHandler

        handler = ChannelsHandler()
        with patch("channel.web.web_channel._require_auth"), \
                patch("channel.web.web_channel.conf", return_value={"channel_type": "web"}):
            result = json.loads(handler.GET())

        item = next((ch for ch in result["channels"] if ch["name"] == "wechat_group"), None)
        self.assertIsNotNone(item)
        self.assertEqual({"zh": "个人微信群", "en": "WeChat Groups"}, item["label"])
        self.assertEqual([], item["fields"])
        self.assertFalse(item["active"])
        self.assertIn("extra", item)
        self.assertIn("persona", item["extra"])
        self.assertIn("persona_presets", item["extra"])
        self.assertNotIn("recent_context", item["extra"])
        self.assertNotIn("context_engine", item["extra"])
        self.assertEqual(
            {
                "alias_sync_cooldown_minutes": 1,
                "proxy": "",
            },
            item["extra"]["basic"],
        )
        self.assertEqual(
            {
                "knowledge_enabled": True,
                "profile_enabled": True,
                "profile_context_limit": 2,
                "group_memory_context_limit": 5,
                "learning_enabled": False,
                "learning_batch_message_limit": 200,
                "learning_profile_min_messages": 6,
                "learning_profile_sample_limit": 30,
                "learning_group_memory_min_messages": 20,
                "learning_group_memory_window_minutes": 120,
                "learning_idle_minutes": 10,
                "learning_auto_apply_threshold": 0.9,
                "learning_max_interval_minutes": 1440,
                "learning_history_max_batches": 10,
                "profile_evolution_enabled": False,
                "profile_evolution_idle_minutes": 10,
                "profile_evolution_min_messages": 10,
                "profile_evolution_max_interval_minutes": 120,
                "profile_evolution_batch_message_limit": 200,
            },
            item["extra"]["memory"],
        )
        self.assertEqual("owner-digital-twin", item["extra"]["persona"]["preset_id"])
        self.assertIn("free_reply", item["extra"])
        self.assertIn("rules", item["extra"]["free_reply"])
        self.assertIn("last_decision", item["extra"]["free_reply"])
        self.assertIn("worker", item["extra"]["free_reply"])
        self.assertEqual(
            {"mode": "force_reply"},
            item["extra"]["voice_interaction"],
        )
        self.assertEqual(
            {
                "understanding_enabled": True,
                "comment_enabled": True,
                "understanding_prompt": "请客观、简洁地描述这张图片中可直接观察到的关键信息和文字。",
                "cache_minutes": 30,
                "free_reply_understanding_enabled": False,
                "create_hourly_limit": 5,
                "video_understanding_enabled": False,
                "forward_preview_enabled": True,
                "quote_context_enabled": True,
                "generation_proxy_enabled": False,
                "generation_proxy_domains": [],
                "multimodal_context_enabled": True,
                "multimodal_image_understanding_context_enabled": True,
                "multimodal_free_reply_image_context_enabled": False,
                "multimodal_same_sender_window_seconds": 120,
                "multimodal_unique_image_window_seconds": 120,
                "multimodal_quote_sender_window_minutes": 30,
                "multimodal_max_recent_messages": 20,
            },
            item["extra"]["image"],
        )

    def test_channels_api_lists_wechat_group_humanization_defaults(self):
        from channel.web.web_channel import ChannelsHandler

        handler = ChannelsHandler()
        with patch("channel.web.web_channel._require_auth"), \
                patch("channel.web.web_channel.conf", return_value={"channel_type": "web"}):
            result = json.loads(handler.GET())

        item = next((ch for ch in result["channels"] if ch["name"] == "wechat_group"), None)
        self.assertIsNotNone(item)
        self.assertEqual(
            {
                "enabled": True,
                "recent_message_limit": 30,
                "context_message_limit": 8,
                "stack_depth": 4,
                "stale_rounds": 20,
                "min_keywords": 2,
                "archive_recall_limit": 20,
            },
            item["extra"]["focus"],
        )
        self.assertEqual(
            {
                "enabled": True,
                "learning_enabled": True,
                "context_limit": 3,
                "candidate_min_evidence": 2,
                "learning_batch_limit": 100,
                "auto_apply_enabled": False,
            },
            item["extra"]["style"],
        )
        self.assertNotIn("emotion", item["extra"])
        self.assertEqual(
            {
                "enabled": True,
                "auto_collect_enabled": True,
                "context_limit": 5,
                "reply_percent": 20,
                "max_size_mb": 2,
                "daily_send_limit": 20,
                "storage_dir": "",
                "online_search_enabled": True,
                "online_provider": "xiaoapi",
                "online_endpoint": "https://api.suol.cc/v1/meme.php",
                "online_allowed_domains": ["biaoqing.gtimg.com", "tugelepic.mse.sogou.com"],
                "online_allow_gif": True,
                "online_search_count": 10,
                "cooldown_seconds": 30,
            },
            item["extra"]["sticker"],
        )
        self.assertEqual(
            {
                "session_scope": "member",
                "thread_followup_ttl_minutes": 15,
                "rolling_summary_enabled": True,
                "tool_continuation_enabled": False,
                "archive_evidence_enabled": True,
                "archive_evidence_days": 90,
                "response_cleanup_max_chars": 800,
                "provider_continuation_supported": False,
                "provider_continuation_enabled": False,
            },
            item["extra"]["humanization"],
        )
        self.assertNotIn("recent_context", item["extra"])
        self.assertNotIn("context_engine", item["extra"])

    def test_wechat_group_qr_handler_returns_running_channel_status(self):
        from channel.web.web_channel import WechatGroupQrHandler

        channel = self.FakeRunningWechatGroupChannel(
            status="qr_ready",
            message="waiting for scan",
            qr_code="https://wechaty.js.org/qrcode/test",
            rooms=[{"id": "room@@abc", "name": "测试群"}],
        )
        handler = WechatGroupQrHandler()

        with patch("channel.web.web_channel._require_auth"), \
                patch.object(WechatGroupQrHandler, "_get_running_channel", return_value=channel), \
                patch.object(WechatGroupQrHandler, "_qr_to_data_uri", return_value="data:image/png;base64,abc"):
            result = json.loads(handler.GET())

        self.assertEqual("success", result["status"])
        self.assertEqual("qr_ready", result["login_status"])
        self.assertEqual("waiting for scan", result["message"])
        self.assertEqual("https://wechaty.js.org/qrcode/test", result["qrcode_url"])
        self.assertEqual("data:image/png;base64,abc", result["qr_image"])
        self.assertEqual([{"id": "room@@abc", "name": "测试群"}], result["rooms"])

        self.assertEqual(1, channel.login_status_calls)

    def test_channels_api_does_not_mark_wechat_group_active_before_login(self):
        from channel.web.web_channel import ChannelsHandler
        from config import conf

        conf()["channel_type"] = "wechat_group"
        channel = self.FakeRunningWechatGroupChannel(status="qr_ready")
        handler = ChannelsHandler()

        with patch("channel.web.web_channel._require_auth"), \
                patch.object(ChannelsHandler, "_get_running_wechat_group_channel", return_value=channel):
            result = json.loads(handler.GET())

        item = self._wechat_group_item(result)
        self.assertFalse(item["active"])
        self.assertTrue(item["configured"])
        self.assertTrue(item["runtime_active"])
        self.assertFalse(item["connected"])
        self.assertEqual("qr_ready", item["login_status"])

    def test_channels_api_marks_wechat_group_active_after_logged_in(self):
        from channel.web.web_channel import ChannelsHandler
        from config import conf

        conf()["channel_type"] = "wechat_group"
        channel = self.FakeRunningWechatGroupChannel(status="logged_in")
        handler = ChannelsHandler()

        with patch("channel.web.web_channel._require_auth"), \
                patch.object(ChannelsHandler, "_get_running_wechat_group_channel", return_value=channel):
            result = json.loads(handler.GET())

        item = self._wechat_group_item(result)
        self.assertTrue(item["active"])
        self.assertTrue(item["configured"])
        self.assertTrue(item["runtime_active"])
        self.assertTrue(item["connected"])
        self.assertEqual("logged_in", item["login_status"])

    def test_channels_api_returns_stable_room_selection_and_runtime_alias(self):
        from channel.web.web_channel import ChannelsHandler
        from config import conf

        conf()["wechat_group_room_ids"] = ["room@@old"]
        conf()["wechat_group_stable_room_ids"] = ["wgr_room"]
        conf()["wechat_group_free_reply_stable_room_ids"] = ["wgr_room"]
        conf()["wechat_group_free_reply_room_ids"] = ["room@@old"]
        channel = self.FakeRunningWechatGroupChannel(
            status="logged_in",
            rooms=[{
                "id": "room@@new",
                "name": "测试群",
                "stable_room_id": "wgr_room",
                "binding_status": "confirmed",
            }],
        )
        handler = ChannelsHandler()

        with patch("channel.web.web_channel._require_auth"), \
                patch.object(ChannelsHandler, "_get_running_wechat_group_channel", return_value=channel):
            result = json.loads(handler.GET())

        item = self._wechat_group_item(result)
        self.assertEqual(["wgr_room"], item["extra"]["selected_room_ids"])
        self.assertEqual(["room@@old"], item["extra"]["runtime_selected_room_ids"])
        room = item["extra"]["rooms"][0]
        self.assertEqual("wgr_room", room["id"])
        self.assertEqual("wgr_room", room["stable_room_id"])
        self.assertEqual("room@@new", room["runtime_room_id"])
        self.assertEqual("confirmed", room["binding_status"])
        self.assertEqual(["wgr_room"], item["extra"]["free_reply"]["stable_room_ids"])
        self.assertEqual(["room@@old"], item["extra"]["free_reply"]["legacy_room_ids"])

    def test_channels_api_does_not_masquerade_unresolved_runtime_room_as_stable(self):
        from channel.web.web_channel import ChannelsHandler

        channel = self.FakeRunningWechatGroupChannel(
            status="logged_in",
            rooms=[{"id": "room@@runtime", "name": "测试群"}],
        )
        handler = ChannelsHandler()

        with patch("channel.web.web_channel._require_auth"), \
                patch.object(ChannelsHandler, "_get_running_wechat_group_channel", return_value=channel):
            result = json.loads(handler.GET())

        room = self._wechat_group_item(result)["extra"]["rooms"][0]
        self.assertEqual("room@@runtime", room["id"])
        self.assertEqual("", room["stable_room_id"])
        self.assertEqual("room@@runtime", room["runtime_room_id"])
        self.assertEqual("identity_unresolved", room["binding_status"])
        recovery = self._wechat_group_item(result)["extra"]["identity_recovery"]
        self.assertFalse(recovery["requires_confirmation"])
        self.assertTrue(recovery["automatic"])
        self.assertEqual("", recovery["diagnostic_rooms"][0]["stable_room_id"])

    def test_channels_api_exposes_automatic_identity_recovery_status(self):
        from channel.web.web_channel import ChannelsHandler

        channel = self.FakeRunningWechatGroupChannel(
            status="logged_in",
            rooms=[
                {
                    "id": "room@@new",
                    "name": "测试群",
                    "stable_account_id": "wga_account",
                    "runtime_self_id": "wxid_bot",
                    "account_binding_status": "legacy_imported",
                    "account_identity_requires_confirmation": True,
                    "stable_room_id": "wgr_room",
                    "runtime_room_id": "room@@new",
                    "binding_status": "suspected",
                },
                {
                    "id": "room@@ok",
                    "name": "稳定群",
                    "stable_room_id": "wgr_ok",
                    "runtime_room_id": "room@@ok",
                    "binding_status": "confirmed",
                },
            ],
        )
        handler = ChannelsHandler()

        with patch("channel.web.web_channel._require_auth"), \
                patch.object(ChannelsHandler, "_get_running_wechat_group_channel", return_value=channel):
            result = json.loads(handler.GET())

        item = self._wechat_group_item(result)
        recovery = item["extra"]["identity_recovery"]
        self.assertFalse(recovery["requires_confirmation"])
        self.assertTrue(recovery["automatic"])
        self.assertIsNone(recovery["pending_account"])
        self.assertEqual(0, recovery["pending_count"])
        self.assertEqual([], recovery["pending_rooms"])
        self.assertEqual(1, recovery["diagnostic_count"])
        self.assertEqual("wgr_room", recovery["diagnostic_rooms"][0]["stable_room_id"])

    def test_channels_api_exposes_wechat_group_error_message(self):
        from channel.web.web_channel import ChannelsHandler
        from config import conf

        conf()["channel_type"] = "wechat_group"
        channel = self.FakeRunningWechatGroupChannel(status="error", message="login failed")
        handler = ChannelsHandler()

        with patch("channel.web.web_channel._require_auth"), \
                patch.object(ChannelsHandler, "_get_running_wechat_group_channel", return_value=channel):
            result = json.loads(handler.GET())

        item = self._wechat_group_item(result)
        self.assertFalse(item["active"])
        self.assertTrue(item["configured"])
        self.assertFalse(item["connected"])
        self.assertEqual("error", item["login_status"])
        self.assertEqual("login failed", item["message"])

    def test_channels_api_returns_wechat_group_admin_config(self):
        from channel.web.web_channel import ChannelsHandler
        from config import conf

        conf()["wechat_group_admin_members"] = [
            {"room_id": "room@@abc", "room_name": "测试群", "sender_id": "wxid_admin"}
        ]
        conf()["wechat_group_blacklist_members"] = [
            {"room_id": "room@@abc", "room_name": "Test Room", "sender_id": "wxid_blocked"}
        ]
        conf()["wechat_group_admin_required_permissions"] = {"knowledge_write": True, "workspace_write": False}

        handler = ChannelsHandler()
        with patch("channel.web.web_channel._require_auth"):
            result = json.loads(handler.GET())

        item = next(channel for channel in result["channels"] if channel["name"] == "wechat_group")
        self.assertEqual("wxid_admin", item["extra"]["admin"]["members"][0]["sender_id"])
        self.assertEqual("wxid_blocked", item["extra"]["admin"]["blacklist_members"][0]["sender_id"])
        self.assertTrue(item["extra"]["admin"]["required_permissions"]["knowledge_write"])
        self.assertFalse(item["extra"]["admin"]["required_permissions"]["workspace_write"])
        definitions = item["extra"]["admin"]["permission_definitions"]
        self.assertEqual(10, len(definitions))
        self.assertEqual("knowledge_write", definitions[0]["id"])
        self.assertIn("blocked_behavior", definitions[0])
        self.assertIn("allowed_behavior", definitions[0])
        self.assertIn("examples", definitions[0])
        self.assertIn("guard_layers", definitions[0])
        self.assertIn("affected_objects", definitions[0])
        self.assertTrue(definitions[0]["enabled"])

    def test_channels_save_wechat_group_admin_config(self):
        from channel.web.web_channel import ChannelsHandler
        from config import conf

        handler = ChannelsHandler()
        body = {
            "action": "save",
            "channel": "wechat_group",
            "config": {
                "wechat_group_admin_members": [
                    {
                        "room_id": "room@@abc",
                        "room_name": "测试群",
                        "sender_id": "wxid_admin",
                        "sender_nickname": "Alice",
                        "wechat_id": "alice_wechat",
                    }
                ],
                "wechat_group_blacklist_members": [
                    {
                        "room_id": "room@@abc",
                        "room_name": "Test Room",
                        "sender_id": "wxid_blocked",
                        "sender_nickname": "Bob",
                        "wechat_id": "bob_wechat",
                    }
                ],
                "wechat_group_admin_required_permissions": {
                    "knowledge_write": True,
                    "workspace_write": False,
                },
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir, \
                patch("channel.web.web_channel._require_auth"), \
                patch("channel.web.web_channel.web.data", return_value=json.dumps(body).encode("utf-8")), \
                patch("channel.web.web_channel.get_data_root", return_value=tmpdir):
            result = json.loads(handler.POST())

        self.assertEqual("success", result["status"])
        self.assertEqual("room@@abc", conf()["wechat_group_admin_members"][0]["room_id"])
        self.assertEqual("wxid_admin", conf()["wechat_group_admin_members"][0]["sender_id"])
        self.assertEqual("room@@abc", conf()["wechat_group_blacklist_members"][0]["room_id"])
        self.assertEqual("wxid_blocked", conf()["wechat_group_blacklist_members"][0]["sender_id"])
        self.assertTrue(conf()["wechat_group_admin_required_permissions"]["knowledge_write"])
        self.assertFalse(conf()["wechat_group_admin_required_permissions"]["workspace_write"])

    def test_wechat_group_members_api_uses_archive(self):
        from channel.web.web_channel import WechatGroupMembersHandler

        class FakeArchive:
            def list_members(self, room_id, query="", limit=20):
                self.args = (room_id, query, limit)
                return [{
                    "sender_id": "wxid_admin",
                    "sender_nickname": "Alice",
                    "wechat_id": "alice_wechat",
                    "last_seen_at": 123,
                    "message_count": 7,
                }]

        fake = FakeArchive()
        handler = WechatGroupMembersHandler()
        with patch("channel.web.web_channel._require_auth"), \
                patch.object(WechatGroupMembersHandler, "_get_archive", return_value=fake), \
                patch("channel.web.web_channel.web.input", return_value=types.SimpleNamespace(room_id="room@@abc", q="alice", limit="20")):
            result = json.loads(handler.GET())

        self.assertEqual("success", result["status"])
        self.assertEqual(("room@@abc", "alice", 20), fake.args)
        self.assertEqual("wxid_admin", result["members"][0]["sender_id"])

    def test_wechat_group_members_api_prefers_running_room_members(self):
        from channel.web.web_channel import WechatGroupMembersHandler, WechatGroupQrHandler

        class FakeRunningChannel:
            def __init__(self):
                self.args = None

            def get_room_members(self, room_id, query="", limit=20, refresh=True):
                self.args = (room_id, query, limit, refresh)
                return [
                    {
                        "sender_id": "wxid_silent",
                        "sender_nickname": "Silent Alice",
                        "wechat_id": "silent_alice",
                        "last_seen_at": 0,
                        "message_count": 0,
                    }
                ]

        class FakeArchive:
            def list_members(self, room_id, query="", limit=20):
                return [{
                    "sender_id": "wxid_archived",
                    "sender_nickname": "Archived Alice",
                    "wechat_id": "archived_alice",
                }]

        running = FakeRunningChannel()
        handler = WechatGroupMembersHandler()
        with patch("channel.web.web_channel._require_auth"), \
                patch.object(WechatGroupQrHandler, "_get_running_channel", return_value=running), \
                patch.object(WechatGroupMembersHandler, "_get_archive", return_value=FakeArchive()), \
                patch("channel.web.web_channel.web.input", return_value=types.SimpleNamespace(room_id="room@@abc", q="alice", limit="20")):
            result = json.loads(handler.GET())

        self.assertEqual("success", result["status"])
        self.assertEqual(("room@@abc", "alice", 20, True), running.args)
        self.assertEqual("wxid_silent", result["members"][0]["sender_id"])

    def test_wechat_group_members_api_resolves_stable_room_for_running_lookup(self):
        from channel.web.web_channel import WechatGroupMembersHandler, WechatGroupQrHandler

        class FakeIdentityService:
            def get_active_runtime_room_id(self, stable_room_id):
                self.stable_room_id = stable_room_id
                return "room@@runtime"

        class FakeRunningChannel:
            def __init__(self):
                self.identity_service = FakeIdentityService()
                self.args = None

            def get_room_members(self, room_id, query="", limit=20, refresh=True):
                self.args = (room_id, query, limit, refresh)
                return [{"sender_id": "wxid_runtime", "stable_member_id": "wgm_member"}]

        running = FakeRunningChannel()
        handler = WechatGroupMembersHandler()
        with patch("channel.web.web_channel._require_auth"), \
                patch.object(WechatGroupQrHandler, "_get_running_channel", return_value=running), \
                patch("channel.web.web_channel.web.input", return_value=types.SimpleNamespace(
                    stable_room_id="wgr_room", runtime_room_id="", room_id="", q="", limit="20",
                )):
            result = json.loads(handler.GET())

        self.assertEqual("success", result["status"])
        self.assertEqual(("room@@runtime", "", 20, True), running.args)
        self.assertEqual("wgr_room", result["identity"]["stable_room_id"])
        self.assertEqual("room@@runtime", result["identity"]["runtime_room_id"])

    def test_wechat_group_members_api_ignores_stable_id_in_legacy_room_parameter(self):
        from channel.web.web_channel import WechatGroupMembersHandler, WechatGroupQrHandler

        class FakeIdentityService:
            def get_active_runtime_room_id(self, stable_room_id):
                return "room@@runtime"

        class FakeRunningChannel:
            def __init__(self):
                self.identity_service = FakeIdentityService()
                self.args = None

            def get_room_members(self, room_id, query="", limit=20, refresh=True):
                self.args = (room_id, query, limit, refresh)
                return [{"sender_id": "wxid_runtime"}]

        running = FakeRunningChannel()
        handler = WechatGroupMembersHandler()
        with patch("channel.web.web_channel._require_auth"), \
                patch.object(WechatGroupQrHandler, "_get_running_channel", return_value=running), \
                patch("channel.web.web_channel.web.input", return_value=types.SimpleNamespace(
                    stable_room_id="wgr_room", runtime_room_id="", room_id="wgr_room", q="", limit="20",
                )):
            result = json.loads(handler.GET())

        self.assertEqual("success", result["status"])
        self.assertEqual(("room@@runtime", "", 20, True), running.args)

    def test_wechat_group_memory_group_get_prefers_stable_room_id(self):
        from channel.web.web_channel import WechatGroupMemoriesHandler

        class FakeKnowledgeService:
            def list_group_memories(self, room_id, query="", limit=20, offset=0):
                self.args = (room_id, query, limit, offset)
                return [{"memory_id": "m1", "room_id": room_id}]

            def count_group_memories(self, room_id, query=""):
                return 1

        fake = FakeKnowledgeService()
        handler = WechatGroupMemoriesHandler()
        with patch("channel.web.web_channel._require_auth"), \
                patch.object(WechatGroupMemoriesHandler, "_get_knowledge_service", return_value=fake), \
                patch("channel.web.web_channel.web.input", return_value=types.SimpleNamespace(
                    stable_room_id="wgr_room", runtime_room_id="", room_id="room@@runtime",
                    sender_id="", stable_member_id="", status="active", limit="5", offset="0", q="",
                    run_id="",
                )):
            result = json.loads(handler.GET("group"))

        self.assertEqual("success", result["status"])
        self.assertEqual(("wgr_room", "", 5, 0), fake.args)
        self.assertEqual(1, result["total"])
        self.assertEqual("wgr_room", result["identity"]["stable_room_id"])

    def test_wechat_group_memory_groups_exposes_only_configured_stable_rooms(self):
        from channel.web.web_channel import WechatGroupMemoriesHandler

        class FakeConfig:
            def get(self, key, default=None):
                values = {
                    "wechat_group_stable_room_ids": ["wgr_a"],
                    "wechat_group_room_ids": ["room@@legacy"],
                }
                return values.get(key, default)

        class FakeKnowledgeService:
            def count_group_memories(self, room_id, query=""):
                return 1

        handler = WechatGroupMemoriesHandler()
        with patch("channel.web.web_channel._require_auth"), \
                patch("channel.web.web_channel.conf", return_value=FakeConfig()), \
                patch.object(WechatGroupMemoriesHandler, "_get_knowledge_service", return_value=FakeKnowledgeService()), \
                patch.object(WechatGroupMemoriesHandler, "_get_room_name_map", return_value={"wgr_a": "A群"}), \
                patch("channel.web.web_channel.web.input", return_value=types.SimpleNamespace(
                    stable_room_id="", runtime_room_id="", room_id="", stable_member_id="",
                    runtime_sender_id="", sender_id="", status="active", limit="20", offset="0", q="",
                    run_id="",
                )):
            result = json.loads(handler.GET("groups"))

        self.assertEqual("success", result["status"])
        self.assertEqual(["wgr_a"], [item["room_id"] for item in result["groups"]])
        self.assertEqual("A群", result["groups"][0]["room_name"])

    def test_wechat_group_memory_groups_does_not_fallback_to_runtime_rooms(self):
        from channel.web.web_channel import WechatGroupMemoriesHandler

        class FakeConfig:
            def get(self, key, default=None):
                values = {
                    "wechat_group_stable_room_ids": [],
                    "wechat_group_room_ids": ["room@@legacy"],
                }
                return values.get(key, default)

        handler = WechatGroupMemoriesHandler()
        with patch("channel.web.web_channel._require_auth"), \
                patch("channel.web.web_channel.conf", return_value=FakeConfig()), \
                patch("channel.web.web_channel.web.input", return_value=types.SimpleNamespace(
                    stable_room_id="", runtime_room_id="", room_id="", stable_member_id="",
                    runtime_sender_id="", sender_id="", status="active", limit="20", offset="0", q="",
                    run_id="",
                )):
            result = json.loads(handler.GET("groups"))

        self.assertEqual("success", result["status"])
        self.assertEqual([], result["groups"])

    def test_wechat_group_memory_group_get_converts_legacy_room_id(self):
        from channel.web.web_channel import WechatGroupMemoriesHandler

        class FakeIdentityService:
            def resolve_legacy_room_id(self, runtime_room_id):
                self.runtime_room_id = runtime_room_id
                return "wgr_room"

        class FakeKnowledgeService:
            def list_group_memories(self, room_id, query="", limit=20, offset=0):
                self.room_id = room_id
                return []

            def count_group_memories(self, room_id, query=""):
                return 0

        handler = WechatGroupMemoriesHandler()
        fake_identity = FakeIdentityService()
        with patch("channel.web.web_channel._require_auth"), \
                patch.object(WechatGroupMemoriesHandler, "_get_identity_service", return_value=fake_identity), \
                patch.object(WechatGroupMemoriesHandler, "_get_knowledge_service", return_value=FakeKnowledgeService()), \
                patch("channel.web.web_channel.web.input", return_value=types.SimpleNamespace(
                    stable_room_id="", runtime_room_id="", room_id="room@@runtime",
                    sender_id="", stable_member_id="", status="active", limit="5", offset="0", q="",
                    run_id="",
                )):
            result = json.loads(handler.GET("group"))

        self.assertEqual("success", result["status"])
        self.assertEqual("room@@runtime", fake_identity.runtime_room_id)
        self.assertEqual("wgr_room", result["identity"]["stable_room_id"])
        self.assertEqual("legacy_runtime_room_id", result["identity"]["source"])

    def test_wechat_group_identity_confirm_room_api_is_disabled(self):
        from channel.web.web_channel import WechatGroupIdentityHandler

        class FakeResolution:
            stable_id = "wgr_room"
            runtime_id = "room@@runtime"
            status = "confirmed"
            confidence = "manual"
            requires_confirmation = False
            display_name = "测试群"
            metadata = {}

        class FakeIdentityService:
            args = None

            def confirm_room_binding(self, stable_room_id, runtime_room_id, actor="", reason=""):
                self.args = (stable_room_id, runtime_room_id, actor, reason)
                return FakeResolution()

        fake = FakeIdentityService()
        handler = WechatGroupIdentityHandler()
        body = {
            "stable_room_id": "wgr_room",
            "runtime_room_id": "room@@runtime",
            "actor": "web",
            "reason": "rescan",
        }
        with patch("channel.web.web_channel._require_auth"), \
                patch.object(WechatGroupIdentityHandler, "_get_identity_service", return_value=fake), \
                patch("channel.web.web_channel.web.data", return_value=json.dumps(body).encode("utf-8")):
            result = json.loads(handler.POST("rooms/confirm"))

        self.assertEqual("error", result["status"])
        self.assertIn("automatic", result["message"])
        self.assertIsNone(fake.args)

    def test_wechat_group_identity_confirm_member_api_is_disabled(self):
        from channel.web.web_channel import ChannelsHandler, WechatGroupIdentityHandler
        from config import conf

        class FakeResolution:
            stable_id = "wgm_member"
            runtime_id = "wxid_runtime"
            status = "confirmed"
            confidence = "manual"
            requires_confirmation = False
            display_name = "Alice"
            metadata = {}

        class FakeIdentityService:
            called = False

            def confirm_member_binding(self, stable_room_id, stable_member_id, runtime_sender_id, actor="", reason=""):
                self.called = True
                return FakeResolution()

        conf()["wechat_group_admin_members"] = [{
            "stable_room_id": "wgr_room",
            "stable_member_id": "wgm_member",
            "legacy_room_id": "room@@runtime",
            "legacy_sender_id": "wxid_runtime",
            "identity_status": "legacy_imported",
        }]
        body = {
            "stable_room_id": "wgr_room",
            "runtime_room_id": "room@@runtime",
            "stable_member_id": "wgm_member",
            "runtime_sender_id": "wxid_runtime",
        }
        handler = WechatGroupIdentityHandler()
        fake = FakeIdentityService()
        with patch("channel.web.web_channel._require_auth"), \
                patch.object(WechatGroupIdentityHandler, "_get_identity_service", return_value=fake), \
                patch.object(ChannelsHandler, "_write_channel_config") as write_config, \
                patch("channel.web.web_channel.web.data", return_value=json.dumps(body).encode("utf-8")):
            result = json.loads(handler.POST("members/confirm"))

        self.assertEqual("error", result["status"])
        self.assertIn("automatic", result["message"])
        self.assertFalse(fake.called)
        admin = conf()["wechat_group_admin_members"][0]
        self.assertEqual("legacy_imported", admin["identity_status"])
        write_config.assert_not_called()

    def test_channels_save_wechat_group_extra_config(self):
        from channel.web.web_channel import ChannelsHandler
        from config import conf

        handler = ChannelsHandler()
        body = {
            "action": "save",
            "channel": "wechat_group",
            "config": {
                "wechat_group_room_ids": ["room@@abc"],
                "wechat_group_names": ["测试群"],
                "wechat_group_persona_prompt": "  自定义人设\r\n第二行  ",
                "wechat_group_persona_preset_id": "tech-duty",
                "wechat_group_alias_sync_cooldown_minutes": "5",
                "wechat_group_recent_context_enabled": False,
                "wechat_group_recent_context_limit": "12",
                "wechat_group_recent_context_minutes": "45",
                "wechat_group_voice_interaction_mode": "free_reply",
                "wechat_group_knowledge_enabled": False,
                "wechat_group_profile_enabled": True,
                "wechat_group_profile_context_limit": "3",
                "wechat_group_group_memory_context_limit": "7",
                "wechat_group_learning_enabled": True,
                "wechat_group_learning_batch_message_limit": "150",
                "wechat_group_learning_profile_min_messages": "4",
                "wechat_group_learning_profile_sample_limit": "12",
                "wechat_group_learning_group_memory_min_messages": "9",
                "wechat_group_learning_group_memory_window_minutes": "90",
                "wechat_group_learning_idle_minutes": "8",
                "wechat_group_learning_auto_apply_threshold": "0.93",
                "wechat_group_learning_max_interval_minutes": "720",
                "wechat_group_learning_history_max_batches": "6",
            },
        }
        with tempfile.TemporaryDirectory() as tmpdir, \
                patch("channel.web.web_channel._require_auth"), \
                patch("channel.web.web_channel.web.data", return_value=json.dumps(body).encode("utf-8")), \
                patch("channel.web.web_channel.get_data_root", return_value=tmpdir):
            result = json.loads(handler.POST())

        self.assertEqual("success", result["status"])
        self.assertEqual(["room@@abc"], conf()["wechat_group_room_ids"])
        self.assertEqual(["测试群"], conf()["wechat_group_names"])
        self.assertEqual("自定义人设\n第二行", conf()["wechat_group_persona_prompt"])
        self.assertEqual("custom", conf()["wechat_group_persona_preset_id"])
        self.assertEqual(5, conf()["wechat_group_alias_sync_cooldown_minutes"])
        self.assertNotIn("wechat_group_recent_context_enabled", conf())
        self.assertNotIn("wechat_group_recent_context_limit", conf())
        self.assertNotIn("wechat_group_recent_context_minutes", conf())
        self.assertEqual("free_reply", conf()["wechat_group_voice_interaction_mode"])
        self.assertFalse(conf()["wechat_group_knowledge_enabled"])
        self.assertTrue(conf()["wechat_group_profile_enabled"])
        self.assertEqual(3, conf()["wechat_group_profile_context_limit"])
        self.assertEqual(7, conf()["wechat_group_group_memory_context_limit"])
        self.assertTrue(conf()["wechat_group_learning_enabled"])
        self.assertEqual(150, conf()["wechat_group_learning_batch_message_limit"])
        self.assertEqual(4, conf()["wechat_group_learning_profile_min_messages"])
        self.assertEqual(12, conf()["wechat_group_learning_profile_sample_limit"])
        self.assertEqual(9, conf()["wechat_group_learning_group_memory_min_messages"])
        self.assertEqual(90, conf()["wechat_group_learning_group_memory_window_minutes"])
        self.assertEqual(8, conf()["wechat_group_learning_idle_minutes"])
        self.assertEqual(0.93, conf()["wechat_group_learning_auto_apply_threshold"])
        self.assertEqual(720, conf()["wechat_group_learning_max_interval_minutes"])
        self.assertEqual(6, conf()["wechat_group_learning_history_max_batches"])

    def test_channels_api_exposes_membership_notice_config_without_absolute_paths(self):
        from channel.web.web_channel import ChannelsHandler
        from config import conf

        conf()["wechat_group_stable_room_ids"] = ["wgr_room"]
        conf()["wechat_group_join_welcome_enabled"] = True
        conf()["wechat_group_join_welcome_image_path"] = (
            "images/wechat_group_membership/welcome.png"
        )
        conf()["wechat_group_join_welcome_room_overrides"] = []

        extra = ChannelsHandler._wechat_group_extra()
        membership = extra["membership_notices"]

        self.assertTrue(membership["join"]["enabled"])
        self.assertIn("{inviter_name}", membership["join"]["placeholders"])
        self.assertNotIn("{remover_name}", membership["join"]["placeholders"])
        self.assertEqual(
            membership["join"]["image_url"],
            "/api/wechat-group/membership-image?path="
            "images%2Fwechat_group_membership%2Fwelcome.png",
        )
        self.assertNotIn(str(Path.home()), json.dumps(membership, ensure_ascii=False))

    def test_channels_save_membership_override_for_newly_selected_stable_room(self):
        from channel.web.web_channel import ChannelsHandler
        from config import conf

        handler = ChannelsHandler()
        body = {
            "action": "save",
            "channel": "wechat_group",
            "config": {
                "wechat_group_stable_room_ids": ["wgr_new"],
                "wechat_group_join_welcome_enabled": True,
                "wechat_group_join_welcome_content_type": "text",
                "wechat_group_join_welcome_text": "欢迎 {member_names}",
                "wechat_group_join_welcome_image_path": "",
                "wechat_group_join_welcome_room_overrides": [{
                    "stable_room_id": "wgr_new",
                    "policy": "custom",
                    "content_type": "text",
                    "text": "欢迎加入 {room_name}，邀请人：{inviter_name}",
                    "image_path": "",
                }],
                "wechat_group_leave_notice_enabled": True,
                "wechat_group_leave_notice_content_type": "text",
                "wechat_group_leave_notice_text": "{member_names} 已离开群聊。",
                "wechat_group_leave_notice_image_path": "",
                "wechat_group_leave_notice_room_overrides": [],
            },
        }
        with tempfile.TemporaryDirectory() as tmpdir, \
                patch("channel.web.web_channel._require_auth"), \
                patch("channel.web.web_channel.web.data", return_value=json.dumps(body).encode("utf-8")), \
                patch("channel.web.web_channel.get_data_root", return_value=tmpdir):
            result = json.loads(handler.POST())
            persisted = json.loads(
                Path(tmpdir, "config.json").read_text(encoding="utf-8")
            )

        self.assertEqual("success", result["status"])
        self.assertEqual(["wgr_new"], conf()["wechat_group_stable_room_ids"])
        self.assertTrue(persisted["wechat_group_join_welcome_enabled"])
        self.assertTrue(persisted["wechat_group_leave_notice_enabled"])
        self.assertEqual(
            "wgr_new",
            conf()["wechat_group_join_welcome_room_overrides"][0]["stable_room_id"],
        )

    def test_channels_save_membership_rejects_cross_event_placeholder(self):
        from channel.web.web_channel import ChannelsHandler
        from config import conf

        conf()["wechat_group_stable_room_ids"] = ["wgr_room"]
        original_text = conf().get("wechat_group_join_welcome_text", "欢迎加入群聊！")
        handler = ChannelsHandler()
        body = {
            "action": "save",
            "channel": "wechat_group",
            "config": {
                "wechat_group_join_welcome_enabled": True,
                "wechat_group_join_welcome_content_type": "text",
                "wechat_group_join_welcome_text": "欢迎 {remover_name}",
            },
        }
        with tempfile.TemporaryDirectory() as tmpdir, \
                patch("channel.web.web_channel._require_auth"), \
                patch("channel.web.web_channel.web.data", return_value=json.dumps(body).encode("utf-8")), \
                patch("channel.web.web_channel.get_data_root", return_value=tmpdir):
            result = json.loads(handler.POST())

        self.assertEqual("error", result["status"])
        self.assertIn("占位符", result["message"])
        self.assertEqual(
            original_text,
            conf().get("wechat_group_join_welcome_text", "欢迎加入群聊！"),
        )

    def test_removing_selected_room_cleans_both_membership_overrides(self):
        from channel.web.web_channel import ChannelsHandler
        from config import conf

        conf()["wechat_group_stable_room_ids"] = ["wgr_room"]
        conf()["wechat_group_join_welcome_room_overrides"] = [{
            "stable_room_id": "wgr_room",
            "policy": "disabled",
        }]
        conf()["wechat_group_leave_notice_room_overrides"] = [{
            "stable_room_id": "wgr_room",
            "policy": "disabled",
        }]

        applied = ChannelsHandler._apply_wechat_group_config({
            "wechat_group_stable_room_ids": [],
        })

        self.assertEqual([], applied["wechat_group_join_welcome_room_overrides"])
        self.assertEqual([], applied["wechat_group_leave_notice_room_overrides"])
        self.assertEqual([], conf()["wechat_group_join_welcome_room_overrides"])
        self.assertEqual([], conf()["wechat_group_leave_notice_room_overrides"])

    def test_membership_image_upload_hashes_content_and_preview_reads_only_scoped_asset(self):
        from PIL import Image
        from channel.web.web_channel import WechatGroupMembershipImageHandler
        from config import conf

        output = BytesIO()
        Image.new("RGB", (3, 2), "white").save(output, format="PNG")
        uploaded = types.SimpleNamespace(
            filename="welcome.png",
            file=BytesIO(output.getvalue()),
        )
        handler = WechatGroupMembershipImageHandler()
        with tempfile.TemporaryDirectory() as workspace, \
                patch("channel.web.web_channel._require_auth"), \
                patch("channel.web.web_channel._raw_web_input", return_value={"file": uploaded}):
            conf()["agent_workspace"] = workspace
            result = json.loads(handler.POST())
            self.assertEqual("success", result["status"])
            self.assertTrue(result["path"].startswith("images/wechat_group_membership/"))
            self.assertNotIn(workspace, json.dumps(result))
            stored = os.path.join(workspace, *result["path"].split("/"))
            self.assertTrue(os.path.isfile(stored))

            with patch("channel.web.web_channel.web.input", return_value=types.SimpleNamespace(path=result["path"])), \
                    patch("channel.web.web_channel.web.header"):
                content = handler.GET()
            self.assertEqual(output.getvalue(), content)

    def test_membership_image_upload_rejects_svg_and_fake_extension(self):
        from channel.web.web_channel import WechatGroupMembershipImageHandler
        from config import conf

        handler = WechatGroupMembershipImageHandler()
        with tempfile.TemporaryDirectory() as workspace, \
                patch("channel.web.web_channel._require_auth"):
            conf()["agent_workspace"] = workspace
            for filename, content in (
                ("image.svg", b"<svg></svg>"),
                ("image.png", b"not an image"),
            ):
                uploaded = types.SimpleNamespace(filename=filename, file=BytesIO(content))
                with self.subTest(filename=filename), \
                        patch("channel.web.web_channel._raw_web_input", return_value={"file": uploaded}):
                    result = json.loads(handler.POST())
                    self.assertEqual("error", result["status"])

    def test_membership_image_preview_rejects_path_traversal(self):
        from channel.web.web_channel import WechatGroupMembershipImageHandler

        handler = WechatGroupMembershipImageHandler()
        with patch("channel.web.web_channel._require_auth"), \
                patch("channel.web.web_channel.web.input", return_value=types.SimpleNamespace(path="../secret.png")), \
                patch(
                    "channel.web.web_channel.web.notfound",
                    return_value=RuntimeError("not found"),
                    create=True,
                ):
            with self.assertRaisesRegex(RuntimeError, "not found"):
                handler.GET()

    def test_membership_notice_console_exposes_complete_editor_and_save_contract(self):
        console_js = Path("channel/web/static/js/console.js").read_text(encoding="utf-8")

        self.assertIn("groups_nav_membership: '进退群消息'", console_js)
        self.assertIn("buildGroupsMembershipPanel(extra)", console_js)
        self.assertIn("insertGroupsMembershipPlaceholder", console_js)
        self.assertIn("/api/wechat-group/membership-image", console_js)
        self.assertIn("class=\"sm:hidden w-full min-h-11", console_js)
        self.assertIn("'wechat_group_join_welcome'", console_js)
        self.assertIn("'wechat_group_leave_notice'", console_js)
        self.assertIn("enabled: source.enabled !== false", console_js)
        self.assertIn("aria-label=\"${escapeHtml(t('groups_membership_enabled'))}\"", console_js)
        for suffix in ("_enabled", "_content_type", "_text", "_image_path", "_room_overrides"):
            self.assertIn("`${prefix}" + suffix + "`", console_js)

    def test_channels_save_wechat_group_stable_room_config(self):
        from channel.web.web_channel import ChannelsHandler
        from config import conf

        handler = ChannelsHandler()
        body = {
            "action": "save",
            "channel": "wechat_group",
            "config": {
                "wechat_group_stable_room_ids": ["wgr_room"],
                "wechat_group_room_ids": ["room@@new"],
            },
        }
        with tempfile.TemporaryDirectory() as tmpdir, \
                patch("channel.web.web_channel._require_auth"), \
                patch("channel.web.web_channel.web.data", return_value=json.dumps(body).encode("utf-8")), \
                patch("channel.web.web_channel.get_data_root", return_value=tmpdir):
            result = json.loads(handler.POST())

        self.assertEqual("success", result["status"])
        self.assertEqual(["wgr_room"], conf()["wechat_group_stable_room_ids"])
        self.assertEqual(["room@@new"], conf()["wechat_group_room_ids"])

    def test_wechat_group_extra_masks_github_webhook_secret(self):
        from channel.web.web_channel import ChannelsHandler, GITHUB_WEBHOOK_SECRET_ENV
        from config import conf

        conf()["github_commit_notify_enabled"] = True
        conf()["github_commit_notify_repository"] = "owner/repository"
        conf()["github_commit_notify_branches"] = ["main", "develop"]
        conf()["github_commit_notify_event_mode"] = "selected"
        conf()["github_commit_notify_events"] = ["push", "pull_request"]
        conf()["github_commit_notify_event_actions"] = {"pull_request": ["opened"]}
        conf()["github_commit_notify_stable_room_id"] = "wgr_room"
        conf()["github_commit_notify_webhook_secret"] = "local-secret-value"
        with patch.dict(os.environ, {GITHUB_WEBHOOK_SECRET_ENV: ""}):
            extra = ChannelsHandler._wechat_group_extra()

        github = extra["github_commit_notify"]
        self.assertTrue(github["enabled"])
        self.assertEqual("owner/repository", github["repository"])
        self.assertEqual(["main", "develop"], github["branches"])
        self.assertEqual("selected", github["event_mode"])
        self.assertEqual(["push", "pull_request"], github["events"])
        self.assertEqual({"pull_request": ["opened"]}, github["event_actions"])
        self.assertEqual(53, len(github["event_catalog"]))
        self.assertEqual(7, len(github["event_categories"]))
        self.assertNotIn("ping", {item["name"] for item in github["event_catalog"]})
        self.assertEqual("wgr_room", github["stable_room_id"])
        self.assertTrue(github["secret_configured"])
        self.assertEqual("config", github["secret_source"])
        self.assertEqual("********", github["secret_masked"])
        self.assertNotIn("local-secret-value", json.dumps(extra, ensure_ascii=False))

    def test_wechat_group_extra_reports_environment_secret_priority(self):
        from channel.web.web_channel import ChannelsHandler, GITHUB_WEBHOOK_SECRET_ENV
        from config import conf

        conf()["github_commit_notify_webhook_secret"] = "local-secret-value"
        with patch.dict(os.environ, {GITHUB_WEBHOOK_SECRET_ENV: "environment-secret-value"}):
            github = ChannelsHandler._wechat_group_extra()["github_commit_notify"]

        self.assertTrue(github["secret_configured"])
        self.assertEqual("environment", github["secret_source"])
        self.assertNotIn("environment-secret-value", json.dumps(github, ensure_ascii=False))
        self.assertNotIn("local-secret-value", json.dumps(github, ensure_ascii=False))

    def test_channels_save_github_commit_notification_config(self):
        from channel.web.web_channel import ChannelsHandler, GITHUB_WEBHOOK_SECRET_ENV
        from config import conf

        handler = ChannelsHandler()
        body = {
            "action": "save",
            "channel": "wechat_group",
            "config": {
                "github_commit_notify_enabled": True,
                "github_commit_notify_repository": "  owner/repository  ",
                "github_commit_notify_branches": ["main", "develop", "main"],
                "github_commit_notify_event_mode": "selected",
                "github_commit_notify_events": ["pull_request", "push", "pull_request"],
                "github_commit_notify_event_actions": {
                    "pull_request": ["opened", "closed", "opened"],
                },
                "github_commit_notify_stable_room_id": "wgr_room",
                "github_commit_notify_max_commits": 99,
                "github_commit_notify_retry_hours": 999,
                "github_commit_notify_delivery_retention_days": 0,
                "github_commit_notify_webhook_secret": "new-local-secret",
            },
        }
        with tempfile.TemporaryDirectory() as tmpdir, \
                patch.dict(os.environ, {GITHUB_WEBHOOK_SECRET_ENV: ""}), \
                patch("channel.web.web_channel._require_auth"), \
                patch("channel.web.web_channel.web.data", return_value=json.dumps(body).encode("utf-8")), \
                patch("channel.web.web_channel.get_data_root", return_value=tmpdir):
            raw_result = handler.POST()
            result = json.loads(raw_result)

        self.assertEqual("success", result["status"])
        self.assertTrue(conf()["github_commit_notify_enabled"])
        self.assertEqual("owner/repository", conf()["github_commit_notify_repository"])
        self.assertEqual(["main", "develop"], conf()["github_commit_notify_branches"])
        self.assertEqual("selected", conf()["github_commit_notify_event_mode"])
        self.assertEqual(["pull_request", "push"], conf()["github_commit_notify_events"])
        self.assertEqual(
            {"pull_request": ["opened", "closed"]},
            conf()["github_commit_notify_event_actions"],
        )
        self.assertEqual("wgr_room", conf()["github_commit_notify_stable_room_id"])
        self.assertEqual(20, conf()["github_commit_notify_max_commits"])
        self.assertEqual(720, conf()["github_commit_notify_retry_hours"])
        self.assertEqual(1, conf()["github_commit_notify_delivery_retention_days"])
        self.assertEqual("new-local-secret", conf()["github_commit_notify_webhook_secret"])
        self.assertNotIn("new-local-secret", raw_result)
        self.assertEqual("********", result["extra"]["github_commit_notify"]["secret_masked"])

    def test_console_places_github_notification_in_basic_settings(self):
        console_js = Path("channel/web/static/js/console.js").read_text(encoding="utf-8")
        basic_start = console_js.index("function buildGroupsBasicPanel(extra)")
        basic_end = console_js.index("function buildGroupsVoiceInteractionPanel", basic_start)
        basic_block = console_js[basic_start:basic_end]

        self.assertIn("buildGroupsGithubCommitNotifyPanel(extra)", basic_block)
        self.assertIn('id="groups-github-target-room"', basic_block)
        self.assertIn("extra.stable_selected_room_ids", basic_block)
        self.assertIn('type="password" value=""', basic_block)
        self.assertIn("saved.secret_source === 'environment'", basic_block)
        self.assertIn('name="groups-github-event-mode"', basic_block)
        self.assertIn('id="groups-github-events-configure"', basic_block)
        self.assertIn("openGroupsGithubEventModal()", basic_block)
        self.assertIn("groups-github-event-modal", basic_block)
        self.assertIn('role="dialog" aria-modal="true"', basic_block)
        self.assertIn("groupsGithubEventModalState", basic_block)
        self.assertIn("data-github-action-event", basic_block)
        self.assertIn("handleGroupsGithubEventModalKeydown", basic_block)
        self.assertIn("if (!document.getElementById('groups-github-notify-enabled')) return true", basic_block)
        self.assertIn("github_commit_notify_event_mode", console_js)
        self.assertIn("github_commit_notify_events", console_js)
        self.assertIn("github_commit_notify_event_actions", console_js)
        self.assertIn("github_commit_notify_webhook_secret", console_js)
        self.assertIn("...githubCommitNotifyConfig", console_js)

    def test_channels_reject_invalid_github_event_configuration(self):
        from channel.web.web_channel import ChannelsHandler

        with self.assertRaisesRegex(ValueError, "Unsupported GitHub webhook events"):
            ChannelsHandler._apply_wechat_group_config({
                "github_commit_notify_event_mode": "selected",
                "github_commit_notify_events": ["push", "not_a_github_event"],
                "github_commit_notify_event_actions": {},
            })

        with self.assertRaisesRegex(ValueError, "Unsupported actions"):
            ChannelsHandler._apply_wechat_group_config({
                "github_commit_notify_event_mode": "selected",
                "github_commit_notify_events": ["pull_request"],
                "github_commit_notify_event_actions": {
                    "pull_request": ["not_an_action"],
                },
            })

    def test_channels_save_invalid_voice_interaction_mode_falls_back_to_force_reply(self):
        from channel.web.web_channel import ChannelsHandler
        from config import conf

        applied = ChannelsHandler._apply_wechat_group_config({
            "wechat_group_voice_interaction_mode": "unsupported",
        })

        self.assertEqual("force_reply", applied["wechat_group_voice_interaction_mode"])
        self.assertEqual("force_reply", conf()["wechat_group_voice_interaction_mode"])

    def test_channels_save_voice_interaction_ignore_mode(self):
        from channel.web.web_channel import ChannelsHandler
        from config import conf

        applied = ChannelsHandler._apply_wechat_group_config({
            "wechat_group_voice_interaction_mode": "ignore",
        })

        self.assertEqual("ignore", applied["wechat_group_voice_interaction_mode"])
        self.assertEqual("ignore", conf()["wechat_group_voice_interaction_mode"])

    def test_channels_extra_exposes_voice_interaction_ignore_mode(self):
        from channel.web.web_channel import ChannelsHandler
        from config import conf

        conf()["wechat_group_voice_interaction_mode"] = "ignore"

        extra = ChannelsHandler._wechat_group_extra()

        self.assertEqual("ignore", extra["voice_interaction"]["mode"])

    def test_console_exposes_wechat_group_voice_interaction_menu(self):
        console_js = Path("channel/web/static/js/console.js").read_text(encoding="utf-8")

        self.assertIn("buildGroupsSectionButton('voice_interaction'", console_js)
        self.assertIn("function buildGroupsVoiceInteractionPanel", console_js)
        self.assertIn('name="groups-voice-interaction-mode"', console_js)
        self.assertIn("wechat_group_voice_interaction_mode: voiceInteractionMode", console_js)
        self.assertIn("saved.mode || 'force_reply'", console_js)
        self.assertIn("value: 'ignore'", console_js)
        self.assertIn("groups_voice_interaction_ignore_hint", console_js)
        self.assertIn("['free_reply', 'ignore'].includes(mode)", console_js)

    def test_channels_save_converts_runtime_id_submitted_as_stable_room_id(self):
        from channel.web.web_channel import ChannelsHandler
        from config import conf

        running = self.FakeRunningWechatGroupChannel(
            status="connected",
            rooms=[{
                "id": "wgr_room",
                "stable_room_id": "wgr_room",
                "runtime_room_id": "room@@runtime",
                "name": "Trusted Room",
                "binding_status": "confirmed",
            }],
        )
        with patch.object(ChannelsHandler, "_get_running_wechat_group_channel", return_value=running):
            applied = ChannelsHandler._apply_wechat_group_config({
                "wechat_group_stable_room_ids": ["room@@runtime"],
            })

        self.assertEqual(["wgr_room"], applied["wechat_group_stable_room_ids"])
        self.assertEqual(["wgr_room"], conf()["wechat_group_stable_room_ids"])

    def test_console_saves_wechat_group_stable_room_ids(self):
        from pathlib import Path

        console_js = Path("channel/web/static/js/console.js").read_text(encoding="utf-8")

        self.assertIn("const selectedStableRoomIds = selectedIds;", console_js)
        self.assertIn("wechat_group_stable_room_ids: selectedStableRoomIds", console_js)
        self.assertIn("wechat_group_room_ids: selectedRuntimeRoomIds", console_js)

    def test_console_profile_edit_requires_stable_member_and_room(self):
        from pathlib import Path

        console_js = Path("channel/web/static/js/console.js").read_text(encoding="utf-8")
        start = console_js.index("function saveGroupsProfileDetail()")
        end = console_js.index("function formatGroupsProfileTimestamp", start)
        save_profile_js = console_js[start:end]

        self.assertIn("const stableMemberId = senderId.startsWith('wgm_') ? senderId : '';", save_profile_js)
        self.assertIn("stable_room_id: groupsProfilesState.roomFilter || ''", save_profile_js)
        self.assertIn("stable_member_id: stableMemberId", save_profile_js)
        self.assertNotIn("runtime_sender_id:", save_profile_js)
        self.assertIn("!groupsProfilesState.roomFilter || !stableMemberId", save_profile_js)
        self.assertNotIn("stable_room_id: roomContext.room_id || groupsProfilesState.roomFilter || ''", save_profile_js)
        self.assertNotIn("stable_member_id: senderId", save_profile_js)

    def test_console_profile_filter_uses_explicit_stable_room_parameter(self):
        from pathlib import Path

        console_js = Path("channel/web/static/js/console.js").read_text(encoding="utf-8")
        start = console_js.index("function refreshGroupsProfilesData(")
        end = console_js.index("function saveGroupsProfileDetail()", start)
        refresh_profiles_js = console_js[start:end]

        self.assertIn("const roomId = groupsProfilesState.roomFilter", refresh_profiles_js)
        self.assertIn(
            "params.set('stable_room_id', roomId)",
            refresh_profiles_js,
        )
        self.assertNotIn(
            "params.set('room_id', groupsProfilesState.roomFilter)",
            refresh_profiles_js,
        )

    def test_console_wechat_group_management_uses_stable_room_api_params(self):
        from pathlib import Path

        console_js = Path("channel/web/static/js/console.js").read_text(encoding="utf-8")

        for token in (
            "/api/wechat-group/members?stable_room_id=",
            "/api/wechat-group/focus/active?stable_room_id=",
            "/api/wechat-group/styles/active?stable_room_id=",
            "/api/wechat-group/stickers/list?stable_room_id=",
            "stable_member_id: stableMemberId",
            "member.identity_status === 'confirmed'",
            "legacy_sender_id: runtimeSenderId",
        ):
            self.assertIn(token, console_js)

        memory_start = console_js.index("async function loadGroupMemoryItems(")
        memory_end = console_js.index("function applyGroupMemorySearch(", memory_start)
        memory_block = console_js[memory_start:memory_end]
        self.assertIn("stable_room_id: roomId", memory_block)
        self.assertIn("/api/wechat-group/memories/group?${params}", memory_block)
        self.assertNotIn("new URLSearchParams({ room_id: roomId", memory_block)
        self.assertNotIn("params.set('room_id'", memory_block)

        for token in (
            "buildGroupsSectionButton('identity'",
            "/api/wechat-group/identity/candidates?entity_type=all",
            "/api/wechat-group/identity/accounts/confirm",
            "/api/wechat-group/identity/rooms/confirm",
            "/api/wechat-group/identity/members/confirm",
            "confirmGroupsIdentityAccount(",
            "confirmGroupsIdentityRoom(",
            "confirmGroupsIdentityMember(",
        ):
            self.assertNotIn(token, console_js)

    def test_console_saved_room_labels_fallback_to_persisted_names(self):
        from pathlib import Path

        console_js = Path("channel/web/static/js/console.js").read_text(encoding="utf-8")
        start = console_js.index("function renderGroupsSelectedRooms(")
        end = console_js.index("function buildGroupsRoomDropdown(", start)
        render_selected_js = console_js[start:end]

        self.assertIn("function renderGroupsSelectedRooms(rooms, selectedIds, selectedNames)", render_selected_js)
        self.assertIn("String(room.name || '')", render_selected_js)
        self.assertIn("selectedNames[idx]", render_selected_js)
        self.assertIn("renderGroupsSelectedRooms(rooms, selectedIds, selectedNames)", console_js)
        self.assertIn(
            "function resolveGroupsSelectedRoomIdsForSave(extra, checkedRoomIds, roomControlsPresent)",
            console_js,
        )
        self.assertIn("function getWechatGroupRoomOptionId", console_js)
        self.assertIn("function isWechatGroupRoomSelected", console_js)
        self.assertIn("selectableByAnyId", console_js)
        self.assertIn(
            "resolveGroupsSelectedRoomIdsForSave(extra, checkedRoomIds, roomControlsPresent)",
            console_js,
        )
        self.assertIn("data-groups-selected-room-id=", render_selected_js)
        self.assertIn("function removeGroupsSelectedRoom(roomId, btn)", console_js)

    def test_console_describes_room_name_as_automatic_recovery_key(self):
        from pathlib import Path

        console_js = Path("channel/web/static/js/console.js").read_text(encoding="utf-8")

        self.assertIn("群名用于重登后自动恢复", console_js)
        self.assertNotIn("群名只用于发现待确认候选", console_js)

    def test_channels_save_wechat_group_free_reply_config(self):
        from channel.web.web_channel import ChannelsHandler
        from config import conf

        handler = ChannelsHandler()
        body = {
            "action": "save",
            "channel": "wechat_group",
            "config": {
                "wechat_group_free_reply_enabled": True,
                "wechat_group_free_reply_stable_room_ids": ["wgr_room"],
                "wechat_group_free_reply_room_ids": ["room@@abc"],
                "wechat_group_blocked_stable_member_ids": ["wgm_blocked"],
                "wechat_group_free_reply_names": ["测试群"],
                "wechat_group_free_reply_activity_level": "active",
                "wechat_group_free_reply_stable_room_activity_levels": {
                    "wgr_room": "quiet",
                    "room@@legacy": "crazy",
                    "wgr_invalid": "invalid",
                },
                "wechat_group_free_reply_mute_minutes": "9999",
                "wechat_group_free_reply_mute_mentions_enabled": True,
                "wechat_group_free_reply_queue_ttl_seconds": "999",
                "wechat_group_free_reply_stale_message_tolerance": "999",
                "wechat_group_free_reply_worker_max_workers": "99",
                "wechat_group_free_reply_worker_queue_size": "9999",
                "wechat_group_free_reply_llm_judge_enabled": False,
                "wechat_group_free_reply_llm_judge_timeout_seconds": "99",
                "wechat_group_free_reply_llm_judge_min_confidence": "2",
                "wechat_group_free_reply_scorer_enabled": True,
                "wechat_group_free_reply_scorer_context_limit": "99",
                "wechat_group_free_reply_scorer_reply_threshold": "2",
                "wechat_group_free_reply_scorer_soft_reply_threshold": "-1",
                "wechat_group_free_reply_scorer_max_tokens": "9999",
                "wechat_group_free_reply_scorer_fallback_to_rules": False,
                "wechat_group_free_reply_force_keywords": "小灯，小风\n前夜",
                "wechat_group_free_reply_profiles": {
                    "active": {
                        "min_score": "25",
                        "min_interval_seconds": "2",
                        "hourly_limit": "3",
                        "consecutive_limit": "4",
                    }
                },
                "wechat_group_free_reply_rule_scores": {
                    "group_question": "40",
                    "banter_opportunity": {"quiet": "1", "normal": "2", "active": "3", "crazy": "4"},
                },
                "wechat_group_free_reply_rule_enabled": {
                    "low_information": False,
                    "below_threshold": True,
                },
            },
        }
        with tempfile.TemporaryDirectory() as tmpdir, \
                patch("channel.web.web_channel._require_auth"), \
                patch("channel.web.web_channel.web.data", return_value=json.dumps(body).encode("utf-8")), \
                patch("channel.web.web_channel.get_data_root", return_value=tmpdir):
            result = json.loads(handler.POST())

        self.assertEqual("success", result["status"])
        self.assertTrue(conf()["wechat_group_free_reply_enabled"])
        self.assertEqual(["wgr_room"], conf()["wechat_group_free_reply_stable_room_ids"])
        self.assertEqual(["room@@abc"], conf()["wechat_group_free_reply_room_ids"])
        self.assertEqual(["wgm_blocked"], conf()["wechat_group_blocked_stable_member_ids"])
        self.assertEqual(["测试群"], conf()["wechat_group_free_reply_names"])
        self.assertEqual("active", conf()["wechat_group_free_reply_activity_level"])
        self.assertEqual(
            {"wgr_room": "quiet"},
            conf()["wechat_group_free_reply_stable_room_activity_levels"],
        )
        self.assertEqual(1440, conf()["wechat_group_free_reply_mute_minutes"])
        self.assertTrue(conf()["wechat_group_free_reply_mute_mentions_enabled"])
        self.assertEqual(600, conf()["wechat_group_free_reply_queue_ttl_seconds"])
        self.assertEqual(100, conf()["wechat_group_free_reply_stale_message_tolerance"])
        self.assertEqual(8, conf()["wechat_group_free_reply_worker_max_workers"])
        self.assertEqual(1000, conf()["wechat_group_free_reply_worker_queue_size"])
        self.assertFalse(conf()["wechat_group_free_reply_llm_judge_enabled"])
        self.assertEqual(30, conf()["wechat_group_free_reply_llm_judge_timeout_seconds"])
        self.assertEqual(1.0, conf()["wechat_group_free_reply_llm_judge_min_confidence"])
        self.assertTrue(conf()["wechat_group_free_reply_scorer_enabled"])
        self.assertEqual(50, conf()["wechat_group_free_reply_scorer_context_limit"])
        self.assertEqual(1.0, conf()["wechat_group_free_reply_scorer_reply_threshold"])
        self.assertEqual(0.0, conf()["wechat_group_free_reply_scorer_soft_reply_threshold"])
        self.assertEqual(2048, conf()["wechat_group_free_reply_scorer_max_tokens"])
        self.assertFalse(conf()["wechat_group_free_reply_scorer_fallback_to_rules"])
        self.assertEqual(["小灯", "小风", "前夜"], conf()["wechat_group_free_reply_force_keywords"])
        self.assertEqual(25, conf()["wechat_group_free_reply_profiles"]["active"]["min_score"])
        self.assertEqual(40, conf()["wechat_group_free_reply_rule_scores"]["group_question"])
        self.assertEqual(
            {"quiet": 1, "normal": 2, "active": 3, "crazy": 4},
            conf()["wechat_group_free_reply_rule_scores"]["banter_opportunity"],
        )
        self.assertFalse(conf()["wechat_group_free_reply_rule_enabled"]["low_information"])
        self.assertTrue(conf()["wechat_group_free_reply_rule_enabled"]["below_threshold"])

    def test_console_saves_wechat_group_free_reply_stable_room_ids(self):
        from pathlib import Path

        console_js = Path("channel/web/static/js/console.js").read_text(encoding="utf-8")

        self.assertIn("const freeReplyStableRoomIds = Array.isArray(freeReply.stable_room_ids) ? freeReply.stable_room_ids : [];", console_js)
        self.assertIn("wechat_group_free_reply_stable_room_ids: freeReplyStableRoomIds", console_js)
        self.assertIn("wechat_group_free_reply_room_ids: freeReplyRuntimeRoomIds", console_js)
        self.assertIn("const stableIdByRuntimeId = new Map", console_js)
        self.assertIn("legacy_room_ids: roomControlsPresent ? []", console_js)
        self.assertIn("const selectable = isWechatGroupRoomSelectable(room);", console_js)
        self.assertIn("const pendingStatuses = ['suspected', 'legacy_imported', 'conflict', 'identity_unresolved'];", console_js)

    def test_group_settings_do_not_accept_scorer_model_credentials(self):
        from channel.web.web_channel import ChannelsHandler
        from config import conf

        conf()["wechat_group_free_reply_scorer_provider"] = "openai"
        conf()["wechat_group_free_reply_scorer_model"] = "gpt-5.4-mini"
        applied = ChannelsHandler._apply_wechat_group_config({
            "wechat_group_free_reply_scorer_provider": "custom:unexpected",
            "wechat_group_free_reply_scorer_model": "unexpected-model",
            "wechat_group_free_reply_scorer_api_key": "unexpected-secret",
        })

        self.assertNotIn("wechat_group_free_reply_scorer_provider", applied)
        self.assertNotIn("wechat_group_free_reply_scorer_model", applied)
        self.assertNotIn("wechat_group_free_reply_scorer_api_key", applied)
        self.assertEqual("openai", conf()["wechat_group_free_reply_scorer_provider"])
        self.assertEqual("gpt-5.4-mini", conf()["wechat_group_free_reply_scorer_model"])

    def test_console_keeps_scorer_behavior_fields_without_credentials(self):
        console_js = Path("channel/web/static/js/console.js").read_text(encoding="utf-8")

        self.assertIn('id="free-reply-scorer-enabled"', console_js)
        self.assertIn(
            "buildFreeReplyNumberField('free-reply-scorer-context-limit'",
            console_js,
        )
        self.assertIn(
            "wechat_group_free_reply_scorer_fallback_to_rules: freeReply.scorer_fallback_to_rules",
            console_js,
        )
        self.assertNotIn('id="free-reply-scorer-provider"', console_js)
        self.assertNotIn('id="free-reply-scorer-model"', console_js)
        self.assertNotIn('id="free-reply-scorer-api-key"', console_js)

    def test_console_explains_wechat_group_free_reply_llm_decision(self):
        from pathlib import Path

        console_js = Path("channel/web/static/js/console.js").read_text(encoding="utf-8")

        self.assertIn("wechat_group_free_reply_llm_hint", console_js)
        self.assertIn("只判断“是否适合接话”，不生成最终回复", console_js)
        self.assertIn("模型失败或 JSON 无效时默认不回复", console_js)
        self.assertIn('aria-describedby="free-reply-llm-hint"', console_js)

    def test_console_exposes_and_saves_per_room_free_reply_activity_levels(self):
        console_js = Path("channel/web/static/js/console.js").read_text(encoding="utf-8")

        self.assertIn("data-wechat-group-free-reply-room-level", console_js)
        self.assertIn("function syncWechatGroupFreeReplyRoomLevelState", console_js)
        self.assertIn("wechat_group_free_reply_follow_global", console_js)
        self.assertIn("stable_room_activity_levels", console_js)
        self.assertIn(
            "wechat_group_free_reply_stable_room_activity_levels: freeReply.stable_room_activity_levels",
            console_js,
        )
        self.assertIn("wechat_group_free_reply_default_level_profiles", console_js)

    def test_channels_save_wechat_group_image_config(self):
        from channel.web.web_channel import ChannelsHandler
        from config import conf

        handler = ChannelsHandler()
        body = {
            "action": "save",
            "channel": "wechat_group",
            "config": {
                "wechat_group_image_understanding_enabled": False,
                "wechat_group_image_understanding_comment_enabled": False,
                "wechat_group_image_understanding_prompt": "  describe\nbriefly  ",
                "wechat_group_image_understanding_cache_minutes": "999",
                "wechat_group_free_reply_image_understanding_enabled": True,
                "wechat_group_multimodal_context_enabled": False,
                "wechat_group_multimodal_image_understanding_context_enabled": False,
                "wechat_group_multimodal_free_reply_image_context_enabled": True,
                "wechat_group_multimodal_same_sender_window_seconds": "999",
                "wechat_group_multimodal_unique_image_window_seconds": "0",
                "wechat_group_multimodal_quote_sender_window_minutes": "999",
                "wechat_group_multimodal_max_recent_messages": "999",
                "wechat_group_image_create_hourly_limit": "999",
                "wechat_group_video_understanding_enabled": True,
                "wechat_group_forward_preview_enabled": False,
                "wechat_group_quote_context_enabled": False,
                "tools_web_fetch_proxy": " http://127.0.0.1:7890 ",
                "image_generation_proxy_enabled": True,
                "image_generation_proxy_domains": "assets.grok.com, *.grok.com\nhttps://cdn.example.com/path",
            },
        }
        with tempfile.TemporaryDirectory() as tmpdir, \
                patch("channel.web.web_channel._require_auth"), \
                patch("channel.web.web_channel.web.data", return_value=json.dumps(body).encode("utf-8")), \
                patch("channel.web.web_channel.get_data_root", return_value=tmpdir):
            result = json.loads(handler.POST())

        self.assertEqual("success", result["status"])
        self.assertFalse(conf()["wechat_group_image_understanding_enabled"])
        self.assertFalse(conf()["wechat_group_image_understanding_comment_enabled"])
        self.assertEqual("describe\nbriefly", conf()["wechat_group_image_understanding_prompt"])
        self.assertEqual(120, conf()["wechat_group_image_understanding_cache_minutes"])
        self.assertTrue(conf()["wechat_group_free_reply_image_understanding_enabled"])
        self.assertFalse(conf()["wechat_group_multimodal_context_enabled"])
        self.assertFalse(conf()["wechat_group_multimodal_image_understanding_context_enabled"])
        self.assertTrue(conf()["wechat_group_multimodal_free_reply_image_context_enabled"])
        self.assertEqual(600, conf()["wechat_group_multimodal_same_sender_window_seconds"])
        self.assertEqual(5, conf()["wechat_group_multimodal_unique_image_window_seconds"])
        self.assertEqual(120, conf()["wechat_group_multimodal_quote_sender_window_minutes"])
        self.assertEqual(100, conf()["wechat_group_multimodal_max_recent_messages"])
        self.assertEqual(100, conf()["wechat_group_image_create_hourly_limit"])
        self.assertTrue(conf()["wechat_group_video_understanding_enabled"])
        self.assertFalse(conf()["wechat_group_forward_preview_enabled"])
        self.assertFalse(conf()["wechat_group_quote_context_enabled"])
        self.assertEqual("http://127.0.0.1:7890", conf()["tools"]["web_fetch"]["proxy"])
        self.assertTrue(conf()["skills"]["image-generation"]["proxy_enabled"])
        self.assertEqual(
            ["assets.grok.com", "*.grok.com", "cdn.example.com"],
            conf()["skills"]["image-generation"]["proxy_domains"],
        )

    def test_channels_api_returns_image_generation_proxy_config(self):
        from channel.web.web_channel import ChannelsHandler
        from config import conf

        conf()["tools"] = {"web_fetch": {"proxy": "http://127.0.0.1:7890"}}
        conf()["skills"] = {
            "image-generation": {
                "proxy_enabled": True,
                "proxy_domains": ["assets.grok.com", "*.grok.com"],
            }
        }
        handler = ChannelsHandler()

        with patch("channel.web.web_channel._require_auth"), \
                patch("channel.web.web_channel.conf", return_value=conf()):
            result = json.loads(handler.GET())

        item = self._wechat_group_item(result)
        self.assertEqual("http://127.0.0.1:7890", item["extra"]["basic"]["proxy"])
        self.assertTrue(item["extra"]["image"]["generation_proxy_enabled"])
        self.assertEqual(["assets.grok.com", "*.grok.com"], item["extra"]["image"]["generation_proxy_domains"])

    def test_channels_save_wechat_group_humanization_config(self):
        from channel.web.web_channel import ChannelsHandler
        from config import conf

        handler = ChannelsHandler()
        body = {
            "action": "save",
            "channel": "wechat_group",
            "config": {
                "wechat_group_focus_enabled": False,
                "wechat_group_focus_recent_message_limit": "0",
                "wechat_group_focus_context_message_limit": "5",
                "wechat_group_focus_stack_depth": "0",
                "wechat_group_focus_stale_rounds": "0",
                "wechat_group_focus_min_keywords": "0",
                "wechat_group_focus_archive_recall_limit": "6",
                "wechat_group_style_enabled": False,
                "wechat_group_style_learning_enabled": False,
                "wechat_group_style_context_limit": "4",
                "wechat_group_style_candidate_min_evidence": "0",
                "wechat_group_style_learning_batch_limit": "88",
                "wechat_group_style_auto_apply_enabled": True,
                "wechat_group_sticker_enabled": False,
                "wechat_group_sticker_auto_collect_enabled": False,
                "wechat_group_sticker_context_limit": "0",
                "wechat_group_sticker_reply_percent": "999",
                "wechat_group_sticker_max_size_mb": "99",
                "wechat_group_sticker_daily_send_limit": "999",
                "wechat_group_sticker_storage_dir": "  stickers/cache  ",
                "wechat_group_sticker_online_search_enabled": True,
                "wechat_group_sticker_online_provider": "other",
                "wechat_group_sticker_online_endpoint": "http://unsafe.example.com/meme",
                "wechat_group_sticker_online_allowed_domains": " biaoqing.gtimg.com\nhttps://tugelepic.mse.sogou.com/path\nlocalhost\n",
                "wechat_group_sticker_online_allow_gif": False,
                "wechat_group_sticker_online_search_count": "99",
                "wechat_group_sticker_cooldown_seconds": "1",
                "wechat_group_humanized_context_enabled": False,
                "wechat_group_context_persist_raw_user_only": False,
                "wechat_group_context_engine_mode": "v2",
                "wechat_group_session_scope": "room",
                "wechat_group_thread_followup_ttl_minutes": "9999",
                "wechat_group_room_singleflight_enabled": False,
                "wechat_group_rolling_summary_enabled": True,
                "wechat_group_tool_continuation_enabled": True,
                "wechat_group_continuation_enabled": False,
                "wechat_group_reply_policy_enabled": False,
                "wechat_group_archive_evidence_enabled": False,
                "wechat_group_archive_evidence_limit": "999",
                "wechat_group_archive_evidence_days": "0",
                "wechat_group_archive_evidence_recent_limit": "-1",
                "wechat_group_local_summary_enabled": False,
                "wechat_group_local_summary_limit": "0",
                "wechat_group_local_summary_hours": "999",
                "wechat_group_reference_policy_enabled": False,
                "wechat_group_link_policy_enabled": False,
                "wechat_group_response_cleanup_enabled": False,
                "wechat_group_response_cleanup_max_chars": "10",
            },
        }
        with tempfile.TemporaryDirectory() as tmpdir, \
                patch("channel.web.web_channel._require_auth"), \
                patch("channel.web.web_channel.web.data", return_value=json.dumps(body).encode("utf-8")), \
                patch("channel.web.web_channel.get_data_root", return_value=tmpdir):
            result = json.loads(handler.POST())

        self.assertEqual("success", result["status"])
        self.assertFalse(conf()["wechat_group_focus_enabled"])
        self.assertEqual(1, conf()["wechat_group_focus_recent_message_limit"])
        self.assertEqual(5, conf()["wechat_group_focus_context_message_limit"])
        self.assertEqual(1, conf()["wechat_group_focus_stack_depth"])
        self.assertEqual(1, conf()["wechat_group_focus_stale_rounds"])
        self.assertEqual(1, conf()["wechat_group_focus_min_keywords"])
        self.assertEqual(6, conf()["wechat_group_focus_archive_recall_limit"])
        self.assertFalse(conf()["wechat_group_style_enabled"])
        self.assertFalse(conf()["wechat_group_style_learning_enabled"])
        self.assertEqual(4, conf()["wechat_group_style_context_limit"])
        self.assertEqual(1, conf()["wechat_group_style_candidate_min_evidence"])
        self.assertEqual(88, conf()["wechat_group_style_learning_batch_limit"])
        self.assertTrue(conf()["wechat_group_style_auto_apply_enabled"])
        self.assertFalse(conf()["wechat_group_sticker_enabled"])
        self.assertFalse(conf()["wechat_group_sticker_auto_collect_enabled"])
        self.assertEqual(1, conf()["wechat_group_sticker_context_limit"])
        self.assertEqual(100, conf()["wechat_group_sticker_reply_percent"])
        self.assertEqual(20, conf()["wechat_group_sticker_max_size_mb"])
        self.assertEqual(200, conf()["wechat_group_sticker_daily_send_limit"])
        self.assertEqual("stickers/cache", conf()["wechat_group_sticker_storage_dir"])
        self.assertTrue(conf()["wechat_group_sticker_online_search_enabled"])
        self.assertEqual("xiaoapi", conf()["wechat_group_sticker_online_provider"])
        self.assertEqual("https://api.suol.cc/v1/meme.php", conf()["wechat_group_sticker_online_endpoint"])
        self.assertEqual(
            ["biaoqing.gtimg.com", "tugelepic.mse.sogou.com"],
            conf()["wechat_group_sticker_online_allowed_domains"],
        )
        self.assertFalse(conf()["wechat_group_sticker_online_allow_gif"])
        self.assertEqual(40, conf()["wechat_group_sticker_online_search_count"])
        self.assertEqual(5, conf()["wechat_group_sticker_cooldown_seconds"])
        self.assertNotIn("wechat_group_humanized_context_enabled", conf())
        self.assertNotIn("wechat_group_context_persist_raw_user_only", conf())
        self.assertNotIn("wechat_group_context_engine_mode", conf())
        self.assertEqual("room", conf()["wechat_group_session_scope"])
        self.assertEqual(1440, conf()["wechat_group_thread_followup_ttl_minutes"])
        self.assertNotIn("wechat_group_room_singleflight_enabled", conf())
        self.assertTrue(conf()["wechat_group_rolling_summary_enabled"])
        self.assertTrue(conf()["wechat_group_tool_continuation_enabled"])
        self.assertNotIn("wechat_group_continuation_enabled", conf())
        self.assertNotIn("wechat_group_reply_policy_enabled", conf())
        self.assertFalse(conf()["wechat_group_archive_evidence_enabled"])
        self.assertNotIn("wechat_group_archive_evidence_limit", conf())
        self.assertEqual(1, conf()["wechat_group_archive_evidence_days"])
        self.assertNotIn("wechat_group_archive_evidence_recent_limit", conf())
        self.assertNotIn("wechat_group_local_summary_enabled", conf())
        self.assertNotIn("wechat_group_local_summary_limit", conf())
        self.assertNotIn("wechat_group_local_summary_hours", conf())
        self.assertNotIn("wechat_group_reference_policy_enabled", conf())
        self.assertNotIn("wechat_group_link_policy_enabled", conf())
        self.assertNotIn("wechat_group_response_cleanup_enabled", conf())
        self.assertEqual(100, conf()["wechat_group_response_cleanup_max_chars"])

    def test_console_updates_free_reply_profile_fields_when_level_changes(self):
        with open("channel/web/static/js/console.js", "r", encoding="utf-8") as f:
            console_js = f.read()

        self.assertIn("function syncFreeReplyProfileFields", console_js)
        self.assertIn("free-reply-activity-level", console_js)
        self.assertIn("syncFreeReplyProfileFields(extra.free_reply || {})", console_js)

    def test_console_exposes_free_reply_force_keywords_setting(self):
        with open("channel/web/static/js/console.js", "r", encoding="utf-8") as f:
            console_js = f.read()

        self.assertIn("free-reply-force-keywords", console_js)
        self.assertIn("wechat_group_free_reply_force_keywords", console_js)
        self.assertIn("force_keywords", console_js)

    def test_console_exposes_and_saves_free_reply_mute_minutes(self):
        with open("channel/web/static/js/console.js", "r", encoding="utf-8") as f:
            console_js = f.read()

        self.assertIn("free-reply-mute-minutes", console_js)
        self.assertIn("free.mute_minutes ?? 10", console_js)
        self.assertIn("saved.mute_minutes ?? 10", console_js)
        self.assertIn("wechat_group_free_reply_mute_minutes: freeReply.mute_minutes", console_js)
        self.assertIn("aria-describedby", console_js)

    def test_console_exposes_and_saves_mute_mentions_switch(self):
        with open("channel/web/static/js/console.js", "r", encoding="utf-8") as f:
            console_js = f.read()

        self.assertIn("free-reply-mute-mentions-enabled", console_js)
        self.assertIn("free.mute_mentions_enabled === true", console_js)
        self.assertIn("saved.mute_mentions_enabled === true", console_js)
        self.assertIn("grid grid-cols-1 md:grid-cols-2", console_js)
        self.assertIn("peer-focus:ring-2", console_js)
        self.assertIn("dark:peer-focus:ring-offset-[#111111]", console_js)
        self.assertIn(
            "wechat_group_free_reply_mute_mentions_enabled: freeReply.mute_mentions_enabled",
            console_js,
        )

    def test_console_exposes_and_saves_stale_message_tolerance(self):
        with open("channel/web/static/js/console.js", "r", encoding="utf-8") as f:
            console_js = f.read()

        self.assertIn("free-reply-stale-tolerance", console_js)
        self.assertIn("free.stale_message_tolerance ?? 5", console_js)
        self.assertIn("saved.stale_message_tolerance ?? 5", console_js)
        self.assertIn(
            "wechat_group_free_reply_stale_message_tolerance: freeReply.stale_message_tolerance",
            console_js,
        )
        self.assertIn("wechat_group_free_reply_stale_tolerance_hint", console_js)
        self.assertIn('type="number" inputmode="numeric"', console_js)

    def test_console_compacts_free_reply_number_fields_in_one_desktop_row(self):
        with open("channel/web/static/js/console.js", "r", encoding="utf-8") as f:
            console_js = f.read()
        with open("channel/web/static/css/console.css", "r", encoding="utf-8") as f:
            console_css = f.read()

        compact_grid_index = console_js.find('class="free-reply-compact-grid mt-3"')
        self.assertGreater(compact_grid_index, -1)
        for field_id in [
            "free-reply-min-score",
            "free-reply-min-interval",
            "free-reply-hourly-limit",
            "free-reply-consecutive-limit",
            "free-reply-queue-ttl",
            "free-reply-stale-tolerance",
            "free-reply-worker-max-workers",
            "free-reply-worker-queue-size",
        ]:
            self.assertGreater(console_js.find(field_id, compact_grid_index), compact_grid_index)

        self.assertIn(".free-reply-compact-grid", console_css)
        self.assertIn("repeat(8, minmax(0, 1fr))", console_css)

    def test_console_renders_free_reply_rules_as_table_with_chinese_labels_and_scores(self):
        with open("channel/web/static/js/console.js", "r", encoding="utf-8") as f:
            console_js = f.read()

        self.assertIn("function buildFreeReplyRulesTable", console_js)
        self.assertIn("free-reply-rules-table", console_js)
        self.assertIn("wechat_group_free_reply_rule_description", console_js)
        self.assertIn("wechat_group_free_reply_rule_score", console_js)
        self.assertIn("rule.label_zh", console_js)
        self.assertIn("data-free-reply-rule-score", console_js)
        self.assertIn("data-free-reply-rule-enabled", console_js)
        self.assertIn("function readWechatGroupFreeReplyRuleScores", console_js)
        self.assertIn("function readWechatGroupFreeReplyRuleEnabled", console_js)
        self.assertIn("function readFreeReplyRuleAttr", console_js)
        self.assertIn("wechat_group_free_reply_rule_scores: freeReply.rule_scores", console_js)
        self.assertIn("wechat_group_free_reply_rule_enabled: freeReply.rule_enabled", console_js)
        self.assertIn("wechat_group_free_reply_rules_not_persisted", console_js)

    def test_console_contains_wechat_group_admin_ui(self):
        with open("channel/web/static/js/console.js", "r", encoding="utf-8") as f:
            console_js = f.read()

        self.assertIn("groups_nav_rooms: '群与管理员'", console_js)
        self.assertIn("groups_admin_member_search_placeholder", console_js)
        self.assertIn("wechat_group_admin_members", console_js)
        self.assertIn("groups_blacklist_title", console_js)
        self.assertIn("groups_blacklist_member_search_placeholder", console_js)
        self.assertIn("wechat_group_blacklist_members", console_js)
        self.assertIn("blacklist_members", console_js)
        self.assertIn("buildGroupsBlacklistPanel", console_js)
        self.assertIn("wechat_group_admin_required_permissions", console_js)
        self.assertIn("permission_definitions", console_js)
        self.assertIn("groups_admin_permission_enabled", console_js)
        self.assertIn("groups_admin_permission_disabled", console_js)
        self.assertIn("groups_admin_permission_blocked_behavior", console_js)
        self.assertIn("groups_admin_permission_allowed_behavior", console_js)
        self.assertIn("groups_admin_permission_examples", console_js)
        self.assertIn("groups_admin_permission_guard_layers", console_js)
        self.assertIn("groups_admin_permission_affected_objects", console_js)
        self.assertIn("toggleGroupsAdminPermissionDetails", console_js)
        self.assertIn("/api/wechat-group/members", console_js)
        self.assertNotIn("id=\"groups-room-names\"", console_js)

    def test_console_reload_admin_members_when_admin_room_changes(self):
        with open("channel/web/static/js/console.js", "r", encoding="utf-8") as f:
            console_js = f.read()

        change_start = console_js.find("function changeGroupsAdminRoom")
        search_start = console_js.find("function searchGroupsAdminMembers")
        toggle_start = console_js.find("function toggleGroupsAdminCandidate")
        self.assertGreater(change_start, -1)
        self.assertGreater(search_start, -1)
        self.assertGreater(toggle_start, search_start)

        change_block = console_js[change_start:search_start]
        search_block = console_js[search_start:toggle_start]

        self.assertIn("searchGroupsAdminMembers()", change_block)
        self.assertIn("const requestedRoomId = roomId", search_block)
        self.assertIn("if (groupsAdminState.roomId !== requestedRoomId) return", search_block)

    def test_console_auto_refreshes_wechat_group_rooms_when_groups_view_loads(self):
        with open("channel/web/static/js/console.js", "r", encoding="utf-8") as f:
            console_js = f.read()

        self.assertIn("let wechatGroupRoomsAutoRefreshTriggered = false;", console_js)
        self.assertIn("function maybeAutoRefreshWechatGroupRooms()", console_js)
        self.assertIn("if (!['logged_in', 'connected'].includes(loginStatus)) return;", console_js)
        self.assertIn("refreshWechatGroupRooms({ silent: true });", console_js)
        self.assertIn("maybeAutoRefreshWechatGroupRooms();", console_js)

    def test_console_refresh_rooms_keeps_normalized_rooms_and_selection(self):
        with open("channel/web/static/js/console.js", "r", encoding="utf-8") as f:
            console_js = f.read()

        refresh_start = console_js.find("function refreshWechatGroupRooms")
        save_start = console_js.find("function saveWechatGroupSettings")
        self.assertGreater(refresh_start, -1)
        self.assertGreater(save_start, refresh_start)
        refresh_block = console_js[refresh_start:save_start]

        # Must prefer normalized extra.rooms; raw data.rooms would use runtime ids and uncheck wgr_* selections.
        self.assertIn("if (Array.isArray(data.extra?.rooms))", refresh_block)
        self.assertIn("ch.extra.rooms = data.extra.rooms;", refresh_block)
        self.assertNotIn("ch.extra.rooms = data.rooms || ch.extra.rooms || [];", refresh_block)
        self.assertIn("previousSelection", refresh_block)
        self.assertIn("function getWechatGroupRoomOptionId", console_js)
        self.assertIn("function isWechatGroupRoomSelected", console_js)
        self.assertIn("isWechatGroupRoomSelected(room, selectedSet)", console_js)

    def test_console_contains_wechat_group_image_settings(self):
        with open("channel/web/static/js/console.js", "r", encoding="utf-8") as f:
            console_js = f.read()

        self.assertIn("function readWechatGroupImageSettings", console_js)
        self.assertIn("groups-image-understanding-enabled", console_js)
        self.assertIn("groups-image-free-reply-understanding-enabled", console_js)
        self.assertIn("groups-multimodal-context-enabled", console_js)
        self.assertIn("groups-multimodal-image-context-enabled", console_js)
        self.assertIn("groups-multimodal-free-reply-image-context-enabled", console_js)
        self.assertIn("groups-multimodal-same-sender-window-seconds", console_js)
        self.assertIn("groups-multimodal-unique-image-window-seconds", console_js)
        self.assertIn("groups-multimodal-quote-sender-window-minutes", console_js)
        self.assertIn("groups-multimodal-max-recent-messages", console_js)
        self.assertIn("groups-image-create-hourly-limit", console_js)
        self.assertIn("wechat_group_free_reply_image_understanding_enabled", console_js)
        self.assertIn("wechat_group_multimodal_context_enabled", console_js)
        self.assertIn("wechat_group_multimodal_image_understanding_context_enabled", console_js)
        self.assertIn("wechat_group_multimodal_free_reply_image_context_enabled", console_js)
        self.assertIn("wechat_group_image_create_hourly_limit", console_js)
        self.assertIn("groups-video-understanding-enabled", console_js)
        self.assertIn("groups-forward-preview-enabled", console_js)
        self.assertIn("groups-quote-context-enabled", console_js)
        self.assertIn("wechat_group_video_understanding_enabled", console_js)
        self.assertIn("wechat_group_forward_preview_enabled", console_js)
        self.assertIn("wechat_group_quote_context_enabled", console_js)
        self.assertIn("groups-basic-proxy", console_js)
        self.assertIn("groups_image_generation_proxy_enabled", console_js)
        self.assertIn("groups-image-generation-proxy-enabled", console_js)
        self.assertIn("groups-image-generation-proxy-domains", console_js)
        self.assertIn("tools_web_fetch_proxy", console_js)
        self.assertIn("image_generation_proxy_enabled", console_js)
        self.assertIn("image_generation_proxy_domains", console_js)

    def test_console_contains_wechat_group_alias_sync_cooldown_setting(self):
        with open("channel/web/static/js/console.js", "r", encoding="utf-8") as f:
            console_js = f.read()

        self.assertIn("groups-alias-sync-cooldown-minutes", console_js)
        self.assertIn("groups_alias_sync_cooldown_minutes", console_js)
        self.assertIn("groups_alias_sync_cooldown_minutes_hint", console_js)
        self.assertIn("wechat_group_alias_sync_cooldown_minutes", console_js)

    def test_console_labels_profile_common_words_as_common_words(self):
        with open("channel/web/static/js/console.js", "r", encoding="utf-8") as f:
            console_js = f.read()

        self.assertIn("groups_memory_common_words: '常用词'", console_js)
        self.assertIn("groups_memory_common_words: 'Common words'", console_js)
        self.assertIn("groups-profiles-detail-common-words", console_js)
        self.assertNotIn("groups-profiles-detail-expertise", console_js)
        self.assertNotIn("groups_memory_expertise: '专业背景'", console_js)

    def test_wechat_group_extra_returns_running_free_reply_status(self):
        from channel.web.web_channel import ChannelsHandler

        running = Mock(free_reply_status=Mock(return_value={
            "config": {"enabled": True},
            "rules": {"positive": [], "negative": []},
            "last_decision": {"triggered": True},
            "worker": {"running": True},
            "scorer": {"scored": 3},
        }))

        with patch.object(ChannelsHandler, "_get_running_wechat_group_channel", return_value=running):
            extra = ChannelsHandler._wechat_group_extra()

        self.assertIn("free_reply", extra)
        self.assertTrue(extra["free_reply"]["enabled"])
        self.assertEqual({"triggered": True}, extra["free_reply"]["last_decision"])
        self.assertEqual({"running": True}, extra["free_reply"]["worker"])
        self.assertEqual({"scored": 3}, extra["free_reply"]["scorer"])

    def test_wechat_group_style_candidates_api_uses_service(self):
        from channel.web.web_channel import WechatGroupStylesHandler

        class FakeStyleService:
            def list_candidates(self, room_id, limit=20):
                self.args = (room_id, limit)
                return [{"style_id": "style-1", "status": "candidate"}]

        fake = FakeStyleService()
        handler = WechatGroupStylesHandler()
        with patch("channel.web.web_channel._require_auth"), \
                patch.object(WechatGroupStylesHandler, "_get_style_service", return_value=fake), \
                patch("channel.web.web_channel.web.input", return_value=types.SimpleNamespace(room_id="room@@abc", q="", limit="5")):
            result = json.loads(handler.GET("candidates"))

        self.assertEqual("success", result["status"])
        self.assertEqual("style-1", result["cards"][0]["style_id"])
        self.assertEqual(("room@@abc", 5), fake.args)

    def test_wechat_group_style_review_api_uses_service(self):
        from channel.web.web_channel import WechatGroupStylesHandler

        class FakeStyleService:
            def review_style(self, room_id, style_id, action="approve"):
                self.args = (room_id, style_id, action)
                return {"style_id": style_id, "status": "active"}

        fake = FakeStyleService()
        body = {"room_id": "room@@abc", "style_id": "style-1", "action": "approve"}
        handler = WechatGroupStylesHandler()
        with patch("channel.web.web_channel._require_auth"), \
                patch.object(WechatGroupStylesHandler, "_get_style_service", return_value=fake), \
                patch("channel.web.web_channel.web.data", return_value=json.dumps(body).encode("utf-8")):
            result = json.loads(handler.POST("review"))

        self.assertEqual("success", result["status"])
        self.assertEqual("active", result["card"]["status"])
        self.assertEqual(("room@@abc", "style-1", "approve"), fake.args)

    def test_wechat_group_focus_active_api_uses_service(self):
        from channel.web.web_channel import WechatGroupFocusHandler

        class FakeFocusService:
            def list_active_focus(self, room_id, limit=None):
                self.args = (room_id, limit)
                return [{"frame_id": "focus-1", "title": "release"}]

        fake = FakeFocusService()
        handler = WechatGroupFocusHandler()
        with patch("channel.web.web_channel._require_auth"), \
                patch.object(WechatGroupFocusHandler, "_get_focus_service", return_value=fake), \
                patch("channel.web.web_channel.web.input", return_value=types.SimpleNamespace(room_id="room@@abc", q="", limit="3")):
            result = json.loads(handler.GET("active"))

        self.assertEqual("success", result["status"])
        self.assertEqual("focus-1", result["focus"][0]["frame_id"])
        self.assertEqual(("room@@abc", 3), fake.args)

    def test_wechat_group_focus_archive_api_uses_service(self):
        from channel.web.web_channel import WechatGroupFocusHandler

        class FakeFocusService:
            def search_focus(self, room_id, query="", limit=20):
                self.args = (room_id, query, limit)
                return [{"frame_id": "focus-2", "title": "release archive", "participants": ["wxid_alice", "wxid_bob"]}]

        class FakeArchive:
            def list_members(self, room_id, query="", limit=20):
                self.args = (room_id, query, limit)
                return [
                    {"sender_id": "wxid_alice", "sender_nickname": "Alice In Group"},
                    {"sender_id": "wxid_bob", "sender_nickname": "Bob In Group"},
                ]

        fake = FakeFocusService()
        archive = FakeArchive()
        handler = WechatGroupFocusHandler()
        with patch("channel.web.web_channel._require_auth"), \
                patch.object(WechatGroupFocusHandler, "_get_focus_service", return_value=fake), \
                patch.object(WechatGroupFocusHandler, "_get_archive", return_value=archive), \
                patch("channel.web.web_channel.web.input", return_value=types.SimpleNamespace(room_id="room@@abc", q="release", limit="4")):
            result = json.loads(handler.GET("archive"))

        self.assertEqual("success", result["status"])
        self.assertEqual("focus-2", result["focus"][0]["frame_id"])
        self.assertEqual(["Alice In Group", "Bob In Group"], result["focus"][0]["participants"])
        self.assertEqual(("room@@abc", "release", 4), fake.args)
        self.assertEqual(("room@@abc", "", 500), archive.args)

    def test_wechat_group_stickers_list_api_uses_service(self):
        from channel.web.web_channel import WechatGroupStickersHandler

        class FakeStickerService:
            def list_stickers(self, room_id, query="", limit=20, status=""):
                self.args = (room_id, query, limit, status)
                return [{"sticker_id": "sticker-1", "status": "active"}]

        fake = FakeStickerService()
        handler = WechatGroupStickersHandler()
        with patch("channel.web.web_channel._require_auth"), \
                patch.object(WechatGroupStickersHandler, "_get_sticker_service", return_value=fake), \
                patch("channel.web.web_channel.web.input", return_value=types.SimpleNamespace(room_id="room@@abc", q="cat", limit="6", status="active")):
            result = json.loads(handler.GET("list"))

        self.assertEqual("success", result["status"])
        self.assertEqual("sticker-1", result["stickers"][0]["sticker_id"])
        self.assertEqual(("room@@abc", "cat", 6, "active"), fake.args)

    def test_wechat_group_stickers_online_search_api_hides_internal_url(self):
        from channel.web.web_channel import WechatGroupStickersHandler

        class FakeStickerService:
            def search_online_stickers(self, room_id, query="", limit=5, seed=""):
                self.args = (room_id, query, limit, seed)
                return [{
                    "source": "online",
                    "online_id": "online-1",
                    "description": "开心",
                    "_url": "https://biaoqing.gtimg.com/hidden.png",
                    "_rank": 1,
                }]

        fake = FakeStickerService()
        handler = WechatGroupStickersHandler()
        with patch("channel.web.web_channel._require_auth"), \
                patch.object(WechatGroupStickersHandler, "_get_sticker_service", return_value=fake), \
                patch("channel.web.web_channel.web.input", return_value=types.SimpleNamespace(room_id="room@@abc", q="开心", limit="4", status="")):
            result = json.loads(handler.GET("search-online"))

        self.assertEqual("success", result["status"])
        self.assertEqual("online-1", result["stickers"][0]["online_id"])
        self.assertNotIn("_url", result["stickers"][0])
        self.assertNotIn("_rank", result["stickers"][0])
        self.assertEqual(("room@@abc", "开心", 4, "room@@abc:开心"), fake.args)

    def test_wechat_group_stickers_disable_api_uses_service(self):
        from channel.web.web_channel import WechatGroupStickersHandler

        class FakeStickerService:
            def disable_sticker(self, room_id, sticker_id):
                self.args = (room_id, sticker_id)
                return {"sticker_id": sticker_id, "status": "disabled"}

        fake = FakeStickerService()
        body = {"room_id": "room@@abc", "sticker_id": "sticker-1"}
        handler = WechatGroupStickersHandler()
        with patch("channel.web.web_channel._require_auth"), \
                patch.object(WechatGroupStickersHandler, "_get_sticker_service", return_value=fake), \
                patch("channel.web.web_channel.web.data", return_value=json.dumps(body).encode("utf-8")):
            result = json.loads(handler.POST("disable"))

        self.assertEqual("success", result["status"])
        self.assertEqual("disabled", result["sticker"]["status"])
        self.assertEqual(("room@@abc", "sticker-1"), fake.args)

    def test_wechat_group_stickers_description_status_api_uses_room_scope(self):
        from channel.web.web_channel import WechatGroupStickersHandler

        class FakeStickerService:
            def get_description_status(self, room_id):
                self.room_id = room_id
                return {"pending": 3, "processable": 2, "job": {"status": "idle"}}

        fake = FakeStickerService()
        handler = WechatGroupStickersHandler()
        with patch("channel.web.web_channel._require_auth"), \
                patch.object(WechatGroupStickersHandler, "_get_sticker_service", return_value=fake), \
                patch("channel.web.web_channel.web.input", return_value=types.SimpleNamespace(room_id="room@@abc")):
            result = json.loads(handler.GET("description-status"))

        self.assertEqual("success", result["status"])
        self.assertEqual(3, result["description_status"]["pending"])
        self.assertEqual("room@@abc", fake.room_id)

    def test_wechat_group_stickers_update_description_api_uses_expected_value(self):
        from channel.web.web_channel import WechatGroupStickersHandler

        class FakeStickerService:
            def update_description(self, room_id, sticker_id, description, expected_description=None):
                self.args = (room_id, sticker_id, description, expected_description)
                return {"sticker_id": sticker_id, "description": description, "status": "active"}

            def get_description_status(self, room_id):
                return {"pending": 0, "processable": 0, "job": {"status": "idle"}}

        fake = FakeStickerService()
        body = {
            "stable_room_id": "stable-room-a",
            "room_id": "stable-room-a",
            "sticker_id": "sticker-1",
            "description": "猫咪开心挥手",
            "expected_description": "群聊表情包",
        }
        handler = WechatGroupStickersHandler()
        with patch("channel.web.web_channel._require_auth"), \
                patch.object(WechatGroupStickersHandler, "_get_sticker_service", return_value=fake), \
                patch("channel.web.web_channel.web.data", return_value=json.dumps(body).encode("utf-8")):
            result = json.loads(handler.POST("update-description"))

        self.assertEqual("success", result["status"])
        self.assertEqual("猫咪开心挥手", result["sticker"]["description"])
        self.assertEqual(
            ("stable-room-a", "sticker-1", "猫咪开心挥手", "群聊表情包"),
            fake.args,
        )

    def test_wechat_group_stickers_describe_pending_api_starts_background_job(self):
        from channel.web.web_channel import WechatGroupStickersHandler

        class FakeStickerService:
            def start_description_labeling(self, room_id, workers=1):
                self.args = (room_id, workers)
                return {"job_id": "job-1", "status": "running", "total": 2}

            def get_description_job_status(self, room_id):
                self.status_room_id = room_id
                return {"job_id": "job-1", "status": "running", "total": 2, "processed": 1}

        fake = FakeStickerService()
        body = {"stable_room_id": "stable-room-a", "room_id": "stable-room-a"}
        handler = WechatGroupStickersHandler()
        with patch("channel.web.web_channel._require_auth"), \
                patch.object(WechatGroupStickersHandler, "_get_sticker_service", return_value=fake), \
                patch("channel.web.web_channel.web.data", return_value=json.dumps(body).encode("utf-8")):
            started = json.loads(handler.POST("describe-pending"))
        with patch("channel.web.web_channel._require_auth"), \
                patch.object(WechatGroupStickersHandler, "_get_sticker_service", return_value=fake), \
                patch("channel.web.web_channel.web.input", return_value=types.SimpleNamespace(room_id="stable-room-a")):
            status = json.loads(handler.GET("describe-status"))

        self.assertEqual("running", started["job"]["status"])
        self.assertEqual(("stable-room-a", 2), fake.args)
        self.assertEqual("running", status["job"]["status"])
        self.assertEqual("stable-room-a", fake.status_room_id)

    def test_wechat_group_memory_preview_api_is_removed(self):
        from channel.web.web_channel import WechatGroupMemoriesHandler

        class FakeContextService:
            def __init__(self):
                self.called = False

            def build_prompt_block(self, **kwargs):
                self.called = True
                return {"content": "不应调用"}

        fake = FakeContextService()
        body = {
            "room_id": "room@@abc",
            "sender_id": "wxid_alice",
            "query": "测试",
            "mentioned_sender_ids": ["wxid_bob"],
        }
        handler = WechatGroupMemoriesHandler()
        with patch("channel.web.web_channel._require_auth"), \
                patch.object(WechatGroupMemoriesHandler, "_get_context_service", return_value=fake), \
                patch("channel.web.web_channel.web.data", return_value=json.dumps(body).encode("utf-8")):
            result = json.loads(handler.POST("preview"))

        self.assertEqual("error", result["status"])
        self.assertEqual("unknown action: preview", result["message"])
        self.assertFalse(fake.called)

    def test_wechat_group_emotion_surface_is_removed(self):
        with open("channel/web/static/js/console.js", "r", encoding="utf-8") as f:
            console_js = f.read()
        with open("channel/web/web_channel.py", "r", encoding="utf-8") as f:
            web_channel = f.read()

        removed_markers = (
            "groups_nav_emotion",
            "buildGroupsEmotionPanel",
            "saveGroupsEmotionConfig",
            "/api/wechat-group/emotion/",
            "WechatGroupEmotionHandler",
            "wechat_group_emotion_enabled",
            "wechat_group_free_reply_time_rules_enabled",
            "wechat_group_free_reply_typing_delay_enabled",
        )
        for marker in removed_markers:
            self.assertNotIn(marker, console_js)
            self.assertNotIn(marker, web_channel)

    def test_console_contains_wechat_group_style_panel(self):
        with open("channel/web/static/js/console.js", "r", encoding="utf-8") as f:
            console_js = f.read()

        self.assertIn("groups_nav_style", console_js)
        self.assertIn("buildGroupsStylePanel", console_js)
        self.assertIn("refreshGroupsStyleData", console_js)
        self.assertIn("reviewGroupsStyleCard", console_js)
        self.assertIn("/api/wechat-group/styles/candidates", console_js)
        self.assertIn("/api/wechat-group/styles/active", console_js)
        self.assertIn("/api/wechat-group/styles/review", console_js)

    def test_console_contains_wechat_group_focus_panel(self):
        with open("channel/web/static/js/console.js", "r", encoding="utf-8") as f:
            console_js = f.read()

        self.assertIn("groups_nav_focus", console_js)
        self.assertIn("buildGroupsFocusPanel", console_js)
        self.assertIn("refreshGroupsFocusData", console_js)
        self.assertIn("/api/wechat-group/focus/active", console_js)
        self.assertIn("/api/wechat-group/focus/archive", console_js)

    def test_console_contains_wechat_group_humanization_section(self):
        with open("channel/web/static/js/console.js", "r", encoding="utf-8") as f:
            console_js = f.read()

        self.assertIn("groups_nav_humanization", console_js)
        self.assertIn("buildGroupsHumanizationPanel", console_js)
        self.assertIn("readWechatGroupHumanizationSettings", console_js)
        self.assertIn("groups-context-session-scope", console_js)
        self.assertIn("groups-context-thread-ttl", console_js)
        self.assertIn("groups-context-rolling-summary-enabled", console_js)
        self.assertIn("groups-context-tool-continuation-enabled", console_js)
        self.assertIn("groups-humanization-archive-evidence-enabled", console_js)
        self.assertIn("groups-humanization-archive-evidence-days", console_js)
        self.assertIn("groups-humanization-response-cleanup-max-chars", console_js)

        start = console_js.index("function buildGroupsHumanizationPanel")
        end = console_js.index("function readWechatGroupHumanizationSettings", start)
        block = console_js[start:end]
        self.assertNotIn("groups-humanization-recent-", block)
        self.assertNotIn("groups-context-engine-mode", block)
        self.assertNotIn("groups-context-singleflight-enabled", block)
        self.assertNotIn("<details", block)
        self.assertNotIn("<summary", block)
        self.assertNotIn("Legacy", block)
        self.assertNotIn("buildGroupsContextPreviewPanel", console_js)
        self.assertNotIn("/api/wechat-group/memories/preview", console_js)

    def test_console_anchors_wechat_group_switch_knobs_to_their_tracks(self):
        with open("channel/web/static/js/console.js", "r", encoding="utf-8") as f:
            console_js = f.read()

        humanization_start = console_js.index("function buildGroupsHumanizationToggle")
        humanization_end = console_js.index("function buildGroupsNumberField", humanization_start)
        humanization_block = console_js[humanization_start:humanization_end]
        self.assertIn('class="relative w-10 h-5', humanization_block)

        image_start = console_js.index("function buildGroupsImageToggle")
        image_end = console_js.index("function buildGroupsImageNumberField", image_start)
        image_block = console_js[image_start:image_end]
        self.assertIn('class="relative w-10 h-5', image_block)

        free_reply_start = console_js.index("function renderWechatGroupFreeReplySettings")
        free_reply_end = console_js.index("function buildFreeReplyNumberField", free_reply_start)
        free_reply_block = console_js[free_reply_start:free_reply_end]
        self.assertEqual(2, free_reply_block.count('class="relative w-10 h-5'))

    def test_chat_handler_emits_single_cache_bust_query_for_console_assets(self):
        from channel.web.web_channel import ChatHandler

        with patch("channel.web.web_channel.time.time", return_value=1234567890):
            html = ChatHandler().GET()

        self.assertIn('href="assets/css/console.css?v=1234567890"', html)
        self.assertIn('src="assets/js/console.js?v=1234567890"', html)
        self.assertEqual(1, html.count("assets/css/console.css?v="))
        self.assertEqual(1, html.count("assets/js/console.js?v="))
        self.assertNotIn("assets/js/console.js?v=1234567890?", html)

    def test_console_removes_obsolete_recent_context_controls(self):
        with open("channel/web/static/js/console.js", "r", encoding="utf-8") as f:
            console_js = f.read()

        basic_start = console_js.index("function buildGroupsBasicPanel")
        basic_end = console_js.index("function buildGroupsNumberField", basic_start)
        basic_block = console_js[basic_start:basic_end]
        self.assertNotIn("groups-recent-enabled", basic_block)
        self.assertNotIn("groups-recent-limit", basic_block)
        self.assertNotIn("groups-recent-minutes", basic_block)

        self.assertNotIn("groups-humanization-recent-enabled", console_js)
        self.assertNotIn("groups-humanization-recent-limit", console_js)
        self.assertNotIn("groups-humanization-recent-minutes", console_js)
        self.assertNotIn("groups_recent_enabled:", console_js)
        self.assertNotIn("groups_recent_limit:", console_js)
        self.assertNotIn("groups_recent_minutes:", console_js)

    def test_console_group_memory_policy_save_does_not_write_recent_context(self):
        with open("channel/web/static/js/console.js", "r", encoding="utf-8") as f:
            console_js = f.read()

        start = console_js.index("async function saveGroupMemoryConfig")
        end = console_js.index("async function runGroupMemoryIncremental", start)
        block = console_js[start:end]
        self.assertNotIn("wechat_group_recent_context_enabled", block)
        self.assertNotIn("wechat_group_recent_context_limit", block)
        self.assertNotIn("wechat_group_recent_context_minutes", block)
        self.assertIn("/api/wechat-group/memories/config", block)

    def test_console_keeps_existing_wechat_group_management_sections(self):
        with open("channel/web/static/js/console.js", "r", encoding="utf-8") as f:
            console_js = f.read()

        for token in (
            "buildGroupsSectionButton('free_reply'",
            "buildGroupsSectionButton('focus'",
            "buildGroupsSectionButton('style'",
            "buildGroupsSectionButton('sticker'",
            "buildGroupsSectionButton('image'",
            "buildGroupsSectionButton('persona'",
            "buildGroupsSectionButton('profiles'",
        ):
            self.assertIn(token, console_js)
        self.assertNotIn("buildGroupsSectionButton('memory'", console_js)
        self.assertNotIn("groups_nav_memory", console_js)

    def test_console_contains_wechat_group_sticker_panel(self):
        with open("channel/web/static/js/console.js", "r", encoding="utf-8") as f:
            console_js = f.read()

        self.assertIn("groups_nav_sticker", console_js)
        self.assertIn("buildGroupsStickerPanel", console_js)
        self.assertIn("refreshGroupsStickerData", console_js)
        self.assertIn("disableGroupsSticker", console_js)
        self.assertIn("testGroupsStickerOnlineSearch", console_js)
        self.assertIn("saveGroupsStickerConfig", console_js)
        self.assertIn("readGroupsStickerConfig", console_js)
        self.assertIn("captureGroupsStickerConfigDraft", console_js)
        self.assertIn("getGroupsStickerConfigForRender", console_js)
        self.assertIn("groups-sticker-enabled", console_js)
        self.assertIn("groups-sticker-auto-collect-enabled", console_js)
        self.assertIn("groups-sticker-context-limit", console_js)
        self.assertIn("groups-sticker-reply-percent", console_js)
        self.assertIn("groups-sticker-max-size-mb", console_js)
        self.assertIn("groups-sticker-daily-send-limit", console_js)
        self.assertIn("groups-sticker-online-search-enabled", console_js)
        self.assertIn("groups-sticker-online-allow-gif", console_js)
        self.assertIn("groups-sticker-online-provider", console_js)
        self.assertIn("groups-sticker-online-endpoint", console_js)
        self.assertIn("groups-sticker-online-allowed-domains", console_js)
        self.assertIn("groups-sticker-online-search-count", console_js)
        self.assertIn("groups-sticker-cooldown-seconds", console_js)
        self.assertIn("groups_sticker_enabled_hint", console_js)
        self.assertIn("groups_sticker_settings_hint", console_js)
        self.assertIn("/api/wechat-group/stickers/list", console_js)
        self.assertIn("/api/wechat-group/stickers/search-online", console_js)
        self.assertIn("/api/wechat-group/stickers/disable", console_js)
        self.assertIn("/api/wechat-group/stickers/description-status", console_js)
        self.assertIn("/api/wechat-group/stickers/describe-status", console_js)
        self.assertIn("/api/wechat-group/stickers/describe-pending", console_js)
        self.assertIn("/api/wechat-group/stickers/update-description", console_js)
        self.assertIn("function renderGroupsStickerDescriptionControls", console_js)
        self.assertIn("function startGroupsStickerDescriptionBatch", console_js)
        self.assertIn("function beginGroupsStickerDescriptionEdit", console_js)
        self.assertIn("function saveGroupsStickerDescription", console_js)
        self.assertIn("function retryGroupsStickerDescriptionStatus", console_js)
        self.assertIn("groups-sticker-describe-pending", console_js)
        self.assertIn("groups-sticker-description-edit", console_js)
        self.assertIn("function buildGroupsMobileSectionSelect", console_js)
        self.assertIn('id="groups-section-select"', console_js)
        self.assertIn("flex-col md:flex-row", console_js)
        self.assertIn("hidden md:block w-56", console_js)
        self.assertIn('role="progressbar"', console_js)
        self.assertIn("motion-reduce:transition-none", console_js)
        self.assertIn("bg-primary-600 hover:bg-primary-700", console_js)
        self.assertIn('aria-live="polite"', console_js)
        self.assertIn('maxlength="200"', console_js)
        self.assertIn('loading="lazy"', console_js)
        self.assertIn("requestId !== groupsStickerState.listRequestId", console_js)
        self.assertIn("groupsStickerState.selectedRoomId !== roomId", console_js)
        # Core runtime knobs must be editable form controls, not read-only summary cards.
        self.assertIn("buildGroupsImageToggle('groups-sticker-enabled'", console_js)
        self.assertIn("buildGroupsImageToggle('groups-sticker-auto-collect-enabled'", console_js)
        self.assertIn("buildGroupsImageToggle('groups-sticker-online-search-enabled'", console_js)
        self.assertIn("buildGroupsImageNumberField('groups-sticker-context-limit'", console_js)
        self.assertIn("buildGroupsImageNumberField('groups-sticker-reply-percent'", console_js)
        self.assertIn("buildGroupsImageNumberField('groups-sticker-max-size-mb'", console_js)
        self.assertIn("buildGroupsImageNumberField('groups-sticker-daily-send-limit'", console_js)
        self.assertIn("buildGroupsImageNumberField('groups-sticker-cooldown-seconds'", console_js)
        self.assertNotIn("summaryItems = [\n        [t('groups_sticker_enabled')", console_js)

    def test_wechat_group_memory_service_uses_configured_embedding_provider(self):
        from agent.memory.config import MemoryConfig, get_default_memory_config, set_global_memory_config
        from channel.web.web_channel import WechatGroupMemoriesHandler

        original_config = get_default_memory_config()
        provider = object()
        WechatGroupMemoriesHandler._context_service = None

        with tempfile.TemporaryDirectory() as tmpdir:
            set_global_memory_config(MemoryConfig(workspace_root=tmpdir))
            with patch(
                "agent.memory.create_default_embedding_provider",
                return_value=provider,
                create=True,
            ):
                service = WechatGroupMemoriesHandler._get_context_service()
            try:
                self.assertIs(service.memory_manager.embedding_provider, provider)
            finally:
                service.memory_manager.close()
                WechatGroupMemoriesHandler._context_service = None
                set_global_memory_config(original_config)

    def test_wechat_group_memory_group_post_requires_room_id(self):
        from channel.web.web_channel import WechatGroupMemoriesHandler

        handler = WechatGroupMemoriesHandler()
        with patch("channel.web.web_channel._require_auth"), \
                patch("channel.web.web_channel.web.data", return_value=json.dumps({"content": "x"}).encode("utf-8")):
            result = json.loads(handler.POST("group"))

        self.assertEqual("error", result["status"])
        self.assertIn("room_id", result["message"])

    def test_wechat_group_memory_profile_api_passes_aliases(self):
        from channel.web.web_channel import WechatGroupMemoriesHandler

        class FakeProfileService:
            def upsert_manual_profile(self, **kwargs):
                self.kwargs = kwargs
                return {"sender_id": kwargs["sender_id"], "aliases": kwargs["aliases"]}

        fake = FakeProfileService()
        body = {
            "stable_room_id": "wgr_a",
            "stable_member_id": "wgm_dali",
            "primary_nickname": "Dali Wang",
            "aliases": "大力, 力佬",
            "speak_style": "资源协调人",
        }
        handler = WechatGroupMemoriesHandler()
        with patch("channel.web.web_channel._require_auth"), \
                patch.object(WechatGroupMemoriesHandler, "_get_profile_service", return_value=fake), \
                patch("channel.web.web_channel.web.data", return_value=json.dumps(body).encode("utf-8")):
            result = json.loads(handler.POST("profiles"))

        self.assertEqual("success", result["status"])
        self.assertEqual(["大力", "力佬"], fake.kwargs["aliases"])
        self.assertEqual("wgm_dali", fake.kwargs["sender_id"])
        self.assertEqual("wgr_a", fake.kwargs["room_id"])

    def test_wechat_group_memory_summary_api_uses_service(self):
        from channel.web.web_channel import WechatGroupMemoriesHandler

        class FakeKnowledgeService:
            def list_group_memories(self, room_id, query="", limit=20, offset=0):
                self.room_id = room_id
                return [{"memory_id": "m1"}, {"memory_id": "m2"}]

            def count_group_memories(self, room_id, query=""):
                self.room_id = room_id
                return 2

        class FakeProfileService:
            def count_profiles(self, room_id, query=""):
                self.room_id = room_id
                return 3

        fake_knowledge = FakeKnowledgeService()
        fake_profiles = FakeProfileService()
        handler = WechatGroupMemoriesHandler()
        with patch("channel.web.web_channel._require_auth"), \
                patch.object(WechatGroupMemoriesHandler, "_get_knowledge_service", return_value=fake_knowledge), \
                patch.object(WechatGroupMemoriesHandler, "_get_profile_service", return_value=fake_profiles), \
                patch("channel.web.web_channel.web.input", return_value=types.SimpleNamespace(
                    stable_room_id="wgr_a", runtime_room_id="", room_id="", stable_member_id="",
                    runtime_sender_id="", sender_id="", status="active", limit="20", offset="0", q="", run_id="",
                )):
            result = json.loads(handler.GET("summary"))

        self.assertEqual("success", result["status"])
        self.assertEqual("wgr_a", fake_knowledge.room_id)
        self.assertEqual("wgr_a", fake_profiles.room_id)
        self.assertEqual(2, result["summary"]["group_memory_count"])
        self.assertEqual(3, result["summary"]["profile_count"])

    def test_profiles_api_lists_current_room_profiles(self):
        from channel.web.web_channel import WechatGroupMemoriesHandler

        class FakeProfileService:
            def list_profiles(self, query="", limit=20, room_id="", offset=0):
                self.args = (query, limit, room_id, offset)
                return [{"sender_id": "wgm_alice", "stable_member_id": "wgm_alice", "primary_nickname": "Alice"}]

            def count_profiles(self, room_id, query=""):
                return 1

        fake = FakeProfileService()
        handler = WechatGroupMemoriesHandler()
        with patch("channel.web.web_channel._require_auth"), \
                patch.object(WechatGroupMemoriesHandler, "_get_profile_service", return_value=fake), \
                patch("channel.web.web_channel.web.input", return_value=types.SimpleNamespace(
                    stable_room_id="wgr_a", runtime_room_id="", room_id="", stable_member_id="",
                    runtime_sender_id="", sender_id="", status="active", limit="5", offset="2", q="alice", run_id="",
                )):
            result = json.loads(handler.GET("profiles"))

        self.assertEqual("success", result["status"])
        self.assertEqual("wgm_alice", result["profiles"][0]["sender_id"])
        self.assertEqual(1, result["total"])
        self.assertEqual(("alice", 5, "wgr_a", 2), fake.args)

    def test_profiles_service_uses_web_identity_service_for_stable_room_scope(self):
        from channel.web.web_channel import WechatGroupMemoriesHandler

        identity = object()
        profile_service = object()
        original = WechatGroupMemoriesHandler._profile_service
        WechatGroupMemoriesHandler._profile_service = None
        try:
            with patch.object(WechatGroupMemoriesHandler, "_get_identity_service", return_value=identity), \
                    patch(
                        "channel.wechat_group.wechat_group_profile_service.WechatGroupProfileService",
                        return_value=profile_service,
                    ) as service_class:
                result = WechatGroupMemoriesHandler._get_profile_service()
        finally:
            WechatGroupMemoriesHandler._profile_service = original

        self.assertIs(profile_service, result)
        service_class.assert_called_once_with(identity_service=identity)

    def test_profiles_api_fills_missing_room_names_from_selected_config(self):
        from channel.web.web_channel import WechatGroupMemoriesHandler

        class FakeConfig:
            def get(self, key, default=None):
                data = {
                    "wechat_group_room_ids": ["@@room_a"],
                    "wechat_group_names": ["Product Launch Group"],
                }
                return data.get(key, default)

        class FakeProfileService:
            def list_profiles(self, query="", limit=20, room_id="", offset=0):
                return [{
                    "sender_id": "wgm_alice",
                    "primary_nickname": "Alice",
                    "room_summaries": [{
                        "room_id": "@@room_a",
                        "room_name": "",
                        "display_names": ["Alice"],
                        "last_seen_at": 300,
                        "name_count": 1,
                    }],
                }]

            def count_profiles(self, room_id, query=""):
                return 1

        handler = WechatGroupMemoriesHandler()
        with patch("channel.web.web_channel._require_auth"), \
                patch("channel.web.web_channel.conf", return_value=FakeConfig()), \
                patch.object(WechatGroupMemoriesHandler, "_get_profile_service", return_value=FakeProfileService()), \
                patch("channel.web.web_channel.web.input", return_value=types.SimpleNamespace(
                    stable_room_id="@@room_a", runtime_room_id="", room_id="", stable_member_id="",
                    runtime_sender_id="", sender_id="", status="active", limit="20", offset="0", q="", run_id="",
                )):
            result = json.loads(handler.GET("profiles"))

        self.assertEqual("success", result["status"])
        self.assertEqual("Product Launch Group", result["profiles"][0]["room_summaries"][0]["room_name"])

    def test_wechat_group_memory_disable_api_uses_service(self):
        from channel.web.web_channel import WechatGroupMemoriesHandler

        class FakeKnowledgeService:
            def disable_group_memory(self, room_id, memory_id):
                self.room_id = room_id
                self.memory_id = memory_id
                return True

        fake = FakeKnowledgeService()
        body = {
            "memory_type": "group",
            "stable_room_id": "wgr_abc",
            "memory_id": "chunk-1",
        }
        handler = WechatGroupMemoriesHandler()
        with patch("channel.web.web_channel._require_auth"), \
                patch.object(WechatGroupMemoriesHandler, "_get_knowledge_service", return_value=fake), \
                patch("channel.web.web_channel.web.data", return_value=json.dumps(body).encode("utf-8")):
            result = json.loads(handler.POST("disable"))

        self.assertEqual("success", result["status"])
        self.assertTrue(result["disabled"])
        self.assertEqual("wgr_abc", fake.room_id)
        self.assertEqual("chunk-1", fake.memory_id)

    def test_wechat_group_learn_runs_api_uses_room_filter(self):
        from channel.web.web_channel import WechatGroupMemoriesHandler

        class FakeKnowledgeStore:
            def list_learning_runs(self, room_id, limit=20):
                self.args = (room_id, limit)
                return [{"run_id": "run-1", "room_id": room_id, "status": "success"}]

        fake = FakeKnowledgeStore()
        handler = WechatGroupMemoriesHandler()
        with patch("channel.web.web_channel._require_auth"), \
                patch.object(WechatGroupMemoriesHandler, "_get_knowledge_store", return_value=fake), \
                patch("channel.web.web_channel.web.input", return_value=types.SimpleNamespace(
                    stable_room_id="wgr_abc", runtime_room_id="", room_id="", sender_id="",
                    stable_member_id="", status="active", limit="5", offset="0", q="",
                )):
            result = json.loads(handler.GET("learn/runs"))

        self.assertEqual("success", result["status"])
        self.assertEqual("run-1", result["runs"][0]["run_id"])
        self.assertEqual(("wgr_abc", 5), fake.args)

    def test_learn_run_api_replaces_candidate_approve_flow(self):
        from channel.web.web_channel import WechatGroupMemoriesHandler

        class FakeLearner:
            def run_once(self, room_id, mode="all"):
                self.args = (room_id, mode)
                return {"status": "success", "run_id": "run-1"}

        fake = FakeLearner()
        body = {"stable_room_id": "wgr_abc", "mode": "all"}
        handler = WechatGroupMemoriesHandler()
        with patch("channel.web.web_channel._require_auth"), \
                patch.object(WechatGroupMemoriesHandler, "_get_learner", return_value=fake), \
                patch("channel.web.web_channel.web.data", return_value=json.dumps(body).encode("utf-8")):
            result = json.loads(handler.POST("learn/run"))

        self.assertEqual("success", result["status"])
        self.assertEqual("run-1", result["run"]["run_id"])
        self.assertEqual(("wgr_abc", "memory"), fake.args)

    def test_learn_history_api_uses_explicit_batch_limit(self):
        from channel.web.web_channel import WechatGroupMemoriesHandler

        class FakeLearner:
            def run_history(self, room_id, max_batches=None, operation="continue"):
                self.args = (room_id, max_batches, operation)
                return {"status": "success", "processed_batches": 2}

        fake = FakeLearner()
        body = {"stable_room_id": "wgr_abc", "max_batches": 4}
        handler = WechatGroupMemoriesHandler()
        with patch("channel.web.web_channel._require_auth"), \
                patch.object(WechatGroupMemoriesHandler, "_get_learner", return_value=fake), \
                patch("channel.web.web_channel.web.data", return_value=json.dumps(body).encode("utf-8")):
            result = json.loads(handler.POST("learn/history"))

        self.assertEqual("success", result["status"])
        self.assertEqual(("wgr_abc", 4, "continue"), fake.args)

    def test_group_memory_list_api_returns_accurate_pagination(self):
        from channel.web.web_channel import WechatGroupMemoriesHandler

        class FakeKnowledgeService:
            def list_group_memories(self, room_id, query="", limit=20, offset=0):
                self.args = (room_id, query, limit, offset)
                return [{"memory_id": "m21", "room_id": room_id}]

            def count_group_memories(self, room_id, query=""):
                return 21

        fake = FakeKnowledgeService()
        params = types.SimpleNamespace(
            stable_room_id="wgr_abc", runtime_room_id="", room_id="",
            stable_member_id="", runtime_sender_id="", sender_id="",
            status="active", limit="20", offset="20", q="", run_id="",
        )
        with patch("channel.web.web_channel._require_auth"), \
                patch.object(WechatGroupMemoriesHandler, "_get_knowledge_service", return_value=fake), \
                patch("channel.web.web_channel.web.input", return_value=params):
            result = json.loads(WechatGroupMemoriesHandler().GET("group"))

        self.assertEqual("success", result["status"])
        self.assertEqual(21, result["total"])
        self.assertEqual(20, result["offset"])
        self.assertEqual(("wgr_abc", "", 20, 20), fake.args)

    def test_group_memory_recall_api_applies_query_and_min_score(self):
        from channel.web.web_channel import WechatGroupMemoriesHandler

        class FakeKnowledgeService:
            def search_group_memories(self, room_id, query, limit=5, min_score=0.2):
                self.args = (room_id, query, limit, min_score)
                return [{"memory_id": "m1", "score": 0.88}]

        fake = FakeKnowledgeService()
        params = types.SimpleNamespace(
            stable_room_id="wgr_abc", runtime_room_id="", room_id="",
            stable_member_id="", runtime_sender_id="", sender_id="",
            status="active", limit="5", offset="0", q="发布", run_id="", min_score="0.6",
        )
        with patch("channel.web.web_channel._require_auth"), \
                patch.object(WechatGroupMemoriesHandler, "_get_knowledge_service", return_value=fake), \
                patch("channel.web.web_channel.web.input", return_value=params):
            result = json.loads(WechatGroupMemoriesHandler().GET("recall"))

        self.assertEqual("success", result["status"])
        self.assertEqual(0.88, result["memories"][0]["score"])
        self.assertEqual(("wgr_abc", "发布", 5, 0.6), fake.args)

    def test_group_memory_learning_status_api_uses_stable_room(self):
        from channel.web.web_channel import WechatGroupMemoriesHandler

        class FakeTrigger:
            def get_status(self, room_id):
                self.room_id = room_id
                return {"pending_text_count": 7, "blocking_reason": "below_threshold"}

        fake = FakeTrigger()
        params = types.SimpleNamespace(
            stable_room_id="wgr_abc", runtime_room_id="", room_id="",
            stable_member_id="", runtime_sender_id="", sender_id="",
            status="active", limit="20", offset="0", q="", run_id="",
        )
        with patch("channel.web.web_channel._require_auth"), \
                patch.object(WechatGroupMemoriesHandler, "_get_memory_dream_trigger", return_value=fake), \
                patch("channel.web.web_channel.web.input", return_value=params):
            result = json.loads(WechatGroupMemoriesHandler().GET("learn/status"))

        self.assertEqual("success", result["status"])
        self.assertEqual("wgr_abc", fake.room_id)
        self.assertEqual(7, result["learning_status"]["pending_text_count"])

    def test_group_memory_history_preview_is_read_only(self):
        from channel.web.web_channel import WechatGroupMemoriesHandler

        class FakeLearner:
            def preview_history(self, room_id, operation="continue"):
                self.args = (room_id, operation)
                return {"cursor_start": 3, "frozen_high_watermark": 9, "pending_count": 6}

        fake = FakeLearner()
        body = {"stable_room_id": "wgr_abc", "operation": "restart"}
        with patch("channel.web.web_channel._require_auth"), \
                patch.object(WechatGroupMemoriesHandler, "_get_learner", return_value=fake), \
                patch("channel.web.web_channel.web.data", return_value=json.dumps(body).encode("utf-8")):
            result = json.loads(WechatGroupMemoriesHandler().POST("learn/history/preview"))

        self.assertEqual("success", result["status"])
        self.assertEqual(("wgr_abc", "restart"), fake.args)
        self.assertEqual(9, result["preview"]["frozen_high_watermark"])

    def test_group_memory_history_restart_requires_explicit_confirmation(self):
        from channel.web.web_channel import WechatGroupMemoriesHandler

        body = {"stable_room_id": "wgr_abc", "operation": "restart"}
        with patch("channel.web.web_channel._require_auth"), \
                patch("channel.web.web_channel.web.data", return_value=json.dumps(body).encode("utf-8")):
            result = json.loads(WechatGroupMemoriesHandler().POST("learn/history"))

        self.assertEqual("error", result["status"])
        self.assertIn("confirm_restart", result["message"])

    def test_group_memory_config_api_applies_only_memory_whitelist(self):
        from channel.web.web_channel import WechatGroupMemoriesHandler

        body = {
            "wechat_group_learning_enabled": True,
            "wechat_group_learning_idle_minutes": "8",
            "wechat_group_persona_prompt": "must-not-change",
            "wechat_group_stable_room_ids": ["must-not-change"],
        }
        with patch("channel.web.web_channel._require_auth"), \
                patch("channel.web.web_channel.ChannelsHandler._apply_wechat_group_config", return_value={
                    "wechat_group_learning_enabled": True,
                    "wechat_group_learning_idle_minutes": 8,
                }) as apply_config, \
                patch("channel.web.web_channel.ChannelsHandler._write_channel_config") as write_config, \
                patch("channel.web.web_channel.web.data", return_value=json.dumps(body).encode("utf-8")):
            result = json.loads(WechatGroupMemoriesHandler().POST("config"))

        applied_input = apply_config.call_args.args[0]
        self.assertEqual("success", result["status"])
        self.assertEqual(
            {"wechat_group_learning_enabled", "wechat_group_learning_idle_minutes"},
            set(applied_input),
        )
        write_config.assert_called_once()

    def test_group_profile_config_api_does_not_apply_memory_fields(self):
        from channel.web.web_channel import WechatGroupMemoriesHandler

        body = {
            "wechat_group_profile_enabled": True,
            "wechat_group_profile_evolution_idle_minutes": "7",
            "wechat_group_learning_enabled": True,
        }
        with patch("channel.web.web_channel._require_auth"), \
                patch("channel.web.web_channel.ChannelsHandler._apply_wechat_group_config", return_value={
                    "wechat_group_profile_enabled": True,
                    "wechat_group_profile_evolution_idle_minutes": 7,
                }) as apply_config, \
                patch("channel.web.web_channel.ChannelsHandler._write_channel_config"), \
                patch("channel.web.web_channel.web.data", return_value=json.dumps(body).encode("utf-8")):
            result = json.loads(WechatGroupMemoriesHandler().POST("profiles/config"))

        self.assertEqual("success", result["status"])
        self.assertNotIn("wechat_group_learning_enabled", apply_config.call_args.args[0])

    def test_profile_evolution_config_api_reads_current_config(self):
        from channel.web.web_channel import WechatGroupMemoriesHandler
        from config import conf

        conf()["wechat_group_profile_evolution_enabled"] = True
        conf()["wechat_group_profile_evolution_idle_minutes"] = 9
        handler = WechatGroupMemoriesHandler()
        with patch("channel.web.web_channel._require_auth"), \
                patch("channel.web.web_channel.web.input", return_value=types.SimpleNamespace(
                    room_id="", sender_id="", status="active", limit="20", offset="0", q="", run_id="",
                )):
            result = json.loads(handler.GET("profile-evolution/config"))

        self.assertEqual("success", result["status"])
        self.assertTrue(result["config"]["wechat_group_profile_evolution_enabled"])
        self.assertEqual(9, result["config"]["wechat_group_profile_evolution_idle_minutes"])

    def test_profile_evolution_config_api_saves_allowed_config(self):
        from channel.web.web_channel import WechatGroupMemoriesHandler
        from config import conf

        body = {
            "wechat_group_profile_evolution_enabled": True,
            "wechat_group_profile_evolution_idle_minutes": "7",
            "wechat_group_profile_evolution_min_messages": "4",
            "wechat_group_profile_evolution_max_interval_minutes": "60",
            "wechat_group_profile_evolution_batch_message_limit": "88",
        }
        handler = WechatGroupMemoriesHandler()
        with patch("channel.web.web_channel._require_auth"), \
                patch("channel.web.web_channel.ChannelsHandler._write_channel_config"), \
                patch("channel.web.web_channel.web.data", return_value=json.dumps(body).encode("utf-8")):
            result = json.loads(handler.POST("profile-evolution/config"))

        self.assertEqual("success", result["status"])
        self.assertTrue(conf()["wechat_group_profile_evolution_enabled"])
        self.assertEqual(7, conf()["wechat_group_profile_evolution_idle_minutes"])
        self.assertEqual(4, conf()["wechat_group_profile_evolution_min_messages"])
        self.assertEqual(60, conf()["wechat_group_profile_evolution_max_interval_minutes"])
        self.assertEqual(88, conf()["wechat_group_profile_evolution_batch_message_limit"])

    def test_profile_evolution_status_runs_and_run_detail_apis_use_room_filter(self):
        from channel.web.web_channel import WechatGroupMemoriesHandler

        class FakeEvolutionStore:
            def get_status(self, room_id):
                self.status_room_id = room_id
                return {"room_id": room_id, "last_archive_row_id": 3, "running": False}

            def list_runs(self, room_id, limit=20):
                self.runs_args = (room_id, limit)
                return [{"run_id": "run-1", "room_id": room_id, "status": "success"}]

            def get_run(self, room_id, run_id):
                self.run_args = (room_id, run_id)
                return {"run_id": run_id, "room_id": room_id, "status": "success"}

            def list_diffs(self, room_id, sender_id="", run_id="", limit=100):
                self.diff_args = (room_id, sender_id, run_id, limit)
                return [{"sender_id": "wxid_a", "before": {}, "after": {"aliases": ["A"]}}]

        fake = FakeEvolutionStore()
        handler = WechatGroupMemoriesHandler()
        base_params = types.SimpleNamespace(
            room_id="room@@abc", sender_id="", status="active", limit="5", offset="0", q="", run_id="run-1",
        )
        with patch("channel.web.web_channel._require_auth"), \
                patch.object(WechatGroupMemoriesHandler, "_get_profile_evolution_store", return_value=fake), \
                patch("channel.web.web_channel.web.input", return_value=base_params):
            status = json.loads(handler.GET("profile-evolution/status"))
            runs = json.loads(handler.GET("profile-evolution/runs"))
            detail = json.loads(handler.GET("profile-evolution/run"))

        self.assertEqual("success", status["status"])
        self.assertEqual("room@@abc", fake.status_room_id)
        self.assertEqual(("room@@abc", 5), fake.runs_args)
        self.assertEqual(("room@@abc", "run-1"), fake.run_args)
        self.assertEqual(("room@@abc", "", "run-1", 100), fake.diff_args)
        self.assertEqual("wxid_a", detail["diffs"][0]["sender_id"])

    def test_profile_evolution_run_api_uses_executor(self):
        from channel.web.web_channel import WechatGroupMemoriesHandler

        class FakeExecutor:
            def run_once(self, room_id, trigger_source="manual"):
                self.args = (room_id, trigger_source)
                return {"status": "success", "run_id": "run-2"}

        fake = FakeExecutor()
        handler = WechatGroupMemoriesHandler()
        body = {"room_id": "room@@abc"}
        with patch("channel.web.web_channel._require_auth"), \
                patch.object(WechatGroupMemoriesHandler, "_get_profile_evolution_executor", return_value=fake), \
                patch("channel.web.web_channel.web.data", return_value=json.dumps(body).encode("utf-8")):
            result = json.loads(handler.POST("profile-evolution/run"))

        self.assertEqual("success", result["status"])
        self.assertEqual(("room@@abc", "manual"), fake.args)
        self.assertEqual("run-2", result["run"]["run_id"])

    def test_profile_evolution_rollback_api_uses_service(self):
        from channel.web.web_channel import WechatGroupMemoriesHandler

        class FakeRollbackService:
            def rollback_run(self, room_id, run_id):
                self.args = (room_id, run_id)
                return {"rolled_back": 1, "run_id": run_id}

        fake = FakeRollbackService()
        handler = WechatGroupMemoriesHandler()
        body = {"room_id": "room@@abc", "run_id": "run-1"}
        with patch("channel.web.web_channel._require_auth"), \
                patch.object(WechatGroupMemoriesHandler, "_get_profile_evolution_rollback_service", return_value=fake), \
                patch("channel.web.web_channel.web.data", return_value=json.dumps(body).encode("utf-8")):
            result = json.loads(handler.POST("profile-evolution/rollback"))

        self.assertEqual("success", result["status"])
        self.assertEqual(("room@@abc", "run-1"), fake.args)
        self.assertEqual(1, result["rollback"]["rolled_back"])

    def test_models_console_surfaces_invalid_voice_provider_warning(self):
        console_js = Path("channel/web/static/js/console.js").read_text(encoding="utf-8")

        def function_source(name):
            marker = f"function {name}("
            start = console_js.find(marker)
            self.assertNotEqual(-1, start, f"missing JavaScript function: {name}")
            end = console_js.find("\nfunction ", start + len(marker))
            self.assertNotEqual(-1, end, f"could not isolate JavaScript function: {name}")
            return console_js[start:end]

        render_source = function_source("renderCapabilityBody")
        options_source = function_source("buildCapabilityProviderOptions")
        visibility_source = function_source("_setTtsConfigVisible")
        save_source = function_source("saveCapability")
        change_source = function_source("onCapabilityProviderChange")
        auto_source = function_source("capabilityUsesAutoProvider")
        voice_source = function_source("rebuildCapabilityVoiceDropdown")

        self.assertIn("invalid_configured_provider", render_source)
        self.assertIn("models_invalid_voice_provider", render_source)
        self.assertIn("data-cap-invalid-provider", render_source)
        self.assertIn("escapeHtml(invalidProvider)", render_source)
        self.assertIn("legacy_configured_provider", render_source)
        self.assertIn("models_legacy_voice_provider", render_source)
        self.assertIn("data-cap-legacy-provider", render_source)
        self.assertIn("escapeHtml(legacyProvider)", render_source)
        self.assertIn(
            "const pickerCurrentProvider = cap.legacy_configured_provider ? '' : cap.current_provider;",
            render_source,
        )
        self.assertIn(
            "const pickerCurrentModel = (cap.legacy_configured_provider || capabilityUsesAutoProvider(def.id, pickerCurrentProvider)) ? '' : cap.current_model;",
            render_source,
        )
        self.assertIn(
            "const pickerCurrentVoice = cap.legacy_configured_provider ? '' : cap.current_voice;",
            render_source,
        )
        self.assertIn(
            "rebuildCapabilityModelDropdown(def, initialProviderValue, pickerCurrentModel || '', body);",
            render_source,
        )
        self.assertIn("pickerCurrentVoice || ''", render_source)
        self.assertIn(
            "!capabilityUsesAutoProvider(def.id, initialProviderValue)",
            render_source,
        )
        self.assertEqual(1, render_source.count("cap.current_model"))
        self.assertEqual(1, render_source.count("cap.current_voice"))
        self.assertIn(
            "const noSelectionAndNoHint = !pickerCurrentProvider && !cap.suggested_provider;",
            render_source,
        )
        self.assertEqual(1, render_source.count("cap.current_provider"))
        self.assertIn(
            "cap.current_provider !== cap.invalid_configured_provider",
            options_source,
        )
        self.assertIn(
            "cap.current_provider !== cap.legacy_configured_provider",
            options_source,
        )
        self.assertIn(
            "child.hasAttribute('data-cap-invalid-provider')",
            visibility_source,
        )
        self.assertIn(
            "child.hasAttribute('data-cap-legacy-provider')",
            visibility_source,
        )
        self.assertIn("(capId === 'asr' || capId === 'tts')", save_source)
        self.assertIn("&& !provider", save_source)
        self.assertIn(
            "capState.invalid_configured_provider || capState.legacy_configured_provider",
            save_source,
        )
        self.assertIn(
            "showStatus(`cap-${capId}-status`, 'models_voice_provider_required', true);",
            save_source,
        )
        self.assertLess(
            save_source.index("models_voice_provider_required"),
            save_source.index("_persistCapability("),
        )
        self.assertIn(
            "const isAuto = capabilityUsesAutoProvider(capId, provider);",
            save_source,
        )
        self.assertIn(
            "!capabilityUsesAutoProvider(def.id, providerId)",
            change_source,
        )
        self.assertIn(
            "return providerId === '' && (capabilitySupportsAuto(capId) || capId === 'asr');",
            auto_source,
        )
        self.assertIn(
            "const customProvider = String(providerId || '').startsWith('custom:');",
            voice_source,
        )
        self.assertIn(
            "if ((!raw || raw.length === 0) && !customProvider)",
            voice_source,
        )
        self.assertIn(
            "if (!initial) initial = codes.length ? codes[0] : '__custom__';",
            voice_source,
        )
        self.assertEqual(2, console_js.count("models_invalid_voice_provider:"))
        self.assertEqual(2, console_js.count("models_legacy_voice_provider:"))
        self.assertEqual(2, console_js.count("models_voice_provider_required:"))


if __name__ == "__main__":
    unittest.main()
