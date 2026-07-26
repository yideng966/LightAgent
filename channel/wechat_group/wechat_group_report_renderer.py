"""Render six-module reports as safe text or local Playwright PNG assets."""

from __future__ import annotations

import html
import os
import re
import shutil
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from channel.wechat_group.wechat_group_report_store import validate_report_asset_relative_path
from channel.wechat_group.wechat_group_report_templates import (
    BUILTIN_TEXT_TEMPLATE_ID,
    get_builtin_text_template,
    render_text_report,
    split_report_text,
)
from channel.wechat_group.wechat_group_report_templates_registry import WechatGroupReportTemplateRegistry
from config import conf


REPORT_IMAGE_WIDTH = 941
REPORT_IMAGE_MAX_HEIGHT = 12000
_LINKS_PER_INITIAL_PART = 14


class ReportImageRenderError(RuntimeError):
    """Known render failure exposed as a stable delivery error code."""


class WechatGroupReportRenderer:
    def __init__(self, registry: Optional[WechatGroupReportTemplateRegistry] = None) -> None:
        self.registry = registry or WechatGroupReportTemplateRegistry()

    def render_text(self, report: Dict[str, Any], output: Dict[str, Any]) -> Dict[str, Any]:
        source = str((output or {}).get("text_template_source") or "builtin")
        if source == "custom":
            template = str((output or {}).get("custom_text_template") or "")
        else:
            template = get_builtin_text_template(
                str((output or {}).get("builtin_text_template_id") or BUILTIN_TEXT_TEMPLATE_ID)
            )
        text = render_text_report(report, template)
        return {"text": text, "parts": split_report_text(text)}

    def render_images(
        self,
        report: Dict[str, Any],
        output: Dict[str, Any],
        report_id: str,
    ) -> Dict[str, Any]:
        source = str((output or {}).get("image_template_source") or "skill")
        if source != "skill":
            raise ReportImageRenderError("builtin_image_template_unavailable")
        template = self.registry.resolve_template(str((output or {}).get("skill_image_template_name") or ""))
        sandbox = self.registry.copy_template_to_sandbox(template)
        try:
            html_template = Path(sandbox, Path(template["entry_html"]).name).read_text(encoding="utf-8")
            css = Path(sandbox, Path(template["stylesheet"]).name).read_text(encoding="utf-8")
            target_root = self._ensure_asset_root()
            chunks = self._split_link_chunks(report.get("links") or [])
            generated = []
            for index, links in enumerate(chunks, 1):
                generated.extend(self._render_chunk_with_split(
                    html_template,
                    css,
                    report,
                    links,
                    target_root,
                    report_id,
                    template,
                    part_index=len(generated) + 1,
                    include_non_link_sections=index == 1,
                    continuation=index > 1,
                ))
            return {
                "template_id": template["template_id"],
                "template_version": template["version"],
                "template_version_hash": template["version_hash"],
                "parts": generated,
            }
        finally:
            shutil.rmtree(sandbox, ignore_errors=True)

    def _render_chunk_with_split(
        self,
        html_template: str,
        css: str,
        report: Dict[str, Any],
        links: List[Dict[str, Any]],
        asset_root: str,
        report_id: str,
        template: Dict[str, Any],
        part_index: int,
        include_non_link_sections: bool,
        continuation: bool,
    ) -> List[Dict[str, Any]]:
        fragment = self._build_report_fragment(
            report,
            links,
            include_non_link_sections=include_non_link_sections,
            continuation=continuation,
        )
        rendered = self._render_png(
            html_template, css, fragment, asset_root, report_id, template, part_index,
        )
        if rendered["height"] <= REPORT_IMAGE_MAX_HEIGHT:
            return [rendered]
        if len(links) <= 1:
            _safe_remove(self.asset_absolute_path(rendered["relative_path"]))
            raise ReportImageRenderError("image_part_too_tall")
        # Keep link rows intact and split only at a link-chapter boundary.
        _safe_remove(self.asset_absolute_path(rendered["relative_path"]))
        midpoint = max(1, len(links) // 2)
        first = self._render_chunk_with_split(
            html_template, css, report, links[:midpoint], asset_root, report_id, template,
            part_index, include_non_link_sections, continuation,
        )
        second = self._render_chunk_with_split(
            html_template, css, report, links[midpoint:], asset_root, report_id, template,
            part_index + len(first), False, True,
        )
        return first + second

    def asset_absolute_path(self, relative_path: str) -> str:
        relative = validate_report_asset_relative_path(relative_path)
        workspace = self._workspace_root()
        candidate = os.path.realpath(os.path.join(workspace, *relative.split("/")))
        if os.path.commonpath([workspace, candidate]) != workspace:
            raise ValueError("invalid report asset path")
        return candidate

    def cleanup_expired_assets(self, retention_days: Optional[int] = None) -> int:
        days = retention_days
        if days is None:
            days = conf().get("wechat_group_report_asset_retention_days", 90)
        try:
            cutoff = time.time() - max(int(days), 1) * 86400
        except (TypeError, ValueError):
            cutoff = time.time() - 90 * 86400
        removed = 0
        root = self._ensure_asset_root()
        for path in Path(root).glob("*.png"):
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink()
                    removed += 1
            except OSError:
                continue
        return removed

    def _render_png(
        self,
        html_template: str,
        css: str,
        fragment: str,
        asset_root: str,
        report_id: str,
        template: Dict[str, Any],
        part_index: int,
    ) -> Dict[str, Any]:
        try:
            from playwright.sync_api import sync_playwright
            from PIL import Image
        except Exception as exc:
            raise ReportImageRenderError("browser_unavailable") from exc
        safe_report_id = re.sub(r"[^A-Za-z0-9_-]", "", str(report_id or ""))[:64]
        if not safe_report_id:
            raise ReportImageRenderError("invalid_report_id")
        filename = f"{safe_report_id}_{template['template_id']}_{template['version_hash'][:10]}_{part_index}.png"
        absolute_path = os.path.join(asset_root, filename)
        document = html_template.replace("{{REPORT_CONTENT}}", fragment)
        document = document.replace("</head>", f"<style>{css}</style></head>")
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                context = browser.new_context(viewport={"width": REPORT_IMAGE_WIDTH, "height": 1000}, device_scale_factor=1)
                try:
                    context.route("**/*", lambda route: route.abort())
                    page = context.new_page()
                    page.set_content(document, wait_until="load")
                    if not page.evaluate("""() => [
                        'WenQuanYi Zen Hei', 'Noto Sans CJK SC', 'Microsoft YaHei', 'Arial'
                    ].some(font => document.fonts.check(`16px "${font}"`))"""):
                        raise ReportImageRenderError("chinese_font_unavailable")
                    page.screenshot(path=absolute_path, full_page=True, type="png")
                finally:
                    context.close()
                    browser.close()
        except ReportImageRenderError:
            raise
        except Exception as exc:
            raise ReportImageRenderError("browser_render_failed") from exc
        try:
            with Image.open(absolute_path) as image:
                width, height = image.size
                extrema = image.convert("RGB").getextrema()
                if width != REPORT_IMAGE_WIDTH or height <= 40 or all(low == high for low, high in extrema):
                    raise ReportImageRenderError("image_output_invalid")
        except ReportImageRenderError:
            _safe_remove(absolute_path)
            raise
        except Exception as exc:
            _safe_remove(absolute_path)
            raise ReportImageRenderError("image_output_invalid") from exc
        relative_path = os.path.relpath(absolute_path, self._workspace_root()).replace("\\", "/")
        return {
            "relative_path": validate_report_asset_relative_path(relative_path),
            "file_name": filename,
            "width": width,
            "height": height,
            "size_bytes": os.path.getsize(absolute_path),
        }

    @staticmethod
    def _split_link_chunks(links: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        rows = list(links or [])
        if not rows:
            return [[]]
        return [rows[index:index + _LINKS_PER_INITIAL_PART] for index in range(0, len(rows), _LINKS_PER_INITIAL_PART)]

    def _build_report_fragment(
        self,
        report: Dict[str, Any],
        links: List[Dict[str, Any]],
        include_non_link_sections: bool,
        continuation: bool,
    ) -> str:
        header = _cyber_header(report, continuation=continuation)
        if not include_non_link_sections:
            return _cyber_page(header + _links_section(links, continuation=True) + _report_footer(report), continuation=True)
        top = report.get("top_speaker") if isinstance(report.get("top_speaker"), dict) else {}
        summary = _summary_band(report, top)
        core = _core_statistics(report, top)
        ranking = _ranking_section(report.get("ranking"))
        topics = _topics_section(report.get("topics"))
        highlights = _highlights_section(report.get("highlights"))
        content = (
            header
            + summary
            + core
            + "<div class='duo-grid'>" + ranking + topics + "</div>"
            + highlights
            + _links_section(links)
            + _report_footer(report)
            + "<p class='report-footnote'>数据来源：当前群归档消息 · 统计事实由 LightAgent 确定性生成 · AI 仅负责内容归纳</p>"
        )
        return _cyber_page(content)

    @staticmethod
    def _workspace_root() -> str:
        configured = os.path.expanduser(str(conf().get("agent_workspace", "~/lightagent")))
        root = os.path.realpath(configured)
        os.makedirs(root, exist_ok=True)
        return root

    def _ensure_asset_root(self) -> str:
        root = os.path.join(self._workspace_root(), "images", "wechat_group_reports")
        os.makedirs(root, exist_ok=True)
        return root


def _cyber_page(content: str, continuation: bool = False) -> str:
    extra = " continuation" if continuation else ""
    return "<div class='cyber-page{}'><div class='top-line'></div>{}</div>".format(extra, content)


def _cyber_header(report: Dict[str, Any], continuation: bool = False) -> str:
    title = "群聊链接归档" if continuation else "群聊智能总结"
    subtitle = "按首次出现顺序 · URL 去重 · 安全抓取" if continuation else "数据聚合 · 话题洞察 · 精彩提炼 · 链接归档"
    tools = "" if continuation else (
        "<div class='hero-tools' aria-hidden='true'>"
        "<span class='hero-tool chat'></span><span class='hero-tool chart'></span><span class='hero-tool scan'></span>"
        "</div>"
    )
    return (
        "<header class='hero'>"
        "<div class='ai-badge'><strong>AI</strong><span>REPORT</span></div>"
        "<div class='hero-copy'><p class='eyebrow'>LIGHTAGENT · GROUP INTELLIGENCE</p>"
        f"<h1>{title}</h1><p class='hero-subtitle'>{subtitle}</p></div>{tools}"
        "</header>"
    )


def _summary_band(report: Dict[str, Any], top: Dict[str, Any]) -> str:
    room_name = _escape(report.get("room_name") or "未命名群聊")
    report_type = _escape(_report_type_label(report.get("report_type")))
    start = _escape(_short_time(report.get("period_start")))
    end = _escape(_short_time(report.get("period_end")))
    return (
        "<section class='summary-band' id='header'>"
        "<div class='summary-item room'><span class='summary-label'>01 群聊总结构 · 群名</span>"
        f"<strong class='summary-value'>{room_name}</strong></div>"
        "<div class='summary-item period'><span class='summary-label'>统计周期 · " + report_type + "</span>"
        f"<strong class='summary-value'>{start} — {end}</strong></div>"
        "<div class='summary-item metric'><span class='summary-label'>发言人数</span>"
        f"<strong class='summary-value'>{_number(report.get('active_speaker_count'))} 人</strong></div>"
        "<div class='summary-item metric count'><span class='summary-label'>消息数量</span>"
        f"<strong class='summary-value'>{_number(report.get('total_messages'))} 条</strong></div>"
        "</section>"
    )


def _module_heading(number: str, title: str, note: str = "", accent: str = "") -> str:
    note_html = f"<span class='module-note'>{_escape(note)}</span>" if note else ""
    accent_class = f" accent-{accent}" if accent else ""
    return (
        f"<header class='module-heading{accent_class}'><span class='module-number'>{number}</span>"
        f"<h2>{_escape(title)}</h2>{note_html}<span class='module-line'></span></header>"
    )


def _core_statistics(report: Dict[str, Any], top: Dict[str, Any]) -> str:
    return (
        "<section class='module core-module' id='core_statistics'>"
        + _module_heading("02", "核心统计")
        + "<div class='core-grid'>"
        f"<article class='core-card'><span class='core-label'>总发言数</span><strong class='core-value'>{_number(report.get('total_messages')):,}</strong></article>"
        f"<article class='core-card'><span class='core-label'>榜一大哥 · 当前昵称</span><strong class='core-value'>{_escape(top.get('display_name') or '暂无')}</strong></article>"
        f"<article class='core-card'><span class='core-label'>重点话题数量</span><strong class='core-value'>{_number(report.get('topic_count'))} 个</strong></article>"
        "</div></section>"
    )


def _ranking_section(items: Any) -> str:
    rows = items if isinstance(items, list) else []
    counts = [_number(item.get("message_count")) for item in rows if isinstance(item, dict)]
    max_count = max(counts) if counts else 1
    body = ""
    for index, item in enumerate(rows[:5], 1):
        row = item if isinstance(item, dict) else {}
        count = _number(row.get("message_count"))
        width = min(max(round(count * 100 / max_count), 8), 100)
        body += (
            "<li class='ranking-row'><span class='rank-index'>"
            + str(_number(row.get("rank") or index)).zfill(2)
            + "</span><span class='rank-avatar'>"
            + _escape(str(row.get("display_name") or "群")[:1])
            + "</span><span class='rank-main'><strong class='rank-name'>"
            + _escape(row.get("display_name") or "未命名群友")
            + "</strong><span class='rank-track'><span style='width:"
            + str(width)
            + "%'></span></span></span><strong class='rank-count'>"
            + str(count)
            + "</strong></li>"
        )
    if not body:
        body = "<p class='ranking-empty'>本周期暂无可稳定归属的发言排行。</p>"
    return (
        "<section class='module ranking-module' id='ranking'>"
        + _module_heading("03", "发言排行榜 TOP 5", accent="blue")
        + "<p class='ranking-kicker'>当前昵称 · 按成员 ID 合并</p><ol class='ranking-list'>"
        + body + "</ol></section>"
    )


def _topics_section(items: Any) -> str:
    rows = items if isinstance(items, list) else []
    cards = ""
    for index in range(3):
        item = rows[index] if index < len(rows) and isinstance(rows[index], dict) else None
        if not item:
            cards += "<article class='topic-card'><div class='heat-chip'>热度<strong>-</strong></div><div><h3 class='topic-title'>本周期有效话题不足</h3><p class='topic-summary'>继续积累群聊归档后，会在这里展示重点讨论。</p></div></article>"
            continue
        cards += (
            "<article class='topic-card'><div class='heat-chip'>热度<strong>"
            + str(_number(item.get("heat")))
            + "</strong></div><div><h3 class='topic-title'>"
            + _escape(item.get("title") or "群内讨论")
            + "</h3><p class='topic-summary'>"
            + _escape(item.get("summary") or "暂无概括。")
            + "</p></div></article>"
        )
    return (
        "<section class='module topics-module' id='topics'>"
        + _module_heading("04", "重点话题 · 热度与内容", accent="purple")
        + "<div class='topic-list'>" + cards + "</div></section>"
    )


def _highlights_section(items: Any) -> str:
    rows = items if isinstance(items, list) else []
    cards = ""
    for index in range(3):
        item = rows[index] if index < len(rows) and isinstance(rows[index], dict) else None
        if not item:
            cards += "<article class='highlight-card'><div class='highlight-head'><span class='highlight-index'>" + str(index + 1) + "</span><strong class='highlight-name'>等待高光发言</strong></div><p class='highlight-quote'>“继续积累群聊内容。”</p><div class='highlight-comment'><strong>AI 锐评</strong>本周期有效精彩发言不足。</div></article>"
            continue
        cards += (
            "<article class='highlight-card'><div class='highlight-head'><span class='highlight-index'>"
            + str(index + 1)
            + "</span><strong class='highlight-name'>"
            + _escape(item.get("speaker_display_name") or "未命名群友")
            + "</strong></div><p class='highlight-quote'>“"
            + _escape(item.get("quote") or "")
            + "”</p><div class='highlight-comment'><strong>AI 锐评</strong>"
            + _escape(item.get("commentary") or "这句话把讨论说得很有画面。")
            + "</div></article>"
        )
    return (
        "<section class='module highlights-module' id='highlights'>"
        + _module_heading("05", "精彩发言 · 今日高光三连", "真实原话 + AI 轻松锐评", "purple")
        + "<div class='highlights-grid'>" + cards + "</div></section>"
    )


def _links_section(items: Any, continuation: bool = False) -> str:
    rows = items if isinstance(items, list) else []
    if not rows:
        return (
            "<section class='module links-module' id='links'>"
            + _module_heading("06", "群聊链接收集 · 共 0 条", "按首次出现顺序 · URL 去重 · 安全抓取", "green")
            + "<p class='link-empty'>本周期未收集到链接。</p></section>"
        )
    cards = ""
    for index, item in enumerate(rows, 1):
        row = item if isinstance(item, dict) else {}
        providers = row.get("provider_display_names") if isinstance(row.get("provider_display_names"), list) else []
        cards += (
            "<article class='link-card'><span class='link-index'>"
            + str(index).zfill(2)
            + "</span><div class='link-main'><strong class='link-domain'>"
            + _escape(row.get("domain") or "链接")
            + "</strong><p class='link-url'>"
            + _escape(row.get("url") or "")
            + "</p><p class='link-summary'>"
            + _escape(row.get("summary") or _link_state_text(row.get("fetch_status")))
            + "</p></div><span class='link-provider'>"
            + _escape("、".join(str(name) for name in providers) or "未稳定归属")
            + "</span></article>"
        )
    title = "群聊链接收集 · 续" if continuation else "群聊链接收集 · 共 {} 条".format(len(rows))
    return (
        "<section class='module links-module' id='links'>"
        + _module_heading("06", title, "按首次出现顺序 · URL 去重 · 安全抓取", "green")
        + "<div class='link-list'>" + cards + "</div></section>"
    )


def _report_footer(report: Dict[str, Any]) -> str:
    archive_count = _number(report.get("archive_message_count"))
    unresolved = _number(report.get("unresolved_message_count"))
    stable_count = max(archive_count - unresolved, 0)
    return (
        "<footer class='report-footer' id='footer'><span>归档 "
        + f"{archive_count:,} 条 · 稳定归属 {stable_count:,} 条 · 未解析 {unresolved:,} 条</span>"
        + "<span>生成于 " + _escape(_format_time(report.get("generated_at")))
        + " · " + _escape(report.get("timezone") or "Asia/Shanghai") + "</span></footer>"
    )


def _link_state_text(value: Any) -> str:
    return {
        "blocked": "链接因安全策略被拒绝。",
        "timeout": "链接抓取超时。",
        "login_required": "链接需要登录后访问。",
        "empty": "链接正文为空或不可解析。",
        "failed": "链接抓取失败。",
    }.get(str(value or ""), "已安全抓取链接正文。")


def _escape(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def _number(value: Any) -> int:
    try:
        return max(int(value or 0), 0)
    except (TypeError, ValueError):
        return 0


def _format_time(value: Any) -> str:
    text = str(value or "").strip()
    try:
        return time.strftime("%Y-%m-%d %H:%M", time.strptime(text[:16], "%Y-%m-%dT%H:%M"))
    except Exception:
        return text or "-"


def _short_time(value: Any) -> str:
    formatted = _format_time(value)
    return formatted[5:] if len(formatted) >= 16 else formatted


def _report_type_label(value: Any) -> str:
    return {
        "daily": "自然日报",
        "weekly": "自然周报",
        "monthly": "自然月报",
        "custom": "自定义范围",
    }.get(str(value or "").lower(), "群聊报告")


def _safe_remove(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass
