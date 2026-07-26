"""Orchestrates deterministic facts, evidence-bound content and link enrichment."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from channel.wechat_group.wechat_group_report_content_service import WechatGroupReportContentService
from channel.wechat_group.wechat_group_report_link_service import WechatGroupReportLinkService
from channel.wechat_group.wechat_group_report_store import WechatGroupReportStore
from channel.wechat_group.wechat_group_statistics_service import WechatGroupStatisticsService
from common.log import logger


REPORT_CONTENT_VERSION = "1"


class WechatGroupReportService:
    """Single generation entry point used by Web, tools and scheduler."""

    def __init__(
        self,
        statistics_service: Optional[WechatGroupStatisticsService] = None,
        content_service: Optional[WechatGroupReportContentService] = None,
        link_service: Optional[WechatGroupReportLinkService] = None,
        store: Optional[WechatGroupReportStore] = None,
    ) -> None:
        self.statistics_service = statistics_service or WechatGroupStatisticsService()
        self.content_service = content_service or WechatGroupReportContentService(
            identity_service=self.statistics_service.identity_service,
        )
        self.link_service = link_service or WechatGroupReportLinkService(
            summary_provider=self._summarize_link,
        )
        self.store = store or WechatGroupReportStore()

    def prepare_generation(
        self,
        stable_room_id: str,
        report_type: str,
        timezone_name: str,
        custom_start: Any = None,
        custom_end: Any = None,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Resolve a stable report range and its current source watermark."""
        start, end = self.statistics_service.resolve_period(
            report_type,
            timezone_name=timezone_name,
            now=now,
            custom_start=custom_start,
            custom_end=custom_end,
        )
        return {
            "stable_room_id": str(stable_room_id),
            "report_type": str(report_type),
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "timezone": timezone_name,
            "source_watermark": self.statistics_service.get_source_watermark(
                stable_room_id, start, end,
            ),
        }

    def generate_report(
        self,
        stable_room_id: str,
        report_type: str,
        period_start: Any,
        period_end: Any,
        timezone_name: str,
        force_regenerate: bool = False,
        use_model: bool = True,
    ) -> Dict[str, Any]:
        """Create or reuse one immutable structured report revision."""
        start, end = self.statistics_service.resolve_period(
            "custom",
            timezone_name=timezone_name,
            custom_start=period_start,
            custom_end=period_end,
        )
        base = self.statistics_service.build_base_report(
            stable_room_id,
            report_type,
            start,
            end,
            timezone_name=timezone_name,
        )
        source_watermark = int(base.get("_source_watermark") or 0)
        reusable = None
        if not force_regenerate:
            reusable = self.store.find_reusable_report(
                stable_room_id,
                report_type,
                base["period_start"],
                base["period_end"],
                source_watermark,
                REPORT_CONTENT_VERSION,
            )
        if reusable:
            return reusable

        evidence = list(self.statistics_service.iter_messages(stable_room_id, start, end))
        report = self.content_service.build_content(base, evidence, use_model=use_model)
        report["links"] = self.link_service.enrich_links(report.get("links") or [])
        report["topic_count"] = len(report.get("topics") or [])
        report["_source_watermark"] = source_watermark
        stored = self.store.create_report(
            stable_room_id,
            report_type,
            report["period_start"],
            report["period_end"],
            source_watermark,
            REPORT_CONTENT_VERSION,
            report,
            force_regenerate=force_regenerate,
        )
        return stored

    def get_public_report(self, report_id: str, stable_room_id: str) -> Optional[Dict[str, Any]]:
        report = self.store.get_report(report_id, stable_room_id)
        if not report:
            return None
        return serialize_public_report(report)

    def _summarize_link(self, title: str, body: str, url: str) -> str:
        router = self.content_service._get_model_router()
        if router is None:
            return title or body[:180]
        prompt = (
            "Summarize the following safely fetched web page in one or two concise Chinese sentences. "
            "Do not add facts not present in the title or body.\n"
            f"title: {title}\nurl: {url}\nbody: {body[:4000]}"
        )
        try:
            result = router.complete(
                [{"role": "user", "content": prompt}],
                purpose="wechat_group_report_link_summary",
                system="Return plain text only.",
                max_tokens=220,
            )
            if isinstance(result, dict) and result.get("success"):
                text = str(result.get("content") or "").strip()
                if text and not _looks_like_error_text(text):
                    return text[:260]
        except Exception as exc:
            logger.debug("[wechat_group_report] link model summary failed: %s", exc)
        return title or body[:180]


def serialize_public_report(value: Dict[str, Any]) -> Dict[str, Any]:
    """Remove evidence identifiers and any internal fields before API/render use."""
    data = _strip_internal(value or {})
    payload = data.get("payload") if isinstance(data.get("payload"), dict) else data
    return _strip_internal(payload)


def _strip_internal(value: Any) -> Any:
    if isinstance(value, list):
        return [_strip_internal(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {}
    for key, item in value.items():
        if str(key).startswith("_") or key in {"stable_room_id", "runtime_room_id", "stable_member_id"}:
            continue
        result[key] = _strip_internal(item)
    return result


def _looks_like_error_text(value: str) -> bool:
    text = str(value or "").strip().lower()
    return text.startswith("{") and ("error" in text or "status_code" in text)
