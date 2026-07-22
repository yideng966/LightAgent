"""Local scoring and runtime state for WeChat group free replies."""

import copy
import re
import time

from config import conf


FREE_REPLY_ACTIVITY_LEVELS = ["quiet", "normal", "active", "crazy"]
FREE_REPLY_MUTE_SUPPRESSION = "muted_by_command"

DEFAULT_FREE_REPLY_PROFILES = {
    "quiet": {"min_score": 65, "min_interval_seconds": 30, "hourly_limit": 0, "consecutive_limit": 0},
    "normal": {"min_score": 50, "min_interval_seconds": 10, "hourly_limit": 0, "consecutive_limit": 0},
    "active": {"min_score": 35, "min_interval_seconds": 3, "hourly_limit": 0, "consecutive_limit": 0},
    "crazy": {"min_score": 20, "min_interval_seconds": 0, "hourly_limit": 0, "consecutive_limit": 0},
}

POSITIVE_RULES = [
    {"id": "bot_name_match", "score": 45, "label": "Mentions bot name without explicit at", "label_zh": "未显式 @ 但提到机器人名称"},
    {"id": "force_keyword_match", "score": 0, "label": "Matches configured force-reply keyword", "label_zh": "命中配置的强触发关键词"},
    {"id": "group_question", "score": 30, "label": "Open group question or help request", "label_zh": "群内开放问题或求助"},
    {"id": "unanswered_question", "score": 25, "label": "Question without recent answer", "label_zh": "近期无人回答的问题"},
    {"id": "bot_capability_match", "score": 25, "label": "Matches assistant capabilities", "label_zh": "命中机器人擅长能力"},
    {"id": "memory_or_transcript", "score": 20, "label": "Needs group memory or recent transcript", "label_zh": "需要群记忆或最近聊天记录"},
    {"id": "ai_opinion", "score": 35, "label": "Asks what AI thinks", "label_zh": "询问 AI 看法"},
    {"id": "sticker_request", "score": 50, "label": "Clear sticker or meme image request", "label_zh": "明确索要表情包或梗图"},
    {"id": "banter_opportunity", "score": "安静 +5 / 普通 +10 / 活跃 +18 / 高频 +28", "label": "Banter, meme or joke opportunity", "label_zh": "玩梗、接梗或吐槽机会"},
    {"id": "repeater_message", "score": 50, "label": "Three or more distinct senders repeat the same message", "label_zh": "3 个及以上不同成员复读同一句话"},
]

NEGATIVE_RULES = [
    {"id": "repeater_text_cooldown", "score": "-", "label": "Same repeated text was recently joined by bot", "label_zh": "同一句复读已由机器人接过"},
    {"id": "disabled", "score": "-", "label": "Free reply disabled", "label_zh": "自由回复未启用"},
    {"id": "room_not_enabled", "score": "-", "label": "Room not in free reply scope", "label_zh": "当前群不在自由回复范围"},
    {"id": "self_message", "score": "-", "label": "Message sent by bot itself", "label_zh": "机器人自己发送的消息"},
    {"id": "blocked_sender", "score": "-", "label": "Sender is blocked", "label_zh": "发送者在屏蔽列表中"},
    {"id": "low_information", "score": "-", "label": "Low-information short text", "label_zh": "低信息短文本"},
    {"id": "bot_silent_notice", "score": "-", "label": "Bot silent notice should not be sent or trigger free reply", "label_zh": "机器人静默说明不发送也不触发自由回复"},
    {"id": "media_payload", "score": "-", "label": "Raw media payload should not trigger free reply", "label_zh": "原始媒体载荷不触发自由回复"},
    {"id": "sensitive_or_dangerous", "score": "-", "label": "Sensitive, private or dangerous request", "label_zh": "敏感、隐私或危险请求"},
    {"id": "image_generation_failure_discussion", "score": "-", "label": "Image generation failure discussion should not trigger free reply", "label_zh": "生图失败讨论不触发自由回复"},
    {"id": "image_context_unavailable", "score": "-", "label": "Image-related question has no free-reply image context", "label_zh": "图片相关追问缺少自由回复图片上下文"},
    {"id": "min_interval", "score": "-", "label": "Room cooldown is active", "label_zh": "当前群冷却时间未结束"},
    {"id": "hourly_limit", "score": "-", "label": "Hourly limit reached", "label_zh": "已达到每小时回复上限"},
    {"id": "consecutive_limit", "score": "-", "label": "Consecutive reply limit reached", "label_zh": "已达到连续发言上限"},
    {"id": "below_threshold", "score": "-", "label": "Score below current threshold", "label_zh": "评分低于当前阈值"},
]

BANTER_SCORE_BY_LEVEL = {
    "quiet": 5,
    "normal": 10,
    "active": 18,
    "crazy": 28,
}

DEFAULT_POSITIVE_RULE_SCORES = {
    "bot_name_match": 45,
    "force_keyword_match": 0,
    "group_question": 30,
    "unanswered_question": 25,
    "bot_capability_match": 25,
    "memory_or_transcript": 20,
    "ai_opinion": 35,
    "sticker_request": 50,
    "banter_opportunity": copy.deepcopy(BANTER_SCORE_BY_LEVEL),
    "repeater_message": 50,
}

STICKER_REQUEST_SCORE = DEFAULT_POSITIVE_RULE_SCORES["sticker_request"]
REPEATER_MESSAGE_SCORE = DEFAULT_POSITIVE_RULE_SCORES["repeater_message"]
REPEATER_TEXT_COOLDOWN_SECONDS = 30 * 60
ACTIVITY_LEVEL_LABELS_ZH = {
    "quiet": "安静",
    "normal": "普通",
    "active": "活跃",
    "crazy": "高频",
}


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value or "").strip().lower() in ("1", "true", "yes", "on")


def _as_list(value) -> list:
    if isinstance(value, list):
        raw = value
    else:
        raw = re.split(r"[，,;；\n\r\t ]+", str(value or ""))
    return list(dict.fromkeys(str(item or "").strip() for item in raw if str(item or "").strip()))


def _clamp_int(value, default, low, high) -> int:
    try:
        value = int(value)
    except (TypeError, ValueError):
        value = default
    return min(max(value, low), high)


def _clamp_float(value, default, low, high) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = default
    return min(max(value, low), high)


def normalize_wechat_group_free_reply_profiles(raw_profiles=None) -> dict:
    profiles = copy.deepcopy(DEFAULT_FREE_REPLY_PROFILES)
    if not isinstance(raw_profiles, dict):
        return profiles
    for level in FREE_REPLY_ACTIVITY_LEVELS:
        raw = raw_profiles.get(level)
        if not isinstance(raw, dict):
            continue
        profiles[level] = {
            "min_score": _clamp_int(raw.get("min_score"), profiles[level]["min_score"], 0, 100),
            "min_interval_seconds": _clamp_int(raw.get("min_interval_seconds"), profiles[level]["min_interval_seconds"], 0, 3600),
            "hourly_limit": _clamp_int(raw.get("hourly_limit"), profiles[level]["hourly_limit"], 0, 999),
            "consecutive_limit": _clamp_int(raw.get("consecutive_limit"), profiles[level]["consecutive_limit"], 0, 99),
        }
    return profiles


def normalize_wechat_group_free_reply_rule_scores(raw_scores=None) -> dict:
    scores = copy.deepcopy(DEFAULT_POSITIVE_RULE_SCORES)
    if not isinstance(raw_scores, dict):
        return scores
    for rule_id, default_value in DEFAULT_POSITIVE_RULE_SCORES.items():
        if rule_id not in raw_scores:
            continue
        raw_value = raw_scores.get(rule_id)
        if rule_id == "banter_opportunity":
            level_scores = copy.deepcopy(default_value)
            if isinstance(raw_value, dict):
                for level in FREE_REPLY_ACTIVITY_LEVELS:
                    if level in raw_value:
                        level_scores[level] = _clamp_int(
                            raw_value.get(level),
                            default_value.get(level, BANTER_SCORE_BY_LEVEL["normal"]),
                            0,
                            100,
                        )
            else:
                shared = _clamp_int(raw_value, default_value.get("normal", 10), 0, 100)
                level_scores = {level: shared for level in FREE_REPLY_ACTIVITY_LEVELS}
            scores[rule_id] = level_scores
        else:
            scores[rule_id] = _clamp_int(raw_value, default_value, 0, 100)
    return scores


