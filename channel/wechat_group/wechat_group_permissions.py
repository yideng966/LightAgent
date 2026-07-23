# encoding:utf-8
"""Permission helpers for the WeChat group channel."""

from typing import Any, Dict, Iterable, List, Optional

from config import conf


DEFAULT_WECHAT_GROUP_ADMIN_REQUIRED_PERMISSIONS: Dict[str, bool] = {
    "knowledge_write": True,
    "memory_write": True,
    "wechat_group_memory_write": True,
    "wechat_group_profile_write": True,
    "wechat_group_learning": True,
    "self_evolution": True,
    "workspace_write": True,
    "wechat_group_config": True,
    "scheduler_write": True,
    "sticker_manage": True,
}

WECHAT_GROUP_ADMIN_PERMISSION_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "id": "knowledge_write",
        "label": "写入知识库",
        "summary": "限制普通成员把资料保存、导入或整理到知识库。",
        "blocked_behavior": "保存、导入、更新知识库或知识页。",
        "allowed_behavior": "查询、引用、总结已有知识库内容。",
        "examples": ["保存到知识库", "把这个资料学习一下"],
        "guard_layers": ["通道意图识别", "Agent 工具过滤", "Prompt 权限提示"],
        "affected_objects": ["knowledge/**", "write", "edit", "知识库索引"],
    },
    {
        "id": "memory_write",
        "label": "写入全局永久记忆",
        "summary": "限制普通成员写入全局长期记忆。",
        "blocked_behavior": "写入 MEMORY.md、每日记忆或全局长期记忆。",
        "allowed_behavior": "搜索、读取、基于记忆回答。",
        "examples": ["加入你的记忆库", "以后记住这件事"],
        "guard_layers": ["通道意图识别", "Agent 工具过滤", "Prompt 权限提示"],
        "affected_objects": ["MEMORY.md", "memory/**", "write", "edit"],
    },
    {
        "id": "wechat_group_memory_write",
        "label": "写入/禁用群永久记忆",
        "summary": "限制普通成员修改当前群的永久记忆。",
        "blocked_behavior": "新增、更新、禁用当前群永久记忆。",
        "allowed_behavior": "查询当前群记忆、基于群记忆回答。",
        "examples": ["记到本群永久记忆", "删掉这条群记忆"],
        "guard_layers": ["通道意图识别", "微信群工具过滤", "Prompt 权限提示"],
        "affected_objects": ["wechat_group_group_memories", "群记忆服务"],
    },
    {
        "id": "wechat_group_profile_write",
        "label": "管理群友画像",
        "summary": "限制普通成员手动修改群友画像和别名。",
        "blocked_behavior": "新增或修改群友画像、别名、常用词、发言风格。",
        "allowed_behavior": "查询群友画像、基于画像调整称呼。",
        "examples": ["把张三画像改成产品负责人", "给他加个别名"],
        "guard_layers": ["通道意图识别", "微信群工具过滤", "Prompt 权限提示"],
        "affected_objects": ["wechat_group_member_profiles", "wechat_group_member_profile_names"],
    },
    {
        "id": "wechat_group_learning",
        "label": "触发微信群学习沉淀",
        "summary": "限制普通成员手动触发归档学习与沉淀任务。",
        "blocked_behavior": "手动触发群学习任务，从归档批量沉淀画像或群记忆。",
        "allowed_behavior": "普通聊天过程中被动归档消息。",
        "examples": ["跑一次群学习", "把最近聊天沉淀一下"],
        "guard_layers": ["通道意图识别", "Web API 保护", "Prompt 权限提示"],
        "affected_objects": ["WechatGroupLearner", "learning runs"],
    },
    {
        "id": "self_evolution",
        "label": "触发自主进化",
        "summary": "限制普通成员要求机器人修改自身长期能力。",
        "blocked_behavior": "触发自主进化、技能沉淀、长期能力修改。",
        "allowed_behavior": "普通建议、反馈和问答。",
        "examples": ["你进化一下", "把这次经验沉淀成技能"],
        "guard_layers": ["通道意图识别", "Agent 工具过滤", "Prompt 权限提示"],
        "affected_objects": ["agent/evolution", "evolution_undo"],
    },
    {
        "id": "workspace_write",
        "label": "写入/编辑工作区文件",
        "summary": "限制普通成员要求机器人改写本地工作区。",
        "blocked_behavior": "创建、覆盖、编辑 workspace 文件或通过 shell 修改文件。",
        "allowed_behavior": "读取允许访问的文件摘要，给手动操作建议。",
        "examples": ["整理成 md 文件", "帮我改这个文件"],
        "guard_layers": ["通道意图识别", "Agent 工具过滤", "Prompt 权限提示"],
        "affected_objects": ["write", "edit", "bash", "agent_workspace"],
    },
    {
        "id": "wechat_group_config",
        "label": "修改微信群配置/人设",
        "summary": "限制普通成员通过群聊修改机器人配置。",
        "blocked_behavior": "修改人设、群配置、管理员、运行状态。",
        "allowed_behavior": "询问当前配置含义、请求说明。",
        "examples": ["修改人设", "把这个群设成自由回复"],
        "guard_layers": ["通道意图识别", "Prompt 权限提示", "配置 API 保护"],
        "affected_objects": ["wechat_group_* 配置", "人设 prompt"],
    },
    {
        "id": "scheduler_write",
        "label": "新增/修改定时任务",
        "summary": "限制普通成员创建或变更持久化定时任务。",
        "blocked_behavior": "创建、更新、删除定时任务或提醒。",
        "allowed_behavior": "查询任务说明、让机器人解释如何手动设置。",
        "examples": ["每天九点提醒我", "删除这个定时任务"],
        "guard_layers": ["通道意图识别", "Agent 工具过滤", "Prompt 权限提示"],
        "affected_objects": ["scheduler 工具", "任务存储"],
    },
    {
        "id": "sticker_manage",
        "label": "管理表情包/素材库",
        "summary": "限制普通成员修改群素材库。",
        "blocked_behavior": "收藏、禁用、改写表情包或素材库元数据。",
        "allowed_behavior": "搜索和发送已启用表情包。",
        "examples": ["禁用这个表情", "把这张图收进素材库"],
        "guard_layers": ["通道意图识别", "微信群工具过滤", "Prompt 权限提示"],
        "affected_objects": ["wechat_group_stickers", "素材目录"],
    },
]

