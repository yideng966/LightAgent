"""Confirmed, ordered delivery of rendered WeChat group report parts."""

from __future__ import annotations

import hashlib
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from channel.wechat_group.wechat_group_identity_service import WechatGroupIdentityService
from channel.wechat_group.wechat_group_report_renderer import (
    ReportImageRenderError,
    WechatGroupReportRenderer,
)
from channel.wechat_group.wechat_group_report_store import WechatGroupReportStore
from common.log import logger


class WechatGroupReportDeliveryService:
    """Keep generation and delivery separate so a failed send preserves its snapshot."""

    def __init__(
        self,
        store: Optional[WechatGroupReportStore] = None,
        renderer: Optional[WechatGroupReportRenderer] = None,
        identity_service: Optional[WechatGroupIdentityService] = None,
        channel_getter=None,
        max_workers: int = 2,
    ) -> None:
        self.store = store or WechatGroupReportStore()
        self.renderer = renderer or WechatGroupReportRenderer()
        self.identity_service = identity_service or WechatGroupIdentityService()
        self.channel_getter = channel_getter or _get_running_wechat_group_channel
        self._executor = ThreadPoolExecutor(
            max_workers=max(1, min(int(max_workers or 2), 4)),
            thread_name_prefix="wechat-group-report-delivery",
        )
        self._lock = threading.RLock()
        self._futures: Dict[str, Future] = {}

    def create_delivery(
        self,
        report_id: str,
        stable_room_id: str,
        actor: str,
        output_settings: Dict[str, Any],
        confirmation_token: str = "",
    ) -> Dict[str, Any]:
        return self.store.create_delivery(
            report_id, stable_room_id, actor, output_settings, confirmation_token,
        )

    def submit_delivery(self, delivery_id: str, stable_room_id: str) -> Dict[str, Any]:
        delivery = self.store.get_delivery(delivery_id, stable_room_id)
        if not delivery:
            raise ValueError("delivery not found")
        with self._lock:
            current = self._futures.get(delivery_id)
            if current is None or current.done():
                self._futures[delivery_id] = self._executor.submit(
                    self._process_delivery, delivery_id, stable_room_id, False,
                )
        return delivery

    def retry_incomplete(self, delivery_id: str, stable_room_id: str) -> Dict[str, Any]:
        delivery = self.store.get_delivery(delivery_id, stable_room_id)
        if not delivery:
            raise ValueError("delivery not found")
        if delivery.get("state") == "delivery_unknown":
            raise ValueError("delivery_unknown cannot be blindly retried")
        if delivery.get("state") not in {"failed", "partial_failed"}:
            raise ValueError("delivery is not retryable")
        with self._lock:
            current = self._futures.get(delivery_id)
            if current is None or current.done():
                self._futures[delivery_id] = self._executor.submit(
                    self._process_delivery, delivery_id, stable_room_id, True,
                )
        return self.store.get_delivery(delivery_id, stable_room_id) or delivery

    def get_status(self, delivery_id: str, stable_room_id: str) -> Optional[Dict[str, Any]]:
        delivery = self.store.get_delivery(delivery_id, stable_room_id)
        if not delivery:
            return None
        delivery["parts"] = self.store.list_delivery_parts(delivery_id, stable_room_id)
        return delivery

    def shutdown(self, wait: bool = False) -> None:
        self._executor.shutdown(wait=wait, cancel_futures=False)

    def _process_delivery(self, delivery_id: str, stable_room_id: str, retry_only: bool) -> None:
        delivery = self.store.get_delivery(delivery_id, stable_room_id)
        if not delivery:
            return
        report = self.store.get_report(delivery.get("report_id"), stable_room_id)
        if not report or report.get("state") != "ready":
            self.store.update_delivery(delivery_id, stable_room_id, state="failed", error_code="stale_report")
            return
        runtime_room_id, client = self._resolve_delivery_client(stable_room_id)
        if not runtime_room_id or client is None:
            self.store.update_delivery(delivery_id, stable_room_id, state="failed", error_code="channel_not_ready")
            return
        output = delivery.get("output_settings") if isinstance(delivery.get("output_settings"), dict) else {}
        mode = str(delivery.get("output_mode") or output.get("mode") or "image_preferred")
        try:
            preview_id = str(output.get("_source_preview_id") or "").strip()
            if preview_id:
                self._send_preview_delivery(
                    delivery_id,
                    stable_room_id,
                    report,
                    output,
                    runtime_room_id,
                    client,
                    retry_only,
                    preview_id,
                )
                return
            if mode == "text":
                self._send_text_delivery(delivery_id, stable_room_id, report["payload"], output, runtime_room_id, client, retry_only)
                return
            self._send_image_delivery(
                delivery_id, stable_room_id, report["payload"], output, runtime_room_id, client, retry_only,
                allow_text_fallback=mode == "image_preferred",
            )
        except Exception as exc:
            logger.exception("[wechat_group_report] delivery failed: %s", exc)
            current = self.store.get_delivery(delivery_id, stable_room_id) or delivery
            if current.get("state") not in {"delivery_unknown", "partial_failed", "fallback_sent", "sent"}:
                self.store.update_delivery(delivery_id, stable_room_id, state="failed", error_code="delivery_failed")

    def _send_preview_delivery(
        self,
        delivery_id: str,
        stable_room_id: str,
        report: Dict[str, Any],
        output: Dict[str, Any],
        runtime_room_id: str,
        client: Any,
        retry_only: bool,
        preview_id: str,
    ) -> None:
        """Deliver the exact output already approved in a Web preview."""
        preview = self.store.get_preview(preview_id, stable_room_id)
        if not preview or str(preview.get("report_id") or "") != str(report.get("report_id") or ""):
            self.store.update_delivery(delivery_id, stable_room_id, state="failed", error_code="preview_unavailable")
            return
        actual_output = str(preview.get("actual_output") or "")
        if preview.get("state") not in {"ready", "text_ready"} or actual_output not in {"image", "text"}:
            self.store.update_delivery(delivery_id, stable_room_id, state="failed", error_code="preview_not_ready")
            return
        if actual_output == "text":
            self._send_text_parts_delivery(
                delivery_id,
                stable_room_id,
                preview.get("text_parts") if isinstance(preview.get("text_parts"), list) else [],
                runtime_room_id,
                client,
                retry_only,
                fallback=bool(preview.get("fallback_reason")),
            )
            return
        parts = self.store.list_preview_parts(preview_id, stable_room_id)
        if not parts:
            self.store.update_delivery(delivery_id, stable_room_id, state="failed", error_code="preview_assets_unavailable")
            return
        self.store.update_delivery(
            delivery_id,
            stable_room_id,
            state="sending",
            actual_output="image",
            template_id=str(output.get("skill_image_template_name") or ""),
            template_version="preview",
        )
        self._send_image_parts_delivery(
            delivery_id,
            stable_room_id,
            report["payload"],
            output,
            runtime_room_id,
            client,
            retry_only,
            parts,
            # The user approved the rendered image preview. Do not replace it
            # with an unseen text fallback when the platform rejects the image.
            allow_text_fallback=False,
        )

    def _send_image_delivery(
        self,
        delivery_id: str,
        stable_room_id: str,
        report: Dict[str, Any],
        output: Dict[str, Any],
        runtime_room_id: str,
        client: Any,
        retry_only: bool,
        allow_text_fallback: bool,
    ) -> None:
        self.store.update_delivery(delivery_id, stable_room_id, state="rendering", actual_output="image")
        try:
            rendered = self.renderer.render_images(report, output, str(delivery_id))
        except Exception as exc:
            error_code = str(exc) if isinstance(exc, ReportImageRenderError) else "image_render_failed"
            if not isinstance(exc, ReportImageRenderError):
                logger.warning("[wechat_group_report] image rendering failed: %s", exc)
            if allow_text_fallback:
                self.store.update_delivery(
                    delivery_id, stable_room_id, state="fallback_sending", actual_output="text",
                    fallback_reason=error_code,
                )
                self._send_text_delivery(
                    delivery_id, stable_room_id, report, output, runtime_room_id, client, retry_only,
                    fallback=True,
                )
                return
            self.store.update_delivery(delivery_id, stable_room_id, state="failed", error_code=error_code)
            return
        self.store.update_delivery(
            delivery_id,
            stable_room_id,
            state="sending",
            actual_output="image",
            template_id=str(rendered.get("template_id") or ""),
            template_version=str(rendered.get("template_version") or ""),
        )
        self._send_image_parts_delivery(
            delivery_id,
            stable_room_id,
            report,
            output,
            runtime_room_id,
            client,
            retry_only,
            rendered.get("parts") or [],
            allow_text_fallback,
        )

    def _send_image_parts_delivery(
        self,
        delivery_id: str,
        stable_room_id: str,
        report: Dict[str, Any],
        output: Dict[str, Any],
        runtime_room_id: str,
        client: Any,
        retry_only: bool,
        parts: List[Dict[str, Any]],
        allow_text_fallback: bool,
    ) -> None:
        sent_count = 0
        existing = {int(row.get("part_index") or 0): row for row in self.store.list_delivery_parts(delivery_id, stable_room_id)}
        for index, part in enumerate(parts):
            previous = existing.get(index)
            if retry_only and previous and previous.get("state") == "sent":
                sent_count += 1
                continue
            relative_path = str(part.get("relative_path") or "")
            self.store.upsert_delivery_part(
                delivery_id, stable_room_id, index, "image",
                content_hash=_file_hash(self.renderer.asset_absolute_path(relative_path)),
                relative_path=relative_path,
                state="sending",
                attempt_count=int((previous or {}).get("attempt_count") or 0) + 1,
            )
            status = _send_image_confirmed(client, runtime_room_id, self.renderer.asset_absolute_path(relative_path))
            if status == "sent":
                sent_count += 1
                self.store.upsert_delivery_part(
                    delivery_id, stable_room_id, index, "image",
                    content_hash=_file_hash(self.renderer.asset_absolute_path(relative_path)),
                    relative_path=relative_path, state="sent",
                    attempt_count=int((previous or {}).get("attempt_count") or 0) + 1,
                )
                continue
            self.store.upsert_delivery_part(
                delivery_id, stable_room_id, index, "image", relative_path=relative_path,
                state=status, attempt_count=int((previous or {}).get("attempt_count") or 0) + 1,
                error_code="send_" + status,
            )
            if status == "unknown":
                self.store.update_delivery(delivery_id, stable_room_id, state="delivery_unknown", error_code="send_unknown")
                return
            if sent_count:
                self.store.update_delivery(delivery_id, stable_room_id, state="partial_failed", error_code="image_part_failed")
                return
            if allow_text_fallback:
                self.store.update_delivery(
                    delivery_id, stable_room_id, state="fallback_sending", actual_output="text",
                    fallback_reason="image_send_failed",
                )
                self._send_text_delivery(
                    delivery_id, stable_room_id, report, output, runtime_room_id, client, retry_only,
                    fallback=True,
                )
                return
            self.store.update_delivery(delivery_id, stable_room_id, state="failed", error_code="image_send_failed")
            return
        self.store.update_delivery(delivery_id, stable_room_id, state="sent", actual_output="image", sent_at=int(time.time()))

    def _send_text_delivery(
        self,
        delivery_id: str,
        stable_room_id: str,
        report: Dict[str, Any],
        output: Dict[str, Any],
        runtime_room_id: str,
        client: Any,
        retry_only: bool,
        fallback: bool = False,
    ) -> None:
        rendered = self.renderer.render_text(report, output)
        self._send_text_parts_delivery(
            delivery_id,
            stable_room_id,
            rendered.get("parts") or [],
            runtime_room_id,
            client,
            retry_only,
            fallback=fallback,
        )

    def _send_text_parts_delivery(
        self,
        delivery_id: str,
        stable_room_id: str,
        parts: List[str],
        runtime_room_id: str,
        client: Any,
        retry_only: bool,
        fallback: bool = False,
    ) -> None:
        self.store.update_delivery(
            delivery_id, stable_room_id, state="fallback_sending" if fallback else "sending", actual_output="text",
        )
        existing = {int(row.get("part_index") or 0): row for row in self.store.list_delivery_parts(delivery_id, stable_room_id)}
        sent_count = 0
        part_offset = 1000 if fallback else 0
        for sequence_index, text in enumerate(parts):
            index = part_offset + sequence_index
            previous = existing.get(index)
            if retry_only and previous and previous.get("state") == "sent":
                sent_count += 1
                continue
            content_hash = _text_hash(text)
            self.store.upsert_delivery_part(
                delivery_id, stable_room_id, index, "text", content_hash=content_hash,
                state="sending", attempt_count=int((previous or {}).get("attempt_count") or 0) + 1,
            )
            status = _send_text_confirmed(client, runtime_room_id, text)
            if status == "sent":
                sent_count += 1
                self.store.upsert_delivery_part(
                    delivery_id, stable_room_id, index, "text", content_hash=content_hash,
                    state="sent", attempt_count=int((previous or {}).get("attempt_count") or 0) + 1,
                )
                continue
            self.store.upsert_delivery_part(
                delivery_id, stable_room_id, index, "text", content_hash=content_hash, state=status,
                attempt_count=int((previous or {}).get("attempt_count") or 0) + 1,
                error_code="send_" + status,
            )
            if status == "unknown":
                self.store.update_delivery(delivery_id, stable_room_id, state="delivery_unknown", error_code="send_unknown")
            elif sent_count:
                self.store.update_delivery(delivery_id, stable_room_id, state="partial_failed", error_code="text_part_failed")
            else:
                self.store.update_delivery(delivery_id, stable_room_id, state="failed", error_code="text_send_failed")
            return
        self.store.update_delivery(
            delivery_id,
            stable_room_id,
            state="fallback_sent" if fallback else "sent",
            actual_output="text",
            sent_at=int(time.time()),
        )

    def _resolve_delivery_client(self, stable_room_id: str):
        channel = self.channel_getter()
        if channel is None:
            return "", None
        service = getattr(channel, "identity_service", None) or self.identity_service
        try:
            runtime_room_id = str(service.get_active_runtime_room_id(stable_room_id) or "").strip()
        except Exception:
            runtime_room_id = ""
        return runtime_room_id, getattr(channel, "client", None)


def _send_text_confirmed(client: Any, room_id: str, text: str) -> str:
    method = getattr(client, "send_text_confirmed", None)
    if not callable(method):
        return "unknown"
    try:
        return _normalize_send_status(method(room_id, text, mention_ids=[]))
    except TypeError:
        return _normalize_send_status(method(room_id, text))
    except Exception:
        return "failed"


def _send_image_confirmed(client: Any, room_id: str, path: str) -> str:
    method = getattr(client, "send_image_confirmed", None)
    if not callable(method):
        return "unknown"
    try:
        return _normalize_send_status(method(room_id, path))
    except Exception:
        return "failed"


def _normalize_send_status(value: Any) -> str:
    status = str(value or "unknown").lower()
    return status if status in {"sent", "failed", "unknown"} else "unknown"


def _text_hash(value: Any) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def _file_hash(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _get_running_wechat_group_channel():
    try:
        import sys
        for name in ("__main__", "app"):
            module = sys.modules.get(name)
            manager = getattr(module, "_channel_mgr", None) if module else None
            if manager is not None:
                channel = manager.get_channel("wechat_group")
                if channel is not None:
                    return channel
    except Exception:
        pass
    return None