def normalize_wechat_group_free_reply_rule_enabled(raw_enabled=None) -> dict:
    enabled = {rule["id"]: True for rule in NEGATIVE_RULES}
    if not isinstance(raw_enabled, dict):
        return enabled
    for rule_id in list(enabled.keys()):
        if rule_id in raw_enabled:
            enabled[rule_id] = _as_bool(raw_enabled.get(rule_id))
    return enabled


def _format_banter_score_display(level_scores) -> str:
    parts = []
    for level in FREE_REPLY_ACTIVITY_LEVELS:
        label = ACTIVITY_LEVEL_LABELS_ZH.get(level, level)
        parts.append("{} +{}".format(label, int((level_scores or {}).get(level, BANTER_SCORE_BY_LEVEL[level]))))
    return " / ".join(parts)


def _rule_score_value(rule_scores, rule_id, activity_level="normal") -> int:
    scores = rule_scores if isinstance(rule_scores, dict) else {}
    if rule_id == "banter_opportunity":
        banter = scores.get(rule_id) if isinstance(scores.get(rule_id), dict) else BANTER_SCORE_BY_LEVEL
        return int(banter.get(activity_level, banter.get("normal", BANTER_SCORE_BY_LEVEL["normal"])))
    if rule_id in scores:
        return int(scores.get(rule_id) or 0)
    default_value = DEFAULT_POSITIVE_RULE_SCORES.get(rule_id, 0)
    if isinstance(default_value, dict):
        return int(default_value.get(activity_level, default_value.get("normal", 0)))
    return int(default_value or 0)


def _is_suppression_enabled(rule_enabled, rule_id) -> bool:
    if not isinstance(rule_enabled, dict):
        return True
    if rule_id not in rule_enabled:
        return True
    return bool(rule_enabled.get(rule_id))


def get_wechat_group_free_reply_config() -> dict:
    level = str(conf().get("wechat_group_free_reply_activity_level", "normal") or "normal").strip()
    if level not in FREE_REPLY_ACTIVITY_LEVELS:
        level = "normal"
    stable_room_ids = _as_list(conf().get("wechat_group_free_reply_stable_room_ids", []))
    legacy_room_ids = _as_list(conf().get("wechat_group_free_reply_room_ids", []))
    return {
        "enabled": _as_bool(conf().get("wechat_group_free_reply_enabled", False)),
        "room_ids": stable_room_ids or legacy_room_ids,
        "stable_room_ids": stable_room_ids,
        "legacy_room_ids": legacy_room_ids,
        "names": _as_list(conf().get("wechat_group_free_reply_names", [])),
        "activity_level": level,
        "mute_minutes": _clamp_int(conf().get("wechat_group_free_reply_mute_minutes", 10), 10, 1, 1440),
        "mute_mentions_enabled": _as_bool(conf().get("wechat_group_free_reply_mute_mentions_enabled", False)),
        "queue_ttl_seconds": _clamp_int(conf().get("wechat_group_free_reply_queue_ttl_seconds", 120), 120, 10, 600),
        "worker_max_workers": _clamp_int(conf().get("wechat_group_free_reply_worker_max_workers", 2), 2, 1, 8),
        "worker_queue_size": _clamp_int(conf().get("wechat_group_free_reply_worker_queue_size", 100), 100, 1, 1000),
        "llm_judge_enabled": _as_bool(conf().get("wechat_group_free_reply_llm_judge_enabled", True)),
        "llm_judge_timeout_seconds": _clamp_int(conf().get("wechat_group_free_reply_llm_judge_timeout_seconds", 8), 8, 1, 30),
        "llm_judge_min_confidence": _clamp_float(conf().get("wechat_group_free_reply_llm_judge_min_confidence", 0.6), 0.6, 0.0, 1.0),
        "force_keywords": _as_list(conf().get("wechat_group_free_reply_force_keywords", [])),
        "profiles": normalize_wechat_group_free_reply_profiles(conf().get("wechat_group_free_reply_profiles", {})),
        "rule_scores": normalize_wechat_group_free_reply_rule_scores(conf().get("wechat_group_free_reply_rule_scores", {})),
        "rule_enabled": normalize_wechat_group_free_reply_rule_enabled(conf().get("wechat_group_free_reply_rule_enabled", {})),
    }


