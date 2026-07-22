"""Wechaty sidecar message adapter for LightAgent group chat."""

import re
import time

from bridge.context import ContextType
from channel.chat_message import ChatMessage
from channel.wechat_group.protocol import SidecarEvent


_MESSAGE_TYPE_TO_CONTEXT = {
    "text": ContextType.TEXT,
    "image": ContextType.IMAGE,
    "sticker": ContextType.IMAGE,
    "voice": ContextType.VOICE,
    "audio": ContextType.VOICE,
    "file": ContextType.FILE,
    "video": ContextType.FILE,
}


_PAT_SELF_RE = re.compile(r'^\s*["“](?P<actor>[^"”]+)["”]\s*拍了拍\s*(?P<target>我)(?P<suffix>[^\r\n]*)\s*$')

_QUOTE_DIAGNOSTIC_TEXT_VALUES = {
    "status": {"resolved", "missing"},
    "source": {"puppet_method", "puppet_cache"},
    "method_error": {
        "",
        "message_id_missing",
        "id_not_found",
        "method_unavailable",
        "empty_payload",
        "error",
        "typeerror",
        "rangeerror",
        "unknown_error",
    },
    "cache_error": {
        "",
        "id_not_found",
        "error",
        "typeerror",
        "rangeerror",
        "unknown_error",
    },
    "parse_status": {
        "not_attempted",
        "quote_parsed",
        "not_quote",
        "refermsg_missing",
        "appmsg_missing",
        "xml_candidate_missing",
        "unexpected_error",
    },
}


def _sanitize_quote_diagnostics(value):
    if not isinstance(value, dict):
        return {}
    sanitized = {}
    for key, allowed in _QUOTE_DIAGNOSTIC_TEXT_VALUES.items():
        if key not in value:
            continue
        text = str(value.get(key) or "").strip().lower()
        if text in allowed:
            sanitized[key] = text
    for key in ("method_available", "cache_available", "has_content", "has_original_content"):
        if key in value:
            sanitized[key] = bool(value.get(key))
    for key in ("msg_type", "app_msg_type"):
        text = str(value.get(key) or "").strip()
        if re.fullmatch(r"-?\d{1,12}", text):
            sanitized[key] = text
    for key in ("xml_candidate_count", "parsed_candidate_count"):
        try:
            count = int(value.get(key))
        except (TypeError, ValueError):
            continue
        sanitized[key] = max(0, min(count, 100))
    return sanitized


def _parse_pat_self_text(text: str):
    match = _PAT_SELF_RE.match(str(text or ""))
    if not match:
        return None
    actor = match.group("actor").strip()
    target = match.group("target").strip()
    if not actor or target != "我":
        return None
    return {
        "actor": actor,
        "target": target,
        "suffix": (match.group("suffix") or "").strip(),
    }


class WechatGroupMessage(ChatMessage):
    def __init__(self, event: SidecarEvent):
        super().__init__(event.payload)
        payload = event.payload

        message_type = payload.get("message_type") or "text"
        self.message_type = message_type
        self.msg_id = payload.get("message_id") or payload.get("id")
        self.create_time = payload.get("timestamp") or int(time.time())
        self.ctype = _MESSAGE_TYPE_TO_CONTEXT.get(message_type, ContextType.TEXT)
        self.text = payload.get("text") or ""
        self.media_path = payload.get("file_path") or ""
        self.content = self.media_path or self.text
        pat_self = _parse_pat_self_text(self.text) if str(message_type or "").lower() == "text" else None
        self.is_pat_self = bool(pat_self)
        self.pat_actor_name = pat_self["actor"] if pat_self else ""
        self.pat_target_name = pat_self["target"] if pat_self else ""
        self.pat_suffix = pat_self["suffix"] if pat_self else ""

        room_id = payload.get("room_id") or ""
        room_name = payload.get("room_name") or room_id
        self_id = payload.get("self_id") or ""
        self_name = payload.get("self_name") or self_id
        sender_id = payload.get("sender_id") or ""
        sender_name = payload.get("sender_name") or sender_id
        account_fingerprint = payload.get("account_fingerprint") if isinstance(payload.get("account_fingerprint"), dict) else {}
        room_fingerprint = payload.get("room_fingerprint") if isinstance(payload.get("room_fingerprint"), dict) else {}
        member_fingerprint = payload.get("member_fingerprint") if isinstance(payload.get("member_fingerprint"), dict) else {}

        self.from_user_id = room_id
        self.from_user_nickname = room_name
        self.to_user_id = self_id
        self.to_user_nickname = self_name
        self.other_user_id = room_id
        self.other_user_nickname = room_name
        self.actual_user_id = sender_id
        self.actual_user_nickname = sender_name
        self.self_display_name = payload.get("self_display_name") or self_name
        self.runtime_room_id = payload.get("runtime_room_id") or room_id
        self.runtime_sender_id = payload.get("runtime_sender_id") or sender_id
        self.runtime_self_id = payload.get("runtime_self_id") or self_id
        self.account_fingerprint = account_fingerprint
        self.room_fingerprint = room_fingerprint
        self.member_fingerprint = member_fingerprint
        self.sender_wechat_id = member_fingerprint.get("wechat_id") or payload.get("sender_wechat_id") or ""
        self.sender_room_alias = member_fingerprint.get("room_alias") or payload.get("sender_room_alias") or ""
        self.identity_fingerprint_metadata = {
            "account": account_fingerprint,
            "room": room_fingerprint,
            "member": member_fingerprint,
        }

        self.is_group = True
        self.is_at = bool(payload.get("is_at", False))
        self.at_list = payload.get("at_list") or []
        self.is_quote_self = bool(payload.get("is_quote_self", False))
        quote = payload.get("quote") or {}
        self.quote = quote if isinstance(quote, dict) else {}
        forward = payload.get("forward") or {}
        self.forward = forward if isinstance(forward, dict) else {}
        self.raw_app_type = str(payload.get("raw_app_type") or "").strip()
        self.quote_diagnostics = _sanitize_quote_diagnostics(payload.get("quote_diagnostics"))
        self.my_msg = bool(payload.get("my_msg", False) or (sender_id and sender_id == self_id))
