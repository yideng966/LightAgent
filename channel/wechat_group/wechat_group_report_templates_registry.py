"""Discover and validate static Skill-backed image report templates."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent.skills.manager import SkillManager
from config import conf


REPORT_TEMPLATE_MANIFEST = "assets/wechat-group-report-template.json"
REPORT_TEMPLATE_REQUIRED_SECTIONS = {
    "header", "core_statistics", "ranking", "topics", "highlights", "links", "footer",
}
DEFAULT_CYBER_INTELLIGENCE_SKILL = "wechat-group-report-cyber-intelligence"
_UNSAFE_HTML_PATTERN = re.compile(r"<\s*script\b|\bon\w+\s*=|<\s*iframe\b", re.IGNORECASE)
_UNSAFE_CSS_PATTERN = re.compile(r"@import|url\s*\(|expression\s*\(", re.IGNORECASE)


class WechatGroupReportTemplateRegistry:
    """Only exposes enabled, local Skill templates with a strict manifest contract."""

    def __init__(self, skill_manager: Optional[SkillManager] = None) -> None:
        self.skill_manager = skill_manager or self._create_skill_manager()

    def list_templates(self, include_invalid: bool = True) -> List[Dict[str, Any]]:
        templates: List[Dict[str, Any]] = []
        for entry in self.skill_manager.list_skills():
            skill = entry.skill
            record = self._load_template_record(skill.name, skill.base_dir)
            record["skill_name"] = skill.name
            record["enabled"] = bool(self.skill_manager.is_skill_enabled(skill.name))
            if not record.get("enabled") and record.get("valid"):
                record["valid"] = False
                record["reason"] = "skill_disabled"
            if include_invalid or record.get("valid"):
                templates.append(record)
        templates.sort(key=lambda item: (not bool(item.get("valid")), str(item.get("display_name") or item.get("skill_name") or "")))
        return templates

    def resolve_template(self, skill_name: str) -> Dict[str, Any]:
        name = str(skill_name or "").strip()
        if not name:
            raise ValueError("skill image template name is required")
        entry = self.skill_manager.get_skill(name)
        if entry is None:
            raise ValueError("skill image template is not found")
        record = self._load_template_record(entry.skill.name, entry.skill.base_dir)
        record["skill_name"] = entry.skill.name
        record["enabled"] = bool(self.skill_manager.is_skill_enabled(entry.skill.name))
        if not record.get("enabled"):
            record["valid"] = False
            record["reason"] = "skill_disabled"
        if not record.get("valid"):
            raise ValueError(str(record.get("reason") or "invalid report image template"))
        return record

    def _load_template_record(self, skill_name: str, base_dir: str) -> Dict[str, Any]:
        """Keep the shipped default report template deterministic across upgrades."""
        resolved_base_dir = self._bundled_default_template_dir(skill_name) or base_dir
        return self._load_skill_template(skill_name, resolved_base_dir)

    def _bundled_default_template_dir(self, skill_name: str) -> str:
        if skill_name != DEFAULT_CYBER_INTELLIGENCE_SKILL:
            return ""
        candidates = []
        builtin_dir = str(getattr(self.skill_manager, "builtin_dir", "") or "").strip()
        if builtin_dir:
            candidates.append(Path(builtin_dir))
        candidates.append(Path(__file__).resolve().parents[2] / "skills")
        for root in candidates:
            candidate = (root / DEFAULT_CYBER_INTELLIGENCE_SKILL).resolve()
            if (candidate / "SKILL.md").is_file():
                return str(candidate)
        return ""

    def copy_template_to_sandbox(self, template: Dict[str, Any]) -> str:
        """Copy approved static assets to an isolated, disposable render directory."""
        base_dir = Path(str(template.get("base_dir") or "")).resolve()
        asset_root = (base_dir / "assets").resolve()
        if not _is_within(asset_root, base_dir / "assets"):
            raise ValueError("invalid template asset root")
        sandbox = Path(tempfile.mkdtemp(prefix="lightagent-wg-report-"))
        try:
            for relative in (template.get("entry_html"), template.get("stylesheet")):
                src = _safe_asset_path(asset_root, relative)
                destination = sandbox / Path(str(relative)).name
                shutil.copy2(src, destination)
            return str(sandbox)
        except Exception:
            shutil.rmtree(sandbox, ignore_errors=True)
            raise

    def _load_skill_template(self, skill_name: str, base_dir: str) -> Dict[str, Any]:
        record: Dict[str, Any] = {
            "skill_name": skill_name,
            "base_dir": str(base_dir or ""),
            "valid": False,
            "reason": "manifest_missing",
        }
        try:
            root = Path(base_dir).resolve()
            manifest_path = _safe_asset_path(root / "assets", "wechat-group-report-template.json")
            with open(manifest_path, "r", encoding="utf-8") as handle:
                manifest = json.load(handle)
            if not isinstance(manifest, dict):
                raise ValueError("manifest_invalid")
            if manifest.get("schema_version") != 1:
                raise ValueError("manifest_schema_version")
            if manifest.get("type") != "wechat_group_report_image_template":
                raise ValueError("manifest_type")
            if int(manifest.get("width") or 0) != 941:
                raise ValueError("manifest_width")
            required_sections = set(manifest.get("required_sections") or [])
            if not REPORT_TEMPLATE_REQUIRED_SECTIONS.issubset(required_sections):
                raise ValueError("manifest_required_sections")
            template_id = str(manifest.get("template_id") or "").strip()
            display_name = str(manifest.get("display_name") or "").strip()
            version = str(manifest.get("version") or "").strip()
            if not template_id or not display_name or not version:
                raise ValueError("manifest_identity")
            asset_root = root / "assets"
            entry_html = str(manifest.get("entry_html") or "")
            stylesheet = str(manifest.get("stylesheet") or "")
            preview = str(manifest.get("preview") or "")
            html_path = _safe_asset_path(asset_root, entry_html)
            css_path = _safe_asset_path(asset_root, stylesheet)
            preview_path = _safe_asset_path(asset_root, preview)
            html_text = html_path.read_text(encoding="utf-8")
            css_text = css_path.read_text(encoding="utf-8")
            if "{{REPORT_CONTENT}}" not in html_text:
                raise ValueError("template_placeholder_missing")
            if _UNSAFE_HTML_PATTERN.search(html_text):
                raise ValueError("template_html_unsafe")
            if _UNSAFE_CSS_PATTERN.search(css_text):
                raise ValueError("template_css_unsafe")
            if not preview_path.is_file():
                raise ValueError("preview_missing")
            version_hash = _hash_files([manifest_path, html_path, css_path, preview_path])
            record.update({
                "valid": True,
                "reason": "",
                "template_id": template_id,
                "display_name": display_name,
                "version": version,
                "version_hash": version_hash,
                "entry_html": entry_html,
                "stylesheet": stylesheet,
                "preview": preview,
                "width": 941,
            })
        except Exception as exc:
            record["reason"] = str(exc)
        return record

    @staticmethod
    def _create_skill_manager() -> SkillManager:
        project_root = Path(__file__).resolve().parents[2]
        workspace = os.path.expanduser(str(conf().get("agent_workspace", "~/lightagent")))
        return SkillManager(
            builtin_dir=str(project_root / "skills"),
            custom_dir=str(Path(workspace) / "skills"),
        )


def _safe_asset_path(asset_root: Path, relative_path: Any) -> Path:
    relative = str(relative_path or "").replace("\\", "/").strip("/")
    if not relative or relative.startswith("/") or ".." in relative.split("/"):
        raise ValueError("template_asset_path")
    root = asset_root.resolve()
    candidate = (root / relative).resolve()
    if not _is_within(root, candidate) or candidate.is_symlink() or not candidate.is_file():
        raise ValueError("template_asset_path")
    return candidate


def _is_within(root: Path, target: Path) -> bool:
    try:
        target.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _hash_files(paths: List[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.name.encode("utf-8"))
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
    return digest.hexdigest()