def get_wechat_group_free_reply_rules() -> dict:
    scores = normalize_wechat_group_free_reply_rule_scores(conf().get("wechat_group_free_reply_rule_scores", {}))
    enabled = normalize_wechat_group_free_reply_rule_enabled(conf().get("wechat_group_free_reply_rule_enabled", {}))
    positive = []
    for rule in POSITIVE_RULES:
        item = copy.deepcopy(rule)
        rule_id = item["id"]
        if rule_id == "banter_opportunity":
            level_scores = scores.get(rule_id) or copy.deepcopy(BANTER_SCORE_BY_LEVEL)
            item["score"] = _format_banter_score_display(level_scores)
            item["score_by_level"] = copy.deepcopy(level_scores)
            item["score_kind"] = "by_level"
        else:
            item["score"] = int(scores.get(rule_id, DEFAULT_POSITIVE_RULE_SCORES.get(rule_id, 0)) or 0)
            item["score_kind"] = "fixed"
        item["score_editable"] = True
        positive.append(item)
    negative = []
    for rule in NEGATIVE_RULES:
        item = copy.deepcopy(rule)
        item["enabled"] = _is_suppression_enabled(enabled, item["id"])
        item["score_kind"] = "suppression"
        item["enabled_editable"] = True
        negative.append(item)
    return {
        "positive": positive,
        "negative": negative,
    }


def is_free_reply_room_enabled(config, room_id, room_name) -> bool:
    room_ids = config.get("room_ids") or []
    return bool(room_ids and room_id in room_ids)


def _text_preview(text: str, limit=120) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    return text[:limit]


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _is_bot_silent_notice_text(text: str) -> bool:
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


def _is_media_payload(text: str, message_type=None) -> bool:
    value = _normalize_text(text)
    msg_type = str(message_type or "").strip().lower() if isinstance(message_type, str) else ""
    if msg_type and msg_type not in ("text", "unknown"):
        return True
    if re.match(r"^<\?xml\b", value, re.IGNORECASE):
        return True
    if re.match(r"^<msg\b", value, re.IGNORECASE):
        return True
    return bool(re.search(r"<(img|emoji|videomsg|appmsg|voicemsg)\b", value, re.IGNORECASE))


def _is_low_information(text: str) -> bool:
    compact = re.sub(r"\s+", "", text or "")
    if len(compact) <= 2:
        return True
    lowered = compact.lower()
    if lowered in {"哈哈", "呵呵", "嗯嗯", "好的", "ok", "hi", "hello"}:
        return True
    without_fillers = re.sub(r"[\W_]+", "", lowered, flags=re.UNICODE)
    without_fillers = re.sub(r"(哈|啊|呀|哦|噢|嗯|额|呃|呵|hi|hello|ok)+", "", without_fillers, flags=re.IGNORECASE)
    return len(without_fillers) == 0 and len(compact) <= 8


def _is_sensitive_or_dangerous(text: str) -> bool:
    lower = (text or "").lower()
    patterns = [
        r"\bapi\s*key\b",
        r"\btoken\b",
        r"\bsecret\b",
        r"file://",
        r"[a-zA-Z]:\\",
        r"本机",
        r"桌面",
        r"私钥",
        r"密码",
        r"cookie",
    ]
    return any(re.search(pattern, lower, re.IGNORECASE) for pattern in patterns)


