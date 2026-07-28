# encoding:utf-8
"""微信群成员进出事件的配置、模板与图片路径规则。"""

import os
import re
from io import BytesIO
from datetime import datetime
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any, Dict, Iterable, Mapping, Optional

from config import conf


WECHAT_GROUP_MEMBERSHIP_EVENT_JOIN = "join"
WECHAT_GROUP_MEMBERSHIP_EVENT_LEAVE = "leave"
WECHAT_GROUP_MEMBERSHIP_CONTENT_TEXT = "text"
WECHAT_GROUP_MEMBERSHIP_CONTENT_IMAGE = "image"
WECHAT_GROUP_MEMBERSHIP_IMAGE_DIR = "images/wechat_group_membership"
WECHAT_GROUP_MEMBERSHIP_TEMPLATE_MAX_LENGTH = 500
WECHAT_GROUP_MEMBERSHIP_IMAGE_MAX_BYTES = 5 * 1024 * 1024
WECHAT_GROUP_MEMBERSHIP_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
WECHAT_GROUP_MEMBERSHIP_IMAGE_MAX_DIMENSION = 16384
WECHAT_GROUP_MEMBERSHIP_IMAGE_MAX_PIXELS = 40000000

_IMAGE_FORMAT_EXTENSIONS = {
    "JPEG": {".jpg", ".jpeg"},
    "PNG": {".png"},
    "GIF": {".gif"},
    "WEBP": {".webp"},
}

_COMMON_PLACEHOLDERS = (
    "room_name",
    "member_name",
    "member_names",
    "member_count",
    "event_time",
    "bot_name",
)
_EVENT_PLACEHOLDERS = {
    WECHAT_GROUP_MEMBERSHIP_EVENT_JOIN: _COMMON_PLACEHOLDERS + ("inviter_name",),
    WECHAT_GROUP_MEMBERSHIP_EVENT_LEAVE: _COMMON_PLACEHOLDERS + ("remover_name",),
}
_EVENT_CONFIG = {
    WECHAT_GROUP_MEMBERSHIP_EVENT_JOIN: {
        "prefix": "wechat_group_join_welcome",
        "default_text": "欢迎加入群聊！",
    },
    WECHAT_GROUP_MEMBERSHIP_EVENT_LEAVE: {
        "prefix": "wechat_group_leave_notice",
        "default_text": "{member_names} 已离开群聊。",
    },
}
_PLACEHOLDER_PATTERN = re.compile(r"\{([^{}]*)\}")


class WechatGroupMembershipNoticeConfigError(ValueError):
    """成员消息配置不合法。"""


def membership_notice_placeholders(event_type: str) -> tuple:
    event = _normalize_event_type(event_type)
    return tuple("{" + name + "}" for name in _EVENT_PLACEHOLDERS[event])


