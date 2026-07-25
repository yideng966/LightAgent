"""Current-scope Agent tools for requesting WeChat group reports."""

from __future__ import annotations

from typing import Any, List

from agent.tools.base_tool import BaseTool, ToolResult
from channel.wechat_group.wechat_group_permissions import can_generate_wechat_group_report


class WechatGroupReportTool(BaseTool):
    name = "wechat_group_report"
    description = (
        "Generate or check a report for the current WeChat group only. The server binds "
        "the stable group and sender identity; this tool never accepts a room id, member id, "
        "or send target from the model."
    )
    params = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["generate", "status"],
                "description": "generate a report or check a current-group job status",
                "default": "generate",
            },
            "report_type": {
                "type": "string",
                "enum": ["daily", "weekly", "monthly", "custom"],
                "description": "Report period. daily/weekly/monthly use the prior natural period.",
                "default": "daily",
            },
            "custom_start": {"type": "string", "description": "ISO start time for custom reports", "default": ""},
            "custom_end": {"type": "string", "description": "ISO end time for custom reports", "default": ""},
            "job_id": {"type": "string", "description": "Current-group report job id for status", "default": ""},
        },
        "required": [],
    }

    def __init__(self, stable_room_id: str, stable_member_id: str, identity_confirmed: bool = True) -> None:
        super().__init__()
        self.stable_room_id = str(stable_room_id or "").strip()
        self.stable_member_id = str(stable_member_id or "").strip()
        self.identity_confirmed = bool(identity_confirmed)

    def execute(self, params: dict) -> ToolResult:
        action = str((params or {}).get("action") or "generate").strip().lower()
        if not self.identity_confirmed or not self.stable_room_id:
            return ToolResult.fail("当前群身份尚未确认，不能请求群聊报告。")
        if action == "status":
            return self._status(params or {})
        if action != "generate":
            return ToolResult.fail("不支持的群聊报告操作。")
        allowed, reason = can_generate_wechat_group_report(self.stable_room_id, self.stable_member_id)
        if not allowed:
            return ToolResult.fail(_permission_message(reason))
        report_type = str((params or {}).get("report_type") or "daily").strip().lower()
        if report_type not in {"daily", "weekly", "monthly", "custom"}:
            return ToolResult.fail("报告周期必须是日报、周报、月报或自定义范围。")
        if report_type == "custom" and not ((params or {}).get("custom_start") and (params or {}).get("custom_end")):
            return ToolResult.fail("自定义报告需要同时提供开始和结束时间。")
        try:
            from agent.tools.scheduler.integration import get_wechat_group_report_runtime

            runner, delivery_service = get_wechat_group_report_runtime()
            settings = runner.store.get_settings(self.stable_room_id)

            def deliver_when_ready(report, job):
                current_settings = runner.store.get_settings(self.stable_room_id)
                if not current_settings.get("enabled"):
                    return
                delivery = delivery_service.create_delivery(
                    report_id=str(report.get("report_id") or ""),
                    stable_room_id=self.stable_room_id,
                    actor="group_member",
                    output_settings=current_settings,
                )
                delivery_service.submit_delivery(delivery["delivery_id"], self.stable_room_id)

            job = runner.submit_generation(
                stable_room_id=self.stable_room_id,
                report_type=report_type,
                actor="group_member",
                draft_settings=settings,
                custom_start=(params or {}).get("custom_start"),
                custom_end=(params or {}).get("custom_end"),
                ready_callback=deliver_when_ready,
            )
        except Exception as exc:
            return ToolResult.fail("群聊报告任务提交失败：{}".format(str(exc)[:120]))
        return ToolResult.success(
            "群聊报告已提交。任务状态：{}。".format(job.get("state") or "queued"),
            ext_data={"job_id": job.get("job_id") or ""},
        )

    def _status(self, params: dict) -> ToolResult:
        job_id = str(params.get("job_id") or "").strip()
        if not job_id:
            return ToolResult.fail("查询报告状态需要 job_id。")
        try:
            from agent.tools.scheduler.integration import get_wechat_group_report_runtime

            runner, _ = get_wechat_group_report_runtime()
            job = runner.get_status(job_id, self.stable_room_id)
        except Exception as exc:
            return ToolResult.fail("群聊报告状态查询失败：{}".format(str(exc)[:120]))
        if not job:
            return ToolResult.fail("未找到当前群的报告任务。")
        return ToolResult.success(
            "群聊报告任务状态：{}，阶段：{}，进度：{}/{}。".format(
                job.get("state") or "unknown",
                job.get("stage") or "unknown",
                job.get("completed_items") or 0,
                job.get("total_items") or 0,
            )
        )


def create_wechat_group_report_tools(
    stable_room_id: str,
    stable_member_id: str,
    identity_confirmed: bool = True,
) -> List[BaseTool]:
    if not stable_room_id:
        return []
    return [WechatGroupReportTool(stable_room_id, stable_member_id, identity_confirmed)]


def _permission_message(reason: str) -> str:
    return {
        "identity_unconfirmed": "当前群身份尚未确认，不能生成群聊报告。",
        "report_disabled": "当前群的群聊报告尚未启用。",
        "admin_required": "生成群聊报告需要当前群管理员触发。",
    }.get(reason, "当前无法生成群聊报告。")