def _is_image_generation_failure_discussion(text: str) -> bool:
    value = _normalize_text(text)
    return bool(
        re.search(
            r"(图片生成失败|图像生成失败|生图失败|绘图密钥|绘图.*密钥|画不了|生成不了图)",
            value,
            re.IGNORECASE,
        )
    )


def _looks_like_sticker_request(text: str) -> bool:
    return bool(
        re.search(
            r"(表情包|表情|梗图|斗图|gif|GIF|动图|来张图|来个图|发张图|发个图|整张图|整一个图)",
            text or "",
            re.IGNORECASE,
        )
    )


def _looks_like_banter(text: str) -> bool:
    return bool(
        re.search(
            r"(笑死|绷不住|蚌埠住|破防|离谱|抽象|逆天|乐|哈哈哈|hhh|草|卧槽|吐槽|好家伙|典|急了|整活|活了|不愧是|太对了|这也行|烂活|名场面|赢麻了|上强度|电子榨菜|遥遥领先|尊嘟假嘟|栓q|泰裤辣|绝绝子)",
            text or "",
            re.IGNORECASE,
        )
    )


def _score_text(text: str, bot_names=None, activity_level="normal", rule_scores=None) -> tuple:
    text = _normalize_text(text)
    score = 0
    reasons = []
    rule_scores = normalize_wechat_group_free_reply_rule_scores(rule_scores)
    bot_names = [
        name for name in (bot_names or ["LightAgent", "白龙马", "小白龙", "机器人", "AI"])
        if isinstance(name, str) and name
    ]
    if any(name and name in text for name in bot_names):
        score += _rule_score_value(rule_scores, "bot_name_match", activity_level)
        reasons.append("bot_name_match")
    if re.search(r"(谁能|谁有|有没有人|大家|帮我|帮忙|求|看看|看下|咋办|怎么办|怎么|如何|为啥|为什么|啥意思|什么意思|哪个|哪位|哪里|哪儿|能不能|可不可以|会不会|吗|嘛|呢|？|\?)", text or ""):
        score += _rule_score_value(rule_scores, "group_question", activity_level)
        reasons.append("group_question")
    if re.search(r"(总结|归纳|方案|记录|上下文|刚才|讨论|记忆|群聊|文档|报告|代码|识图|图片|截图|视频|解析|表情包|梗图|斗图|文件|txt|pdf|word|excel|ppt|链接|网页|搜索|查一下)", text or "", re.IGNORECASE):
        score += _rule_score_value(rule_scores, "bot_capability_match", activity_level)
        reasons.append("bot_capability_match")
    if re.search(r"(记得|群记忆|聊天记录|刚才说|之前|上面|前面|谁说|谁发|谁讲|群里|群友|这个人|他们|她们)", text or ""):
        score += _rule_score_value(rule_scores, "memory_or_transcript", activity_level)
        reasons.append("memory_or_transcript")
    if re.search(r"(ai怎么看|问问ai)", text or "", re.IGNORECASE):
        score += _rule_score_value(rule_scores, "ai_opinion", activity_level)
        reasons.append("ai_opinion")
    if _looks_like_sticker_request(text):
        score += _rule_score_value(rule_scores, "sticker_request", activity_level)
        reasons.append("sticker_request")
    if _looks_like_banter(text):
        score += _rule_score_value(rule_scores, "banter_opportunity", activity_level)
        reasons.append("banter_opportunity")
    return score, reasons


def _is_repeater_message(text: str, sender_id: str, sender_name: str, recent_messages=None) -> bool:
    target = _normalize_text(text)
    if not target:
        return False
    senders = set()

    def add_sender(item_sender_id, item_sender_name):
        key = str(item_sender_id or "").strip() or str(item_sender_name or "").strip()
        if key:
            senders.add(key)

    add_sender(sender_id, sender_name)
    for item in recent_messages or []:
        if not isinstance(item, dict):
            continue
        item_text = _normalize_text(item.get("text") or item.get("content") or "")
        if item_text != target:
            continue
        add_sender(
            item.get("stable_member_id") or item.get("sender_id") or item.get("actual_user_id"),
            item.get("sender_nickname") or item.get("sender_name") or item.get("actual_user_nickname"),
        )
        if len(senders) >= 3:
            return True
    return False


