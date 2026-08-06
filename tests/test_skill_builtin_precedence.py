import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent.skills.loader import SkillLoader
from agent.skills.manager import SkillManager
from agent.skills.names import BuiltinSkillNameError, ensure_not_builtin_skill_name
from cli.commands.skill import _merge_builtin_into_config


def _write_skill(root: Path, name: str, marker: str) -> Path:
    skill_dir = root / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {marker}\n---\n\n{marker}\n",
        encoding="utf-8",
    )
    return skill_dir


def _load_lightagent_cli_plugin():
    import plugins

    module_names = ("plugins.lightagent_cli", "plugins.lightagent_cli.lightagent_cli")
    old_modules = {
        name: sys.modules[name]
        for name in module_names
        if name in sys.modules
    }
    old_plugin_path = plugins.instance.current_plugin_path
    old_registered = plugins.instance.plugins.get("LIGHTAGENT_CLI")
    plugins.instance.current_plugin_path = os.path.join(
        os.path.dirname(__file__), "..", "plugins", "lightagent_cli"
    )
    try:
        import plugins.lightagent_cli.lightagent_cli

        return plugins.instance.plugins["LIGHTAGENT_CLI"]
    finally:
        plugins.instance.current_plugin_path = old_plugin_path
        if old_registered is None:
            plugins.instance.plugins.pop("LIGHTAGENT_CLI", None)
        else:
            plugins.instance.plugins["LIGHTAGENT_CLI"] = old_registered
        for name in module_names:
            if name in old_modules:
                sys.modules[name] = old_modules[name]
            else:
                sys.modules.pop(name, None)
        if hasattr(plugins, "lightagent_cli"):
            delattr(plugins, "lightagent_cli")


class BuiltinSkillPrecedenceTest(unittest.TestCase):
    def test_builtin_frontmatter_name_is_reserved_even_when_directory_differs(self):
        with tempfile.TemporaryDirectory() as tmp:
            builtin = Path(tmp) / "builtin"
            _write_skill(builtin, "declared-name", "builtin marker").rename(
                builtin / "directory-name"
            )

            with self.assertRaises(BuiltinSkillNameError):
                ensure_not_builtin_skill_name("declared-name", builtin)

    def test_workspace_copy_cannot_override_builtin_skill(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            builtin = root / "builtin"
            custom = root / "workspace" / "skills"
            builtin_dir = _write_skill(
                builtin, "protected-skill", "builtin marker"
            )
            _write_skill(custom, "protected-skill", "workspace marker")

            skills = SkillLoader().load_all_skills(
                builtin_dir=str(builtin),
                custom_dir=str(custom),
            )

            selected = skills["protected-skill"].skill
            self.assertEqual(builtin_dir.resolve(), Path(selected.base_dir).resolve())
            self.assertEqual("builtin", selected.source)
            self.assertIn("builtin marker", selected.content)
            self.assertNotIn("workspace marker", selected.content)

    def test_non_conflicting_workspace_skill_remains_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            builtin = root / "builtin"
            custom = root / "workspace" / "skills"
            _write_skill(builtin, "protected-skill", "builtin marker")
            custom_dir = _write_skill(custom, "custom-skill", "custom marker")

            skills = SkillLoader().load_all_skills(
                builtin_dir=str(builtin),
                custom_dir=str(custom),
            )

            selected = skills["custom-skill"].skill
            self.assertEqual(custom_dir.resolve(), Path(selected.base_dir).resolve())
            self.assertEqual("custom", selected.source)

    def test_manager_corrects_stale_builtin_source_and_preserves_enabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            builtin = root / "builtin"
            custom = root / "workspace" / "skills"
            builtin_dir = _write_skill(
                builtin, "protected-skill", "builtin marker"
            )
            _write_skill(custom, "protected-skill", "workspace marker")
            (custom / "skills_config.json").write_text(
                json.dumps({
                    "protected-skill": {
                        "name": "protected-skill",
                        "description": "stale workspace description",
                        "source": "custom",
                        "enabled": False,
                        "category": "skill",
                    }
                }),
                encoding="utf-8",
            )

            with patch.object(SkillManager, "_sync_wechat_group_skill_access"):
                manager = SkillManager(
                    builtin_dir=str(builtin),
                    custom_dir=str(custom),
                )

            selected = manager.get_skill("protected-skill").skill
            self.assertEqual(builtin_dir.resolve(), Path(selected.base_dir).resolve())
            self.assertEqual("builtin", manager.skills_config["protected-skill"]["source"])
            self.assertFalse(manager.skills_config["protected-skill"]["enabled"])

    def test_cli_merge_corrects_stale_builtin_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            builtin = root / "builtin"
            custom = root / "workspace" / "skills"
            _write_skill(builtin, "protected-skill", "builtin marker")
            _write_skill(custom, "protected-skill", "workspace marker")
            config = {
                "protected-skill": {
                    "name": "protected-skill",
                    "description": "workspace marker",
                    "source": "custom",
                    "enabled": False,
                    "category": "skill",
                    "display_name": "Protected",
                }
            }

            _merge_builtin_into_config(config, str(builtin), str(custom))

            entry = config["protected-skill"]
            self.assertEqual("builtin", entry["source"])
            self.assertEqual("builtin marker", entry["description"])
            self.assertFalse(entry["enabled"])
            self.assertEqual("Protected", entry["display_name"])

    def test_chat_skill_info_prefers_builtin_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            builtin = root / "builtin"
            custom = root / "workspace" / "skills"
            _write_skill(builtin, "protected-skill", "builtin marker")
            _write_skill(custom, "protected-skill", "workspace marker")
            plugin_class = _load_lightagent_cli_plugin()
            plugin = plugin_class.__new__(plugin_class)

            with patch("cli.utils.get_builtin_skills_dir", return_value=str(builtin)), \
                    patch("cli.utils.get_skills_dir", return_value=str(custom)):
                result = plugin._skill_info("protected-skill")

            self.assertIn("[builtin]", result)
            self.assertIn("builtin marker", result)
            self.assertNotIn("workspace marker", result)


if __name__ == "__main__":
    unittest.main()
