import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from config import plugin_config
from common.sorted_dict import SortedDict
from plugins.plugin import Plugin
from plugins import plugin_manager
from plugins.plugin_manager import _plugins_data_dir


ROOT = Path(__file__).resolve().parents[1]


class PersistentDataPathTest(unittest.TestCase):
    def test_plugin_data_dir_honors_lightagent_data_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"LIGHTAGENT_DATA_DIR": tmp}):
                self.assertEqual(
                    Path(tmp, "plugins").resolve(),
                    Path(_plugins_data_dir()).resolve(),
                )
                self.assertTrue(hasattr(plugin_manager, "_plugins_install_dir"))
                self.assertEqual(
                    Path(tmp, "plugins").resolve(),
                    Path(plugin_manager._plugins_install_dir()).resolve(),
                )

    def test_plugin_save_does_not_modify_builtin_resource(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as resources:
            resource_dir = Path(resources, "demo")
            resource_dir.mkdir()
            resource_config = resource_dir / "config.json"
            resource_config.write_text('{"value": "builtin"}', encoding="utf-8")

            plugin = Plugin()
            plugin.name = "demo"
            plugin.path = str(resource_dir)
            with patch.dict(
                os.environ, {"LIGHTAGENT_DATA_DIR": tmp}
            ), patch.dict(plugin_config, {}, clear=True):
                plugin.save_config({"value": "user"})

            self.assertEqual(
                '{"value": "builtin"}',
                resource_config.read_text(encoding="utf-8"),
            )
            saved = json.loads(
                Path(tmp, "plugins", "config.json").read_text(encoding="utf-8")
            )
            self.assertEqual("user", saved["demo"]["value"])

    def test_plugin_scan_loads_user_plugins_without_shadowing_builtin(self):
        with tempfile.TemporaryDirectory() as resources, tempfile.TemporaryDirectory() as data:
            resource_dir = Path(resources)
            install_dir = Path(data)
            for base, name in (
                (resource_dir, "builtin"),
                (install_dir, "builtin"),
                (install_dir, "custom"),
            ):
                plugin_dir = base / name
                plugin_dir.mkdir()
                (plugin_dir / "__init__.py").touch()

            manager = plugin_manager.PluginManager()
            package_paths = sys.modules["plugins"].__path__
            original_paths = list(package_paths)
            original_state = {
                "plugins": manager.plugins,
                "pconf": manager.pconf,
                "loaded": manager.loaded,
                "current_plugin_path": manager.current_plugin_path,
            }
            imported = []

            def fake_import(module_name):
                plugin_name = module_name.rsplit(".", 1)[-1]
                plugin_class = type(f"{plugin_name.title()}Plugin", (), {})
                manager.register(plugin_name)(plugin_class)
                imported.append((module_name, manager.current_plugin_path))
                return object()

            try:
                manager.plugins = SortedDict(
                    lambda key, value: value.priority,
                    reverse=True,
                )
                manager.pconf = {
                    "plugins": {
                        "builtin": {"enabled": True, "priority": 0},
                        "custom": {"enabled": True, "priority": 0},
                    }
                }
                manager.loaded = {}
                manager.current_plugin_path = None
                with patch.object(
                    plugin_manager, "_plugins_resource_dir", return_value=str(resource_dir)
                ), patch.object(
                    plugin_manager, "_plugins_install_dir", return_value=str(install_dir)
                ), patch.object(
                    plugin_manager.importlib, "import_module", side_effect=fake_import
                ):
                    manager.scan_plugins()

                self.assertEqual(
                    ["plugins.builtin", "plugins.custom"],
                    [module_name for module_name, _ in imported],
                )
                self.assertEqual(
                    str(resource_dir / "builtin"),
                    manager.plugins["BUILTIN"].path,
                )
                self.assertEqual(
                    str(install_dir / "custom"),
                    manager.plugins["CUSTOM"].path,
                )
            finally:
                package_paths[:] = original_paths
                manager.plugins = original_state["plugins"]
                manager.pconf = original_state["pconf"]
                manager.loaded = original_state["loaded"]
                manager.current_plugin_path = original_state["current_plugin_path"]

    def test_cloud_config_save_uses_data_root(self):
        source = (ROOT / "common" / "cloud_client.py").read_text(encoding="utf-8")
        self.assertIn(
            'config_path = os.path.join(get_data_root(), "config.json")',
            source,
        )
        self.assertNotIn(
            'config_path = os.path.join(get_root(), "config.json")',
            source,
        )


if __name__ == "__main__":
    unittest.main()
