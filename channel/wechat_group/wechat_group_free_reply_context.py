"""Deterministic, prompt-safe context for WeChat group free-reply routing."""

from __future__ import annotations

import re
import time
from typing import Any, Dict, Iterable

from channel.wechat_group.wechat_group_context import (
    is_wechat_group_transport_payload,
    sanitize_wechat_group_prompt_text,
)
from channel.wechat_group.wechat_group_transport import project_wechat_message_type


_QUESTION_RE = re.compile(r"(?:吗|嘛|呢|么|咋|怎么|如何|为何|为什么|为啥|谁|哪|多少|几|[?？])")
_OPEN_GROUP_RE = re.compile(r"(?:大家|各位|群友|谁能|谁有|有没有人|有人|哪位|诸位|大伙|你们)")
_BOT_CAPABILITY_RE = re.compile(
    r"(?:(?:帮我|请|麻烦|能不能|可以帮我|谁能|替我).{0,12}"
    r"(?:总结|归纳|查|搜索|识图|识别|解析|生成|画|写|翻译|提醒|定时))"
    r"|(?:总结一下|归纳一下|查一下|搜索一下|识别一下|解析一下|翻译一下|"
    r"提醒我|定时提醒|生成一|画一|写一)"
)
_BOT_FOLLOWUP_RE = re.compile(
    r"(?:继续|接着|刚才你|你刚才|再说|再查|再看|然后呢|前面你|上面你|你说的)"
)
_PUNCTUATION_RE = re.compile(r"[\s，。！？!?、,.~～…：:；;（）()【】\[\]{}<>《》]+")


def _field(mapping: Dict[str, Any], *names: str, default: Any = "") -> Any:
    mapping = mapping if isinstance(mapping, dict) else {}
    for name in names:
        value = mapping.get(name)
        if value is not None:
            return value
    return default


def _identity(mapping: Dict[str, Any]) -> str:
    return str(
        _field(
            mapping,
            "stable_member_id",
            "sender_id",
            "runtime_sender_id",
            "actual_user_id",
            default="",
        )
        or ""
    ).strip()


def _timestamp(mapping: Dict[str, Any], default: float = 0.0) -> float:
    try:
        return float(_field(mapping, "created_at", "timestamp", "create_time", default=default) or default)
    except (TypeError, ValueError):
        return float(default)


def is_explicit_open_group_question(text: str) -> bool:
    value = str(text or "").strip()
    return bool(_OPEN_GROUP_RE.search(value) and _QUESTION_RE.search(value))


def is_short_question(text: str, max_chars: int = 12) -> bool:
    value = str(text or "").strip()
    compact = _PUNCTUATION_RE.sub("", value)
    return bool(compact and len(compact) <= max(int(max_chars or 12), 1) and _QUESTION_RE.search(value))


def is_explicit_bot_followup_text(text: str) -> bool:
    return bool(_BOT_FOLLOWUP_RE.search(str(text or "")))


def _has_bot_target(current: Dict[str, Any], bot_names: Iterable[str]) -> bool:
    if current.get("is_at") is True or current.get("is_quote_self") is True:
        return True
    text = str(_field(current, "text", "content") or "")
    if any(str(name or "").strip() and str(name).strip() in text for name in bot_names or []):
        return True
    return bool(_BOT_CAPABILITY_RE.search(text))


def _meaningful_human_statement(item: Dict[str, Any]) -> bool:
    if item.get("is_bot") is True:
        return False
    text = str(_field(item, "text", "content") or "").strip()
    message_type = project_wechat_message_type(_field(item, "message_type", default="text"), text)
    if message_type != "text" or is_wechat_group_transport_payload(text):
        return False
    safe = sanitize_wechat_group_prompt_text(text, 160)
    if not safe or safe.startswith("["):
        return False
    compact = _PUNCTUATION_RE.sub("", safe)
    return len(compact) >= 2


