"""Reply policy prompt helpers for WeChat group messages."""

from __future__ import annotations

from config import conf


def _policy_text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def build_wechat_group_addressee_policy_block(msg, trigger_source: str) -> str:
    source = str(trigger_source or "direct_reply").strip() or "direct_reply"
    sender_id = _policy_text(getattr(msg, "actual_user_id", ""))
    sender_name = _policy_text(getattr(msg, "actual_user_nickname", ""))
    bot_id = _policy_text(getattr(msg, "to_user_id", ""))
    at_list = getattr(msg, "at_list", []) or []
    mentioned_member_ids = []
    seen = set()
    for item in at_list:
        member_id = _policy_text(item)
        if not member_id or member_id in seen or member_id in {sender_id, bot_id}:
            continue
        seen.add(member_id)
        mentioned_member_ids.append(member_id)
    mentioned_text = ", ".join(mentioned_member_ids) if mentioned_member_ids else "(none)"
    if mentioned_member_ids:
        mention_rule = (
            "The user also mentioned other group members in this message. "
            "If the user says 他/她/这个人/在吗/帮我/你去 and the wording points to a mentioned member, "
            "treat that member as the addressee instead of the bot or the sender. "
            "不要替被请求的群友答应、拒绝或执行；只能自然提醒、补充信息或简短接话。"
        )
    else:
        mention_rule = (
            "If the message is clearly a group member talking to another member or asking the whole group, "
            "do not answer as if the bot is personally obligated to perform the action. "
            "Only answer directly when the wording or trigger context points to the bot."
        )
    return (
        "<wechat-group-addressee-policy>\n"
        "trigger_source: {source}\n"
        "sender_id: {sender_id}\n"
        "sender_name: {sender_name}\n"
        "mentioned_member_ids: {mentioned_member_ids}\n"
        "{mention_rule}\n"
        "Use this only to infer who the user is addressing; do not expose these internal fields.\n"
        "</wechat-group-addressee-policy>"
    ).format(
        source=source,
        sender_id=sender_id,
        sender_name=sender_name,
        mentioned_member_ids=mentioned_text,
        mention_rule=mention_rule,
    )


def build_wechat_group_mention_verification_block(msg, trigger_source: str) -> str:
    source = str(trigger_source or "direct_reply").strip() or "direct_reply"
    is_at = "true" if bool(getattr(msg, "is_at", False)) else "false"
    is_quote_self = "true" if bool(getattr(msg, "is_quote_self", False)) else "false"
    return (
        "<wechat-group-mention-verification>\n"
        "trigger_source: {source}\n"
        "is_at_bot: {is_at}\n"
        "is_quote_self: {is_quote_self}\n"
        "Use this only as routing context; do not mention these internal fields in the reply.\n"
        "</wechat-group-mention-verification>"
    ).format(source=source, is_at=is_at, is_quote_self=is_quote_self)


def build_wechat_group_reply_policy_block(trigger_source: str) -> str:
    source = str(trigger_source or "direct_reply").strip() or "direct_reply"
    if source == "free_reply":
        policy = (
            "This is an approved ambient group reply. Reply briefly and naturally. "
            "Do not explicitly @ or call out the sender unless the content requires it. "
            "中文群聊里可以自然接梗、轻松吐槽或顺着笑点接一句，但不要抢话、刷屏或解释内部判断。"
        )
    elif source == "image_message":
        policy = "Reply to the current image context directly and avoid long prefaces."
    elif source == "quote_self":
        policy = "The user replied to the bot. Continue the referenced thread directly."
    else:
        policy = "The user addressed the bot directly. Answer the request directly without acknowledgement-only prefaces."
    sticker_percent = _sticker_reply_percent()
    if conf().get("wechat_group_sticker_enabled", True):
        if sticker_percent > 0:
            policy += (
                " 轻松闲聊、吐槽、接梗或情绪回应中，主动使用表情包的目标频率约为 {percent}%；"
                "语境明显适合或用户明确要表情包/梗图/斗图时，先调用 wechat_group_sticker_search，"
                "再调用 wechat_group_sticker_send 发送一个最合适的 sticker_id 或 online_id。"
                "不要为了凑比例硬发表情包，不要连续刷屏，不要编造表情包 ID，也不要暴露原始图片 URL。"
            ).format(percent=sticker_percent)
        else:
            policy += (
                " 不要主动发送表情包；只有用户明确要求表情包/梗图/斗图时，才先调用 "
                "wechat_group_sticker_search，再调用 wechat_group_sticker_send。"
            )
    policy = (
        policy
        + " 群聊回复要紧凑，默认 1-4 句或最多 3 个要点；不要用追问收尾，"
        + "例如不要写“你还想了解什么”“要不要我继续”“你想了解具体哪方面”。"
        + " 不要使用 Markdown 展示格式，例如 **加粗**、# 标题、* 列表、代码围栏；微信群里直接发自然纯文本。"
    )
    return (
        "<wechat-group-reply-policy>\n"
        "trigger_source: {source}\n"
        "{policy}\n"
        "</wechat-group-reply-policy>"
    ).format(source=source, policy=policy)


def _sticker_reply_percent() -> int:
    try:
        value = int(conf().get("wechat_group_sticker_reply_percent", 20) or 0)
    except (TypeError, ValueError):
        value = 20
    return min(max(value, 0), 100)