def _elapsed_seconds(now, previous) -> float:
    diff = float(now) - float(previous)
    # Some legacy tests and snapshots use compact millisecond-like values.
    if diff > 1000 and float(now) < 1000000:
        return diff / 1000.0
    return diff


def _repeater_text_cooldown_active(text: str, state: dict, now) -> bool:
    key = _normalize_text(text)
    if not key:
        return False
    recent = state.get("repeater_text_triggered_at") if isinstance(state, dict) else {}
    if not isinstance(recent, dict):
        return False
    last_triggered = float(recent.get(key) or 0)
    return bool(last_triggered and _elapsed_seconds(now, last_triggered) < REPEATER_TEXT_COOLDOWN_SECONDS)


def _remember_repeater_text(state: dict, text: str, now) -> None:
    key = _normalize_text(text)
    if not key:
        return
    recent = state.setdefault("repeater_text_triggered_at", {})
    if not isinstance(recent, dict):
        recent = {}
        state["repeater_text_triggered_at"] = recent
    cutoff = float(now) - REPEATER_TEXT_COOLDOWN_SECONDS
    for item_key, ts in list(recent.items()):
        try:
            if float(ts) < cutoff:
                recent.pop(item_key, None)
        except (TypeError, ValueError):
            recent.pop(item_key, None)
    recent[key] = now


def evaluate_wechat_group_free_reply(
    config,
    room_id,
    room_name,
    sender_id,
    sender_name,
    text,
    recent_messages=None,
    state=None,
    now=None,
    is_self=False,
    blocked_sender_ids=None,
    bot_names=None,
    message_type=None,
    allow_media_payload=False,
) -> dict:
    now = time.time() if now is None else now
    state = state or {}
    suppressions = []
    normalized_text = _normalize_text(text or "")
    force_keywords = _as_list(config.get("force_keywords") or [])
    force_keyword_match = any(keyword and keyword in normalized_text for keyword in force_keywords)
    media_payload = _is_media_payload(normalized_text, message_type=message_type)
    level = config.get("activity_level") or "normal"
    profile = (config.get("profiles") or DEFAULT_FREE_REPLY_PROFILES).get(level, DEFAULT_FREE_REPLY_PROFILES["normal"])
    threshold = int(profile.get("min_score", 50))
    rule_scores = normalize_wechat_group_free_reply_rule_scores(config.get("rule_scores"))
    rule_enabled = normalize_wechat_group_free_reply_rule_enabled(config.get("rule_enabled"))

    def maybe_suppress(rule_id: str) -> None:
        if _is_suppression_enabled(rule_enabled, rule_id):
            suppressions.append(rule_id)

    if media_payload:
        if allow_media_payload:
            score, reasons = threshold, ["media_payload_allowed"]
        else:
            score, reasons = 0, []
    else:
        score, reasons = _score_text(
            normalized_text,
            bot_names=bot_names,
            activity_level=level,
            rule_scores=rule_scores,
        )
        if "group_question" in reasons and len(recent_messages or []) >= 2:
            score += _rule_score_value(rule_scores, "unanswered_question", level)
            reasons.append("unanswered_question")
        if _is_repeater_message(normalized_text, sender_id, sender_name, recent_messages):
            score += _rule_score_value(rule_scores, "repeater_message", level)
            reasons.append("repeater_message")
    if force_keyword_match:
        if "force_keyword_match" not in reasons:
            reasons.append("force_keyword_match")
        force_score = _rule_score_value(rule_scores, "force_keyword_match", level)
        if force_score:
            score += force_score

    if not config.get("enabled"):
        maybe_suppress("disabled")
    if not is_free_reply_room_enabled(config, room_id, room_name):
        maybe_suppress("room_not_enabled")
    if is_self:
        maybe_suppress("self_message")
    if sender_id and sender_id in (blocked_sender_ids or []):
        maybe_suppress("blocked_sender")
    try:
        muted_until = float(state.get("muted_until") or 0)
    except (TypeError, ValueError):
        muted_until = 0
    if muted_until > float(now):
        suppressions.append(FREE_REPLY_MUTE_SUPPRESSION)
    if _is_bot_silent_notice_text(normalized_text):
        maybe_suppress("bot_silent_notice")
    if _is_low_information(text or "") and not force_keyword_match and not (media_payload and allow_media_payload):
        maybe_suppress("low_information")
    if media_payload and not allow_media_payload:
        maybe_suppress("media_payload")
    if _is_sensitive_or_dangerous(text or ""):
        maybe_suppress("sensitive_or_dangerous")
    if _is_image_generation_failure_discussion(text or ""):
        maybe_suppress("image_generation_failure_discussion")
    if "repeater_message" in reasons and _repeater_text_cooldown_active(normalized_text, state, now):
        maybe_suppress("repeater_text_cooldown")

    min_interval = int(profile.get("min_interval_seconds", 0) or 0)
    last_triggered = float(state.get("last_triggered_at") or 0)
    if min_interval and last_triggered and _elapsed_seconds(now, last_triggered) < min_interval:
        maybe_suppress("min_interval")

    hourly_limit = int(profile.get("hourly_limit", 0) or 0)
    recent_triggered = [
        float(ts) for ts in (state.get("recent_triggered_at") or [])
        if _elapsed_seconds(now, float(ts)) < 3600
    ]
    if hourly_limit and len(recent_triggered) >= hourly_limit:
        maybe_suppress("hourly_limit")

    consecutive_limit = int(profile.get("consecutive_limit", 0) or 0)
    if consecutive_limit and int(state.get("consecutive_triggered") or 0) >= consecutive_limit:
        maybe_suppress("consecutive_limit")

    if score < threshold and not force_keyword_match:
        maybe_suppress("below_threshold")

    return {
        "triggered": not suppressions,
        "score": score,
        "threshold": threshold,
        "activity_level": level,
        "reasons": reasons,
        "suppressions": suppressions,
        "room_id": room_id or "",
        "room_name": room_name or "",
        "sender_id": sender_id or "",
        "sender_name": sender_name or "",
        "text_preview": _text_preview(text),
        "timestamp": now,
    }