def _previous_event(current: Dict[str, Any], recent_timeline: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    current_id = str(_field(current, "message_id", "msg_id") or "").strip()
    current_ts = _timestamp(current, time.time())
    for item in reversed(list(recent_timeline or [])):
        if not isinstance(item, dict):
            continue
        item_id = str(_field(item, "message_id", "msg_id") or "").strip()
        if current_id and item_id == current_id:
            continue
        item_ts = _timestamp(item)
        if item_ts and item_ts > current_ts + 1:
            continue
        if not str(_field(item, "text", "content") or "").strip():
            continue
        return item
    return {}


def analyze_free_reply_addressee(
    current_message: Dict[str, Any],
    recent_timeline: Iterable[Dict[str, Any]],
    bot_names: Iterable[str] = (),
    max_followup_seconds: int = 120,
) -> Dict[str, Any]:
    current = current_message if isinstance(current_message, dict) else {}
    text = str(_field(current, "text", "content") or "").strip()
    now = _timestamp(current, time.time())
    previous = _previous_event(current, recent_timeline)
    previous_ts = _timestamp(previous)
    age = now - previous_ts if previous_ts else None
    short_question = is_short_question(text)
    open_question = is_explicit_open_group_question(text)
    explicit_bot = _has_bot_target(current, bot_names)
    previous_is_bot = previous.get("is_bot") is True
    current_identity = _identity(current)
    previous_identity = _identity(previous)
    different_human = bool(
        previous
        and not previous_is_bot
        and previous_identity
        and (not current_identity or previous_identity != current_identity)
    )
    within_window = bool(age is not None and 0 <= age <= max(int(max_followup_seconds or 120), 0))
    immediate_bot_followup = bool(short_question and previous_is_bot and within_window)
    likely_human_followup = bool(
        short_question
        and not explicit_bot
        and not open_question
        and different_human
        and within_window
        and _meaningful_human_statement(previous)
    )

    evidence = []
    if short_question:
        evidence.append("short_question")
    if open_question:
        evidence.append("explicit_open_group_question")
    if explicit_bot:
        evidence.append("explicit_bot_target")
    if immediate_bot_followup:
        evidence.append("immediate_bot_followup")
    if likely_human_followup:
        evidence.append("previous_other_human_within_120s")

    if explicit_bot or immediate_bot_followup:
        target_kind = "bot"
    elif likely_human_followup:
        target_kind = "human"
    elif open_question:
        target_kind = "group"
    else:
        target_kind = "unknown"
    return {
        "target_kind": target_kind,
        "target_member_token": "member_previous" if target_kind == "human" else "",
        "is_short_question": short_question,
        "is_explicit_open_group_question": open_question,
        "is_immediate_bot_followup": immediate_bot_followup,
        "is_followup_to_bot": bool(immediate_bot_followup or _BOT_FOLLOWUP_RE.search(text)),
        "is_likely_human_followup": likely_human_followup,
        "evidence_codes": evidence,
    }


def build_safe_free_reply_timeline(
    current_message: Dict[str, Any],
    recent_timeline: Iterable[Dict[str, Any]],
    limit: int = 12,
) -> list:
    """Return an oldest-to-newest timeline without stable/runtime identifiers."""
    current = current_message if isinstance(current_message, dict) else {}
    try:
        max_limit = min(max(int(limit or 12), 1), 50)
    except (TypeError, ValueError):
        max_limit = 12
    current_id = str(_field(current, "message_id", "msg_id") or "").strip()
    now = _timestamp(current, time.time())
    actor_tokens: Dict[str, str] = {}
    bot_ids = {
        str(value or "").strip()
        for value in (
            _field(current, "bot_sender_id"),
            _field(current, "runtime_bot_sender_id"),
            _field(current, "bot_id"),
        )
        if str(value or "").strip()
    }

    def actor_token(item: Dict[str, Any]) -> str:
        if item.get("is_bot") is True or _identity(item) in bot_ids:
            return "assistant"
        identity = _identity(item) or str(_field(item, "sender_name", "sender_nickname") or "unknown")
        if identity not in actor_tokens:
            actor_tokens[identity] = "member_{:03d}".format(len(actor_tokens) + 1)
        return actor_tokens[identity]

    result = []
    for raw in recent_timeline or []:
        if not isinstance(raw, dict):
            continue
        message_id = str(_field(raw, "message_id", "msg_id") or "").strip()
        if current_id and message_id == current_id:
            continue
        text = str(_field(raw, "text", "content") or "")
        msg_type = project_wechat_message_type(_field(raw, "message_type", default="text"), text)
        if is_wechat_group_transport_payload(text):
            safe_text = "[media message]"
        elif msg_type != "text":
            safe_text = "[{} message]".format(msg_type)
        else:
            safe_text = sanitize_wechat_group_prompt_text(text, 300)
        if not safe_text:
            continue
        created_at = _timestamp(raw)
        is_bot = bool(raw.get("is_bot") is True or _identity(raw) in bot_ids)
        safe_raw = dict(raw)
        safe_raw["is_bot"] = is_bot
        result.append(
            {
                "message_id": "context_{:03d}".format(len(result) + 1),
                "age_seconds": max(int(now - created_at), 0) if created_at else None,
                "actor": actor_token(safe_raw),
                "is_bot": is_bot,
                "text": safe_text,
            }
        )

    current_copy = dict(current)
    current_copy["is_bot"] = False
    current_text = str(_field(current, "text", "content") or "")
    safe_current_text = (
        "[media message]"
        if is_wechat_group_transport_payload(current_text)
        else sanitize_wechat_group_prompt_text(current_text, 300)
    )
    result.append(
        {
            "message_id": "CURRENT_MESSAGE",
            "age_seconds": 0,
            "actor": actor_token(current_copy),
            "is_bot": False,
            "text": safe_current_text,
        }
    )
    return result[-max_limit:]
