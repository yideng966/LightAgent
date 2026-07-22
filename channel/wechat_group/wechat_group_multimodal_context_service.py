"""Global multimodal prompt context assembly for WeChat group messages."""

import re
import time
from typing import Any, Dict, List, Optional

from bridge.context import ContextType
from channel.wechat_group.wechat_group_transport import (
    detect_wechat_transport_message_type,
    project_wechat_message_type,
)
from common.expired_dict import ExpiredDict
from common.log import logger
from config import conf


IMAGE_UNDERSTANDING_FAILURE_SUMMARY = "图片理解失败：视觉模型调用失败。"
IMAGE_UNDERSTANDING_EMPTY_SUMMARY = "图片理解未返回内容。"
IMAGE_REFERENCE_AMBIGUOUS_SUMMARY = "图片引用无法唯一定位，不得猜测图片内容；请让用户重新引用目标图片或重新发送。"


def _as_bool(value, default=False) -> bool:
    if value is None:
        return bool(default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


def _clamp_int(value, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except Exception:
        number = int(default)
    return max(int(minimum), min(int(maximum), number))


def get_wechat_group_multimodal_context_config() -> Dict[str, Any]:
    cfg = conf()
    return {
        "enabled": _as_bool(cfg.get("wechat_group_multimodal_context_enabled", True), True),
        "image_understanding_enabled": _as_bool(
            cfg.get("wechat_group_multimodal_image_understanding_context_enabled", True),
            True,
        ),
        "free_reply_image_context_enabled": _as_bool(
            cfg.get("wechat_group_multimodal_free_reply_image_context_enabled", False),
            False,
        ),
        "same_sender_window_seconds": _clamp_int(
            cfg.get("wechat_group_multimodal_same_sender_window_seconds", 120),
            120,
            5,
            600,
        ),
        "unique_image_window_seconds": _clamp_int(
            cfg.get("wechat_group_multimodal_unique_image_window_seconds", 120),
            120,
            5,
            600,
        ),
        "quote_sender_window_minutes": _clamp_int(
            cfg.get("wechat_group_multimodal_quote_sender_window_minutes", 30),
            30,
            1,
            120,
        ),
        "max_recent_messages": _clamp_int(
            cfg.get("wechat_group_multimodal_max_recent_messages", 20),
            20,
            1,
            100,
        ),
    }


def _looks_like_image_reference_question(text: str) -> bool:
    value = re.sub(r"\s+", "", str(text or "")).strip()
    if not value:
        return False
    if re.search(r"[［\[]图片[\]］]", value) and re.search(
        r"哪(个|一个|款|种)|什么|啥|谁|怎么看|怎么样|意思|识别|看看|看我|看下|看一下|\?|？",
        value,
    ):
        return True
    return bool(
        re.search(
            r"(识别|看看|看下|看一下|分析|描述|总结|解释).{0,20}(图|图片|照片|截图|这张|这个)"
            r"|这张(图|图片|照片|截图)|图里|图上|图片里|图片上|"
            r"(这|这个|这张|这图|图片|图里|图上).{0,8}(真|真假|真的|靠谱吗|啥|什么|意思|怎么样)"
            r"|.{1,12}(刚发|发的|发了|发过).{0,4}(啥|什么|啥内容|什么内容)(了|呀|啊|呢|吗|\?|？)?$"
            r"|.{1,12}发(啥|什么)(了|呀|啊|呢|吗|\?|？)?$"
            r"|真的假的|真吗|靠谱吗|啥意思|什么意思|这个呢|这啥|这是啥|怎么样",
            value,
        )
    )


def _is_image_item(item: Any) -> bool:
    return bool(
        isinstance(item, dict)
        and project_wechat_message_type(item.get("message_type"), item.get("text")) == "image"
        and str(item.get("media_path") or "").strip()
    )


def _format_sender(name, sender_id) -> str:
    display_name = str(name or "").strip()
    display_id = str(sender_id or "").strip()
    if display_name and display_id and display_name != display_id:
        return "{} ({})".format(display_name, display_id)
    return display_name or display_id


def _trim(value, limit: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    return "{}...".format(text[: max(int(limit or 0) - 3, 0)])


def _format_timestamp(value: Any) -> str:
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(value)))
    except Exception:
        return ""


def _normalize_quote_message_type(value) -> str:
    raw = str(value or "").strip().lower()
    if raw in ("1", "text", "7"):
        return "text"
    if raw in ("3", "image"):
        return "image"
    if raw in ("47", "sticker", "emoticon"):
        return "sticker"
    if raw in ("43", "video"):
        return "video"
    if raw in ("49", "app", "link", "forward"):
        return "app"
    return raw


def _is_successful_image_summary(summary: str) -> bool:
    value = str(summary or "").strip()
    return bool(
        value
        and value != IMAGE_UNDERSTANDING_EMPTY_SUMMARY
        and not value.startswith("图片理解失败")
    )


def _scope_text(value) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def _stable_room_scope(msg) -> str:
    return (
        _scope_text(getattr(msg, "wechat_group_stable_room_id", ""))
        or _scope_text(getattr(msg, "stable_room_id", ""))
        or _scope_text(getattr(msg, "other_user_id", ""))
    )


def _stable_member_scope(msg) -> str:
    return (
        _scope_text(getattr(msg, "wechat_group_stable_member_id", ""))
        or _scope_text(getattr(msg, "stable_member_id", ""))
        or _scope_text(getattr(msg, "actual_user_id", ""))
    )


def _runtime_sender_scope(msg) -> str:
    return (
        _scope_text(getattr(msg, "runtime_sender_id", ""))
        or _scope_text(getattr(msg, "actual_user_id", ""))
    )


class WechatGroupMultimodalContextService:
    def __init__(self, archive):
        self.archive = archive
        self._summary_cache = None
        self._summary_cache_seconds = 0

    def build_context(
        self,
        msg,
        query: str,
        trigger_source: str = "",
        now=None,
        include_quote: bool = True,
    ) -> Dict[str, Any]:
        cfg = get_wechat_group_multimodal_context_config()
        diagnostics = {
            "enabled": cfg["enabled"],
            "image_understanding_enabled": cfg["image_understanding_enabled"],
            "trigger_source": str(trigger_source or ""),
            "reason": "",
            "skipped_reason": "",
            "matched_image_message_id": "",
            "matched_image_sender_id": "",
            "summary_generated": False,
        }
        if not cfg["enabled"]:
            diagnostics["skipped_reason"] = "disabled"
            return {"block": "", "matched_images": [], "diagnostics": diagnostics}

        sections: List[str] = []
        matched_images: List[Dict[str, Any]] = []
        if cfg["image_understanding_enabled"] and self._image_context_allowed(trigger_source):
            image_match = self._select_image_candidate(msg, query, trigger_source, cfg, now=now)
            if image_match.get("item") or image_match.get("skipped_reason") != "not_image_reference_question":
                item = image_match.get("item") or {}
                quote = getattr(msg, "quote", {}) or {}
                quote_diagnostics = getattr(msg, "quote_diagnostics", {}) or {}
                logger.info(
                    "[wechat_group] multimodal image selection: "
                    "quote_message_id={} raw_app_type={} raw_payload_status={} raw_payload_source={} "
                    "quote_parse_status={} reason={} skipped_reason={} matched_message_id={}".format(
                        str(quote.get("message_id") or "") if isinstance(quote, dict) else "",
                        _scope_text(getattr(msg, "raw_app_type", "")),
                        _scope_text(quote_diagnostics.get("status")) if isinstance(quote_diagnostics, dict) else "",
                        _scope_text(quote_diagnostics.get("source")) if isinstance(quote_diagnostics, dict) else "",
                        _scope_text(quote_diagnostics.get("parse_status")) if isinstance(quote_diagnostics, dict) else "",
                        str(image_match.get("reason") or ""),
                        str(image_match.get("skipped_reason") or ""),
                        str(item.get("message_id") or ""),
                    )
                )
            if image_match.get("item"):
                image_section = self._build_image_understanding_section(image_match)
                if image_section:
                    sections.append(image_section)
                    item = image_match["item"]
                    diagnostics["reason"] = image_match.get("reason", "")
                    diagnostics["matched_image_message_id"] = str(item.get("message_id") or "")
                    diagnostics["matched_image_sender_id"] = str(item.get("sender_id") or "")
                    diagnostics["matched_image_stable_member_id"] = str(item.get("stable_member_id") or "")
                    diagnostics["summary_generated"] = bool(image_match.get("summary_generated"))
                    matched_images.append({
                        "reason": image_match.get("reason", ""),
                        "message_id": str(item.get("message_id") or ""),
                        "sender_id": str(item.get("sender_id") or ""),
                        "stable_member_id": str(item.get("stable_member_id") or ""),
                        "sender_name": str(item.get("sender_nickname") or ""),
                        "summary": image_match.get("summary", ""),
                    })
            elif image_match.get("skipped_reason"):
                skipped_reason = image_match.get("skipped_reason", "")
                diagnostics["skipped_reason"] = skipped_reason
                if skipped_reason in ("ambiguous_same_sender_images", "ambiguous_recent_images"):
                    sections.append(
                        "[image_understanding]\nstatus: ambiguous_reference\nsummary: {}".format(
                            IMAGE_REFERENCE_AMBIGUOUS_SUMMARY
                        )
                    )

        if include_quote:
            quote_section = self._build_quote_section(msg)
            if quote_section:
                sections.append(quote_section)
        forward_section = self._build_forward_section(msg)
        if forward_section:
            sections.append(forward_section)
        video_section = self._build_video_section(msg)
        if video_section:
            sections.append(video_section)

        if not sections:
            if not diagnostics["skipped_reason"]:
                diagnostics["skipped_reason"] = "no_multimodal_context"
            return {"block": "", "matched_images": matched_images, "diagnostics": diagnostics}
        block = "<wechat-group-multimodal>\n{}\n</wechat-group-multimodal>".format("\n\n".join(sections))
        return {"block": block, "matched_images": matched_images, "diagnostics": diagnostics}

    @staticmethod
    def _image_context_allowed(trigger_source: str) -> bool:
        source = str(trigger_source or "").strip()
        if source == "free_reply":
            return _as_bool(conf().get("wechat_group_multimodal_free_reply_image_context_enabled", False), False)
        if source in ("direct_reply", "quote_self", "image_message"):
            return _as_bool(conf().get("wechat_group_image_understanding_enabled", True), True)
        return True

    def _select_image_candidate(self, msg, query: str, trigger_source: str, cfg: Dict[str, Any], now=None) -> Dict[str, Any]:
        current = self._current_image_item(msg)
        if current:
            return {"item": current, "reason": "current_image"}

        quoted = self._find_quoted_image(msg)
        if quoted:
            return {"item": quoted, "reason": "quoted_image"}

        quoted_sender = self._find_quoted_sender_recent_image(msg, cfg, now=now)
        if quoted_sender:
            return {"item": quoted_sender, "reason": "quoted_sender_recent_image"}

        if not _looks_like_image_reference_question(query):
            return {"skipped_reason": "not_image_reference_question"}

        effective_now = self._coerce_now(now, msg)
        recent = self._recent_images(
            msg,
            seconds=max(cfg["same_sender_window_seconds"], cfg["unique_image_window_seconds"]),
            limit=cfg["max_recent_messages"],
            now=effective_now,
        )
        stable_member_id = _stable_member_scope(msg)
        runtime_sender_id = _runtime_sender_scope(msg)
        same_sender = [
            item for item in recent
            if (
                (
                    stable_member_id
                    and str(item.get("stable_member_id") or "").strip() == stable_member_id
                ) or (
                    not str(item.get("stable_member_id") or "").strip()
                    and str(item.get("sender_id") or "").strip() == runtime_sender_id
                )
            )
            and int(item.get("created_at") or 0) >= effective_now - cfg["same_sender_window_seconds"]
        ]
        if len(same_sender) == 1:
            return {"item": same_sender[-1], "reason": "same_sender_recent_image"}
        if len(same_sender) > 1:
            return {"item": same_sender[-1], "reason": "same_sender_latest_image"}

        unique_window_images = [
            item for item in recent
            if int(item.get("created_at") or 0) >= effective_now - cfg["unique_image_window_seconds"]
        ]
        if len(unique_window_images) == 1:
            return {"item": unique_window_images[0], "reason": "unique_recent_image"}
        if len(unique_window_images) > 1:
            return {"skipped_reason": "ambiguous_recent_images"}
        return {"skipped_reason": "no_recent_image"}

    @staticmethod
    def _coerce_now(now, msg) -> int:
        try:
            return int(now)
        except Exception:
            pass
        try:
            return int(getattr(msg, "create_time", None))
        except Exception:
            return int(time.time())

    @staticmethod
    def _current_image_item(msg) -> Optional[Dict[str, Any]]:
        message_type = str(getattr(msg, "message_type", "") or "").lower()
        if message_type != "image" and getattr(msg, "ctype", None) != ContextType.IMAGE:
            return None
        media_path = str(getattr(msg, "media_path", "") or getattr(msg, "content", "") or "").strip()
        if not media_path:
            return None
        return {
            "message_id": str(getattr(msg, "msg_id", "") or "").strip(),
            "message_type": "image",
            "media_path": media_path,
            "sender_nickname": str(getattr(msg, "actual_user_nickname", "") or "").strip(),
            "sender_id": str(getattr(msg, "actual_user_id", "") or "").strip(),
            "stable_member_id": _stable_member_scope(msg),
            "runtime_sender_id": _runtime_sender_scope(msg),
            "created_at": int(getattr(msg, "create_time", None) or time.time()),
        }

    def _find_quoted_image(self, msg) -> Optional[Dict[str, Any]]:
        quote = getattr(msg, "quote", {}) or {}
        if not isinstance(quote, dict):
            return None
        quote_message_id = str(quote.get("message_id") or "").strip()
        if not quote_message_id:
            return None
        getter = getattr(self.archive, "get_message_by_id", None)
        if not callable(getter):
            return None
        try:
            item = getter(_stable_room_scope(msg), quote_message_id)
        except Exception as e:
            logger.debug("[wechat_group] failed to load quoted multimodal image: {}".format(e))
            return None
        return item if _is_image_item(item) else None

    def _find_quoted_sender_recent_image(self, msg, cfg: Dict[str, Any], now=None) -> Optional[Dict[str, Any]]:
        quote = getattr(msg, "quote", {}) or {}
        if not isinstance(quote, dict):
            return None
        quote_sender_id = str(quote.get("sender_id") or "").strip()
        quote_stable_member_id = str(quote.get("stable_member_id") or quote.get("wechat_group_stable_member_id") or "").strip()
        quote_sender_name = str(quote.get("sender_name") or "").strip()
        if not quote_stable_member_id and not quote_sender_id and not quote_sender_name:
            return None
        recent = self._recent_messages(
            msg,
            minutes=cfg["quote_sender_window_minutes"],
            limit=cfg["max_recent_messages"],
            now=now,
        )
        for item in reversed(recent):
            if not _is_image_item(item):
                continue
            stable_member_id = str(item.get("stable_member_id") or "").strip()
            sender_id = str(item.get("sender_id") or "").strip()
            sender_name = str(item.get("sender_nickname") or "").strip()
            if (
                (quote_stable_member_id and stable_member_id == quote_stable_member_id)
                or (not stable_member_id and quote_sender_id and sender_id == quote_sender_id)
                or (quote_sender_name and sender_name == quote_sender_name)
            ):
                return item
        return None

    def _recent_images(self, msg, seconds: int, limit: int, now=None) -> List[Dict[str, Any]]:
        minutes = max(1, int((int(seconds or 60) + 59) / 60))
        effective_now = self._coerce_now(now, msg)
        cutoff = effective_now - int(seconds or 60)
        return [
            item for item in self._recent_messages(msg, minutes=minutes, limit=limit, now=effective_now)
            if _is_image_item(item) and int(item.get("created_at") or 0) >= cutoff
        ]

    def _recent_messages(self, msg, minutes: int, limit: int, now=None) -> List[Dict[str, Any]]:
        getter = getattr(self.archive, "get_recent_messages", None)
        if not callable(getter):
            return []
        try:
            rows = getter(
                _stable_room_scope(msg),
                limit=limit,
                minutes=minutes,
                now=now if now is not None else getattr(msg, "create_time", None),
            )
        except Exception as e:
            logger.debug("[wechat_group] failed to load multimodal recent messages: {}".format(e))
            return []
        return rows if isinstance(rows, list) else []

    def _build_image_understanding_section(self, image_match: Dict[str, Any]) -> str:
        item = image_match.get("item") or {}
        image_path = str(item.get("media_path") or "").strip()
        if not image_path:
            return ""
        question = (
            conf().get("wechat_group_image_understanding_prompt")
            or "请简洁描述这张图片中的关键信息，并指出可能需要回复的内容。"
        )
        summary = self._get_image_summary(image_path, question)
        lines = ["[image_understanding]"]
        message_id = str(item.get("message_id") or "").strip()
        if message_id:
            lines.append("message_id: {}".format(message_id))
        sender = _format_sender(item.get("sender_nickname"), item.get("sender_id"))
        if sender:
            lines.append("sender: {}".format(sender))
        reason = str(image_match.get("reason") or "").strip()
        if reason:
            lines.append("reason: {}".format(reason))
        created_at = _format_timestamp(item.get("created_at"))
        if created_at:
            lines.append("created_at: {}".format(created_at))
        lines.append("summary: {}".format(summary or IMAGE_UNDERSTANDING_EMPTY_SUMMARY))
        image_match["summary"] = summary
        image_match["summary_generated"] = _is_successful_image_summary(summary)
        return "\n".join(lines)

    def _get_image_summary(self, image_path: str, question: str) -> str:
        cache = self._get_summary_cache()
        cache_key = "{}\n{}".format(image_path, question)
        cached = cache.get(cache_key, "")
        if cached:
            return cached
        try:
            from agent.tools.vision.vision import Vision

            result = Vision().execute({
                "image": image_path,
                "question": question,
            })
            if getattr(result, "status", "") == "success":
                payload = getattr(result, "result", None)
                if isinstance(payload, dict):
                    summary = str(payload.get("content") or "").strip()
                else:
                    summary = str(payload or "").strip()
            else:
                summary = IMAGE_UNDERSTANDING_FAILURE_SUMMARY
        except Exception as e:
            logger.warning("[wechat_group] multimodal image understanding failed: {}".format(type(e).__name__))
            summary = IMAGE_UNDERSTANDING_FAILURE_SUMMARY
        if _is_successful_image_summary(summary):
            cache[cache_key] = summary
        return summary or IMAGE_UNDERSTANDING_EMPTY_SUMMARY

    def _get_summary_cache(self):
        try:
            minutes = int(conf().get("wechat_group_image_understanding_cache_minutes", 30))
        except Exception:
            minutes = 30
        seconds = max(60, min(minutes, 120) * 60)
        if self._summary_cache is None or self._summary_cache_seconds != seconds:
            self._summary_cache = ExpiredDict(seconds)
            self._summary_cache_seconds = seconds
        return self._summary_cache

    def _build_quote_section(self, msg) -> str:
        if not conf().get("wechat_group_quote_context_enabled", True):
            return ""
        quote = getattr(msg, "quote", {}) or {}
        if not isinstance(quote, dict) or not quote:
            return ""
        quoted_item = None
        quote_message_id = str(quote.get("message_id") or "").strip()
        if quote_message_id:
            getter = getattr(self.archive, "get_message_by_id", None)
            if callable(getter):
                try:
                    item = getter(_stable_room_scope(msg), quote_message_id)
                    quoted_item = item if isinstance(item, dict) else None
                except Exception as e:
                    logger.debug("[wechat_group] failed to load quote context: {}".format(e))
        message_type = ""
        sender_id = ""
        sender_name = ""
        content = ""
        if quoted_item:
            message_type = _normalize_quote_message_type(quoted_item.get("message_type"))
            sender_id = str(quoted_item.get("sender_id") or "").strip()
            sender_name = str(quoted_item.get("sender_nickname") or "").strip()
            content = str(quoted_item.get("text") or "").strip()
        else:
            message_type = _normalize_quote_message_type(quote.get("type"))
            sender_id = str(quote.get("sender_id") or "").strip()
            sender_name = str(quote.get("sender_name") or "").strip()
            content = str(quote.get("content") or "").strip()
        message_type = detect_wechat_transport_message_type(content) or message_type
        if message_type and message_type != "text":
            content = "[{}]".format(message_type)
        lines = ["[quoted_message]"]
        if quote_message_id:
            lines.append("message_id: {}".format(quote_message_id))
        sender = _format_sender(sender_name, sender_id)
        if sender:
            lines.append("sender: {}".format(sender))
        if message_type:
            lines.append("message_type: {}".format(message_type))
        if content:
            lines.append("content: {}".format(_trim(content, 320)))
        return "\n".join(lines) if len(lines) > 1 else ""

    @staticmethod
    def _build_forward_section(msg) -> str:
        if not conf().get("wechat_group_forward_preview_enabled", True):
            return ""
        forward = getattr(msg, "forward", {}) or {}
        if not isinstance(forward, dict) or not forward:
            return ""
        title = str(forward.get("title") or "").strip()
        description = str(forward.get("description") or "").strip()
        source = str(forward.get("source") or "").strip()
        record_item = str(forward.get("record_item") or "").strip()
        record_count = int(forward.get("record_count_hint") or 0)
        raw_app_type = str(getattr(msg, "raw_app_type", "") or "").strip()
        if not any([title, description, source, record_item, record_count, raw_app_type]):
            return ""
        lines = ["[forward_preview]"]
        if raw_app_type:
            lines.append("app_type: {}".format(raw_app_type))
        if title:
            lines.append("title: {}".format(_trim(title, 160)))
        if description:
            lines.append("description: {}".format(_trim(description, 320)))
        if source:
            lines.append("source: {}".format(_trim(source, 120)))
        if record_count > 0:
            lines.append("record_count_hint: {}".format(record_count))
        if record_item and not description:
            lines.append("record_item: {}".format(_trim(record_item, 320)))
        return "\n".join(lines)

    @staticmethod
    def _build_video_section(msg) -> str:
        if not conf().get("wechat_group_video_understanding_enabled", False):
            return ""
        if str(getattr(msg, "message_type", "") or "").lower() != "video":
            return ""
        video_path = str(getattr(msg, "media_path", "") or getattr(msg, "content", "") or "").strip()
        if not video_path:
            return ""
        lines = ["[video_message]"]
        sender = _format_sender(getattr(msg, "actual_user_nickname", ""), getattr(msg, "actual_user_id", ""))
        if sender:
            lines.append("sender: {}".format(sender))
        message_id = str(getattr(msg, "msg_id", "") or "").strip()
        if message_id:
            lines.append("message_id: {}".format(message_id))
        text = str(getattr(msg, "text", "") or "").strip()
        if text:
            lines.append("caption: {}".format(_trim(text, 200)))
        return "\n".join(lines)