class WechatGroupFreeReplyStateStore:
    def __init__(self):
        self._states = {}
        self._last_decision = {}

    def get(self, room_id) -> dict:
        state = self._states.setdefault(room_id or "", {
            "last_triggered_at": 0,
            "recent_triggered_at": [],
            "consecutive_triggered": 0,
            "repeater_text_triggered_at": {},
            "muted_until": 0,
        })
        return state

    def mute(self, room_id, minutes, now=None) -> float:
        now = time.time() if now is None else float(now)
        try:
            duration_seconds = max(0, int(minutes)) * 60
        except (TypeError, ValueError):
            duration_seconds = 0
        state = self.get(room_id)
        state["muted_until"] = now + duration_seconds
        state["consecutive_triggered"] = 0
        return state["muted_until"]

    def is_muted(self, room_id, now=None) -> bool:
        now = time.time() if now is None else float(now)
        state = self.get(room_id)
        try:
            muted_until = float(state.get("muted_until") or 0)
        except (TypeError, ValueError):
            muted_until = 0
        if muted_until <= now:
            state["muted_until"] = 0
            return False
        return True

    def mark_triggered(self, room_id, now=None, repeater_text="") -> None:
        now = time.time() if now is None else now
        state = self.get(room_id)
        state["last_triggered_at"] = now
        state["recent_triggered_at"] = [
            ts for ts in state.get("recent_triggered_at", []) if _elapsed_seconds(now, float(ts)) < 3600
        ] + [now]
        state["consecutive_triggered"] = int(state.get("consecutive_triggered") or 0) + 1
        _remember_repeater_text(state, repeater_text, now)

    def mark_observed(self, room_id) -> None:
        self.get(room_id)["consecutive_triggered"] = 0

    def remember_decision(self, decision) -> None:
        self._last_decision = copy.deepcopy(decision or {})

    def last_decision(self) -> dict:
        return copy.deepcopy(self._last_decision)
