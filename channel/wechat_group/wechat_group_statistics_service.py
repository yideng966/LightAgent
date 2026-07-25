"""Deterministic, stable-scope statistics for WeChat group reports."""

from __future__ import annotations

import re
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple
from zoneinfo import ZoneInfo

from channel.wechat_group.wechat_group_archive import WechatGroupArchive
from channel.wechat_group.wechat_group_identity_service import WechatGroupIdentityService
from channel.wechat_group.wechat_group_report_link_service import (
    extract_http_urls,
    link_domain,
    normalize_http_url,
)
from channel.wechat_group.wechat_group_transport import (
    is_wechat_transport_xml,
    project_wechat_message_type,
)


COUNTABLE_MESSAGE_TYPES = frozenset({"text", "image", "sticker", "audio", "video", "file"})
REPORT_TIMEZONE_DEFAULT = "Asia/Shanghai"


class WechatGroupStatisticsService:
    """Build report facts without calling a model or querying live members."""

    def __init__(
        self,
        archive: Optional[WechatGroupArchive] = None,
        identity_service: Optional[WechatGroupIdentityService] = None,
    ) -> None:
        self.archive = archive or WechatGroupArchive()
        self.identity_service = identity_service or WechatGroupIdentityService()

    def resolve_period(
        self,
        report_type: str,
        timezone_name: str = REPORT_TIMEZONE_DEFAULT,
        now: Optional[datetime] = None,
        custom_start: Optional[Any] = None,
        custom_end: Optional[Any] = None,
    ) -> Tuple[datetime, datetime]:
        """Resolve a report range as a timezone-aware half-open interval."""
        zone = _resolve_zone(timezone_name)
        current = _coerce_datetime(now, zone) if now is not None else datetime.now(zone)
        report_kind = str(report_type or "").strip().lower()
        if report_kind == "daily":
            end = current.replace(hour=0, minute=0, second=0, microsecond=0)
            return end - timedelta(days=1), end
        if report_kind == "weekly":
            end = current.replace(hour=0, minute=0, second=0, microsecond=0)
            end -= timedelta(days=end.weekday())
            return end - timedelta(days=7), end
        if report_kind == "monthly":
            end = current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            previous_month_end = end - timedelta(days=1)
            start = previous_month_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            return start, end
        if report_kind == "custom":
            start = _coerce_datetime(custom_start, zone)
            end = _coerce_datetime(custom_end, zone)
            if end <= start:
                raise ValueError("custom report end must be later than start")
            return start, end
        raise ValueError("report_type must be daily, weekly, monthly, or custom")

    def iter_messages(
        self,
        stable_room_id: str,
        start_at: datetime,
        end_at: datetime,
        page_size: int = 200,
    ) -> Iterator[Dict[str, Any]]:
        """Yield countable report messages in archive order without a bulk SQL load."""
        room_id = _required_stable_room_id(stable_room_id)
        start_ts = int(start_at.timestamp())
        end_ts = int(end_at.timestamp())
        legacy_aliases = self._confirmed_legacy_room_aliases(room_id)
        cursor = 0
        while True:
            page = self.archive.get_report_messages_page(
                room_id,
                start_ts,
                end_ts,
                after_id=cursor,
                limit=page_size,
                legacy_room_ids=legacy_aliases,
            )
            if not page:
                break
            for message in page:
                cursor = max(cursor, int(message.get("id") or 0))
                normalized_type = project_wechat_message_type(
                    message.get("message_type"), message.get("text")
                )
                if normalized_type not in COUNTABLE_MESSAGE_TYPES:
                    continue
                if _is_bot_message(message):
                    continue
                message["report_message_type"] = normalized_type
                yield message
            if len(page) < min(max(int(page_size or 200), 1), 500):
                break

    def build_base_report(
        self,
        stable_room_id: str,
        report_type: str,
        period_start: datetime,
        period_end: datetime,
        timezone_name: str = REPORT_TIMEZONE_DEFAULT,
    ) -> Dict[str, Any]:
        """Build all non-LLM report facts and link evidence deterministically."""
        room_id = _required_stable_room_id(stable_room_id)
        zone = _resolve_zone(timezone_name)
        start = _coerce_datetime(period_start, zone)
        end = _coerce_datetime(period_end, zone)
        if end <= start:
            raise ValueError("period_end must be later than period_start")

        member_counts: Dict[str, int] = defaultdict(int)
        latest_names: Dict[str, Tuple[int, int, str]] = {}
        total_messages = 0
        unresolved_message_count = 0
        source_watermark = 0
        links: Dict[str, Dict[str, Any]] = {}

        for message in self.iter_messages(room_id, start, end):
            total_messages += 1
            row_id = int(message.get("id") or 0)
            source_watermark = max(source_watermark, row_id)
            canonical_member_id = self._canonical_member_id(room_id, message.get("stable_member_id"))
            if canonical_member_id:
                member_counts[canonical_member_id] += 1
                nickname = _safe_nickname(message.get("sender_nickname"))
                if nickname:
                    candidate = (int(message.get("created_at") or 0), row_id, nickname)
                    if candidate > latest_names.get(canonical_member_id, (0, 0, "")):
                        latest_names[canonical_member_id] = candidate
            else:
                unresolved_message_count += 1

            safe_text = safe_report_message_text(message)
            for original_url in extract_http_urls(safe_text):
                normalized_url = normalize_http_url(original_url)
                if not normalized_url:
                    continue
                item = links.get(normalized_url)
                if item is None:
                    item = {
                        "url": normalized_url,
                        "domain": link_domain(normalized_url),
                        "provider_member_ids": [],
                        "_evidence": [],
                    }
                    links[normalized_url] = item
                if canonical_member_id and canonical_member_id not in item["provider_member_ids"]:
                    item["provider_member_ids"].append(canonical_member_id)
                item["_evidence"].append({
                    "message_id": str(message.get("message_id") or ""),
                    "row_id": row_id,
                    "created_at": int(message.get("created_at") or 0),
                })

        display_names = self._resolve_display_names(room_id, member_counts, latest_names)
        ranked = sorted(
            member_counts.items(),
            key=lambda item: (-item[1], display_names[item[0]].casefold(), item[0]),
        )
        ranking = [
            {
                "rank": index,
                "display_name": display_names[member_id],
                "message_count": count,
            }
            for index, (member_id, count) in enumerate(ranked[:5], 1)
        ]
        resolved_links = []
        for item in links.values():
            providers = [display_names.get(member_id, "未命名群友") for member_id in item["provider_member_ids"]]
            resolved_links.append({
                "url": item["url"],
                "domain": item["domain"],
                "provider_display_names": _unique_in_order(providers),
                "_evidence": list(item["_evidence"]),
            })

        room_name = self._resolve_room_name(room_id)
        generated_at = datetime.now(zone)
        return {
            "schema_version": 1,
            "stable_room_id": room_id,
            "room_name": room_name or "未命名群聊",
            "report_type": str(report_type or "").lower(),
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "timezone": zone.key,
            "active_speaker_count": len(member_counts),
            "total_messages": total_messages,
            "top_speaker": ranking[0] if ranking else {"display_name": "暂无", "message_count": 0},
            "topic_count": 0,
            "ranking": ranking,
            "topics": [],
            "highlights": [],
            "links": resolved_links,
            "archive_message_count": total_messages,
            "unresolved_message_count": unresolved_message_count,
            "generated_at": generated_at.isoformat(),
            "_source_watermark": source_watermark,
        }

    def get_archive_bounds(self, stable_room_id: str) -> Dict[str, int]:
        room_id = _required_stable_room_id(stable_room_id)
        return self.archive.get_report_archive_bounds(
            room_id,
            legacy_room_ids=self._confirmed_legacy_room_aliases(room_id),
        )

    def get_source_watermark(
        self,
        stable_room_id: str,
        period_start: datetime,
        period_end: datetime,
    ) -> int:
        room_id = _required_stable_room_id(stable_room_id)
        return self.archive.get_report_source_watermark(
            room_id,
            int(period_start.timestamp()),
            int(period_end.timestamp()),
            legacy_room_ids=self._confirmed_legacy_room_aliases(room_id),
        )

    def _confirmed_legacy_room_aliases(self, stable_room_id: str) -> List[str]:
        try:
            values = self.identity_service.list_confirmed_room_scope_ids(stable_room_id)
        except Exception:
            values = []
        return [str(value or "").strip() for value in values if str(value or "").strip()]

    def _canonical_member_id(self, stable_room_id: str, stable_member_id: Any) -> str:
        member_id = str(stable_member_id or "").strip()
        if not member_id:
            return ""
        try:
            return str(self.identity_service.resolve_canonical_member_id(stable_room_id, member_id) or "").strip()
        except Exception:
            return ""

    def _resolve_display_names(
        self,
        stable_room_id: str,
        member_counts: Dict[str, int],
        latest_names: Dict[str, Tuple[int, int, str]],
    ) -> Dict[str, str]:
        result: Dict[str, str] = {}
        unnamed_index = 0
        for member_id in sorted(member_counts):
            name = ""
            try:
                member = self.identity_service.store.get_member(member_id)
                name = _safe_nickname(member.get("display_name"))
            except Exception:
                name = ""
            if not name:
                name = _safe_nickname((latest_names.get(member_id) or (0, 0, ""))[2])
            if not name:
                unnamed_index += 1
                name = f"未命名群友 {unnamed_index}"
            result[member_id] = name
        return result

    def _resolve_room_name(self, stable_room_id: str) -> str:
        try:
            room = self.identity_service.store.get_room(stable_room_id)
            value = _safe_nickname(room.get("canonical_name"))
            if value:
                return value
        except Exception:
            pass
        return _safe_nickname(self.archive.find_room_name(stable_room_id))