def validate_membership_notice_template(
    text: Any,
    event_type: str,
    required: bool = True,
) -> str:
    event = _normalize_event_type(event_type)
    normalized = str(text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if required and not normalized:
        raise WechatGroupMembershipNoticeConfigError("文本内容不能为空")
    if len(normalized) > WECHAT_GROUP_MEMBERSHIP_TEMPLATE_MAX_LENGTH:
        raise WechatGroupMembershipNoticeConfigError(
            "文本内容不能超过 {} 个字符".format(WECHAT_GROUP_MEMBERSHIP_TEMPLATE_MAX_LENGTH)
        )
    allowed = set(_EVENT_PLACEHOLDERS[event])
    placeholders = _PLACEHOLDER_PATTERN.findall(normalized)
    unknown = [name for name in placeholders if name not in allowed]
    remaining = _PLACEHOLDER_PATTERN.sub("", normalized)
    if unknown or "{" in remaining or "}" in remaining:
        invalid = "{" + unknown[0] + "}" if unknown else "不完整的占位符"
        raise WechatGroupMembershipNoticeConfigError("不支持的占位符：{}".format(invalid))
    return normalized


def render_membership_notice_template(
    text: Any,
    event_type: str,
    values: Mapping[str, Any],
) -> str:
    event = _normalize_event_type(event_type)
    rendered = validate_membership_notice_template(text, event, required=True)
    for name in _EVENT_PLACEHOLDERS[event]:
        rendered = rendered.replace("{" + name + "}", str(values.get(name, "")))
    return rendered


def build_membership_notice_template_values(
    event_type: str,
    payload: Mapping[str, Any],
    now: Optional[float] = None,
) -> Dict[str, str]:
    event = _normalize_event_type(event_type)
    members = [item for item in (payload.get("members") or []) if isinstance(item, Mapping)]
    member_fallback = "新成员" if event == WECHAT_GROUP_MEMBERSHIP_EVENT_JOIN else "群成员"
    names = [_best_visible_name(item, member_fallback) for item in members]
    if not names:
        names = [member_fallback]
    operator_key = "inviter" if event == WECHAT_GROUP_MEMBERSHIP_EVENT_JOIN else "remover"
    operator_fallback = "群成员" if event == WECHAT_GROUP_MEMBERSHIP_EVENT_JOIN else "群管理员"
    operator = payload.get(operator_key) if isinstance(payload.get(operator_key), Mapping) else {}
    values = {
        "room_name": _clean_visible_text(payload.get("room_name")) or "当前群",
        "member_name": names[0],
        "member_names": "、".join(names),
        "member_count": str(len(members)),
        "event_time": _format_event_time(payload.get("timestamp"), now=now),
        "bot_name": _clean_visible_text(payload.get("self_name")) or "机器人",
    }
    values["inviter_name" if event == WECHAT_GROUP_MEMBERSHIP_EVENT_JOIN else "remover_name"] = (
        _best_visible_name(operator, operator_fallback)
    )
    return values


def normalize_membership_notice_image_path(value: Any, required: bool = False) -> str:
    text = str(value or "").strip().replace("\\", "/")
    if not text:
        if required:
            raise WechatGroupMembershipNoticeConfigError("请先上传图片")
        return ""
    if "://" in text or text.startswith("//"):
        raise WechatGroupMembershipNoticeConfigError("图片路径必须是工作区内的相对路径")
    posix_path = PurePosixPath(text)
    windows_path = PureWindowsPath(text)
    if posix_path.is_absolute() or windows_path.is_absolute() or ".." in posix_path.parts:
        raise WechatGroupMembershipNoticeConfigError("图片路径必须是工作区内的相对路径")
    normalized = posix_path.as_posix()
    if normalized.startswith("./"):
        normalized = normalized[2:]
    prefix = WECHAT_GROUP_MEMBERSHIP_IMAGE_DIR + "/"
    if not normalized.startswith(prefix) or len(normalized) <= len(prefix):
        raise WechatGroupMembershipNoticeConfigError("图片不在进退群消息目录内")
    if PurePosixPath(normalized).suffix.lower() not in WECHAT_GROUP_MEMBERSHIP_IMAGE_EXTENSIONS:
        raise WechatGroupMembershipNoticeConfigError("图片格式仅支持 JPEG、PNG、GIF 或 WEBP")
    return normalized


def resolve_membership_notice_image_path(
    workspace: str,
    relative_path: Any,
    require_file: bool = True,
) -> str:
    normalized = normalize_membership_notice_image_path(relative_path, required=True)
    workspace_root = os.path.realpath(os.path.expanduser(str(workspace or "~/lightagent")))
    image_root = os.path.realpath(os.path.join(workspace_root, *WECHAT_GROUP_MEMBERSHIP_IMAGE_DIR.split("/")))
    resolved = os.path.realpath(os.path.join(workspace_root, *normalized.split("/")))
    try:
        within_root = os.path.commonpath([image_root, resolved]) == image_root
    except ValueError:
        within_root = False
    if not within_root:
        raise WechatGroupMembershipNoticeConfigError("图片路径越界")
    if require_file and not os.path.isfile(resolved):
        raise WechatGroupMembershipNoticeConfigError("配置的图片不存在")
    return resolved


def validate_membership_notice_image_bytes(content: bytes, file_name: Any = "") -> str:
    if not isinstance(content, bytes) or not content:
        raise WechatGroupMembershipNoticeConfigError("图片内容为空")
    if len(content) > WECHAT_GROUP_MEMBERSHIP_IMAGE_MAX_BYTES:
        raise WechatGroupMembershipNoticeConfigError("图片不能超过 5 MiB")
    try:
        from PIL import Image

        with Image.open(BytesIO(content)) as image:
            image_format = str(image.format or "").upper()
            width, height = image.size
            if image_format not in _IMAGE_FORMAT_EXTENSIONS:
                raise WechatGroupMembershipNoticeConfigError("图片格式仅支持 JPEG、PNG、GIF 或 WEBP")
            if (
                width <= 0
                or height <= 0
                or width > WECHAT_GROUP_MEMBERSHIP_IMAGE_MAX_DIMENSION
                or height > WECHAT_GROUP_MEMBERSHIP_IMAGE_MAX_DIMENSION
                or width * height > WECHAT_GROUP_MEMBERSHIP_IMAGE_MAX_PIXELS
            ):
                raise WechatGroupMembershipNoticeConfigError("图片尺寸无效或过大")
            image.verify()
    except WechatGroupMembershipNoticeConfigError:
        raise
    except Exception as exc:
        raise WechatGroupMembershipNoticeConfigError("无法识别图片内容") from exc
    configured_extension = PurePosixPath(str(file_name or "").replace("\\", "/")).suffix.lower()
    allowed_extensions = _IMAGE_FORMAT_EXTENSIONS[image_format]
    if configured_extension and configured_extension not in allowed_extensions:
        raise WechatGroupMembershipNoticeConfigError("图片扩展名与实际格式不一致")
    return configured_extension or sorted(allowed_extensions)[0]


def validate_membership_notice_image_file(path: str) -> str:
    try:
        size = os.path.getsize(path)
    except OSError as exc:
        raise WechatGroupMembershipNoticeConfigError("配置的图片不存在") from exc
    if size <= 0 or size > WECHAT_GROUP_MEMBERSHIP_IMAGE_MAX_BYTES:
        raise WechatGroupMembershipNoticeConfigError("图片为空或超过 5 MiB")
    try:
        with open(path, "rb") as file_obj:
            content = file_obj.read(WECHAT_GROUP_MEMBERSHIP_IMAGE_MAX_BYTES + 1)
    except OSError as exc:
        raise WechatGroupMembershipNoticeConfigError("无法读取配置的图片") from exc
    detected_extension = validate_membership_notice_image_bytes(content)
    configured_extension = os.path.splitext(path)[1].lower()
    image_format_extensions = next(
        extensions
        for extensions in _IMAGE_FORMAT_EXTENSIONS.values()
        if detected_extension in extensions
    )
    if configured_extension not in image_format_extensions:
        raise WechatGroupMembershipNoticeConfigError("图片扩展名与实际格式不一致")
    return detected_extension


def normalize_wechat_group_membership_notice_config(
    config: Optional[Mapping[str, Any]] = None,
    selected_room_ids: Optional[Iterable[Any]] = None,
    strict: bool = False,
) -> Dict[str, Any]:
    source = conf() if config is None else config
    if selected_room_ids is None:
        selected_room_ids = source.get("wechat_group_stable_room_ids", []) or []
    selected = {
        str(room_id or "").strip()
        for room_id in selected_room_ids
        if str(room_id or "").strip().startswith("wgr_")
    }
    result: Dict[str, Any] = {}
    for event, definition in _EVENT_CONFIG.items():
        prefix = definition["prefix"]
        enabled = _normalize_bool(source.get(prefix + "_enabled", False))
        content_type = _normalize_content_type(source.get(prefix + "_content_type", "text"))
        raw_text = source.get(prefix + "_text", definition["default_text"])
        raw_image_path = source.get(prefix + "_image_path", "")
        try:
            text = validate_membership_notice_template(
                raw_text,
                event,
                required=enabled and content_type == WECHAT_GROUP_MEMBERSHIP_CONTENT_TEXT,
            )
            image_path = normalize_membership_notice_image_path(
                raw_image_path,
                required=enabled and content_type == WECHAT_GROUP_MEMBERSHIP_CONTENT_IMAGE,
            )
        except WechatGroupMembershipNoticeConfigError:
            if strict:
                raise
            enabled = False
            text = definition["default_text"]
            image_path = ""
        overrides = _normalize_room_overrides(
            source.get(prefix + "_room_overrides", []),
            event,
            selected,
            strict,
        )
        result[prefix + "_enabled"] = enabled
        result[prefix + "_content_type"] = content_type
        result[prefix + "_text"] = text
        result[prefix + "_image_path"] = image_path
        result[prefix + "_room_overrides"] = overrides
    return result


def resolve_wechat_group_membership_notice(
    event_type: str,
    stable_room_id: str,
    config: Optional[Mapping[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    event = _normalize_event_type(event_type)
    room_id = str(stable_room_id or "").strip()
    if not room_id.startswith("wgr_"):
        return None
    source = conf() if config is None else config
    selected_room_ids = {
        str(value or "").strip()
        for value in (source.get("wechat_group_stable_room_ids", []) or [])
        if str(value or "").strip().startswith("wgr_")
    }
    if room_id not in selected_room_ids:
        return None
    normalized = normalize_wechat_group_membership_notice_config(
        source,
        selected_room_ids=selected_room_ids,
        strict=False,
    )
    prefix = _EVENT_CONFIG[event]["prefix"]
    override = next(
        (
            item for item in normalized[prefix + "_room_overrides"]
            if item.get("stable_room_id") == room_id
        ),
        None,
    )
    if override and override["policy"] == "disabled":
        return None
    if override and override["policy"] == "custom":
        return {**override, "source": "room"}
    if not normalized[prefix + "_enabled"]:
        return None
    return {
        "policy": "custom",
        "content_type": normalized[prefix + "_content_type"],
        "text": normalized[prefix + "_text"],
        "image_path": normalized[prefix + "_image_path"],
        "source": "global",
    }


def _normalize_room_overrides(raw, event: str, selected: set, strict: bool) -> list:
    if not isinstance(raw, list):
        if strict:
            raise WechatGroupMembershipNoticeConfigError("按群配置必须是列表")
        return []
    normalized: Dict[str, Dict[str, Any]] = {}
    for item in raw:
        if not isinstance(item, Mapping):
            if strict:
                raise WechatGroupMembershipNoticeConfigError("按群配置项格式错误")
            continue
        room_id = str(item.get("stable_room_id") or "").strip()
        policy = str(item.get("policy") or "").strip().lower()
        try:
            if not room_id.startswith("wgr_") or room_id not in selected:
                raise WechatGroupMembershipNoticeConfigError("按群配置只能使用当前已选择的稳定群")
            if policy in ("", "inherit", "global"):
                normalized.pop(room_id, None)
                continue
            if policy not in {"custom", "disabled"}:
                raise WechatGroupMembershipNoticeConfigError("按群策略仅支持自定义或关闭")
            if policy == "disabled":
                normalized[room_id] = {
                    "stable_room_id": room_id,
                    "policy": "disabled",
                    "content_type": "text",
                    "text": "",
                    "image_path": "",
                }
                continue
            content_type = _normalize_content_type(item.get("content_type", "text"))
            text = validate_membership_notice_template(
                item.get("text", ""),
                event,
                required=content_type == WECHAT_GROUP_MEMBERSHIP_CONTENT_TEXT,
            )
            image_path = normalize_membership_notice_image_path(
                item.get("image_path", ""),
                required=content_type == WECHAT_GROUP_MEMBERSHIP_CONTENT_IMAGE,
            )
            normalized[room_id] = {
                "stable_room_id": room_id,
                "policy": "custom",
                "content_type": content_type,
                "text": text,
                "image_path": image_path,
            }
        except WechatGroupMembershipNoticeConfigError:
            normalized.pop(room_id, None)
            if strict:
                raise
    return list(normalized.values())


def _normalize_event_type(value: Any) -> str:
    event = str(value or "").strip().lower()
    if event not in _EVENT_CONFIG:
        raise WechatGroupMembershipNoticeConfigError("不支持的成员事件类型")
    return event


def _normalize_content_type(value: Any) -> str:
    value = str(value or "").strip().lower()
    if value == WECHAT_GROUP_MEMBERSHIP_CONTENT_IMAGE:
        return WECHAT_GROUP_MEMBERSHIP_CONTENT_IMAGE
    return WECHAT_GROUP_MEMBERSHIP_CONTENT_TEXT


def _normalize_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _clean_visible_text(value: Any) -> str:
    text = str(value or "").strip()
    return " ".join(text.split())


def _looks_like_raw_member_name(value: Any, sender_id: Any = "") -> bool:
    text = _clean_visible_text(value)
    if not text:
        return True
    normalized = text.lstrip("@")
    sender_text = _clean_visible_text(sender_id)
    if sender_text and normalized == sender_text.lstrip("@"):
        return True
    if normalized.startswith("wxid_"):
        return True
    return bool(text.startswith("@") and re.fullmatch(r"[0-9A-Za-z_-]{12,}", normalized))


def _best_visible_name(item: Mapping[str, Any], fallback: str) -> str:
    sender_id = item.get("sender_id") or item.get("id") or ""
    for key in ("display_name", "room_alias", "sender_nickname", "name"):
        name = _clean_visible_text(item.get(key))
        if name and not _looks_like_raw_member_name(name, sender_id):
            return name
    return fallback


def _format_event_time(timestamp: Any, now: Optional[float] = None) -> str:
    try:
        value = float(timestamp)
        if value <= 0:
            raise ValueError
    except (TypeError, ValueError):
        value = float(now if now is not None else datetime.now().timestamp())
    return datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M:%S")
