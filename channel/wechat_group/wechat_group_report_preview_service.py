"""Asynchronous, authenticated Web previews for WeChat group reports."""

from __future__ import annotations

import threading
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Dict, Optional

from channel.wechat_group.wechat_group_report_renderer import (
    ReportImageRenderError,
    WechatGroupReportRenderer,
)
from channel.wechat_group.wechat_group_report_store import WechatGroupReportStore
from common.log import logger


class WechatGroupReportPreviewService:
    """Render a preview outside the HTTP request and independently of delivery."""

    def __init__(
        self,
        store: Optional[WechatGroupReportStore] = None,
        renderer: Optional[WechatGroupReportRenderer] = None,
        max_workers: int = 1,
    ) -> None:
        self.store = store or WechatGroupReportStore()
        self.renderer = renderer or WechatGroupReportRenderer()
        self._executor = ThreadPoolExecutor(
            max_workers=max(1, min(int(max_workers or 1), 2)),
            thread_name_prefix="wechat-group-report-preview",
        )
        self._lock = threading.RLock()
        self._futures: Dict[str, Future] = {}

    def submit(
        self,
        preview_id: str,
        job_id: str,
        stable_room_id: str,
        report: Dict[str, Any],
        output_settings: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Queue one preview render. Repeated polling never creates more work."""
        preview_text = str(preview_id or "").strip()
        if not preview_text:
            raise ValueError("preview_id is required")
        with self._lock:
            current = self._futures.get(preview_text)
            if current is not None and not current.done():
                return self.get_status(preview_text, stable_room_id) or {
                    "preview_id": preview_text,
                    "state": "pending",
                }
            if current is not None:
                self._futures.pop(preview_text, None)
            self._futures[preview_text] = self._executor.submit(
                self._render_preview,
                preview_text,
                str(job_id or ""),
                str(stable_room_id or ""),
                dict(report or {}),
                dict(output_settings or {}),
            )
        return self.get_status(preview_text, stable_room_id) or {
            "preview_id": preview_text,
            "state": "pending",
        }

    def get_status(self, preview_id: str, stable_room_id: str) -> Optional[Dict[str, Any]]:
        preview = self.store.get_preview(preview_id, stable_room_id)
        if not preview:
            return None
        preview["parts"] = self.store.list_preview_parts(preview_id, stable_room_id)
        return preview

    def shutdown(self, wait: bool = False) -> None:
        self._executor.shutdown(wait=wait, cancel_futures=False)

    def _render_preview(
        self,
        preview_id: str,
        job_id: str,
        stable_room_id: str,
        report: Dict[str, Any],
        output_settings: Dict[str, Any],
    ) -> None:
        report_id = str(report.get("report_id") or "").strip()
        payload = report.get("payload") if isinstance(report.get("payload"), dict) else report
        if not report_id or not isinstance(payload, dict):
            return
        try:
            preview = self.store.create_preview(
                preview_id,
                job_id,
                report_id,
                stable_room_id,
                output_settings,
            )
            output = preview.get("output_settings") if isinstance(preview.get("output_settings"), dict) else {}
            mode = str(preview.get("output_mode") or output.get("mode") or "image_preferred")
            self.store.update_preview(preview_id, stable_room_id, state="rendering")
            if mode == "text":
                self._render_text(preview_id, stable_room_id, payload, output)
                return
            try:
                rendered = self.renderer.render_images(payload, output, "preview_" + preview_id)
            except Exception as exc:
                image_error = str(exc) if isinstance(exc, ReportImageRenderError) else "image_render_failed"
                if mode == "image_preferred":
                    self._render_text(
                        preview_id,
                        stable_room_id,
                        payload,
                        output,
                        fallback_reason=image_error,
                    )
                    return
                self.store.update_preview(
                    preview_id,
                    stable_room_id,
                    state="failed",
                    error_code=image_error,
                )
                return
            self.store.replace_preview_parts(preview_id, stable_room_id, rendered.get("parts") or [])
            self.store.update_preview(
                preview_id,
                stable_room_id,
                state="ready",
                actual_output="image",
            )
        except Exception as exc:
            logger.exception("[wechat_group_report] preview rendering failed: %s", exc)
            try:
                self.store.update_preview(
                    preview_id,
                    stable_room_id,
                    state="failed",
                    error_code="preview_failed",
                )
            except Exception:
                return

    def _render_text(
        self,
        preview_id: str,
        stable_room_id: str,
        report: Dict[str, Any],
        output: Dict[str, Any],
        fallback_reason: str = "",
    ) -> None:
        try:
            rendered = self.renderer.render_text(report, output)
        except Exception as exc:
            logger.warning("[wechat_group_report] text preview rendering failed: %s", exc)
            self.store.update_preview(
                preview_id,
                stable_room_id,
                state="failed",
                error_code="text_preview_failed",
            )
            return
        self.store.update_preview(
            preview_id,
            stable_room_id,
            state="text_ready",
            actual_output="text",
            fallback_reason=fallback_reason,
            text_parts=rendered.get("parts") or [],
        )