def safe_report_message_text(message: Dict[str, Any], max_chars: int = 1200) -> str:
    """Project archived text to report-safe evidence without transport fields."""
    message_type = str(message.get("report_message_type") or message.get("message_type") or "").lower()
    raw = str(message.get("text") or "")
    if is_wechat_transport_xml(raw):
        return "[媒体消息]"
    if message_type != "text" and not raw.strip():
        labels = {"image": "[图片]", "sticker": "[表情]", "audio": "[语音]", "video": "[视频]", "file": "[文件]"}
        return labels.get(message_type, "[消息]")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", raw)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


def _required_stable_room_id(value: Any) -> str:
    room_id = str(value or "").strip()
    if not room_id:
        raise ValueError("stable_room_id is required")
    return room_id


def _resolve_zone(value: Any) -> ZoneInfo:
    try:
        return ZoneInfo(str(value or REPORT_TIMEZONE_DEFAULT))
    except Exception as exc:
        raise ValueError("invalid report timezone") from exc


def _coerce_datetime(value: Any, zone: ZoneInfo) -> datetime:
    if isinstance(value, datetime):
        return value.astimezone(zone) if value.tzinfo else value.replace(tzinfo=zone)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, zone)
    text = str(value or "").strip()
    if not text:
        raise ValueError("datetime value is required")
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return parsed.astimezone(zone) if parsed.tzinfo else parsed.replace(tzinfo=zone)


def _safe_nickname(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not text or text.startswith("wxid_") or re.fullmatch(r"@?[A-Za-z0-9_-]{12,}", text):
        return ""
    return text[:80]


def _is_bot_message(message: Dict[str, Any]) -> bool:
    metadata = message.get("metadata") if isinstance(message.get("metadata"), dict) else {}
    self_id = str(metadata.get("self_id") or "").strip()
    sender_id = str(message.get("runtime_sender_id") or message.get("sender_id") or "").strip()
    return bool(self_id and sender_id and self_id == sender_id)


def _unique_in_order(values: Iterable[str]) -> List[str]:
    result: List[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
    return result
