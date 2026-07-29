"""WeChat group channel backed by a Node.js Wechaty sidecar."""

import re
import threading
import time
from collections import OrderedDict
from pathlib import Path

from bridge.bridge import Bridge
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from channel.chat_channel import ChatChannel
from channel.wechat_group.protocol import SidecarEvent, SidecarEventType
from channel.wechat_group.wechat_group_archive import WechatGroupArchive
from channel.wechat_group.wechat_group_client import (
    WechatGroupClient,
    get_wechat_group_sidecar_memory_path,
)
from channel.wechat_group.wechat_group_context import (
    build_safe_wechat_group_recent_context_block_from_rows,
    build_wechat_group_recent_context_block,
    build_wechat_group_recent_context_block_from_rows,
)
from channel.wechat_group.wechat_group_context_service import WechatGroupContextService
from channel.wechat_group.wechat_group_emotion_service import WechatGroupEmotionService
from channel.wechat_group.wechat_group_identity_service import WechatGroupIdentityService
from channel.wechat_group.wechat_group_message import WechatGroupMessage
from channel.wechat_group.wechat_group_membership_notice import (
    WECHAT_GROUP_MEMBERSHIP_CONTENT_IMAGE,
    WECHAT_GROUP_MEMBERSHIP_EVENT_JOIN,
    WECHAT_GROUP_MEMBERSHIP_EVENT_LEAVE,
    build_membership_notice_template_values,
    render_membership_notice_template,
    resolve_membership_notice_image_path,
    resolve_wechat_group_membership_notice,
    validate_membership_notice_image_file,
)
from channel.wechat_group.wechat_group_multimodal_context_service import (
    WechatGroupMultimodalContextService,
    _looks_like_image_reference_question,
)
from channel.wechat_group.wechat_group_persona import (
    build_wechat_group_persona_block,
    get_wechat_group_persona_config,
    should_skip_persona_for_message,
)
from channel.wechat_group.wechat_group_permissions import (
    build_wechat_group_blocked_sender_ids,
    build_wechat_group_admin_policy_block,
    build_wechat_group_admin_reject_message,
    get_blocked_admin_permissions_for_text,
    can_generate_wechat_group_report,
    is_wechat_group_report_generation_request,
    is_wechat_group_blacklisted,
    is_wechat_group_admin,
)
from channel.wechat_group.wechat_group_style_service import WechatGroupStyleService
from channel.wechat_group.wechat_group_sticker_service import WechatGroupStickerService
from channel.wechat_group.wechat_group_transport import project_wechat_message_type
from channel.wechat_group.wechat_group_focus_service import WechatGroupFocusService
from channel.wechat_group.wechat_group_humanized_context import (
    WECHAT_GROUP_FREE_REPLY_RECENT_LIMIT,
    WECHAT_GROUP_FREE_REPLY_RECENT_MINUTES,
    WechatGroupHumanizedContextBuilder,
)
from channel.wechat_group.wechat_group_free_reply import (
    FREE_REPLY_MUTE_SUPPRESSION,
    WechatGroupFreeReplyStateStore,
    evaluate_wechat_group_free_reply,
    get_wechat_group_free_reply_config,
    get_wechat_group_free_reply_rules,
    is_contextual_short_question,
)
from channel.wechat_group.wechat_group_free_reply_judge import WechatGroupFreeReplyJudge
from channel.wechat_group.wechat_group_free_reply_scorer import WechatGroupFreeReplyScorer
from channel.wechat_group.wechat_group_free_reply_worker import WechatGroupFreeReplyWorkerPool
from channel.wechat_group.wechat_group_free_reply_context import is_explicit_bot_followup_text
from channel.wechat_group.wechat_group_session_policy import (
    WechatGroupSessionPolicy,
    wechat_group_context_engine_v2_enabled,
)
from channel.wechat_group.wechat_group_reply_coordinator import (
    WechatGroupReplyCoordinator,
)
from channel.wechat_group.wechat_group_intent_router import WechatGroupIntentRouter
from channel.wechat_group.wechat_group_rolling_summary import (
    WechatGroupRollingSummaryService,
)
from channel.wechat_group.wechat_group_reply_cleanup import cleanup_wechat_group_reply_text
from channel.wechat_group.wechat_group_reply_policy import (
    build_wechat_group_addressee_policy_block,
    build_wechat_group_mention_verification_block,
    build_wechat_group_reply_policy_block,
)
from common import const
from common.expired_dict import ExpiredDict
from common.log import logger
from config import conf
from agent.protocol.agent_stream import looks_like_scheduler_request


WECHAT_GROUP_FREE_REPLY_DEBOUNCE_SECONDS = 1.5
WECHAT_GROUP_SHORT_QUESTION_BOT_FOLLOWUP_SECONDS = 60
WECHAT_GROUP_FREE_REPLY_MUTE_COMMAND = "闭嘴"
WECHAT_GROUP_VOICE_INTERACTION_FORCE_REPLY = "force_reply"
WECHAT_GROUP_VOICE_INTERACTION_FREE_REPLY = "free_reply"
WECHAT_GROUP_VOICE_INTERACTION_IGNORE = "ignore"
WECHAT_GROUP_DEFAULT_IMAGE_REPLY_QUESTION = "请根据这张图片作出简短回应。"
WECHAT_GROUP_AGENT_HISTORY_FRESH = "fresh"
WECHAT_GROUP_AGENT_HISTORY_INTERACTIVE = "interactive_session"
WECHAT_GROUP_AGENT_HISTORY_OBSERVE_ONLY = "observe_only"
WECHAT_GROUP_MEMBERSHIP_EVENT_TTL_SECONDS = 600
WECHAT_GROUP_MEMBERSHIP_EVENT_CACHE_SIZE = 512
WECHAT_GROUP_TRANSIENT_MODEL_ERROR_FALLBACK = "别@我了哥，没Token了。"
_WECHAT_GROUP_TRANSIENT_MODEL_STATUS_RE = re.compile(
    r"(?:status|http)\s*[:=]?\s*(?:408|429|500|502|503|504)\b",
    re.IGNORECASE,
)
_WECHAT_GROUP_TRANSIENT_MODEL_ERROR_KEYWORDS = (
    "rate limit",
    "freeusagelimiterror",
    "too many requests",
    "insufficient_quota",
    "quota exceeded",
    "no token",
    "token exhausted",
    "out of token",
    "timeout",
    "timed out",
    "temporarily unavailable",
    "temporary unavailable",
    "overloaded",
    "service unavailable",
    "bad gateway",
    "gateway timeout",
)


def _wechat_group_log_preview(text, limit=120) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(value) <= limit:
        return value
    return "{}...(+{} chars)".format(value[:limit], len(value) - limit)


def normalize_wechat_group_voice_interaction_mode(value) -> str:
    mode = str(value or "").strip().lower()
    if mode in (
        WECHAT_GROUP_VOICE_INTERACTION_FREE_REPLY,
        WECHAT_GROUP_VOICE_INTERACTION_IGNORE,
    ):
        return mode
    return WECHAT_GROUP_VOICE_INTERACTION_FORCE_REPLY


def _is_wechat_group_transient_model_error_text(text) -> bool:
    value = str(text or "").strip()
    if not value:
        return False
    lowered = value.lower()
    if not lowered.startswith("agent error:"):
        return False
    if _WECHAT_GROUP_TRANSIENT_MODEL_STATUS_RE.search(value):
        return True
    return any(
        keyword in lowered
        for keyword in _WECHAT_GROUP_TRANSIENT_MODEL_ERROR_KEYWORDS
    )


def _wechat_group_log_value(value) -> str:
    if value is None:
        return ""
    if "unittest.mock" in type(value).__module__:
        return ""
    return str(value)


def _wechat_group_stable_room_scope(msg) -> str:
    return (
        _wechat_group_log_value(getattr(msg, "wechat_group_stable_room_id", "")).strip()
        or _wechat_group_log_value(getattr(msg, "stable_room_id", "")).strip()
        or _wechat_group_log_value(getattr(msg, "other_user_id", "")).strip()
    )


def _wechat_group_stable_member_scope(msg) -> str:
    return (
        _wechat_group_log_value(getattr(msg, "wechat_group_stable_member_id", "")).strip()
        or _wechat_group_log_value(getattr(msg, "stable_member_id", "")).strip()
        or _wechat_group_log_value(getattr(msg, "actual_user_id", "")).strip()
    )


def _is_wechat_group_silent_reply_text(text: str) -> bool:
    value = re.sub(r"\s+", "", str(text or "")).strip()
    value = value.strip("()（）[]【】{}")
    if not value or len(value) > 24:
        return False
    has_not_addressed_bot = any(marker in value for marker in (
        "没@我",
        "没有@我",
        "未@我",
        "不是在问我",
        "不是问我",
        "没在问我",
        "没有在问我",
        "不是对我说",
        "不是在跟我说",
        "不是跟我说",
    ))
    has_silent_action = any(marker in value for marker in (
        "不插嘴",
        "不用插嘴",
        "无需插嘴",
        "不接话",
        "不用接话",
        "无需接话",
        "不回复",
        "不用回复",
        "无需回复",
        "不回应",
        "不用回应",
        "无需回应",
    ))
    return has_not_addressed_bot and has_silent_action


def _free_reply_rule_label_map() -> dict:
    labels = {}
    for group in (get_wechat_group_free_reply_rules() or {}).values():
        for rule in group or []:
            rule_id = str(rule.get("id") or "")
            if rule_id:
                labels[rule_id] = str(rule.get("label_zh") or rule.get("label") or rule_id)
    return labels


def _format_free_reply_items(items) -> str:
    values = [str(item) for item in (items or []) if str(item)]
    if not values:
        return "-"
    labels = _free_reply_rule_label_map()
    labels.setdefault(FREE_REPLY_MUTE_SUPPRESSION, "“闭嘴”禁言中")
    return ", ".join(
        "{}({})".format(item, labels[item]) if labels.get(item) else item
        for item in values
    )


def _is_archived_image_message(item) -> bool:
    return bool(
        item
        and str(item.get("message_type") or "").lower() == "image"
        and str(item.get("media_path") or "").strip()
    )


def select_wechat_group_agent_history_mode(
    trigger_source: str,
    text: str,
    is_free_reply: bool = False,
    local_decision: dict = None,
    llm_decision: dict = None,
) -> str:
    source = str(trigger_source or "").strip()
    local = local_decision if isinstance(local_decision, dict) else {}
    llm = llm_decision if isinstance(llm_decision, dict) else {}
    addressee = local.get("addressee") if isinstance(local.get("addressee"), dict) else {}
    if is_free_reply:
        target = str(llm.get("target") or addressee.get("target_kind") or "unknown")
        follows_bot = bool(
            llm.get("is_followup_to_bot") is True
            or addressee.get("is_followup_to_bot") is True
        )
        if target == "bot":
            return (
                WECHAT_GROUP_AGENT_HISTORY_INTERACTIVE
                if follows_bot
                else WECHAT_GROUP_AGENT_HISTORY_FRESH
            )
        return WECHAT_GROUP_AGENT_HISTORY_OBSERVE_ONLY
    if source == "quote_self":
        return WECHAT_GROUP_AGENT_HISTORY_INTERACTIVE
    if is_explicit_bot_followup_text(text):
        return WECHAT_GROUP_AGENT_HISTORY_INTERACTIVE
    return WECHAT_GROUP_AGENT_HISTORY_FRESH


