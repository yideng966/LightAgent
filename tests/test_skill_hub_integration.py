import unittest
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from agent.protocol.agent_stream import AgentStreamExecutor
from agent.skills.manager import SkillManager
from agent.skills.types import Skill, SkillEntry, SkillSnapshot
from cli.commands.skill import InstallResult, SkillInstallError, _install_hub
from channel.web.web_channel import _filter_skill_hub_source, _paginate_skill_hub_catalog


ROOT = Path(__file__).resolve().parents[1]


class SkillHubIntegrationSurfaceTest(unittest.TestCase):
    def test_web_route_and_management_controls_are_present(self):
        backend = (ROOT / "channel/web/web_channel.py").read_text(encoding="utf-8")
        frontend = (ROOT / "channel/web/static/js/console.js").read_text(encoding="utf-8")
        html = (ROOT / "channel/web/chat.html").read_text(encoding="utf-8")
        self.assertIn("'/api/skill-hub', 'SkillHubHandler'", backend)
        self.assertNotIn("approval_required", backend)
        self.assertIn("function openSkillHubModal()", frontend)
        self.assertIn("page_size: String(skillHubState.pageSize)", frontend)
        self.assertIn("loadSkillHub({refresh: true})", frontend)
        self.assertIn("function runSkillHubBatch(operation)", frontend)
        self.assertIn("selected: new Map()", frontend)
        self.assertIn("永久删除，且无法恢复", frontend)
        self.assertIn("id=\"skill-hub-modal\"", html)
        self.assertIn("id=\"skill-hub-detail-modal\"", html)
        self.assertIn("id=\"skill-hub-search\"", html)
        self.assertNotIn("id=\"skill-hub-risk\"", html)
        self.assertNotIn("approve-risk", frontend)
        self.assertIn("id=\"skill-hub-select-page\"", html)
        self.assertIn("id=\"skill-hub-batch-result\"", html)
        self.assertIn('data-skill-hub-source="lightagent-skillhub"', html)
        self.assertIn('data-skill-hub-source="cowagent-skillhub"', html)
        self.assertIn("source: 'lightagent-skillhub'", frontend)
        self.assertIn("source: skillHubState.source", frontend)
        self.assertIn("function switchSkillHubSource(source)", frontend)
        self.assertIn("if (search) search.value = '';", frontend)
        self.assertIn("formatSkillCategory(skill.category)", frontend)
        self.assertIn("访问原技能广场", frontend)
        dockerfile = (ROOT / "docker/Dockerfile.latest").read_text(encoding="utf-8")
        self.assertIn("/usr/local/bin/npm /usr/local/bin/npm", dockerfile)
        self.assertIn("/usr/local/lib/node_modules/npm", dockerfile)
        self.assertNotIn("loadSkillHub();\n}", frontend.split("function loadSkillsView()", 1)[1].split("let skillHubSearchTimer", 1)[0])

    def test_web_api_exposes_versions_batch_and_purge_uninstall(self):
        backend = (ROOT / "channel/web/web_channel.py").read_text(encoding="utf-8")
        for field in (
            '"installed_version"', '"available_version"', '"update_available"',
            '"update_status"', '"last_checked_at"',
        ):
            self.assertIn(field, backend)
        self.assertIn('if action == "batch":', backend)
        self.assertIn('purge_data=operation == "uninstall"', backend)
        self.assertIn('manager.uninstall(name, purge_data=True)', backend)
        self.assertIn('get_builtin_skills_dir()', backend)
        self.assertIn('"builtin"\n                            if is_builtin', backend)

    def test_web_catalog_supports_filtering_and_pagination(self):
        backend = (ROOT / "channel/web/web_channel.py").read_text(encoding="utf-8")
        frontend = (ROOT / "channel/web/static/js/console.js").read_text(encoding="utf-8")
        self.assertIn('source="lightagent-skillhub", action="list", category="", page="1", page_size="12"', backend)
        self.assertIn("_paginate_skill_hub_catalog", backend)
        self.assertIn("_filter_skill_hub_source", backend)
        self.assertIn('"catalog_sources": source_counts', backend)
        self.assertIn("skill.registry_source || 'lightagent-skillhub'", frontend)
        self.assertIn("原技能广场", frontend)

    def test_web_catalog_paginates_and_filters_by_category(self):
        skills = [
            {
                "name": f"skill-{index:02d}",
                "category": "office" if index % 2 else "developer",
            }
            for index in range(25)
        ]
        page, categories, pagination = _paginate_skill_hub_catalog(
            skills, page=2, page_size=12
        )
        self.assertEqual(12, len(page))
        self.assertEqual("skill-12", page[0]["name"])
        self.assertEqual(["developer", "office"], categories)
        self.assertEqual({"page": 2, "page_size": 12, "total": 25, "total_pages": 3}, pagination)

        filtered, _, filtered_pagination = _paginate_skill_hub_catalog(
            skills, category="office", page=1, page_size=12
        )
        self.assertEqual(
            [f"skill-{index:02d}" for index in range(1, 25, 2)],
            [item["name"] for item in filtered],
        )
        self.assertEqual(12, filtered_pagination["total"])

    def test_web_catalog_defaults_to_official_source_and_separates_marketplace(self):
        skills = [
            {"name": "official", "registry_source": "lightagent-skillhub"},
            {"name": "legacy", "registry_source": "cowagent-skillhub"},
            {"name": "implicit-official"},
        ]
        self.assertEqual(
            ["official", "implicit-official"],
            [item["name"] for item in _filter_skill_hub_source(skills)],
        )
        self.assertEqual(
            ["legacy"],
            [item["name"] for item in _filter_skill_hub_source(skills, "cowagent-skillhub")],
        )
        with self.assertRaises(ValueError):
            _filter_skill_hub_source(skills, "unknown")

    def test_chat_mutations_require_admin(self):
        plugin = (ROOT / "plugins/lightagent_cli/lightagent_cli.py").read_text(encoding="utf-8")
        self.assertIn("def _require_skill_admin", plugin)
        self.assertIn("denied = self._require_skill_admin(e_context)", plugin)

    def test_cli_search_and_install_use_the_merged_catalog(self):
        cli = (ROOT / "cli/commands/skill.py").read_text(encoding="utf-8")
        self.assertIn("all_skills = SkillLifecycleManager().search()", cli)
        self.assertIn('SkillLifecycleManager().search(query=query)', cli)
        self.assertIn('source=LegacySkillRegistryClient.SOURCE', cli)

    def test_active_executor_uses_the_skill_snapshot_content(self):
        old_skill = Skill(
            name="snapshot-skill", description="old", file_path="/old/SKILL.md",
            base_dir="/old", source="custom", content="OLD SNAPSHOT CONTENT",
        )
        snapshot = SkillSnapshot(prompt="", skills=[], resolved_skills=[old_skill])
        agent = SimpleNamespace(skill_manager=None)
        executor = AgentStreamExecutor(
            agent=agent, model=None, system_prompt="", tools=[], skill_snapshot=snapshot,
        )
        message = executor._build_tool_not_found_message("snapshot-skill")
        self.assertIn("OLD SNAPSHOT CONTENT", message)

    def test_hub_skill_snapshot_pins_scripts_until_request_finishes(self):
        with tempfile.TemporaryDirectory() as workspace:
            skill_dir = Path(workspace, "skills", "snapshot-skill")
            skill_dir.mkdir(parents=True)
            Path(skill_dir, "SKILL.md").write_text("old instructions", encoding="utf-8")
            Path(skill_dir, "script.py").write_text("old code", encoding="utf-8")
            skill = Skill(
                name="snapshot-skill", description="snapshot", file_path=str(skill_dir / "SKILL.md"),
                base_dir=str(skill_dir), source="custom", content="old instructions",
            )
            manager = SkillManager.__new__(SkillManager)
            manager.custom_dir = str(Path(workspace, "skills"))
            manager.skills_config = {"snapshot-skill": {"source": "lightagent-skillhub"}}
            with patch.object(manager, "filter_skills", return_value=[SkillEntry(skill=skill)]):
                snapshot = manager.build_skill_snapshot()
            Path(skill_dir, "script.py").unlink()
            Path(skill_dir, "script.py").write_text("new code", encoding="utf-8")
            pinned = Path(snapshot.resolved_skills[0].base_dir, "script.py")
            self.assertEqual("old code", pinned.read_text(encoding="utf-8"))
            cleanup_dir = snapshot.cleanup_dir
            manager.cleanup_skill_snapshot(snapshot)
            self.assertFalse(os.path.exists(cleanup_dir))

    def test_legacy_fallback_without_signed_entry_is_rejected(self):
        with self.assertRaisesRegex(SkillInstallError, "signed registry entry"):
            _install_hub("sample-skill", InstallResult(), require_verified=True)


if __name__ == "__main__":
    unittest.main()
