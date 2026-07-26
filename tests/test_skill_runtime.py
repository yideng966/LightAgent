import json
import os
import tempfile
import unittest
from pathlib import Path

from agent.skills.runtime import build_skill_runtime_env


class SkillRuntimeEnvironmentTest(unittest.TestCase):
    def test_installed_dependency_paths_are_injected(self):
        with tempfile.TemporaryDirectory() as workspace:
            env_root = Path(workspace, ".skill-envs", "docx")
            python_dir = env_root / "python"
            python_bin = python_dir / "bin"
            node_dir = env_root / "npm" / "node_modules"
            node_bin = node_dir / ".bin"
            python_bin.mkdir(parents=True)
            node_bin.mkdir(parents=True)
            Path(workspace, "skills.lock.json").write_text(
                json.dumps({"skills": {"docx": {"version": "1.0.0"}}}),
                encoding="utf-8",
            )

            env = build_skill_runtime_env(
                workspace,
                {"PATH": "/system/bin", "PYTHONPATH": "/existing/python"},
            )

            self.assertEqual(str(python_dir.resolve()), env["PYTHONPATH"].split(os.pathsep)[0])
            self.assertEqual(str(node_dir.resolve()), env["NODE_PATH"].split(os.pathsep)[0])
            self.assertIn(str(node_bin.resolve()), env["PATH"].split(os.pathsep))
            self.assertEqual(str(Path(workspace, ".skill-envs").resolve()), env["LIGHTAGENT_SKILL_ENVS"])

    def test_orphan_and_unsafe_environment_names_are_not_injected(self):
        with tempfile.TemporaryDirectory() as workspace:
            orphan = Path(workspace, ".skill-envs", "orphan", "python")
            orphan.mkdir(parents=True)
            Path(workspace, "skills.lock.json").write_text(
                json.dumps({"skills": {"../outside": {}, "missing": {}}}),
                encoding="utf-8",
            )
            env = build_skill_runtime_env(workspace, {"PATH": "/system/bin"})
            self.assertNotIn(str(orphan), env.get("PYTHONPATH", ""))


if __name__ == "__main__":
    unittest.main()
