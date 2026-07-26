"""Scheduler reconciliation for room-scoped WeChat group report settings."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from agent.tools.scheduler.integration import get_task_store
from channel.wechat_group.wechat_group_identity_service import WechatGroupIdentityService
from channel.wechat_group.wechat_group_report_store import WechatGroupReportStore


REPORT_TYPES = ("daily", "weekly", "monthly")


class WechatGroupReportScheduler:
    def __init__(
        self,
        store: Optional[WechatGroupReportStore] = None,
        identity_service: Optional[WechatGroupIdentityService] = None,
        task_store=None,
    ) -> None:
        self.store = store or WechatGroupReportStore()
        self.identity_service = identity_service or WechatGroupIdentityService()
        self.task_store = task_store

    def reconcile(self, stable_room_id: str, settings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        room_id = str(stable_room_id or "").strip()
        if not room_id:
            raise ValueError("stable_room_id is required")
        settings = settings or self.store.get_settings(room_id)
        task_store = self.task_store or get_task_store()
        if task_store is None:
            raise RuntimeError("scheduler task store is unavailable")
        runtime_room_id = self.identity_service.get_active_runtime_room_id(room_id)
        timezone_name = str(settings.get("timezone") or "Asia/Shanghai")
        schedules = settings.get("schedules") if isinstance(settings.get("schedules"), dict) else {}
        tasks = []
        for report_type in REPORT_TYPES:
            schedule = schedules.get(report_type) if isinstance(schedules.get(report_type), dict) else {}
            enabled = bool(settings.get("enabled")) and bool(schedule.get("enabled"))
            send_time = str(schedule.get("send_time") or "09:00")
            cron = _build_report_cron(report_type, send_time)
            task = {
                "id": report_task_id(room_id, report_type),
                "name": f"微信群{_report_type_label(report_type)}",
                "enabled": enabled,
                "created_at": datetime.now().isoformat(),
                "schedule": {"type": "cron", "expression": cron, "timezone": timezone_name},
                "action": {
                    "type": "wechat_group_report",
                    "channel_type": "wechat_group",
                    "receiver_kind": "wechat_group",
                    "stable_receiver": room_id,
                    "receiver": runtime_room_id,
                    "runtime_receiver": runtime_room_id,
                    "report_type": report_type,
                    "settings_version": int(settings.get("version") or 0),
                },
            }
            task_store.upsert_task(task)
            tasks.append({
                "report_type": report_type,
                "task_id": task["id"],
                "enabled": enabled,
                "cron": cron,
                "timezone": timezone_name,
            })
        return {"status": "synced", "tasks": tasks}


def report_task_id(stable_room_id: str, report_type: str) -> str:
    room_id = str(stable_room_id or "").strip()
    if not room_id:
        raise ValueError("stable_room_id is required")
    if report_type not in REPORT_TYPES:
        raise ValueError("invalid report type")
    return f"wechat_group_report:{room_id}:{report_type}"


def _build_report_cron(report_type: str, send_time: str) -> str:
    try:
        hour_text, minute_text = str(send_time or "").split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)
    except Exception as exc:
        raise ValueError("invalid report send_time") from exc
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("invalid report send_time")
    if report_type == "daily":
        return f"{minute} {hour} * * *"
    if report_type == "weekly":
        return f"{minute} {hour} * * 1"
    if report_type == "monthly":
        return f"{minute} {hour} 1 * *"
    raise ValueError("invalid report type")


def _report_type_label(report_type: str) -> str:
    return {"daily": "日报", "weekly": "周报", "monthly": "月报"}.get(report_type, "报告")
