"""Bounded asynchronous generation runner for WeChat group reports."""

from __future__ import annotations

import threading
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Dict, Optional

from channel.wechat_group.wechat_group_report_service import (
    REPORT_CONTENT_VERSION,
    WechatGroupReportService,
)
from channel.wechat_group.wechat_group_report_store import WechatGroupReportStore
from common.log import logger


class WechatGroupReportJobRunner:
    """Runs report work outside HTTP and scheduler threads with key de-duplication."""

    def __init__(
        self,
        report_service: Optional[WechatGroupReportService] = None,
        store: Optional[WechatGroupReportStore] = None,
        max_workers: int = 2,
        on_ready=None,
    ) -> None:
        self.report_service = report_service or WechatGroupReportService(store=store)
        self.store = store or self.report_service.store
        self._executor = ThreadPoolExecutor(
            max_workers=max(1, min(int(max_workers or 2), 4)),
            thread_name_prefix="wechat-group-report",
        )
        self._lock = threading.RLock()
        self._futures: Dict[str, Future] = {}
        self._ready_callbacks: Dict[str, Any] = {}
        self.on_ready = on_ready
        self.store.recover_incomplete_jobs()

    def submit_generation(
        self,
        stable_room_id: str,
        report_type: str,
        actor: str,
        draft_settings: Optional[Dict[str, Any]] = None,
        custom_start: Any = None,
        custom_end: Any = None,
        force_regenerate: bool = False,
        ready_callback=None,
    ) -> Dict[str, Any]:
        settings = dict(draft_settings or self.store.get_settings(stable_room_id))
        timezone_name = str(settings.get("timezone") or "Asia/Shanghai")
        prepared = self.report_service.prepare_generation(
            stable_room_id,
            report_type,
            timezone_name,
            custom_start=custom_start,
            custom_end=custom_end,
        )
        reusable = None
        if not force_regenerate:
            reusable = self.store.find_reusable_report(
                stable_room_id,
                report_type,
                prepared["period_start"],
                prepared["period_end"],
                prepared["source_watermark"],
                REPORT_CONTENT_VERSION,
            )
        job = self.store.create_or_reuse_job(
            stable_room_id,
            report_type,
            prepared["period_start"],
            prepared["period_end"],
            prepared["source_watermark"],
            REPORT_CONTENT_VERSION,
            actor,
            draft_settings=settings,
            force_regenerate=force_regenerate,
        )
        if reusable:
            ready = self.store.update_job(
                job["job_id"], stable_room_id,
                state="ready", stage="ready", completed_items=1, total_items=1,
                report_id=reusable["report_id"],
            )
            self._notify_ready(reusable, ready, ready_callback)
            return ready
        if ready_callback is not None:
            with self._lock:
                self._ready_callbacks[job["job_id"]] = ready_callback
        with self._lock:
            future = self._futures.get(job["job_id"])
            if future is None or future.done():
                self._futures[job["job_id"]] = self._executor.submit(
                    self._run_job, job["job_id"], stable_room_id, force_regenerate,
                )
        return self.store.get_job(job["job_id"], stable_room_id) or job

    def resume_pending_jobs(self) -> int:
        count = 0
        for job in self.store.list_queued_jobs():
            room_id = str(job.get("stable_room_id") or "")
            job_id = str(job.get("job_id") or "")
            if not room_id or not job_id:
                continue
            with self._lock:
                current = self._futures.get(job_id)
                if current is not None and not current.done():
                    continue
                self._futures[job_id] = self._executor.submit(self._run_job, job_id, room_id, False)
                count += 1
        return count

    def get_status(self, job_id: str, stable_room_id: str) -> Optional[Dict[str, Any]]:
        return self.store.get_job(job_id, stable_room_id)

    def shutdown(self, wait: bool = False) -> None:
        self._executor.shutdown(wait=wait, cancel_futures=False)

    def _run_job(self, job_id: str, stable_room_id: str, force_regenerate: bool) -> None:
        job = self.store.get_job(job_id, stable_room_id)
        if not job or job.get("state") not in {"queued", "collecting", "summarizing", "validating"}:
            return
        try:
            self.store.update_job(job_id, stable_room_id, state="collecting", stage="collecting", completed_items=0, total_items=3)
            self.store.update_job(job_id, stable_room_id, state="summarizing", stage="summarizing", completed_items=1, total_items=3)
            report = self.report_service.generate_report(
                stable_room_id,
                str(job.get("report_type") or "daily"),
                job.get("period_start"),
                job.get("period_end"),
                str((job.get("draft_settings") or {}).get("timezone") or "Asia/Shanghai"),
                force_regenerate=force_regenerate,
            )
            self.store.update_job(job_id, stable_room_id, state="validating", stage="validating", completed_items=2, total_items=3)
            self.store.update_job(
                job_id,
                stable_room_id,
                state="ready",
                stage="ready",
                completed_items=3,
                total_items=3,
                report_id=str(report.get("report_id") or ""),
            )
            self._save_daily_topics_memory(report, job)
            ready_job = self.store.get_job(job_id, stable_room_id) or {}
            callback = None
            with self._lock:
                callback = self._ready_callbacks.pop(job_id, None)
            self._notify_ready(report, ready_job, callback)
        except Exception as exc:
            logger.exception("[wechat_group_report] generation job failed: %s", exc)
            self.store.update_job(
                job_id,
                stable_room_id,
                state="failed",
                stage="failed",
                error_code=_error_code(exc),
            )

    def _notify_ready(self, report: Dict[str, Any], job: Dict[str, Any], callback=None) -> None:
        target = callback or self.on_ready
        if target is None:
            return
        try:
            target(report, job)
        except Exception as exc:
            logger.warning("[wechat_group_report] ready callback failed: %s", exc)

    def _save_daily_topics_memory(self, report: Dict[str, Any], job: Dict[str, Any]) -> None:
        settings = job.get("draft_settings") if isinstance(job.get("draft_settings"), dict) else {}
        if (
            str(job.get("report_type") or "") != "daily"
            or not settings.get("enabled")
            or not settings.get("save_daily_topics_to_group_memory")
        ):
            return
        payload = report.get("payload") if isinstance(report.get("payload"), dict) else report
        topics = payload.get("topics") if isinstance(payload.get("topics"), list) else []
        if not topics:
            return
        lines = ["日报重点话题："]
        for topic in topics[:3]:
            if not isinstance(topic, dict):
                continue
            title = str(topic.get("title") or "群内讨论").strip()
            summary = str(topic.get("summary") or "").strip()
            if title:
                lines.append(f"- {title}：{summary}".strip())
        content = "\n".join(lines).strip()
        if len(lines) <= 1 or not content:
            return
        try:
            from channel.wechat_group.wechat_group_knowledge_store import WechatGroupKnowledgeStore

            room_id = str(job.get("stable_room_id") or "").strip()
            period_start = str(payload.get("period_start") or job.get("period_start") or "")
            memory_id = "chat_report_daily:{}:{}".format(room_id, period_start)
            WechatGroupKnowledgeStore().upsert_group_memory(
                room_id,
                content,
                memory_id=memory_id,
                source_kind="chat_report_daily",
                evidence_message_ids=[],
            )
        except Exception as exc:
            logger.warning("[wechat_group_report] failed to save daily topic memory: %s", exc)


def _error_code(error: Exception) -> str:
    value = str(error or "").lower()
    if "timeout" in value:
        return "timeout"
    if "429" in value or "rate" in value:
        return "model_rate_limited"
    if "template" in value:
        return "template_invalid"
    return "generation_failed"