PERMISSION_LABELS_ZH: Dict[str, str] = {
    "knowledge_write": "写入知识库",
    "memory_write": "写入永久记忆",
    "wechat_group_memory_write": "写入或禁用群永久记忆",
    "wechat_group_profile_write": "新增或修改群友画像",
    "wechat_group_learning": "触发微信群学习沉淀",
    "self_evolution": "触发自主进化",
    "workspace_write": "写入或编辑工作区文件",
    "wechat_group_config": "修改微信群人设或配置",
    "scheduler_write": "新增或修改定时任务",
    "sticker_manage": "管理表情包或素材库",
}

HIGH_RISK_TOOL_NAMES = {"write", "edit", "bash", "scheduler", "evolution_undo"}


def _cfg(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return config if isinstance(config, dict) else conf()


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def normalize_wechat_group_admin_members(value: Any) -> List[Dict[str, str]]:
    if not isinstance(value, list):
        return []
    result: List[Dict[str, str]] = []
    seen = set()
    for raw in value:
        if not isinstance(raw, dict):
            continue
        stable_room_id = _clean_text(raw.get("stable_room_id"))
        stable_member_id = _clean_text(raw.get("stable_member_id"))
        room_id = _clean_text(raw.get("room_id"))
        sender_id = _clean_text(raw.get("sender_id"))
        legacy_room_id = _clean_text(raw.get("legacy_room_id"))
        legacy_sender_id = _clean_text(raw.get("legacy_sender_id"))
        if not ((stable_room_id and stable_member_id) or (room_id and sender_id) or (legacy_room_id and legacy_sender_id)):
            continue
        key = (
            stable_room_id or room_id or legacy_room_id,
            stable_member_id or sender_id or legacy_sender_id,
        )
        if key in seen:
            continue
        seen.add(key)
        result.append({
            "stable_room_id": stable_room_id,
            "stable_member_id": stable_member_id,
            "room_id": room_id,
            "room_name": _clean_text(raw.get("room_name")),
            "sender_id": sender_id,
            "legacy_room_id": legacy_room_id,
            "legacy_sender_id": legacy_sender_id,
            "member_name": _clean_text(raw.get("member_name")),
            "sender_nickname": _clean_text(raw.get("sender_nickname")),
            "wechat_id": _clean_text(raw.get("wechat_id")),
            "identity_status": _clean_text(raw.get("identity_status") or raw.get("status")),
        })
    return result


def get_wechat_group_admin_members(config: Optional[Dict[str, Any]] = None) -> List[Dict[str, str]]:
    return normalize_wechat_group_admin_members(_cfg(config).get("wechat_group_admin_members", []))


def normalize_wechat_group_blacklist_members(value: Any) -> List[Dict[str, str]]:
    return normalize_wechat_group_admin_members(value)


def get_wechat_group_blacklist_members(config: Optional[Dict[str, Any]] = None) -> List[Dict[str, str]]:
    return normalize_wechat_group_blacklist_members(_cfg(config).get("wechat_group_blacklist_members", []))


def is_wechat_group_blacklisted(
    room_id: Any,
    sender_id: Any,
    config: Optional[Dict[str, Any]] = None,
    runtime_sender_id: Any = "",
) -> bool:
    room_text = _clean_text(room_id)
    sender_text = _clean_text(sender_id)
    runtime_sender_text = _clean_text(runtime_sender_id)
    if not sender_text and runtime_sender_text:
        sender_text = runtime_sender_text
    if not room_text or not sender_text:
        return False
    cfg = _cfg(config)
    members = get_wechat_group_blacklist_members(cfg)
    for item in members:
        identity_status = item.get("identity_status", "")
        if identity_status and identity_status != "confirmed":
            continue
        stable_match = (
            item.get("stable_room_id") == room_text
            and item.get("stable_member_id") == sender_text
        )
        current_runtime_match = (
            item.get("room_id") == room_text
            and item.get("sender_id") == sender_text
        )
        legacy_match = (
            item.get("legacy_room_id") == room_text
            and item.get("legacy_sender_id") in {sender_text, runtime_sender_text}
        )
        if stable_match or current_runtime_match or legacy_match:
            return True
    blocked_stable_ids = {
        _clean_text(item)
        for item in (cfg.get("wechat_group_blocked_stable_member_ids", []) or [])
        if _clean_text(item)
    }
    if sender_text in blocked_stable_ids:
        return True
    blocked_runtime_ids = {
        _clean_text(item)
        for item in (cfg.get("wechat_group_blocked_sender_ids", []) or [])
        if _clean_text(item)
    }
    return bool(
        (sender_text and sender_text in blocked_runtime_ids)
        or (runtime_sender_text and runtime_sender_text in blocked_runtime_ids)
    )


def build_wechat_group_blocked_sender_ids(
    room_id: Any,
    sender_id: Any,
    runtime_sender_id: Any = "",
    config: Optional[Dict[str, Any]] = None,
) -> List[str]:
    cfg = _cfg(config)
    blocked = []
    for value in list(cfg.get("wechat_group_blocked_stable_member_ids", []) or []):
        text = _clean_text(value)
        if text and text not in blocked:
            blocked.append(text)
    for value in list(cfg.get("wechat_group_blocked_sender_ids", []) or []):
        text = _clean_text(value)
        if text and text not in blocked:
            blocked.append(text)
    sender_text = _clean_text(sender_id)
    runtime_sender_text = _clean_text(runtime_sender_id)
    if is_wechat_group_blacklisted(room_id, sender_text, config=cfg, runtime_sender_id=runtime_sender_text):
        for value in (sender_text, runtime_sender_text):
            if value and value not in blocked:
                blocked.append(value)
    return blocked


def get_wechat_group_admin_required_permissions(
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, bool]:
    raw = _cfg(config).get("wechat_group_admin_required_permissions", {})
    normalized = dict(DEFAULT_WECHAT_GROUP_ADMIN_REQUIRED_PERMISSIONS)
    if isinstance(raw, dict):
        for key in normalized:
            if key in raw:
                normalized[key] = bool(raw.get(key))
    return normalized


def get_wechat_group_admin_permission_definitions(
    config: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    permissions = get_wechat_group_admin_required_permissions(config)
    result = []
    for item in WECHAT_GROUP_ADMIN_PERMISSION_DEFINITIONS:
        permission_id = item["id"]
        enriched = dict(item)
        enriched["default_enabled"] = DEFAULT_WECHAT_GROUP_ADMIN_REQUIRED_PERMISSIONS.get(permission_id, True)
        enriched["enabled"] = permissions.get(permission_id, True)
        result.append(enriched)
    return result


def is_wechat_group_admin(
    room_id: Any,
    sender_id: Any,
    config: Optional[Dict[str, Any]] = None,
) -> bool:
    room_text = _clean_text(room_id)
    sender_text = _clean_text(sender_id)
    if not room_text or not sender_text:
        return False
    cfg = _cfg(config)
    members = get_wechat_group_admin_members(cfg)
    if members:
        for item in members:
            identity_status = item.get("identity_status", "")
            if identity_status and identity_status != "confirmed":
                continue
            stable_match = (
                item.get("stable_room_id") == room_text
                and item.get("stable_member_id") == sender_text
            )
            current_runtime_match = (
                item.get("room_id") == room_text
                and item.get("sender_id") == sender_text
            )
            legacy_match = (
                item.get("legacy_room_id") == room_text
                and item.get("legacy_sender_id") == sender_text
            )
            if stable_match or current_runtime_match or legacy_match:
                return True
        return False
    legacy_ids = cfg.get("wechat_group_admin_sender_ids", []) or []
    return sender_text in {str(item).strip() for item in legacy_ids if str(item).strip()}


def detect_wechat_group_admin_required_permissions(text: Any) -> List[str]:
    content = _clean_text(text)
    if not content:
        return []
    detected: List[str] = []

    def add(permission_id: str) -> None:
        if permission_id not in detected:
            detected.append(permission_id)

    knowledge_words = ("知识库", "知识页", "学习资料", "保存到知识", "写入知识")
    memory_words = ("永久记忆", "长期记忆", "记忆库", "以后记住", "加入你的记忆", "记住这件事")
    group_memory_words = ("本群永久记忆", "群永久记忆", "群记忆", "删掉这条群记忆", "记到本群")
    profile_words = ("群友画像", "画像", "别名", "常用词", "发言风格")
    learning_words = ("群学习", "沉淀一下", "学习沉淀", "归档学习", "最近聊天沉淀")
    evolution_words = ("自主进化", "自我进化", "你进化", "沉淀成技能", "进化一下")
    workspace_words = ("写入工作区", "编辑文件", "改这个文件", "整理成 md", "整理成md", "保存成文件", "创建文件")
    config_words = ("修改人设", "改人设", "群配置", "自由回复", "管理员", "运行状态")
    scheduler_words = ("定时任务", "提醒我", "每天", "每周", "删除这个定时")
    sticker_words = ("表情包", "素材库", "禁用这个表情", "收进素材")

    if any(word in content for word in knowledge_words):
        add("knowledge_write")
    if any(word in content for word in group_memory_words):
        add("wechat_group_memory_write")
    if any(word in content for word in memory_words):
        add("memory_write")
    if any(word in content for word in profile_words):
        add("wechat_group_profile_write")
    if any(word in content for word in learning_words):
        add("wechat_group_learning")
    if any(word in content for word in evolution_words):
        add("self_evolution")
    if any(word in content for word in workspace_words):
        add("workspace_write")
    if any(word in content for word in config_words):
        add("wechat_group_config")
    if any(word in content for word in scheduler_words):
        add("scheduler_write")
    if any(word in content for word in sticker_words):
        add("sticker_manage")

    return detected


def get_blocked_admin_permissions_for_text(
    text: Any,
    room_id: Any,
    sender_id: Any,
    config: Optional[Dict[str, Any]] = None,
) -> List[str]:
    if is_wechat_group_admin(room_id, sender_id, config=config):
        return []
    required = get_wechat_group_admin_required_permissions(config)
    detected = detect_wechat_group_admin_required_permissions(text)
    return [permission_id for permission_id in detected if required.get(permission_id, True)]


def build_wechat_group_admin_reject_message(permission_ids: Iterable[str]) -> str:
    labels = [
        PERMISSION_LABELS_ZH.get(permission_id, permission_id)
        for permission_id in permission_ids
    ]
    if labels:
        return "这个操作需要当前群管理员触发：{}。".format("、".join(labels))
    return "这个操作需要当前群管理员触发。"


def build_wechat_group_admin_policy_block(
    room_id: Any,
    sender_id: Any,
    config: Optional[Dict[str, Any]] = None,
    identity_confirmed: bool = True,
) -> str:
    is_admin = bool(identity_confirmed) and is_wechat_group_admin(room_id, sender_id, config=config)
    permissions = get_wechat_group_admin_required_permissions(config)
    enabled_labels = [
        PERMISSION_LABELS_ZH.get(permission_id, permission_id)
        for permission_id, enabled in permissions.items()
        if enabled
    ]
    if not enabled_labels:
        return ""
    role = "admin" if is_admin else "member"
    return (
        "<wechat-group-admin-policy>\n"
        f"current_sender_role: {role}\n"
        "admin_scoped_by: stable_room_id + stable_member_id\n"
        "admin_required_permissions: {}\n"
        "</wechat-group-admin-policy>"
    ).format("、".join(enabled_labels))


def filter_wechat_group_tools_for_permissions(
    tools: Iterable[Any],
    room_id: Any,
    sender_id: Any,
    config: Optional[Dict[str, Any]] = None,
) -> List[Any]:
    tool_list = list(tools or [])
    if is_wechat_group_admin(room_id, sender_id, config=config):
        return tool_list
    permissions = get_wechat_group_admin_required_permissions(config)
    blocked_names = set()
    if permissions.get("workspace_write"):
        blocked_names.update({"write", "edit", "bash"})
    if permissions.get("scheduler_write"):
        blocked_names.add("scheduler")
    if permissions.get("self_evolution"):
        blocked_names.add("evolution_undo")
    if permissions.get("wechat_group_memory_write"):
        blocked_names.update({"wechat_group_memory_write", "wechat_group_memory_disable"})
    if permissions.get("wechat_group_profile_write"):
        blocked_names.update({"wechat_group_profile_write", "wechat_group_profile_update"})
    if permissions.get("sticker_manage"):
        blocked_names.update({"wechat_group_sticker_disable", "wechat_group_sticker_collect"})
    return [
        tool
        for tool in tool_list
        if _clean_text(getattr(tool, "name", "")) not in blocked_names
    ]