class WechatGroupChannel(ChatChannel):
    channel_type = const.WECHAT_GROUP
    NOT_SUPPORT_REPLYTYPE = []

    STATUS_IDLE = "idle"
    STATUS_STARTING = "starting"
    STATUS_QR_READY = "qr_ready"
    STATUS_LOGGED_IN = "logged_in"
    STATUS_CONNECTED = "connected"
    STATUS_ERROR = "error"

    def __init__(
        self,
        client=None,
        archive=None,
        memory_service=None,
        focus_service=None,
        emotion_service=None,
        style_service=None,
        sticker_service=None,
        multimodal_context_service=None,
        profile_service=None,
        identity_service=None,
        session_policy=None,
        reply_coordinator=None,
        intent_router=None,
        rolling_summary_service=None,
    ):
        super().__init__()
        self.client = client or WechatGroupClient(event_handler=self.consume_sidecar_event)
        if hasattr(self.client, "event_handler"):
            self.client.event_handler = self.consume_sidecar_event
        self.archive = archive or WechatGroupArchive()
        self.memory_service = memory_service
        self.focus_service = focus_service
        self.emotion_service = emotion_service
        self.style_service = style_service
        self.sticker_service = sticker_service
        self.multimodal_context_service = multimodal_context_service
        self.profile_service = profile_service
        self.identity_service = identity_service
        self.session_policy = session_policy or WechatGroupSessionPolicy()
        self.reply_coordinator = reply_coordinator or WechatGroupReplyCoordinator()
        self.intent_router = intent_router or WechatGroupIntentRouter()
        self._wechat_group_rolling_summary_service = rolling_summary_service
        self.status = self.STATUS_IDLE
        self.last_error = ""
        self.qr_code = ""
        self.rooms = []
        self.room_members = {}
        self._room_members_lock = threading.Lock()
        self._room_members_waiters = {}
        self._room_member_refresh_requested_at = {}
        self._room_member_updated_at = {}
        self._login_session_room_ids_by_name = {}
        self._login_session_room_ids_lock = threading.RLock()
        self._received_msgs = ExpiredDict(60 * 60 * 8)
        self._membership_events = OrderedDict()
        self._membership_events_lock = threading.Lock()
        self.free_reply_state = WechatGroupFreeReplyStateStore()
        self._free_reply_scorer = WechatGroupFreeReplyScorer()
        self.free_reply_judge = WechatGroupFreeReplyJudge(scorer=self._free_reply_scorer)
        self.free_reply_worker = self._create_free_reply_worker()
        self._free_reply_worker_started = False
        if get_wechat_group_free_reply_config()["enabled"]:
            self._ensure_free_reply_worker_started()

    def startup(self):
        self.status = self.STATUS_STARTING
        self.last_error = ""
        try:
            self.client.start()
        except Exception as e:
            self.status = self.STATUS_ERROR
            self.last_error = str(e)
            self.report_startup_error(self.last_error)
            return
        error = self._poll_client_error()
        if error:
            self.status = self.STATUS_ERROR
            self.last_error = error
            self.report_startup_error(error)
            return
        self._ensure_profile_evolution_trigger_started()
        self._ensure_memory_dream_trigger_started()
        self.report_startup_success()

    def _handle(self, context):
        if not context or not wechat_group_context_engine_v2_enabled():
            return super()._handle(context)
        msg = context.get("msg")
        if not msg or not getattr(msg, "is_group", False):
            return super()._handle(context)
        try:
            room_id = str(
                context.get("wechat_group_stable_room_id")
                or context.get("receiver")
                or ""
            )
            priority = 10 if context.get("wechat_group_is_free_reply") is True else 0
            if not conf().get("wechat_group_room_singleflight_enabled", True):
                self._refresh_v2_request_context(context)
                return super()._handle(context)
            with self.reply_coordinator.turn(room_id, priority=priority):
                self._refresh_v2_request_context(context)
                return super()._handle(context)
        finally:
            self._discard_pending_agent_delivery(
                context,
                reason="request_completed_without_confirmed_send",
            )

    def _refresh_v2_request_context(self, context) -> None:
        if not conf().get("wechat_group_humanized_context_enabled", True):
            return
        msg = context.get("msg")
        raw_text = str(
            context.get("wechat_group_user_content") or context.content or ""
        )
        intent_route = self.intent_router.route(raw_text)
        context["wechat_group_intent_route"] = intent_route.route
        context["wechat_group_intent_route_details"] = intent_route.to_dict()
        context["wechat_group_suggested_tool_names"] = list(
            intent_route.suggested_tool_names
        )
        result = WechatGroupHumanizedContextBuilder(self).build(
            msg=msg,
            user_content=raw_text,
            trigger_source=str(context.get("wechat_group_trigger_source") or ""),
            include_quote=not context.get("wechat_group_skip_multimodal_quote", False),
            reply_mode=str(context.get("wechat_group_free_reply_mode") or ""),
            is_free_reply=context.get("wechat_group_is_free_reply") is True,
            request_context=context,
        )
        for key, value in result.metadata.items():
            context[key] = value
        context.content = result.content

    def stop(self):
        self.free_reply_worker.stop()
        self._free_reply_worker_started = False
        summary_service = self._wechat_group_rolling_summary_service
        if summary_service is not None:
            summary_service.stop()
        self.client.stop()
        self.status = self.STATUS_IDLE
        self.last_error = ""

    def force_rescan(self):
        self.status = self.STATUS_STARTING
        self.last_error = ""
        self.qr_code = ""
        self.rooms = []
        self.user_id = ""
        self.name = ""
        with self._room_members_lock:
            self.room_members.clear()
            self._room_member_refresh_requested_at.clear()
            self._room_member_updated_at.clear()
        self._startup_error = None
        self._startup_event.clear()
        try:
            self.client.force_rescan()
        except Exception as e:
            error = str(e)
            self.status = self.STATUS_ERROR
            self.last_error = error
            self.report_startup_error(error)
            raise
        self.report_startup_success()

    def _poll_client_error(self) -> str:
        poll_error = getattr(self.client, "poll_error", None)
        if callable(poll_error):
            error = poll_error()
            if error:
                return str(error)
        return ""

    @staticmethod
    def _ensure_profile_evolution_trigger_started() -> None:
        try:
            from channel.wechat_group.wechat_group_profile_evolution_trigger import (
                get_wechat_group_profile_evolution_trigger,
            )

            get_wechat_group_profile_evolution_trigger().start()
        except Exception as e:
            logger.debug("[wechat_group] profile evolution trigger start skipped: {}".format(e))

    @staticmethod
    def _ensure_memory_dream_trigger_started() -> None:
        try:
            from channel.wechat_group.wechat_group_memory_dream_trigger import (
                get_wechat_group_memory_dream_trigger,
            )

            get_wechat_group_memory_dream_trigger().start()
        except Exception as e:
            logger.debug("[wechat_group] memory Dream trigger start skipped: {}".format(e))

    def get_login_status(self) -> str:
        error = self._poll_client_error()
        if error and self.status not in (self.STATUS_IDLE, self.STATUS_LOGGED_IN, self.STATUS_CONNECTED):
            self.status = self.STATUS_ERROR
            self.last_error = error
            self.report_startup_error(error)
        return self.status

    def refresh_rooms(self):
        self.client.list_rooms()

    def refresh_room_members(self, room_id: str, wait: bool = True, timeout: float = 3.0, query: str = ""):
        room_text = str(room_id or "").strip()
        if not room_text:
            return []
        request_id = "room_members_{}_{}".format(int(time.time() * 1000), id(self))
        waiter = threading.Event()
        with self._room_members_lock:
            self._room_members_waiters[request_id] = waiter
        try:
            self.client.list_room_members(room_text, request_id=request_id, query=str(query or "").strip())
        except Exception as e:
            logger.warning("[wechat_group] failed to request room members: {}".format(e))
            with self._room_members_lock:
                self._room_members_waiters.pop(request_id, None)
            return self.room_members.get(room_text, [])
        if wait:
            waiter.wait(max(float(timeout or 0), 0))
        with self._room_members_lock:
            self._room_members_waiters.pop(request_id, None)
            return list(self.room_members.get(room_text, []))

    def get_room_members(self, room_id: str, query: str = "", limit: int = 20, refresh: bool = True):
        room_text = str(room_id or "").strip()
        if not room_text:
            return []
        if refresh:
            wait_seconds = 8.0 if str(query or "").strip() else 3.0
            members = self.refresh_room_members(room_text, wait=True, timeout=wait_seconds, query=query)
        else:
            members = list(self.room_members.get(room_text, []))
        members = self._enrich_room_members_with_profiles(members, room_text, query=query)
        return self._filter_room_members(members, query=query, limit=limit)

    def consume_sidecar_event(self, event: SidecarEvent) -> bool:
        if event.type == SidecarEventType.MESSAGE:
            return self._consume_message(event)
        if event.type == SidecarEventType.ROOM_JOIN:
            return self._consume_membership_event(event, WECHAT_GROUP_MEMBERSHIP_EVENT_JOIN)
        if event.type == SidecarEventType.ROOM_LEAVE:
            return self._consume_membership_event(event, WECHAT_GROUP_MEMBERSHIP_EVENT_LEAVE)
        if event.type == SidecarEventType.QR:
            self.status = self.STATUS_QR_READY
            self.last_error = ""
            self.qr_code = event.get("qrcode") or event.get("url") or ""
            qr_url = event.get("url") or self.qr_code
            logger.info("[wechat_group] QR ready, scan URL: {}".format(qr_url))
            return True
        if event.type == SidecarEventType.STATUS:
            previous_status = self.status
            status = event.get("status") or self.status
            if status == self.STATUS_LOGGED_IN and previous_status != self.STATUS_LOGGED_IN:
                self._reset_login_session_room_names()
            self.status = status
            if status in (self.STATUS_LOGGED_IN, self.STATUS_CONNECTED):
                self.last_error = ""
            self.name = event.get("self_name") or self.name
            self.user_id = event.get("self_id") or self.user_id
            return True
        if event.type == SidecarEventType.ROOMS:
            self.rooms = self._enrich_rooms_with_stable_identity(event.get("rooms", []))
            if self.status in (
                self.STATUS_STARTING,
                self.STATUS_QR_READY,
                self.STATUS_LOGGED_IN,
                self.STATUS_ERROR,
            ):
                self.status = self.STATUS_CONNECTED
                self.last_error = ""
            self._warm_free_reply_room_member_counts()
            return True
        if event.type == SidecarEventType.ROOM_MEMBERS:
            return self._consume_room_members(event)
        if event.type == SidecarEventType.SEND_RESULT:
            consume_result = getattr(self.client, "consume_send_result", None)
            if callable(consume_result):
                consume_result(event)
            return True
        if event.type == SidecarEventType.ERROR:
            error = str(event.get("message") or event.get("error") or event.payload or "")
            if self.status in (self.STATUS_LOGGED_IN, self.STATUS_CONNECTED) or self.rooms:
                self.last_error = error
                logger.warning("[wechat_group] sidecar error after login: {}".format(event.payload))
                return True
            self.status = self.STATUS_ERROR
            self.last_error = error
            self.report_startup_error(error)
            logger.error("[wechat_group] sidecar error: {}".format(event.payload))
            return True
        return False

    def _consume_membership_event(self, event: SidecarEvent, event_type: str) -> bool:
        try:
            runtime_room_id = str(event.get("room_id") or "").strip()
            members = self._normalize_room_members(event.get("members", []))
            memberless_join = (
                event_type == WECHAT_GROUP_MEMBERSHIP_EVENT_JOIN
                and event.get("member_info_missing") is True
                and not members
            )
            if not runtime_room_id or (not members and not memberless_join):
                logger.warning("[wechat_group] membership event skipped: missing room or members")
                return False

            self_id = str(event.get("self_id") or self.user_id or "").strip()
            member_ids = [str(member.get("sender_id") or "").strip() for member in members]
            if event_type == WECHAT_GROUP_MEMBERSHIP_EVENT_LEAVE and self_id in member_ids:
                logger.info("[wechat_group] self leave observed; notification skipped")
                return True
            if event_type == WECHAT_GROUP_MEMBERSHIP_EVENT_JOIN and self_id and members:
                members = [member for member in members if member.get("sender_id") != self_id]
                if not members:
                    logger.info("[wechat_group] self join observed; welcome skipped")
                    return True

            operator_key = "inviter" if event_type == WECHAT_GROUP_MEMBERSHIP_EVENT_JOIN else "remover"
            operator = self._normalize_membership_operator(event.get(operator_key))
            if self._is_duplicate_membership_event(
                event_type,
                runtime_room_id,
                members,
                operator,
                event.get("timestamp"),
            ):
                logger.debug("[wechat_group] duplicate membership event skipped")
                return False

            identity = self._resolve_membership_event_identity(event, runtime_room_id)
            if not identity:
                return True
            stable_room_id = identity["stable_room_id"]
            selected_rooms = {
                str(room_id or "").strip()
                for room_id in (conf().get("wechat_group_stable_room_ids", []) or [])
                if str(room_id or "").strip().startswith("wgr_")
            }
            if stable_room_id not in selected_rooms:
                logger.info("[wechat_group] membership event skipped: stable room is not selected")
                return True

            members = [
                self._enrich_membership_contact(identity["service"], stable_room_id, member)
                for member in members
            ]
            operator = self._enrich_membership_contact(
                identity["service"],
                stable_room_id,
                operator,
            ) if operator else {}
            notice = resolve_wechat_group_membership_notice(event_type, stable_room_id, conf())
            if not notice:
                return True

            if memberless_join:
                logger.warning(
                    "[wechat_group] join member info missing; sending welcome without mention: "
                    "stable_room_id={}".format(stable_room_id)
                )

            if notice["content_type"] == WECHAT_GROUP_MEMBERSHIP_CONTENT_IMAGE:
                image_path = resolve_membership_notice_image_path(
                    conf().get("agent_workspace", "~/lightagent") or "~/lightagent",
                    notice.get("image_path"),
                )
                validate_membership_notice_image_file(image_path)
                self.client.send_image(runtime_room_id, image_path)
            else:
                payload = dict(event.payload)
                payload["members"] = members
                payload[operator_key] = operator
                values = build_membership_notice_template_values(event_type, payload)
                text = render_membership_notice_template(notice.get("text"), event_type, values)
                mention_ids = (
                    [member["sender_id"] for member in members if member.get("sender_id")]
                    if event_type == WECHAT_GROUP_MEMBERSHIP_EVENT_JOIN
                    else []
                )
                self.client.send_text(runtime_room_id, text, mention_ids=mention_ids)
            logger.info(
                "[wechat_group] membership notice queued: event={} stable_room_id={} "
                "member_count={} scope={} degraded={}".format(
                    event_type,
                    stable_room_id,
                    len(members),
                    notice.get("source") or "global",
                    memberless_join,
                )
            )
            return True
        except Exception as exc:
            logger.warning("[wechat_group] membership event failed: {}".format(exc))
            return True

    @staticmethod
    def _normalize_membership_operator(value):
        if not isinstance(value, dict):
            return {}
        normalized = WechatGroupChannel._normalize_room_members([value])
        return normalized[0] if normalized else {}

    def _is_duplicate_membership_event(
        self,
        event_type,
        runtime_room_id,
        members,
        operator,
        timestamp,
    ) -> bool:
        member_ids = tuple(sorted(
            str(member.get("sender_id") or "").strip()
            for member in members
            if str(member.get("sender_id") or "").strip()
        ))
        operator_id = str((operator or {}).get("sender_id") or "").strip()
        try:
            event_timestamp = int(float(timestamp))
        except (TypeError, ValueError):
            event_timestamp = int(time.time())
        cache_key = (event_type, runtime_room_id, member_ids, operator_id, event_timestamp)
        now = time.time()
        with self._membership_events_lock:
            while self._membership_events:
                _, created_at = next(iter(self._membership_events.items()))
                if now - created_at <= WECHAT_GROUP_MEMBERSHIP_EVENT_TTL_SECONDS:
                    break
                self._membership_events.popitem(last=False)
            if cache_key in self._membership_events:
                self._membership_events.move_to_end(cache_key)
                return True
            self._membership_events[cache_key] = now
            while len(self._membership_events) > WECHAT_GROUP_MEMBERSHIP_EVENT_CACHE_SIZE:
                self._membership_events.popitem(last=False)
        return False

    def _resolve_membership_event_identity(self, event, runtime_room_id):
        runtime_self_id = str(event.get("self_id") or self.user_id or "").strip()
        self_name = str(event.get("self_name") or self.name or "").strip()
        if not runtime_self_id:
            logger.warning("[wechat_group] membership event skipped: stable account cannot be resolved")
            return {}
        try:
            service = self.identity_service or WechatGroupIdentityService()
            self.identity_service = service
            account = service.resolve_account(
                runtime_self_id,
                self_name,
                get_wechat_group_sidecar_memory_path(),
                {"wechat_id": str(event.get("self_wechat_id") or "").strip()},
            )
            room = self._resolve_room_with_session_name_recovery(
                service,
                account.stable_id,
                runtime_room_id,
                str(event.get("room_name") or "").strip(),
                runtime_self_id,
                {},
            )
            if (
                account.status != "confirmed"
                or account.requires_confirmation
                or room.status != "confirmed"
                or room.requires_confirmation
                or not str(room.stable_id or "").startswith("wgr_")
            ):
                logger.warning("[wechat_group] membership event skipped: stable identity is unconfirmed")
                return {}
            return {"service": service, "stable_room_id": str(room.stable_id)}
        except Exception as exc:
            logger.warning("[wechat_group] membership event identity resolution failed: {}".format(exc))
            return {}

    def _enrich_membership_contact(self, service, stable_room_id, member):
        item = dict(member or {})
        runtime_sender_id = str(item.get("sender_id") or "").strip()
        if not runtime_sender_id:
            return item
        nickname = str(item.get("sender_nickname") or "").strip()
        room_alias = str(item.get("room_alias") or "").strip()
        visible_name = room_alias or nickname
        if self._looks_like_raw_member_name(visible_name, runtime_sender_id):
            visible_name = ""
        try:
            resolution = service.resolve_member(
                stable_room_id,
                runtime_sender_id,
                visible_name,
                room_alias,
                {"wechat_id": str(item.get("wechat_id") or "").strip()},
            )
            resolved_name = str(resolution.display_name or "").strip()
            item["stable_member_id"] = str(resolution.stable_id or "")
            item["display_name"] = visible_name or (
                "" if self._looks_like_raw_member_name(resolved_name, runtime_sender_id) else resolved_name
            )
        except Exception:
            item["stable_member_id"] = ""
            item["display_name"] = visible_name
            logger.debug("[wechat_group] membership member identity unresolved")
        return item

    def _enrich_rooms_with_stable_identity(self, rooms):
        normalized = [dict(room) for room in (rooms or []) if isinstance(room, dict)]
        room_runtime_ids_by_name = {}
        for room in normalized:
            runtime_room_id = str(room.get("runtime_room_id") or room.get("room_id") or room.get("id") or "").strip()
            room_name = str(room.get("name") or room.get("room_name") or room.get("topic") or "").strip()
            if runtime_room_id and room_name:
                room_runtime_ids_by_name.setdefault(room_name, set()).add(runtime_room_id)
        runtime_self_id = str(self.user_id or "").strip()
        if not runtime_self_id:
            return normalized
        try:
            service = self.identity_service or WechatGroupIdentityService()
            self.identity_service = service
            account = service.resolve_account(
                runtime_self_id,
                self.name or "",
                get_wechat_group_sidecar_memory_path(),
                {},
            )
        except Exception as e:
            logger.warning("[wechat_group] failed to resolve room list account identity: {}".format(e))
            return normalized
        enriched = []
        for room in normalized:
            runtime_room_id = str(room.get("runtime_room_id") or room.get("room_id") or room.get("id") or "").strip()
            room_name = str(room.get("name") or room.get("room_name") or room.get("topic") or "").strip()
            if not runtime_room_id:
                enriched.append(room)
                continue
            try:
                resolution = self._resolve_room_with_session_name_recovery(
                    service,
                    account.stable_id,
                    runtime_room_id,
                    room_name,
                    runtime_self_id,
                    {},
                    allow_name_recovery=len(room_runtime_ids_by_name.get(room_name, set())) <= 1,
                )
                room["stable_account_id"] = account.stable_id
                room["runtime_self_id"] = runtime_self_id
                room["account_binding_status"] = account.status
                room["account_identity_confidence"] = account.confidence
                room["account_identity_requires_confirmation"] = bool(account.requires_confirmation)
                room["stable_room_id"] = resolution.stable_id
                room["runtime_room_id"] = runtime_room_id
                room["binding_status"] = resolution.status
                room["identity_confidence"] = resolution.confidence
                room["identity_requires_confirmation"] = bool(resolution.requires_confirmation)
            except Exception as e:
                room["runtime_room_id"] = runtime_room_id
                room["stable_room_id"] = ""
                room["binding_status"] = "identity_unresolved"
                room["identity_requires_confirmation"] = True
                logger.warning(
                    "[wechat_group] failed to resolve room list identity: room={} error={}".format(
                        runtime_room_id,
                        e,
                    )
                )
            enriched.append(room)
        return enriched

    def _resolve_room_with_session_name_recovery(
        self,
        service,
        stable_account_id,
        runtime_room_id,
        room_name,
        runtime_self_id,
        metadata,
        allow_name_recovery=True,
    ):
        with self._login_session_room_ids_lock:
            session_allows_name_recovery = self._allow_room_name_recovery_in_current_session(
                runtime_room_id,
                room_name,
            )
            return service.resolve_room(
                stable_account_id,
                runtime_room_id,
                room_name,
                runtime_self_id,
                metadata,
                allow_name_recovery=(
                    allow_name_recovery
                    and session_allows_name_recovery
                ),
            )

    def _allow_room_name_recovery_in_current_session(self, runtime_room_id, room_name) -> bool:
        runtime_id = str(runtime_room_id or "").strip()
        exact_name = str(room_name or "").strip()
        if not runtime_id or not exact_name:
            return True
        with self._login_session_room_ids_lock:
            seen_runtime_ids = self._login_session_room_ids_by_name.setdefault(exact_name, set())
            allow_name_recovery = not seen_runtime_ids or seen_runtime_ids == {runtime_id}
            seen_runtime_ids.add(runtime_id)
            return allow_name_recovery

    def _reset_login_session_room_names(self) -> None:
        with self._login_session_room_ids_lock:
            self._login_session_room_ids_by_name.clear()

    def _consume_room_members(self, event: SidecarEvent) -> bool:
        room_id = str(event.get("room_id") or "").strip()
        if not room_id:
            return False
        members = self._normalize_room_members(event.get("members", []))
        members = self._enrich_room_members_with_stable_identity(members, room_id)
        request_id = str(event.get("request_id") or "").strip()
        with self._room_members_lock:
            self.room_members[room_id] = members
            self._room_member_updated_at[room_id] = time.time()
            waiter = self._room_members_waiters.get(request_id)
            if waiter:
                waiter.set()
        return True

    def _request_room_members_for_free_reply(self, runtime_room_id: str, now=None) -> None:
        room_id = str(runtime_room_id or "").strip()
        if not room_id:
            return
        current_time = float(now if now is not None else time.time())
        with self._room_members_lock:
            members = self.room_members.get(room_id)
            updated_at = float(self._room_member_updated_at.get(room_id) or 0)
            if members and current_time - updated_at < 1800:
                return
            last_requested_at = float(
                self._room_member_refresh_requested_at.get(room_id) or 0
            )
            if current_time - last_requested_at < 600:
                return
            self._room_member_refresh_requested_at[room_id] = current_time
        try:
            self.client.list_room_members(room_id, request_id="", query="")
        except Exception as e:
            with self._room_members_lock:
                self._room_member_refresh_requested_at.pop(room_id, None)
            logger.debug(
                "[wechat_group] free reply member-count refresh skipped: {}".format(e)
            )

    def _warm_free_reply_room_member_counts(self) -> None:
        config = get_wechat_group_free_reply_config()
        if not config.get("enabled"):
            return
        selected_ids = {
            str(value or "").strip()
            for value in (config.get("room_ids") or [])
            if str(value or "").strip()
        }
        selected_names = {
            str(value or "").strip()
            for value in (config.get("names") or [])
            if str(value or "").strip()
        }
        if not selected_ids and not selected_names:
            return
        for room in self.rooms or []:
            runtime_room_id = str(
                room.get("runtime_room_id") or room.get("room_id") or room.get("id") or ""
            ).strip()
            stable_room_id = str(room.get("stable_room_id") or "").strip()
            room_name = str(
                room.get("name") or room.get("room_name") or room.get("topic") or ""
            ).strip()
            if (
                runtime_room_id in selected_ids
                or stable_room_id in selected_ids
                or room_name in selected_names
            ):
                self._request_room_members_for_free_reply(runtime_room_id)

    def _free_reply_group_size(self, runtime_room_id: str) -> tuple:
        room_id = str(runtime_room_id or "").strip()
        if not room_id:
            return 0, "unknown"
        with self._room_members_lock:
            members = list(self.room_members.get(room_id) or [])
            updated_at = float(self._room_member_updated_at.get(room_id) or 0)
        if members:
            if time.time() - updated_at >= 1800:
                self._request_room_members_for_free_reply(room_id)
            return len(members), "room_member_cache"
        self._request_room_members_for_free_reply(room_id)
        return 0, "refresh_pending"

    @staticmethod
    def _normalize_room_members(value):
        if not isinstance(value, list):
            return []
        result = []
        seen = set()
        for raw in value:
            if not isinstance(raw, dict):
                continue
            sender_id = str(raw.get("sender_id") or raw.get("id") or "").strip()
            if not sender_id or sender_id in seen:
                continue
            seen.add(sender_id)
            nickname = str(raw.get("sender_nickname") or raw.get("name") or "").strip()
            result.append({
                "sender_id": sender_id,
                "sender_nickname": nickname or sender_id,
                "room_alias": str(raw.get("room_alias") or raw.get("roomAlias") or "").strip(),
                "wechat_id": str(raw.get("wechat_id") or raw.get("wechatId") or "").strip(),
                "last_seen_at": int(raw.get("last_seen_at") or 0),
                "message_count": int(raw.get("message_count") or 0),
            })
        return result

    def _get_profile_service(self):
        if self.profile_service is None:
            try:
                from channel.wechat_group.wechat_group_profile_service import WechatGroupProfileService
                self.profile_service = WechatGroupProfileService(
                    identity_service=self.identity_service,
                )
            except Exception as e:
                logger.debug("[wechat_group] failed to create profile service for member search: {}".format(e))
                return None
        return self.profile_service

    def _enrich_room_members_with_profiles(self, members, room_id: str, query: str = ""):
        if not str(query or "").strip():
            return list(members or [])
        service = self._get_profile_service()
        if not service:
            return list(members or [])
        stable_room_id = self._stable_room_id_for_runtime_room(room_id)
        if not stable_room_id:
            return list(members or [])
        result = []
        for member in members or []:
            item = dict(member)
            sender_id = str(item.get("stable_member_id") or item.get("sender_id") or "").strip()
            if not sender_id:
                result.append(item)
                continue
            try:
                profile = service.get_profile(sender_id, room_id=stable_room_id) or {}
            except Exception as e:
                logger.debug("[wechat_group] failed to load profile for member search: {}".format(e))
                profile = {}
            profile_nickname = str(profile.get("primary_nickname") or "").strip()
            profile_aliases = [
                str(alias or "").strip()
                for alias in (profile.get("aliases") or [])
                if str(alias or "").strip()
            ]
            if profile_nickname:
                item["profile_nickname"] = profile_nickname
            if profile_aliases:
                item["profile_aliases"] = profile_aliases
            if profile_nickname and self._looks_like_raw_member_name(item.get("sender_nickname"), sender_id):
                item["sender_nickname"] = profile_nickname
            result.append(item)
        return result

    def _stable_room_id_for_runtime_room(self, runtime_room_id: str) -> str:
        runtime_id = str(runtime_room_id or "").strip()
        for room in self.rooms or []:
            current_runtime_id = str(
                room.get("runtime_room_id") or room.get("room_id") or room.get("id") or ""
            ).strip()
            if current_runtime_id == runtime_id:
                stable_room_id = str(room.get("stable_room_id") or "").strip()
                if stable_room_id:
                    return stable_room_id
        try:
            return str(self.identity_service.resolve_legacy_room_id(runtime_id) or "").strip()
        except Exception:
            return ""

    @staticmethod
    def _filter_room_members(members, query: str = "", limit: int = 20):
        max_limit = min(max(int(limit or 20), 1), 500)
        q = str(query or "").strip().lower()
        result = []
        for member in members or []:
            haystack = " ".join([
                str(member.get("sender_id") or ""),
                str(member.get("sender_nickname") or ""),
                str(member.get("wechat_id") or ""),
                str(member.get("profile_nickname") or ""),
                " ".join(str(alias or "") for alias in (member.get("profile_aliases") or [])),
            ]).lower()
            if q and q not in haystack:
                continue
            result.append(member)
            if len(result) >= max_limit:
                break
        return result

    @staticmethod
    def _looks_like_raw_member_name(value, sender_id: str = "") -> bool:
        text = str(value or "").strip()
        if not text:
            return True
        normalized = text.lstrip("@")
        sender_text = str(sender_id or "").strip()
        sender_normalized = sender_text.lstrip("@")
        if sender_text and text == sender_text:
            return True
        if sender_normalized and normalized == sender_normalized:
            return True
        if normalized.startswith("wxid_"):
            return True
        return bool(text.startswith("@") and re.fullmatch(r"[0-9A-Za-z_-]{12,}", normalized))

    def _consume_message(self, event: SidecarEvent) -> bool:
        msg = WechatGroupMessage(event)
        if not msg.msg_id:
            logger.warning("[wechat_group] message missing id, skipped")
            return False
        if msg.msg_id in self._received_msgs:
            logger.debug("[wechat_group] duplicate message skipped: {}".format(msg.msg_id))
            return False
        self._received_msgs[msg.msg_id] = True
        if msg.my_msg:
            logger.debug("[wechat_group] self message skipped: {}".format(msg.msg_id))
            return False
        self._resolve_message_identity(msg)
        if not self._is_selected_room(msg):
            self._log_inbound_route_drop(msg, "unselected_room")
            logger.debug("[wechat_group] unselected room skipped: {}".format(msg.other_user_id))
            return False
        archive_row_id = self._record_inbound_message(msg)
        if archive_row_id:
            msg.wechat_group_inbound_archive_row_id = int(archive_row_id)
            self._schedule_rolling_summary(
                getattr(msg, "wechat_group_stable_room_id", "")
            )
        self.handle_text(msg)
        return True

    @staticmethod
    def _log_inbound_route_drop(msg: WechatGroupMessage, reason: str) -> None:
        logger.info(
            '[wechat_group] inbound skipped: reason={} message_id="{}" runtime_room_id="{}" '
            'stable_room_id="{}" room="{}"'.format(
                _wechat_group_log_value(reason),
                _wechat_group_log_value(getattr(msg, "msg_id", "")),
                _wechat_group_log_value(getattr(msg, "runtime_room_id", "")),
                _wechat_group_log_value(
                    getattr(msg, "wechat_group_stable_room_id", "")
                    or getattr(msg, "stable_room_id", "")
                ),
                _wechat_group_log_value(getattr(msg, "other_user_nickname", "")),
            )
        )

    def handle_text(self, msg: WechatGroupMessage):
        self._log_inbound_message(msg)
        voice_interaction_mode = normalize_wechat_group_voice_interaction_mode(
            conf().get("wechat_group_voice_interaction_mode")
        )
        if (
            msg.ctype == ContextType.VOICE
            and voice_interaction_mode == WECHAT_GROUP_VOICE_INTERACTION_IGNORE
        ):
            logger.info(
                '[wechat_group] voice message ignored: message_id="{}" room="{}" sender="{}"'.format(
                    _wechat_group_log_value(getattr(msg, "msg_id", "")),
                    _wechat_group_stable_room_scope(msg)
                    or _wechat_group_log_value(getattr(msg, "other_user_id", "")).strip(),
                    _wechat_group_stable_member_scope(msg)
                    or _wechat_group_log_value(getattr(msg, "actual_user_id", "")).strip(),
                )
            )
            return
        self._observe_emotion(msg)
        is_pat_self = getattr(msg, "is_pat_self", False) is True
        direct_reply = (
            getattr(msg, "is_at", False) is True
            or getattr(msg, "is_quote_self", False) is True
            or is_pat_self
        )
        if self._is_blacklisted_member(msg):
            logger.info(
                '[wechat_group] blacklisted member skipped: room="{}" sender="{}"'.format(
                    _wechat_group_stable_room_scope(msg) or _wechat_group_log_value(getattr(msg, "other_user_id", "")).strip(),
                    _wechat_group_stable_member_scope(msg) or _wechat_group_log_value(getattr(msg, "actual_user_id", "")).strip(),
                )
            )
            return
        if self._handle_free_reply_mute_command(msg):
            return
        if self._should_suppress_at_during_free_reply_mute(msg):
            return
        if msg.ctype == ContextType.IMAGE:
            if not direct_reply:
                if not conf().get("wechat_group_free_reply_image_understanding_enabled", False):
                    return
                image_text = self._build_free_reply_image_text(msg)
                should_enqueue, decision, recent_messages = self._should_enqueue_free_reply_message(
                    msg,
                    allow_media_payload=True,
                    text_override=image_text,
                )
                if not should_enqueue:
                    return
                self._ensure_free_reply_worker_started()
                submitted = self.free_reply_worker.submit(
                    self._build_free_reply_task(
                        msg,
                        decision,
                        text=image_text,
                        recent_messages=recent_messages,
                    )
                )
                if submitted:
                    self._log_free_reply_decision(decision, "queued")
                else:
                    self._log_free_reply_decision(decision, "queue_full")
                return
            if not conf().get("wechat_group_image_understanding_enabled", True):
                return
            if not conf().get("wechat_group_image_understanding_comment_enabled", True):
                return
            content = self._build_image_reply_content()
            context = self._compose_context(
                ContextType.TEXT,
                content,
                isgroup=True,
                msg=msg,
                wechat_group_force_reply=True,
                wechat_group_trigger_source="image_message",
            )
            if context:
                if context.get("wechat_group_multimodal_matched_images"):
                    context["wechat_group_image_understanding_triggered"] = True
                self.produce(context)
            return
        if str(getattr(msg, "message_type", "") or "").lower() == "video" and direct_reply:
            content = self._build_video_understanding_request_content(msg)
            if content:
                context = self._compose_context(
                    ContextType.TEXT,
                    content,
                    isgroup=True,
                    msg=msg,
                    wechat_group_force_reply=True,
                )
                if context:
                    context["wechat_group_video_understanding_triggered"] = True
                    self.produce(context)
                return
        if msg.ctype == ContextType.TEXT and not direct_reply:
            should_enqueue, decision, recent_messages = self._should_enqueue_free_reply_message(msg)
            if not should_enqueue:
                return
            self._ensure_free_reply_worker_started()
            submitted = self.free_reply_worker.submit(
                self._build_free_reply_task(msg, decision, recent_messages=recent_messages)
            )
            if submitted:
                self._log_free_reply_decision(decision, "queued")
            else:
                self._log_free_reply_decision(decision, "queue_full")
            return
        is_quote_self = getattr(msg, "is_quote_self", False) is True
        force_reply = direct_reply
        trigger_source = "quote_self" if is_quote_self else ("pat_self" if is_pat_self else ("direct_reply" if direct_reply else ""))
        context = self._compose_context(
            msg.ctype,
            msg.content,
            isgroup=True,
            msg=msg,
            wechat_group_force_reply=force_reply,
            wechat_group_trigger_source=trigger_source,
        )
        if context:
            if is_quote_self:
                context["wechat_group_quote_self_triggered"] = True
            if is_pat_self:
                context["wechat_group_pat_self_triggered"] = True
            if context.get("wechat_group_multimodal_matched_images"):
                context["wechat_group_image_understanding_triggered"] = True
            self.produce(context)

    def _handle_free_reply_mute_command(self, msg: WechatGroupMessage) -> bool:
        if not self._is_free_reply_mute_command(msg):
            return False
        room_id = _wechat_group_stable_room_scope(msg) or _wechat_group_log_value(
            getattr(msg, "other_user_id", "")
        ).strip()
        if not room_id:
            logger.warning("[wechat_group] free reply mute command missing room scope")
            return True
        cfg = get_wechat_group_free_reply_config()
        mute_minutes = cfg["mute_minutes"]
        muted_until = self.free_reply_state.mute(
            room_id,
            mute_minutes,
            now=time.time(),
        )
        logger.info(
            '[wechat_group] free reply muted: room="{}" duration_minutes={} muted_until={}'.format(
                room_id,
                mute_minutes,
                int(muted_until),
            )
        )
        return True

    def _should_suppress_at_during_free_reply_mute(self, msg: WechatGroupMessage) -> bool:
        if getattr(msg, "is_at", False) is not True:
            return False
        cfg = get_wechat_group_free_reply_config()
        if not cfg.get("mute_mentions_enabled", False):
            return False
        room_id = _wechat_group_stable_room_scope(msg) or _wechat_group_log_value(
            getattr(msg, "other_user_id", "")
        ).strip()
        if not room_id or self.free_reply_state.is_muted(room_id) is not True:
            return False
        logger.info(
            '[wechat_group] at reply muted: room="{}" sender="{}"'.format(
                room_id,
                _wechat_group_stable_member_scope(msg)
                or _wechat_group_log_value(getattr(msg, "actual_user_id", "")).strip(),
            )
        )
        return True

    @staticmethod
    def _is_blacklisted_member(msg: WechatGroupMessage) -> bool:
        if not msg or not getattr(msg, "is_group", False):
            return False
        room_id = _wechat_group_stable_room_scope(msg) or _wechat_group_log_value(
            getattr(msg, "other_user_id", "")
        ).strip()
        sender_id = _wechat_group_stable_member_scope(msg) or _wechat_group_log_value(
            getattr(msg, "actual_user_id", "")
        ).strip()
        runtime_sender_id = _wechat_group_log_value(getattr(msg, "actual_user_id", "")).strip()
        return is_wechat_group_blacklisted(
            room_id,
            sender_id,
            runtime_sender_id=runtime_sender_id,
        )

    def _is_free_reply_mute_command(self, msg: WechatGroupMessage) -> bool:
        if (
            getattr(msg, "ctype", None) != ContextType.TEXT
            or getattr(msg, "is_at", False) is not True
        ):
            return False
        text = _wechat_group_log_value(
            getattr(msg, "text", None) or getattr(msg, "content", "")
        ).strip()
        if text == WECHAT_GROUP_FREE_REPLY_MUTE_COMMAND:
            return True
        bot_names = [
            getattr(msg, "self_display_name", ""),
            getattr(msg, "to_user_nickname", ""),
            getattr(msg, "to_user_id", ""),
            getattr(msg, "runtime_self_id", ""),
            self.name,
        ]
        for bot_name in dict.fromkeys(
            _wechat_group_log_value(name).strip() for name in bot_names
        ):
            if not bot_name:
                continue
            without_mention = re.sub(
                r"^\s*@{}\s*".format(re.escape(bot_name)),
                "",
                text,
                count=1,
            ).strip()
            if without_mention != text and without_mention == WECHAT_GROUP_FREE_REPLY_MUTE_COMMAND:
                return True
        return False

    @staticmethod
    def _build_video_understanding_request_content(msg: WechatGroupMessage) -> str:
        if not conf().get("wechat_group_video_understanding_enabled", False):
            return ""
        video_path = str(getattr(msg, "media_path", "") or getattr(msg, "content", "") or "").strip()
        if not video_path:
            return ""
        user_text = str(getattr(msg, "text", "") or "").strip()
        return user_text or "请结合上面的多模态上下文理解这个视频并给出简短回复。"

    def _generate_reply(self, context, reply=Reply()):
        blocked_by_admin_guard = self._check_admin_guard(context)
        if blocked_by_admin_guard:
            return blocked_by_admin_guard
        if context and context.type == ContextType.IMAGE_CREATE:
            blocked = self._check_image_create_limit(context)
            if blocked:
                return blocked
            reply = super()._generate_reply(context, reply)
            if reply and reply.type in (ReplyType.IMAGE, ReplyType.IMAGE_URL):
                self._record_image_create_usage(context, "accepted")
            return reply
        return super()._generate_reply(context, reply)

    def _handle_voice_transcription(self, context, transcription):
        mode = normalize_wechat_group_voice_interaction_mode(
            conf().get("wechat_group_voice_interaction_mode")
        )
        if mode == WECHAT_GROUP_VOICE_INTERACTION_IGNORE:
            return None
        if mode == WECHAT_GROUP_VOICE_INTERACTION_FORCE_REPLY:
            kwargs = dict(context.kwargs)
            kwargs["wechat_group_force_reply"] = True
            kwargs["wechat_group_trigger_source"] = "voice_message"
            kwargs["origin_ctype"] = ContextType.VOICE
            return self._compose_context(ContextType.TEXT, transcription, **kwargs)

        msg = context.get("msg")
        if not msg:
            return None
        should_enqueue, decision, recent_messages = self._should_enqueue_free_reply_message(
            msg,
            text_override=transcription,
            message_type_override="text",
        )
        if not should_enqueue:
            return None
        task = self._build_free_reply_task(
            msg,
            decision,
            text=transcription,
            recent_messages=recent_messages,
        )
        task["voice_transcription"] = transcription
        task["desire_rtype"] = context.get("desire_rtype")
        self._ensure_free_reply_worker_started()
        submitted = self.free_reply_worker.submit(task)
        if submitted:
            self._log_free_reply_decision(decision, "queued")
        else:
            self._log_free_reply_decision(decision, "queue_full")
        return None

    def _check_admin_guard(self, context):
        if not context or context.get("channel_type") != "wechat_group":
            return None
        room_id = (
            context.get("wechat_group_stable_room_id")
            or context.get("wechat_group_stable_receiver")
            or context.get("wechat_group_room_id")
            or context.get("receiver")
            or ""
        )
        sender_id = (
            context.get("wechat_group_stable_member_id")
            or context.get("wechat_group_stable_sender_id")
            or context.get("wechat_group_sender_id")
            or ""
        )
        if context.get("wechat_group_identity_requires_confirmation") is True:
            sender_id = ""
        guard_text = context.get("wechat_group_user_content", context.content)
        if is_wechat_group_report_generation_request(guard_text):
            allowed, reason = can_generate_wechat_group_report(room_id, sender_id)
            if not allowed:
                messages = {
                    "identity_unconfirmed": "当前群身份尚未确认，不能生成群聊报告。",
                    "report_disabled": "当前群的群聊报告尚未启用。",
                    "admin_required": "生成群聊报告需要当前群管理员触发。",
                }
                return Reply(ReplyType.ERROR, messages.get(reason, "当前无法生成群聊报告。"))
        blocked = get_blocked_admin_permissions_for_text(guard_text, room_id, sender_id)
        if not blocked:
            return None
        context["wechat_group_admin_blocked_permissions"] = blocked
        return Reply(ReplyType.ERROR, build_wechat_group_admin_reject_message(blocked))

    def _check_image_create_limit(self, context) -> Reply:
        try:
            limit = int(conf().get("wechat_group_image_create_hourly_limit", 5))
        except Exception:
            limit = 5
        room_id = (
            context.get("wechat_group_stable_room_id")
            or context.get("wechat_group_stable_receiver")
            or context.get("receiver")
            or context.get("wechat_group_room_id")
            or ""
        )
        if limit <= 0:
            return Reply(ReplyType.ERROR, "当前微信群生图额度已关闭，请在控制台调整生图额度。")
        try:
            used = self.archive.count_image_create_usage(room_id=room_id, window_seconds=3600)
        except Exception as e:
            logger.warning("[wechat_group] failed to count image create usage: {}".format(e))
            used = 0
        if used >= limit:
            return Reply(ReplyType.ERROR, "当前群本小时生图额度已用完（{}/{}），请稍后再试。".format(used, limit))
        return None

    def _record_image_create_usage(self, context, status: str):
        msg = context.get("msg")
        try:
            self.archive.record_image_create_usage(
                room_id=context.get("wechat_group_stable_room_id") or context.get("receiver") or "",
                sender_id=context.get("wechat_group_stable_member_id") or (getattr(msg, "actual_user_id", "") if msg else ""),
                prompt=context.content or "",
                status=status,
                stable_room_id=context.get("wechat_group_stable_room_id") or "",
                runtime_room_id=context.get("wechat_group_runtime_room_id") or context.get("receiver") or "",
                stable_member_id=context.get("wechat_group_stable_member_id") or "",
                runtime_sender_id=context.get("wechat_group_runtime_sender_id") or (getattr(msg, "actual_user_id", "") if msg else ""),
            )
        except Exception as e:
            logger.warning("[wechat_group] failed to record image create usage: {}".format(e))

    def _log_inbound_message(self, msg: WechatGroupMessage):
        try:
            text = _wechat_group_log_value(getattr(msg, "text", None)) or _wechat_group_log_value(getattr(msg, "content", ""))
            message_type = _wechat_group_log_value(getattr(msg, "message_type", "")) or _wechat_group_log_value(getattr(msg, "ctype", ""))
            projected_type = project_wechat_message_type(message_type, text)
            if projected_type in ("image", "sticker"):
                text = "[{}]".format(projected_type)
            room_name = _wechat_group_log_value(getattr(msg, "other_user_nickname", "")) or _wechat_group_log_value(getattr(msg, "other_user_id", ""))
            sender_name = _wechat_group_log_value(getattr(msg, "actual_user_nickname", "")) or _wechat_group_log_value(getattr(msg, "actual_user_id", ""))
            logger.info(
                '[wechat_group] inbound: room="{}" sender="{}" type={} is_at={} text="{}"'.format(
                    room_name,
                    sender_name,
                    message_type,
                    bool(getattr(msg, "is_at", False)),
                    _wechat_group_log_preview(text),
                )
            )
        except Exception as e:
            logger.debug("[wechat_group] inbound log skipped: {}".format(e))

    def _log_free_reply_decision(self, decision: dict, status: str):
        try:
            logger.info(
                '[wechat_group] free reply {}: room="{}" sender="{}" score={} threshold={} level={} '
                'reasons={} suppressions={} text="{}"'.format(
                    status,
                    decision.get("room_name") or "[room]",
                    decision.get("sender_name") or "[member]",
                    decision.get("score", 0),
                    decision.get("threshold", 0),
                    decision.get("activity_level", ""),
                    _format_free_reply_items(decision.get("reasons")),
                    _format_free_reply_items(decision.get("suppressions")),
                    _wechat_group_log_preview(decision.get("text_preview", "")),
                )
            )
        except Exception as e:
            logger.debug("[wechat_group] free reply decision log skipped: {}".format(e))

    def _compose_context(self, ctype, content, **kwargs):
        msg = kwargs.get("msg")
        identity = self._resolve_message_identity(msg)
        if identity:
            kwargs = dict(kwargs)
            kwargs.update(identity)
        context = super()._compose_context(ctype, content, **kwargs)
        if not context or context.type != ContextType.TEXT:
            return context
        msg = context.get("msg")
        if not msg or not getattr(msg, "is_group", False):
            return context
        reply_mode = str(
            context.get("wechat_group_free_reply_mode")
            or kwargs.get("wechat_group_free_reply_mode")
            or ""
        )
        if reply_mode:
            context["wechat_group_free_reply_mode"] = reply_mode
        context["wechat_group_room_id"] = getattr(msg, "runtime_room_id", msg.other_user_id)
        context["wechat_group_sender_id"] = getattr(msg, "runtime_sender_id", msg.actual_user_id)
        context["wechat_group_bot_sender_id"] = getattr(msg, "runtime_self_id", msg.to_user_id)
        context["wechat_group_runtime_room_id"] = getattr(msg, "runtime_room_id", msg.other_user_id)
        context["wechat_group_runtime_sender_id"] = getattr(msg, "runtime_sender_id", msg.actual_user_id)
        context["wechat_group_runtime_bot_sender_id"] = getattr(msg, "runtime_self_id", msg.to_user_id)
        if context.get("wechat_group_stable_room_id"):
            context["wechat_group_stable_receiver"] = context.get("wechat_group_stable_room_id")
        if context.get("wechat_group_stable_member_id"):
            context["wechat_group_stable_sender_id"] = context.get("wechat_group_stable_member_id")
        context["wechat_group_user_content"] = context.content
        if kwargs.get("wechat_group_is_free_reply"):
            context["wechat_group_is_free_reply"] = True
        if looks_like_scheduler_request(context.content):
            context["intent_requires_scheduler"] = True
        try:
            archive_row_id = int(
                getattr(msg, "wechat_group_inbound_archive_row_id", 0) or 0
            )
        except (TypeError, ValueError):
            archive_row_id = 0
        if not archive_row_id:
            recorded_row_id = self._record_inbound_message(msg)
            try:
                archive_row_id = int(recorded_row_id or 0)
            except (TypeError, ValueError):
                archive_row_id = 0
            if archive_row_id:
                msg.wechat_group_inbound_archive_row_id = archive_row_id
        if archive_row_id:
            context["wechat_group_inbound_archive_row_id"] = archive_row_id
        trigger_source = (
            context.get("wechat_group_trigger_source")
            or kwargs.get("wechat_group_trigger_source")
            or ("free_reply" if context.get("wechat_group_is_free_reply") else "")
            or self._infer_multimodal_trigger_source(msg)
        )
        context["wechat_group_trigger_source"] = trigger_source
        if wechat_group_context_engine_v2_enabled():
            session_decision = self.session_policy.resolve(
                stable_room_id=context.get("wechat_group_stable_room_id") or "",
                stable_member_id=context.get("wechat_group_stable_member_id") or "",
                fallback_member_id=getattr(msg, "actual_user_id", ""),
                trigger_source=trigger_source,
                text=context.get("wechat_group_user_content") or context.content,
                is_free_reply=context.get("wechat_group_is_free_reply") is True,
                local_decision=(
                    context.get("wechat_group_free_reply_decision")
                    or kwargs.get("wechat_group_free_reply_decision")
                    or {}
                ),
                llm_decision=(
                    context.get("wechat_group_free_reply_llm_decision")
                    or kwargs.get("wechat_group_free_reply_llm_decision")
                    or {}
                ),
                is_quote_self=bool(getattr(msg, "is_quote_self", False)),
            )
            for key, value in session_decision.to_context().items():
                context[key] = value
            history_mode = session_decision.history_mode
        else:
            history_mode = str(
                context.get("wechat_group_agent_history_mode")
                or kwargs.get("wechat_group_agent_history_mode")
                or select_wechat_group_agent_history_mode(
                    trigger_source,
                    context.get("wechat_group_user_content") or context.content,
                    is_free_reply=context.get("wechat_group_is_free_reply") is True,
                )
            )
        context["wechat_group_agent_history_mode"] = history_mode
        if conf().get("wechat_group_humanized_context_enabled", True):
            if wechat_group_context_engine_v2_enabled():
                # V2 rebuilds one immutable snapshot after the request wins
                # the room coordinator, so queued work never uses stale facts.
                return context
            try:
                result = WechatGroupHumanizedContextBuilder(self).build(
                    msg=msg,
                    user_content=context.content,
                    trigger_source=trigger_source,
                    include_quote=not context.get("wechat_group_skip_multimodal_quote", False),
                    reply_mode=reply_mode,
                    is_free_reply=context.get("wechat_group_is_free_reply") is True,
                    request_context=context,
                )
                for key, value in result.metadata.items():
                    context[key] = value
                context.content = result.content
                return context
            except Exception as e:
                logger.warning("[wechat_group] failed to build humanized context: {}".format(e))
        is_free_reply = context.get("wechat_group_is_free_reply") is True
        focus = {} if is_free_reply else self._resolve_focus_context(msg, context.content)
        if focus:
            context["wechat_group_focus"] = focus
        blocks = []
        room_scope = _wechat_group_stable_room_scope(msg)
        member_scope = _wechat_group_stable_member_scope(msg)
        identity_confirmed = getattr(msg, "wechat_group_identity_requires_confirmation", False) is not True
        admin_policy_block = build_wechat_group_admin_policy_block(
            room_scope,
            member_scope,
            identity_confirmed=identity_confirmed,
        )
        if admin_policy_block:
            context["wechat_group_is_admin"] = identity_confirmed and is_wechat_group_admin(room_scope, member_scope)
            blocks.append(admin_policy_block)
        if conf().get("wechat_group_reply_policy_enabled", True):
            blocks.append(build_wechat_group_mention_verification_block(msg, trigger_source))
            blocks.append(build_wechat_group_addressee_policy_block(msg, trigger_source))
            blocks.append(
                build_wechat_group_reply_policy_block(
                    trigger_source,
                    reply_mode=reply_mode,
                )
            )
        if should_skip_persona_for_message(msg):
            context["wechat_group_persona_skipped"] = True
        else:
            persona = get_wechat_group_persona_config()
            block = build_wechat_group_persona_block(persona["prompt"])
            if block:
                context["wechat_group_persona_preset_id"] = persona["preset_id"]
                blocks.append(block)
        if is_free_reply:
            getter = getattr(self.archive, "get_recent_conversation_messages", None)
            rows = getter(
                room_scope,
                limit=WECHAT_GROUP_FREE_REPLY_RECENT_LIMIT,
                minutes=WECHAT_GROUP_FREE_REPLY_RECENT_MINUTES,
                now=getattr(msg, "create_time", None),
            ) if callable(getter) else self.archive.get_recent_messages(
                room_scope,
                limit=WECHAT_GROUP_FREE_REPLY_RECENT_LIMIT,
                minutes=WECHAT_GROUP_FREE_REPLY_RECENT_MINUTES,
                now=getattr(msg, "create_time", None),
            )
            rows = [
                row for row in rows or []
                if str(row.get("message_id") or "") != str(getattr(msg, "msg_id", "") or "")
            ]
            recent_block = build_safe_wechat_group_recent_context_block_from_rows(rows)
        else:
            recent_block = self._build_recent_context_block(msg, focus=focus)
        if recent_block:
            blocks.append(recent_block)
            context["wechat_group_recent_context_injected"] = True
        focus_block = self._build_focus_context_block(focus)
        if focus_block:
            blocks.append(focus_block)
            context["wechat_group_focus_injected"] = True
        memory_block = self._build_memory_context_block(msg, context.content)
        if memory_block:
            blocks.append(memory_block)
            context["wechat_group_memory_injected"] = True
        style_block = self._build_style_context_block(msg)
        if style_block:
            blocks.append(style_block)
            context["wechat_group_style_injected"] = True
        emotion_block = self._build_emotion_context_block(msg)
        if emotion_block:
            blocks.append(emotion_block)
            context["wechat_group_emotion_injected"] = True
        trigger_source = (
            context.get("wechat_group_trigger_source")
            or kwargs.get("wechat_group_trigger_source")
            or self._infer_multimodal_trigger_source(msg)
        )
        context["wechat_group_trigger_source"] = trigger_source
        multimodal = self._build_multimodal_context(
            msg,
            query=context.content,
            trigger_source=trigger_source,
            include_quote=not context.get("wechat_group_skip_multimodal_quote", False),
        )
        multimodal_block = multimodal.get("block") or ""
        context["wechat_group_multimodal_diagnostics"] = multimodal.get("diagnostics") or {}
        matched_images = multimodal.get("matched_images") or []
        if matched_images:
            context["wechat_group_multimodal_matched_images"] = matched_images
        if multimodal_block:
            blocks.append(multimodal_block)
            context["wechat_group_multimodal_injected"] = True
        if blocks:
            context.content = "{}\n\n{}".format("\n\n".join(blocks), context.content).strip()
        return context

    def _decorate_reply(self, context, reply):
        if context.get("isgroup", False):
            context["no_need_at"] = True
        reply = super()._decorate_reply(context, reply)
        error_prefix = "[{}]\n".format(ReplyType.ERROR)
        if (
            reply
            and reply.type == ReplyType.ERROR
            and isinstance(reply.content, str)
            and reply.content.startswith(error_prefix)
        ):
            reply.content = reply.content[len(error_prefix):]
        return reply

    def send(self, reply, context):
        try:
            return self._send_with_confirmed_delivery(reply, context)
        finally:
            self._discard_pending_agent_delivery(
                context,
                reason="reply_not_confirmed",
            )

    def _send_with_confirmed_delivery(self, reply, context):
        receiver = context.get("receiver")
        if not receiver:
            logger.warning("[wechat_group] missing receiver, skip send")
            return
        if self._should_suppress_stale_ambient(context):
            return
        if reply.type in (ReplyType.TEXT, ReplyType.INFO, ReplyType.ERROR):
            if (
                reply.type == ReplyType.ERROR
                and _is_wechat_group_transient_model_error_text(reply.content)
            ):
                if context.get("wechat_group_force_reply", False):
                    reply = Reply(
                        ReplyType.TEXT,
                        WECHAT_GROUP_TRANSIENT_MODEL_ERROR_FALLBACK,
                    )
                else:
                    logger.info(
                        "[wechat_group] transient model error reply suppressed: {}".format(
                            _wechat_group_log_preview(reply.content)
                        )
                    )
                    return
            if reply.type == ReplyType.TEXT and conf().get("wechat_group_response_cleanup_enabled", True):
                cleaned = cleanup_wechat_group_reply_text(
                    reply.content,
                    max_chars=conf().get("wechat_group_response_cleanup_max_chars", 800),
                )
                if not cleaned:
                    logger.info("[wechat_group] cleaned reply is empty, skip send")
                    return
                reply.content = cleaned
            if _is_wechat_group_silent_reply_text(reply.content):
                logger.info("[wechat_group] silent reply notice suppressed")
                return
            self._simulate_typing_delay_if_needed(reply)
            mention_ids = self._build_reply_mentions(context)
            if not self._send_text_reply(receiver, reply.content, mention_ids):
                return
            archive_row_id = self._record_assistant_reply(context, reply, mention_ids)
            self._commit_pending_agent_delivery(
                context,
                archive_row_id=archive_row_id,
                assistant_text=reply.content,
            )
        elif reply.type in (ReplyType.IMAGE, ReplyType.IMAGE_URL):
            if not self._send_media_reply(
                "image",
                receiver,
                self._normalize_sidecar_media_path(reply.content),
            ):
                return
            archive_row_id = self._record_assistant_reply(context, reply, [])
            self._commit_pending_agent_delivery(context, archive_row_id=archive_row_id)
        elif reply.type == ReplyType.VOICE:
            if not self._send_media_reply(
                "audio",
                receiver,
                self._normalize_sidecar_media_path(reply.content),
            ):
                return
            archive_row_id = self._record_assistant_reply(context, reply, [])
            self._commit_pending_agent_delivery(context, archive_row_id=archive_row_id)
        elif reply.type in (ReplyType.FILE, ReplyType.VIDEO):
            if not self._send_media_reply(
                "file",
                receiver,
                self._normalize_sidecar_media_path(reply.content),
            ):
                return
            archive_row_id = self._record_assistant_reply(context, reply, [])
            self._commit_pending_agent_delivery(context, archive_row_id=archive_row_id)
        else:
            logger.warning("[wechat_group] unsupported reply type: {}".format(reply.type))
            return
        self._record_emotion_reply(context)
        self._record_sticker_reply(reply, context)

    def _send_text_reply(self, receiver: str, content: str, mention_ids) -> bool:
        if not wechat_group_context_engine_v2_enabled():
            self.client.send_text(receiver, content, mention_ids=mention_ids)
            return True
        confirmed = getattr(self.client, "send_text_confirmed", None)
        if not callable(confirmed):
            logger.error("[wechat_group] V2 requires confirmed text sending")
            return False
        status = confirmed(receiver, content, mention_ids=mention_ids)
        if status == "sent":
            return True
        logger.warning(
            "[wechat_group] text send was not confirmed: room=%s status=%s",
            receiver,
            status,
        )
        return False

    def _send_media_reply(self, media_type: str, receiver: str, path: str) -> bool:
        legacy_method = getattr(self.client, "send_{}".format(media_type))
        if not wechat_group_context_engine_v2_enabled():
            legacy_method(receiver, path)
            return True
        confirmed = getattr(
            self.client,
            "send_{}_confirmed".format(media_type),
            None,
        )
        if not callable(confirmed):
            logger.error(
                "[wechat_group] V2 requires confirmed %s sending",
                media_type,
            )
            return False
        status = confirmed(receiver, path)
        if status == "sent":
            return True
        logger.warning(
            "[wechat_group] %s send was not confirmed: room=%s status=%s",
            media_type,
            receiver,
            status,
        )
        return False

    def _should_suppress_stale_ambient(self, context) -> bool:
        if context.get("wechat_group_stale_suppressed") is True:
            return True
        if not wechat_group_context_engine_v2_enabled():
            return False
        if context.get("wechat_group_is_free_reply") is not True:
            return False
        before = context.get("wechat_group_room_revision_before")
        if not isinstance(before, dict):
            return False
        room_id = str(
            context.get("wechat_group_stable_room_id")
            or context.get("receiver")
            or ""
        )
        try:
            after = self.archive.get_room_revision(room_id)
        except Exception as e:
            logger.warning("[wechat_group] ambient revision check failed: {}".format(e))
            context["wechat_group_stale_suppressed"] = True
            return True
        if after == before:
            return False
        context["wechat_group_stale_suppressed"] = True
        logger.info(
            "[wechat_group] stale ambient reply suppressed: room=%s before=%s after=%s request=%s",
            room_id,
            before,
            after,
            context.get("request_id") or "",
        )
        return True

    def _record_inbound_message(self, msg: WechatGroupMessage):
        if not conf().get("wechat_group_record_messages", True):
            return 0
        try:
            quote_diagnostics = getattr(msg, "quote_diagnostics", {})
            if not isinstance(quote_diagnostics, dict):
                quote_diagnostics = {}
            archive_row_id = self.archive.record_message(
                message_id=msg.msg_id,
                room_id=msg.other_user_id,
                room_name=msg.other_user_nickname,
                sender_id=msg.actual_user_id,
                sender_nickname=msg.actual_user_nickname,
                message_type=msg.message_type,
                text=msg.text,
                media_path=msg.media_path,
                is_at=msg.is_at,
                metadata={
                    "at_list": getattr(msg, "at_list", []) or [],
                    "self_id": getattr(msg, "to_user_id", "") or "",
                    "quote": getattr(msg, "quote", {}) or {},
                    "forward": getattr(msg, "forward", {}) or {},
                    "raw_app_type": getattr(msg, "raw_app_type", "") or "",
                    "quote_diagnostics": quote_diagnostics,
                    "is_quote_self": bool(getattr(msg, "is_quote_self", False)),
                    "self_display_name": getattr(msg, "self_display_name", "") or "",
                    "runtime_media_path": getattr(msg, "media_path", "") or "",
                    "stable_media_path": "",
                    "media_path_storage": "runtime_legacy",
                },
                created_at=msg.create_time,
                stable_room_id=getattr(msg, "wechat_group_stable_room_id", "") or "",
                runtime_room_id=getattr(msg, "runtime_room_id", msg.other_user_id) or "",
                stable_member_id=getattr(msg, "wechat_group_stable_member_id", "") or "",
                runtime_sender_id=getattr(msg, "runtime_sender_id", msg.actual_user_id) or "",
            )
            try:
                row = self.archive.get_message_by_id(
                    getattr(msg, "wechat_group_stable_room_id", "") or msg.other_user_id,
                    msg.msg_id,
                )
                archive_row_id = int(archive_row_id or (row or {}).get("id") or 0)
                from channel.wechat_group.wechat_group_profile_evolution_trigger import note_wechat_group_profile_signal
                note_wechat_group_profile_signal(
                    getattr(msg, "wechat_group_stable_room_id", "") or msg.other_user_id,
                    archive_row_id=archive_row_id,
                )
            except Exception as signal_error:
                logger.debug("[wechat_group] failed to notify profile evolution signal: {}".format(signal_error))
            stable_room_id = str(getattr(msg, "wechat_group_stable_room_id", "") or "").strip()
            if stable_room_id and conf().get("wechat_group_learning_enabled", False):
                try:
                    from channel.wechat_group.wechat_group_memory_dream_trigger import (
                        note_wechat_group_memory_signal,
                    )

                    note_wechat_group_memory_signal(
                        stable_room_id,
                        archive_row_id=int(archive_row_id or 0),
                    )
                except Exception as signal_error:
                    logger.debug("[wechat_group] failed to notify memory Dream signal: {}".format(signal_error))
            self._collect_sticker_from_message(msg)
            return int(archive_row_id or 0)
        except Exception as e:
            logger.warning("[wechat_group] failed to archive inbound message: {}".format(e))
            return 0

    def _record_assistant_reply(self, context, reply, mention_ids):
        if not conf().get("wechat_group_record_messages", True):
            return 0
        msg = context.get("msg")
        try:
            archive_row_id = self.archive.record_assistant_reply(
                room_id=context.get("wechat_group_stable_room_id") or context.get("receiver") or "",
                room_name=getattr(msg, "other_user_nickname", "") if msg else "",
                reply_type=str(reply.type),
                content=reply.content,
                mention_ids=mention_ids,
                stable_room_id=context.get("wechat_group_stable_room_id") or "",
                runtime_room_id=context.get("wechat_group_runtime_room_id") or context.get("receiver") or "",
                thread_id=context.get("wechat_group_thread_id") or "",
                request_id=context.get("request_id") or "",
            )
            if archive_row_id:
                self._schedule_rolling_summary(
                    context.get("wechat_group_stable_room_id") or ""
                )
            return int(archive_row_id or 0)
        except Exception as e:
            logger.warning("[wechat_group] failed to archive assistant reply: {}".format(e))
            return 0

    def _commit_pending_agent_delivery(
        self,
        context,
        archive_row_id: int = 0,
        assistant_text=None,
    ) -> bool:
        pending = context.get("wechat_group_pending_agent_delivery") if context else None
        if not isinstance(pending, dict) or pending.get("state") != "pending":
            return False
        session_id = str(pending.get("owner_session_id") or "")
        thread_id = str(pending.get("thread_id") or "")
        request_id = str(pending.get("request_id") or "")
        if not session_id or not thread_id or not request_id:
            return False
        try:
            from agent.memory import get_conversation_store

            source_event_id = (
                "assistant:{}".format(int(archive_row_id))
                if archive_row_id
                else ""
            )
            updated = get_conversation_store().confirm_thread_turn_delivery(
                session_id,
                thread_id,
                request_id,
                assistant_source_event_id=source_event_id,
                assistant_text=(
                    str(assistant_text) if assistant_text is not None else None
                ),
                thread_action=str(pending.get("action") or ""),
                channel_type=const.WECHAT_GROUP,
                stable_room_id=str(pending.get("stable_room_id") or ""),
                stable_member_id=str(pending.get("stable_member_id") or ""),
                message_id=str(pending.get("message_id") or ""),
                ttl_seconds=int(pending.get("ttl_seconds") or 900),
                metadata={
                    "reason": str(pending.get("reason") or ""),
                    "requested_action": str(pending.get("action") or ""),
                },
            )
            if updated <= 0:
                logger.warning(
                    "[wechat_group] confirmed send had no pending thread turn: "
                    "session=%s thread=%s request=%s",
                    session_id,
                    thread_id,
                    request_id,
                )
                return False
            pending["state"] = "committed"
            self._save_confirmed_continuation(pending)
            self._sync_cached_agent_thread(session_id, thread_id)
            return True
        except Exception as e:
            logger.warning(
                "[wechat_group] failed to commit confirmed agent delivery: "
                "session=%s thread=%s request=%s error=%s",
                session_id,
                thread_id,
                request_id,
                e,
            )
            return False

    @staticmethod
    def _save_confirmed_continuation(pending) -> bool:
        capsule = pending.get("continuation_capsule")
        if not isinstance(capsule, dict):
            return False
        try:
            from channel.wechat_group.wechat_group_continuation_store import (
                WechatGroupContinuationStore,
            )

            return WechatGroupContinuationStore().save_capsule(
                str(pending.get("owner_session_id") or ""),
                str(pending.get("thread_id") or ""),
                capsule,
                stable_room_id=str(pending.get("stable_room_id") or ""),
                stable_member_id=str(pending.get("stable_member_id") or ""),
                request_id=str(pending.get("request_id") or ""),
                ttl_seconds=int(
                    pending.get("continuation_ttl_seconds") or 600
                ),
            )
        except Exception as e:
            logger.warning(
                "[wechat_group] failed to save confirmed continuation: %s",
                e,
            )
            return False

    def _discard_pending_agent_delivery(self, context, reason: str = "") -> int:
        pending = context.get("wechat_group_pending_agent_delivery") if context else None
        if not isinstance(pending, dict) or pending.get("state") != "pending":
            return 0
        session_id = str(pending.get("owner_session_id") or "")
        thread_id = str(pending.get("thread_id") or "")
        request_id = str(pending.get("request_id") or "")
        if not session_id or not thread_id or not request_id:
            return 0
        try:
            from agent.memory import get_conversation_store

            removed = get_conversation_store().discard_pending_thread_turn(
                session_id,
                thread_id,
                request_id,
            )
            pending["state"] = "discarded"
            pending["discard_reason"] = str(reason or "")
            self._sync_cached_agent_thread(session_id, thread_id)
            logger.info(
                "[wechat_group] pending agent delivery discarded: "
                "session=%s thread=%s request=%s rows=%s reason=%s",
                session_id,
                thread_id,
                request_id,
                removed,
                reason or "unspecified",
            )
            return int(removed or 0)
        except Exception as e:
            logger.warning(
                "[wechat_group] failed to discard pending agent delivery: "
                "session=%s thread=%s request=%s error=%s",
                session_id,
                thread_id,
                request_id,
                e,
            )
            return 0

    @staticmethod
    def _sync_cached_agent_thread(session_id: str, thread_id: str) -> int:
        try:
            agent_bridge = getattr(Bridge(), "_agent_bridge", None)
            if agent_bridge is None:
                return -1
            return agent_bridge.sync_thread_messages_from_store(
                session_id,
                thread_id,
            )
        except Exception as e:
            logger.warning(
                "[wechat_group] failed to sync delivered Agent thread cache: %s",
                e,
            )
            return -1

    def _schedule_rolling_summary(self, stable_room_id: str) -> None:
        if not wechat_group_context_engine_v2_enabled():
            return
        if not conf().get("wechat_group_rolling_summary_enabled", False):
            return
        scope = str(stable_room_id or "").strip()
        if not scope:
            return
        try:
            service = self._wechat_group_rolling_summary_service
            if service is None:
                service = WechatGroupRollingSummaryService(self.archive)
                self._wechat_group_rolling_summary_service = service
            service.schedule(scope)
        except Exception as exc:
            logger.warning(
                "[wechat_group_summary] schedule failed: room=%s error=%s",
                scope,
                exc,
            )

    def _build_recent_context_block(self, msg: WechatGroupMessage, focus=None) -> str:
        if not conf().get("wechat_group_recent_context_enabled", True):
            return ""
        try:
            if focus and isinstance(focus, dict) and focus.get("messages"):
                return build_wechat_group_recent_context_block_from_rows(focus.get("messages") or [])
            return build_wechat_group_recent_context_block(
                self.archive,
                _wechat_group_stable_room_scope(msg),
                limit=conf().get("wechat_group_recent_context_limit", 20),
                minutes=conf().get("wechat_group_recent_context_minutes", 60),
                now=msg.create_time,
            )
        except Exception as e:
            logger.warning("[wechat_group] failed to build recent context: {}".format(e))
            return ""

    def _resolve_focus_context(self, msg: WechatGroupMessage, query: str) -> dict:
        if not conf().get("wechat_group_focus_enabled", True):
            return {}
        try:
            return self._get_focus_service().resolve_reply_focus(
                self.archive,
                msg,
                query=query,
                now=msg.create_time,
            )
        except Exception as e:
            logger.warning("[wechat_group] failed to resolve focus context: {}".format(e))
            return {}

    def _build_focus_context_block(self, focus: dict) -> str:
        if not focus:
            return ""
        try:
            return self._get_focus_service().build_prompt_block(focus)
        except Exception as e:
            logger.warning("[wechat_group] failed to build focus context: {}".format(e))
            return ""

    def _build_memory_context_block(self, msg: WechatGroupMessage, query: str) -> str:
        knowledge_enabled = bool(conf().get(
            "wechat_group_knowledge_enabled",
            conf().get("wechat_group_memory_enabled", True),
        ))
        profile_enabled = bool(conf().get(
            "wechat_group_profile_enabled",
            conf().get("wechat_group_member_memory_enabled", True),
        ))
        if not knowledge_enabled and not profile_enabled:
            return ""
        try:
            service = self._get_memory_service()
            preview = service.preview_context(
                room_id=_wechat_group_stable_room_scope(msg),
                sender_id=_wechat_group_stable_member_scope(msg),
                query=query,
                mentioned_sender_ids=getattr(msg, "at_list", []) or [],
                bot_sender_id=msg.to_user_id,
            )
            content = (preview or {}).get("content")
            return content if isinstance(content, str) else ""
        except Exception as e:
            logger.warning("[wechat_group] failed to build memory context: {}".format(e))
            return ""

    def _build_emotion_context_block(self, msg: WechatGroupMessage) -> str:
        if not conf().get("wechat_group_emotion_enabled", True):
            return ""
        try:
            return self._get_emotion_service().build_prompt_block(_wechat_group_stable_room_scope(msg), now=msg.create_time)
        except Exception as e:
            logger.warning("[wechat_group] failed to build emotion context: {}".format(e))
            return ""

    def _build_style_context_block(self, msg: WechatGroupMessage) -> str:
        if not conf().get("wechat_group_style_enabled", True):
            return ""
        try:
            return self._get_style_service().build_prompt_block_from_archive(
                self.archive,
                _wechat_group_stable_room_scope(msg),
                now=msg.create_time,
            )
        except Exception as e:
            logger.warning("[wechat_group] failed to build style context: {}".format(e))
            return ""

    @staticmethod
    def _infer_multimodal_trigger_source(msg: WechatGroupMessage) -> str:
        if str(getattr(msg, "message_type", "") or "").lower() == "image" or getattr(msg, "ctype", None) == ContextType.IMAGE:
            return "image_message"
        if getattr(msg, "is_quote_self", False) is True:
            return "quote_self"
        if getattr(msg, "is_at", False) is True:
            return "direct_reply"
        return ""

    def _build_multimodal_context(self, msg: WechatGroupMessage, query: str, trigger_source: str = "", include_quote: bool = True) -> dict:
        try:
            return self._get_multimodal_context_service().build_context(
                msg,
                query=query,
                trigger_source=trigger_source,
                now=getattr(msg, "create_time", None),
                include_quote=include_quote,
            )
        except Exception as e:
            logger.warning("[wechat_group] failed to build multimodal context: {}".format(e))
            return {
                "block": "",
                "matched_images": [],
                "diagnostics": {
                    "enabled": False,
                    "skipped_reason": "exception",
                    "error": str(e),
                },
            }

    def _get_memory_service(self):
        if self.memory_service is None:
            self.memory_service = WechatGroupContextService(
                profile_service=self._get_profile_service(),
            )
            try:
                from agent.memory.manager import MemoryManager
                from agent.memory import create_default_embedding_provider
                from bridge.bridge import Bridge

                text_model = None
                try:
                    text_model = Bridge().get_text_model_router()
                except Exception as e:
                    logger.warning(
                        "[wechat_group] shared text router unavailable for memory summaries: {}".format(e)
                    )
                self.memory_service.memory_manager = MemoryManager(
                    embedding_provider=create_default_embedding_provider(),
                    llm_model=text_model,
                )
            except Exception:
                self.memory_service.memory_manager = None
        return self.memory_service

    def _get_focus_service(self):
        if self.focus_service is None:
            self.focus_service = WechatGroupFocusService()
        return self.focus_service

    def _get_emotion_service(self):
        if self.emotion_service is None:
            self.emotion_service = WechatGroupEmotionService()
        return self.emotion_service

    def _get_style_service(self):
        if self.style_service is None:
            self.style_service = WechatGroupStyleService()
        return self.style_service

    def _get_sticker_service(self):
        if self.sticker_service is None:
            self.sticker_service = WechatGroupStickerService()
        return self.sticker_service

    def _get_multimodal_context_service(self):
        if self.multimodal_context_service is None:
            self.multimodal_context_service = WechatGroupMultimodalContextService(self.archive)
        return self.multimodal_context_service

    def _observe_emotion(self, msg: WechatGroupMessage):
        if not conf().get("wechat_group_emotion_enabled", True):
            return
        text = getattr(msg, "text", None) or getattr(msg, "content", "")
        if not str(text or "").strip():
            return
        try:
            self._get_emotion_service().observe_message(
                room_id=_wechat_group_stable_room_scope(msg),
                text=text,
                is_at=bool(getattr(msg, "is_at", False)),
                now=getattr(msg, "create_time", None),
            )
        except Exception as e:
            logger.warning("[wechat_group] failed to observe emotion: {}".format(e))

    def _record_emotion_reply(self, context):
        if not conf().get("wechat_group_emotion_enabled", True):
            return
        room_id = context.get("wechat_group_stable_room_id") or context.get("wechat_group_stable_receiver") or context.get("receiver") or context.get("wechat_group_room_id") or ""
        if not room_id:
            return
        msg = context.get("msg")
        try:
            self._get_emotion_service().mark_replied(
                room_id=room_id,
                now=getattr(msg, "create_time", None) if msg else None,
            )
        except Exception as e:
            logger.warning("[wechat_group] failed to record emotion reply: {}".format(e))

    def _collect_sticker_from_message(self, msg: WechatGroupMessage):
        if not conf().get("wechat_group_sticker_enabled", True):
            return
        if not conf().get("wechat_group_sticker_auto_collect_enabled", True):
            return
        if str(getattr(msg, "message_type", "") or "").lower() != "sticker":
            return
        media_path = str(getattr(msg, "media_path", "") or "").strip()
        if not media_path:
            return
        try:
            description = Path(media_path).stem
            self._get_sticker_service().collect_from_message(
                room_id=_wechat_group_stable_room_scope(msg),
                media_path=media_path,
                source_message_id=getattr(msg, "msg_id", ""),
                description=description,
                now=getattr(msg, "create_time", None),
            )
        except Exception as e:
            logger.warning("[wechat_group] failed to collect sticker: {}".format(e))

    def _record_sticker_reply(self, reply, context):
        if not conf().get("wechat_group_sticker_enabled", True):
            return
        sticker_id = str(getattr(reply, "wechat_group_sticker_id", "") or "").strip()
        room_id = str(context.get("wechat_group_stable_room_id") or context.get("wechat_group_stable_receiver") or context.get("receiver") or context.get("wechat_group_room_id") or "").strip()
        if not sticker_id or not room_id:
            return
        try:
            self._get_sticker_service().record_sent(room_id, sticker_id)
        except Exception as e:
            logger.warning("[wechat_group] failed to record sticker reply: {}".format(e))

    @staticmethod
    def _normalize_sidecar_media_path(value):
        text = str(value or "").strip()
        if text.startswith("file://"):
            return text[7:]
        return text

    def _resolve_message_identity(self, msg):
        if not msg or not getattr(msg, "is_group", False):
            return {}
        existing_room = _wechat_group_log_value(getattr(msg, "wechat_group_stable_room_id", "")) or _wechat_group_log_value(getattr(msg, "stable_room_id", ""))
        existing_member = _wechat_group_log_value(getattr(msg, "wechat_group_stable_member_id", "")) or _wechat_group_log_value(getattr(msg, "stable_member_id", ""))
        existing_account = _wechat_group_log_value(getattr(msg, "wechat_group_stable_account_id", "")) or _wechat_group_log_value(getattr(msg, "stable_account_id", ""))
        if existing_room and existing_member:
            room_status = getattr(msg, "wechat_group_room_identity_status", "confirmed")
            return {
                "wechat_group_stable_account_id": existing_account,
                "wechat_group_stable_room_id": existing_room,
                "wechat_group_stable_member_id": existing_member,
                "wechat_group_stable_receiver": existing_room,
                "wechat_group_identity_status": getattr(msg, "wechat_group_identity_status", "confirmed"),
                "wechat_group_identity_requires_confirmation": getattr(
                    msg,
                    "wechat_group_identity_requires_confirmation",
                    False,
                ),
                "wechat_group_room_identity_status": room_status,
                "wechat_group_room_identity_requires_confirmation": getattr(
                    msg,
                    "wechat_group_room_identity_requires_confirmation",
                    False,
                ),
            }
        metadata = getattr(msg, "identity_fingerprint_metadata", {}) or {}
        has_fingerprint = any(bool(value) for value in metadata.values()) if isinstance(metadata, dict) else False
        if not has_fingerprint and not conf().get("wechat_group_stable_room_ids", []):
            return {}
        try:
            service = self.identity_service or WechatGroupIdentityService()
            self.identity_service = service
            account = service.resolve_account(
                getattr(msg, "runtime_self_id", getattr(msg, "to_user_id", "")),
                getattr(msg, "to_user_nickname", ""),
                get_wechat_group_sidecar_memory_path(),
                getattr(msg, "account_fingerprint", {}) or {},
            )
            runtime_room_id = getattr(msg, "runtime_room_id", getattr(msg, "other_user_id", ""))
            room_name = getattr(msg, "other_user_nickname", "")
            room = self._resolve_room_with_session_name_recovery(
                service,
                account.stable_id,
                runtime_room_id,
                room_name,
                getattr(msg, "runtime_self_id", getattr(msg, "to_user_id", "")),
                getattr(msg, "room_fingerprint", {}) or {},
            )
            member = service.resolve_member(
                room.stable_id,
                getattr(msg, "runtime_sender_id", getattr(msg, "actual_user_id", "")),
                getattr(msg, "actual_user_nickname", ""),
                getattr(msg, "sender_room_alias", ""),
                getattr(msg, "member_fingerprint", {}) or {},
            )
            identity = {
                "wechat_group_stable_account_id": account.stable_id,
                "wechat_group_stable_room_id": room.stable_id,
                "wechat_group_stable_member_id": member.stable_id,
                "wechat_group_stable_receiver": room.stable_id,
                "wechat_group_identity_status": member.status,
                "wechat_group_identity_requires_confirmation": bool(
                    account.requires_confirmation or room.requires_confirmation or member.requires_confirmation
                ),
                "wechat_group_room_identity_status": room.status,
                "wechat_group_room_identity_requires_confirmation": bool(room.requires_confirmation),
            }
            msg.wechat_group_stable_account_id = account.stable_id
            msg.wechat_group_stable_room_id = room.stable_id
            msg.wechat_group_stable_member_id = member.stable_id
            msg.wechat_group_identity_status = identity["wechat_group_identity_status"]
            msg.wechat_group_identity_requires_confirmation = identity["wechat_group_identity_requires_confirmation"]
            msg.wechat_group_room_identity_status = room.status
            msg.wechat_group_room_identity_requires_confirmation = bool(room.requires_confirmation)
            return identity
        except Exception as e:
            logger.warning("[wechat_group] failed to resolve stable identity: {}".format(e))
            return {}

    @staticmethod
    def _is_selected_room(msg: WechatGroupMessage) -> bool:
        if getattr(msg, "wechat_group_room_identity_requires_confirmation", False) is True:
            return False
        stable_room_ids = conf().get("wechat_group_stable_room_ids", [])
        stable_room_id = getattr(msg, "wechat_group_stable_room_id", "") or getattr(msg, "stable_room_id", "")
        if stable_room_ids:
            return bool(stable_room_id and stable_room_id in stable_room_ids)
        room_ids = conf().get("wechat_group_room_ids", [])
        if room_ids:
            return msg.other_user_id in room_ids
        room_names = conf().get("wechat_group_names", [])
        if room_names:
            current_name = str(getattr(msg, "other_user_nickname", "") or "").strip()
            selected_names = {str(name or "").strip() for name in room_names if str(name or "").strip()}
            return bool(current_name and current_name in selected_names)
        return True

    def _enrich_room_members_with_stable_identity(self, members, runtime_room_id: str):
        service = self.identity_service
        if service is None:
            return list(members or [])
        stable_room_id = self._stable_room_id_for_runtime_room(runtime_room_id)
        if not stable_room_id:
            return list(members or [])
        result = []
        for member in members or []:
            item = dict(member)
            runtime_sender_id = str(item.get("sender_id") or "").strip()
            if not runtime_sender_id:
                result.append(item)
                continue
            nickname = str(item.get("sender_nickname") or "").strip()
            room_alias = str(item.get("room_alias") or "").strip()
            display_name = room_alias or nickname
            if self._looks_like_raw_member_name(display_name, runtime_sender_id):
                display_name = ""
            try:
                resolution = service.resolve_member(
                    stable_room_id,
                    runtime_sender_id,
                    display_name,
                    room_alias,
                    {"wechat_id": str(item.get("wechat_id") or "").strip()},
                )
                item["stable_member_id"] = resolution.stable_id
                item["runtime_sender_id"] = runtime_sender_id
                item["identity_status"] = resolution.status
                item["identity_confidence"] = resolution.confidence
                item["identity_requires_confirmation"] = bool(resolution.requires_confirmation)
                resolved_name = str(resolution.display_name or "").strip()
                visible_name = room_alias or nickname or resolved_name
                if self._looks_like_raw_member_name(visible_name, runtime_sender_id):
                    visible_name = ""
                item["display_name"] = visible_name
            except Exception as e:
                item["stable_member_id"] = ""
                item["runtime_sender_id"] = runtime_sender_id
                item["identity_status"] = "identity_unresolved"
                item["identity_requires_confirmation"] = True
                logger.warning(
                    "[wechat_group] failed to resolve room member identity: room={} sender={} error={}".format(
                        runtime_room_id,
                        runtime_sender_id,
                        e,
                    )
                )
            result.append(item)
        return result

    @staticmethod
    def _build_reply_mentions(context):
        if context.get("suppress_mention"):
            return []
        if context.get("wechat_group_trigger_source") == "pat_self":
            return []
        msg = context.get("msg")
        if not msg or not getattr(msg, "is_group", False):
            return []
        if getattr(msg, "is_pat_self", False) is True:
            return []
        actual_user_id = getattr(msg, "actual_user_id", None)
        return [actual_user_id] if actual_user_id else []

    @staticmethod
    def _simulate_typing_delay_if_needed(reply):
        if not conf().get("wechat_group_free_reply_typing_delay_enabled", True):
            return
        content = str(getattr(reply, "content", "") or "")
        if not content:
            return
        try:
            chars_per_second = max(int(conf().get("wechat_group_free_reply_typing_chars_per_second", 7) or 7), 1)
        except Exception:
            chars_per_second = 7
        delay_seconds = min(len(content) / float(chars_per_second), 8.0)
        if delay_seconds > 0:
            time.sleep(delay_seconds)

    def _create_free_reply_worker(self):
        cfg = get_wechat_group_free_reply_config()
        return WechatGroupFreeReplyWorkerPool(
            judge=self.free_reply_judge,
            submit_callback=self._submit_free_reply_after_judge,
            max_workers=cfg["worker_max_workers"],
            queue_size=cfg["worker_queue_size"],
            ttl_seconds=cfg["queue_ttl_seconds"],
            debounce_seconds=WECHAT_GROUP_FREE_REPLY_DEBOUNCE_SECONDS,
        )

    def _ensure_free_reply_worker_started(self):
        if self._free_reply_worker_started:
            return
        self.free_reply_worker.start()
        self._free_reply_worker_started = True

    @staticmethod
    def _build_free_reply_image_text(msg: WechatGroupMessage) -> str:
        # Keep local media paths out of free-reply scoring, logs, and LLM judge prompts.
        return "[image]"

    @staticmethod
    def _build_image_reply_content() -> str:
        # Wechaty message.text() is transport XML for image/sticker messages.
        return WECHAT_GROUP_DEFAULT_IMAGE_REPLY_QUESTION

    def _should_enqueue_free_reply_message(
        self,
        msg: WechatGroupMessage,
        allow_media_payload=False,
        text_override=None,
        message_type_override=None,
    ):
        recent_messages = []
        cfg = get_wechat_group_free_reply_config()
        text = text_override if text_override is not None else (getattr(msg, "text", None) or msg.content)
        room_scope = _wechat_group_stable_room_scope(msg)
        member_scope = _wechat_group_stable_member_scope(msg)
        if not self._is_selected_room(msg):
            decision = {
                "triggered": False,
                "score": 0,
                "threshold": 0,
                "activity_level": cfg["activity_level"],
                "reasons": [],
                "suppressions": ["room_not_selected"],
                "room_id": room_scope or getattr(msg, "other_user_id", ""),
                "room_name": getattr(msg, "other_user_nickname", ""),
                "sender_id": member_scope or getattr(msg, "actual_user_id", ""),
                "sender_name": getattr(msg, "actual_user_nickname", ""),
                "text_preview": text,
                "timestamp": time.time(),
            }
        else:
            state = self.free_reply_state.get(room_scope or msg.other_user_id)
            try:
                recent_messages = self.archive.get_recent_messages(
                    room_scope or msg.other_user_id,
                    limit=18,
                    minutes=120,
                    now=getattr(msg, "create_time", None),
                )
                conversation_getter = getattr(
                    self.archive,
                    "get_recent_conversation_messages",
                    None,
                )
                if callable(conversation_getter):
                    merged = conversation_getter(
                        room_scope or msg.other_user_id,
                        limit=max(18, int(cfg.get("scorer_context_limit", 12) or 12)),
                        minutes=120,
                        now=getattr(msg, "create_time", None),
                    )
                    if isinstance(merged, list):
                        recent_messages = merged
            except Exception as e:
                logger.debug("[wechat_group] failed to load free reply recent messages: {}".format(e))
            runtime_sender_id = _wechat_group_log_value(getattr(msg, "actual_user_id", "")).strip()
            blocked_sender_ids = build_wechat_group_blocked_sender_ids(
                room_scope or msg.other_user_id,
                member_scope or msg.actual_user_id,
                runtime_sender_id=runtime_sender_id,
            )
            message_now = getattr(msg, "create_time", None)
            try:
                message_now = float(message_now)
            except (TypeError, ValueError):
                message_now = time.time()
            decision = evaluate_wechat_group_free_reply(
                cfg,
                room_id=room_scope or msg.other_user_id,
                room_name=msg.other_user_nickname,
                sender_id=member_scope or msg.actual_user_id,
                sender_name=msg.actual_user_nickname,
                text=text,
                recent_messages=recent_messages,
                state=state,
                now=message_now,
                is_self=getattr(msg, "my_msg", False) is True,
                blocked_sender_ids=blocked_sender_ids,
                bot_names=[getattr(msg, "self_display_name", ""), getattr(msg, "to_user_nickname", ""), self.name],
                message_type=(
                    message_type_override
                    if message_type_override is not None
                    else getattr(msg, "message_type", None)
                ),
                allow_media_payload=allow_media_payload,
                current_message_id=getattr(msg, "msg_id", ""),
                is_at=getattr(msg, "is_at", False) is True,
                is_quote_self=getattr(msg, "is_quote_self", False) is True,
            )
            rule_enabled = cfg.get("rule_enabled") if isinstance(cfg.get("rule_enabled"), dict) else {}
            image_context_suppression_enabled = rule_enabled.get("image_context_unavailable", True)
            if (
                decision.get("triggered")
                and not allow_media_payload
                and image_context_suppression_enabled
                and self._free_reply_image_context_unavailable(text, recent_messages)
            ):
                decision["triggered"] = False
                suppressions = list(decision.get("suppressions") or [])
                if "image_context_unavailable" not in suppressions:
                    suppressions.append("image_context_unavailable")
                decision["suppressions"] = suppressions
            if conf().get("wechat_group_emotion_enabled", True):
                try:
                    decision = self._get_emotion_service().adjust_free_reply_decision(
                        decision,
                        room_id=room_scope or msg.other_user_id,
                        now=getattr(msg, "create_time", None) or time.time(),
                    )
                except Exception as e:
                    logger.warning("[wechat_group] failed to adjust free reply by emotion: {}".format(e))
        suppressions = list(decision.get("suppressions") or [])
        if (
            cfg.get("scorer_enabled")
                and "low_information" in suppressions
                and is_contextual_short_question(text)
                and self._is_immediate_recent_bot_followup(
                recent_messages,
                current_message_id=getattr(msg, "msg_id", ""),
                now=getattr(msg, "create_time", None) or time.time(),
            )
        ):
            decision["suppressions"] = [
                item for item in suppressions if item != "low_information"
            ]
            decision["triggered"] = not decision["suppressions"]
            decision["contextual_short_question"] = True
        decision["local_rule_triggered"] = bool(decision.get("triggered"))
        hard_suppressions = set(decision.get("suppressions") or []) - {"below_threshold"}
        if cfg.get("scorer_enabled") and not hard_suppressions:
            decision["triggered"] = True
        self.free_reply_state.remember_decision(decision)
        if not decision.get("triggered"):
            self._log_free_reply_decision(decision, "skipped")
            self.free_reply_state.mark_observed(room_scope or getattr(msg, "other_user_id", ""))
            return False, decision, recent_messages
        return True, decision, recent_messages

    @staticmethod
    def _is_immediate_recent_bot_followup(
        recent_messages,
        current_message_id="",
        now=None,
        max_age_seconds=WECHAT_GROUP_SHORT_QUESTION_BOT_FOLLOWUP_SECONDS,
    ) -> bool:
        current_id = str(current_message_id or "")
        current_time = float(now or time.time())
        for item in reversed(list(recent_messages or [])):
            if not isinstance(item, dict):
                continue
            if current_id and str(item.get("message_id") or "") == current_id:
                continue
            if not str(item.get("text") or "").strip():
                continue
            try:
                created_at = float(item.get("created_at") or item.get("timestamp") or 0)
            except (TypeError, ValueError):
                return False
            if created_at <= 0 or created_at > current_time + 1:
                continue
            age = current_time - created_at
            return bool(
                item.get("is_bot") is True
                and 0 <= age <= max(float(max_age_seconds or 0), 0)
            )
        return False

    @staticmethod
    def _free_reply_image_context_unavailable(text, recent_messages) -> bool:
        if conf().get("wechat_group_multimodal_context_enabled", True) and conf().get(
            "wechat_group_multimodal_image_understanding_context_enabled",
            True,
        ) and conf().get("wechat_group_multimodal_free_reply_image_context_enabled", False):
            return False
        if not _looks_like_image_reference_question(text):
            return False
        return any(_is_archived_image_message(item) for item in (recent_messages or []))

    def _build_free_reply_task(
        self,
        msg: WechatGroupMessage,
        decision: dict,
        text=None,
        recent_messages=None,
    ) -> dict:
        task_text = text if text is not None else (getattr(msg, "text", None) or msg.content)
        group_size, group_size_source = self._free_reply_group_size(msg.other_user_id)
        task = {
            "room_id": _wechat_group_stable_room_scope(msg) or msg.other_user_id,
            "runtime_room_id": msg.other_user_id,
            "room_name": msg.other_user_nickname,
            "sender_id": _wechat_group_stable_member_scope(msg) or msg.actual_user_id,
            "runtime_sender_id": msg.actual_user_id,
            "sender_name": msg.actual_user_nickname,
            "text": task_text,
            "msg": msg,
            "local_decision": decision,
            "recent_messages": list(recent_messages or []),
            "group_size": group_size,
            "group_size_source": group_size_source,
            "queued_at": time.time(),
            "config": get_wechat_group_free_reply_config(),
        }
        if "unanswered_question" in (decision.get("reasons") or []):
            task["pre_judge_validator"] = self._free_reply_candidate_still_unanswered
        return task

    def _free_reply_candidate_still_unanswered(self, task) -> bool:
        msg = (task or {}).get("msg")
        if msg is None:
            return False
        room_id = (task or {}).get("room_id") or _wechat_group_stable_room_scope(msg)
        candidate_id = str(getattr(msg, "msg_id", "") or "")
        try:
            candidate_ts = float(getattr(msg, "create_time", 0) or 0)
        except (TypeError, ValueError):
            return False
        getter = getattr(self.archive, "get_recent_conversation_messages", None)
        if not room_id or not callable(getter) or candidate_ts <= 0:
            return False
        try:
            rows = getter(
                room_id,
                limit=12,
                minutes=5,
                now=time.time(),
            )
        except Exception:
            return False
        if not isinstance(rows, list):
            return False
        seen_candidate = False
        for item in rows or []:
            if candidate_id and str(item.get("message_id") or "") == candidate_id:
                seen_candidate = True
                continue
            try:
                created_at = float(item.get("created_at") or 0)
            except (TypeError, ValueError):
                continue
            if seen_candidate or created_at > candidate_ts:
                return False
        return True

    def _submit_free_reply_after_judge(self, task, llm_decision):
        msg = task["msg"]
        room_id = task.get("room_id") or _wechat_group_stable_room_scope(msg) or msg.other_user_id
        if self.free_reply_state.is_muted(room_id) is True:
            decision = dict(task.get("local_decision") or {})
            decision["triggered"] = False
            suppressions = list(decision.get("suppressions") or [])
            if FREE_REPLY_MUTE_SUPPRESSION not in suppressions:
                suppressions.append(FREE_REPLY_MUTE_SUPPRESSION)
            decision["suppressions"] = suppressions
            decision["timestamp"] = time.time()
            self.free_reply_state.remember_decision(decision)
            self._log_free_reply_decision(decision, "muted")
            return
        voice_transcription = task.get("voice_transcription")
        context_type = ContextType.TEXT if voice_transcription is not None else msg.ctype
        content = voice_transcription if voice_transcription is not None else msg.content
        image_understanding_triggered = False
        if msg.ctype == ContextType.IMAGE:
            if not conf().get("wechat_group_free_reply_image_understanding_enabled", False):
                return
            content = self._build_image_reply_content()
            context_type = ContextType.TEXT
            image_understanding_triggered = True
        trigger_source = "image_message" if msg.ctype == ContextType.IMAGE else "free_reply"
        reply_mode = str((llm_decision or {}).get("reply_mode") or "")
        history_mode = select_wechat_group_agent_history_mode(
            trigger_source,
            content,
            is_free_reply=True,
            local_decision=task.get("local_decision") or {},
            llm_decision=llm_decision or {},
        )
        context_kwargs = {
            "isgroup": True,
            "msg": msg,
            "wechat_group_force_reply": True,
            "wechat_group_is_free_reply": True,
            "wechat_group_trigger_source": trigger_source,
            "wechat_group_free_reply_mode": reply_mode,
            "wechat_group_agent_history_mode": history_mode,
            "wechat_group_free_reply_decision": task.get("local_decision") or {},
            "wechat_group_free_reply_llm_decision": llm_decision or {},
        }
        if voice_transcription is not None:
            context_kwargs["origin_ctype"] = ContextType.VOICE
            context_kwargs["wechat_group_voice_interaction"] = True
            if task.get("desire_rtype") is not None:
                context_kwargs["desire_rtype"] = task.get("desire_rtype")
        context = self._compose_context(context_type, content, **context_kwargs)
        if not context:
            return
        context["wechat_group_free_reply_triggered"] = True
        context["wechat_group_free_reply_mode"] = reply_mode
        history_mode = str(
            context.get("wechat_group_agent_history_mode") or history_mode
        )
        context["wechat_group_agent_history_mode"] = history_mode
        context["wechat_group_free_reply_decision"] = task.get("local_decision") or {}
        context["wechat_group_free_reply_llm_decision"] = llm_decision or {}
        if image_understanding_triggered or context.get("wechat_group_multimodal_matched_images"):
            context["wechat_group_image_understanding_triggered"] = True
        context["suppress_mention"] = True
        context["no_need_at"] = True
        local_decision = task.get("local_decision") or {}
        repeater_text = task.get("text") if "repeater_message" in (local_decision.get("reasons") or []) else ""
        self.free_reply_state.mark_triggered(
            task.get("room_id") or msg.other_user_id,
            now=time.time(),
            repeater_text=repeater_text,
        )
        if repeater_text:
            self._send_reply(context, Reply(ReplyType.TEXT, repeater_text))
            return
        self.produce(context)

    def free_reply_status(self):
        cfg = get_wechat_group_free_reply_config()
        return {
            "config": cfg,
            "rules": get_wechat_group_free_reply_rules(),
            "last_decision": self.free_reply_state.last_decision(),
            "worker": self.free_reply_worker.status(),
            "scorer": self._free_reply_scorer.status(),
        }
