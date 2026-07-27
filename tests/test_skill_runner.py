import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from agent.skills.runtime import build_single_skill_runtime_env
from agent.skills.types import Skill
from agent.tools.skill_run.skill_run import SkillRun


class SkillRunnerTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name)
        self.workspace.joinpath("tmp").mkdir()
        self.workspace.joinpath("skills.lock.json").write_text(
            json.dumps({"lock_version": 2, "skills": {"sample-skill": {"version": "1.0.0"}}}),
            encoding="utf-8",
        )
        root = self.workspace / "snapshot" / "sample-skill"
        root.joinpath("scripts").mkdir(parents=True)
        root.joinpath("scripts/run.py").write_text(
            "import json,sys; print(json.dumps({'args': sys.argv[1:]}))",
            encoding="utf-8",
        )
        self.skill = Skill(
            name="sample-skill", description="sample", file_path=str(root / "SKILL.md"),
            base_dir=str(root), source="custom", content="", frontmatter={
                "schema_version": 2,
                "requirements": {"env": []},
                "lightagent": {"entrypoints": [{
                    "name": "run", "path": "scripts/run.py", "runtime": "python",
                    "timeout_seconds": 5, "max_output_bytes": 4096,
                    "arguments": {"min_items": 1, "max_items": 2, "max_length": 64},
                }]},
            },
        )
        self.tool = SkillRun({"cwd": str(self.workspace), "skill_workspace": str(self.workspace)})
        self.tool.set_skill_snapshot({"sample-skill": self.skill})

    def tearDown(self):
        self.temp.cleanup()

    def test_declared_snapshot_entrypoint_runs_without_shell(self):
        result = self.tool.execute({
            "skill_name": "sample-skill", "entrypoint": "run", "arguments": ["value"],
        })
        self.assertEqual("success", result.status)
        self.assertEqual(["value"], json.loads(result.result)["args"])

    def test_unknown_entrypoint_and_invalid_arguments_are_rejected(self):
        missing = self.tool.execute({"skill_name": "sample-skill", "entrypoint": "missing", "arguments": []})
        self.assertEqual("error", missing.status)
        invalid = self.tool.execute({"skill_name": "sample-skill", "entrypoint": "run", "arguments": []})
        self.assertEqual("error", invalid.status)

    def test_snapshot_path_traversal_is_rejected(self):
        self.skill.frontmatter["lightagent"]["entrypoints"][0]["path"] = "../outside.py"
        result = self.tool.execute({"skill_name": "sample-skill", "entrypoint": "run", "arguments": ["x"]})
        self.assertEqual("error", result.status)
        self.assertIn("越界", result.result)

    def test_single_skill_environment_does_not_include_other_skill(self):
        other = self.workspace / ".skill-envs" / "other" / "python"
        other.mkdir(parents=True)
        env = build_single_skill_runtime_env(str(self.workspace), "sample-skill", {"PATH": "/bin"})
        self.assertNotIn(str(other), env.get("PYTHONPATH", ""))

    def test_timeout_is_enforced_and_temp_directory_is_removed(self):
        script = Path(self.skill.base_dir) / "scripts" / "run.py"
        script.write_text("import time; time.sleep(5)", encoding="utf-8")
        entrypoint = self.skill.frontmatter["lightagent"]["entrypoints"][0]
        entrypoint["timeout_seconds"] = 1

        result = self.tool.execute({
            "skill_name": "sample-skill", "entrypoint": "run", "arguments": ["value"],
        })

        self.assertEqual("error", result.status)
        self.assertIn("超时", result.result)
        self.assertEqual([], list(self.workspace.joinpath("tmp").iterdir()))

    def test_output_limit_is_enforced(self):
        script = Path(self.skill.base_dir) / "scripts" / "run.py"
        script.write_text("print('x' * 4096)", encoding="utf-8")
        entrypoint = self.skill.frontmatter["lightagent"]["entrypoints"][0]
        entrypoint["max_output_bytes"] = 1024

        result = self.tool.execute({
            "skill_name": "sample-skill", "entrypoint": "run", "arguments": ["value"],
        })

        self.assertEqual("error", result.status)
        self.assertIn("输出超过", result.result)

    @unittest.skipUnless(sys.platform.startswith("linux"), "RLIMIT_NPROC task accounting is Linux-specific")
    def test_process_budget_is_relative_to_existing_user_tasks(self):
        script = Path(self.skill.base_dir) / "scripts" / "run.py"
        script.write_text(
            "import threading\n"
            "thread = threading.Thread(target=lambda: None)\n"
            "thread.start()\n"
            "thread.join()\n"
            "print('thread-ok')\n",
            encoding="utf-8",
        )
        entrypoint = self.skill.frontmatter["lightagent"]["entrypoints"][0]
        entrypoint["max_processes"] = 2

        result = self.tool.execute({
            "skill_name": "sample-skill", "entrypoint": "run", "arguments": ["value"],
        })

        self.assertEqual("success", result.status)
        self.assertEqual("thread-ok", result.result)

    def test_environment_only_exposes_declared_secret(self):
        script = Path(self.skill.base_dir) / "scripts" / "run.py"
        script.write_text(
            "import json,os; print(json.dumps({"
            "'allowed': os.getenv('SKILL_ALLOWED'), "
            "'hidden': os.getenv('SKILL_HIDDEN')}))",
            encoding="utf-8",
        )
        self.skill.frontmatter["requirements"]["env"] = ["SKILL_ALLOWED"]
        with mock.patch.dict(
            os.environ,
            {"SKILL_ALLOWED": "visible", "SKILL_HIDDEN": "secret"},
            clear=False,
        ):
            result = self.tool.execute({
                "skill_name": "sample-skill", "entrypoint": "run", "arguments": ["value"],
            })

        self.assertEqual("success", result.status)
        payload = json.loads(result.result)
        self.assertEqual("visible", payload["allowed"])
        self.assertIsNone(payload["hidden"])

    def test_reserved_environment_names_are_rejected(self):
        self.skill.frontmatter["requirements"]["env"] = ["PYTHONPATH"]
        result = self.tool.execute({
            "skill_name": "sample-skill", "entrypoint": "run", "arguments": ["value"],
        })
        self.assertEqual("error", result.status)
        self.assertIn("不允许注入", result.result)

    @unittest.skipUnless(os.name == "posix", "POSIX process groups are required")
    def test_timeout_terminates_child_process_group(self):
        script = Path(self.skill.base_dir) / "scripts" / "run.py"
        script.write_text(
            "import subprocess,sys,time\n"
            "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\n"
            "open(sys.argv[1], 'w').write(str(child.pid))\n"
            "time.sleep(30)\n",
            encoding="utf-8",
        )
        entrypoint = self.skill.frontmatter["lightagent"]["entrypoints"][0]
        entrypoint["timeout_seconds"] = 1
        pid_file = self.workspace / "child.pid"
        result = self.tool.execute({
            "skill_name": "sample-skill", "entrypoint": "run",
            "arguments": ["<workspace>/child.pid"],
        })
        self.assertEqual("error", result.status)
        child_pid = int(pid_file.read_text(encoding="utf-8"))
        for _ in range(20):
            proc_stat = Path(f"/proc/{child_pid}/stat")
            if proc_stat.exists():
                fields = proc_stat.read_text(encoding="utf-8").split()
                if len(fields) > 2 and fields[2] == "Z":
                    break
            try:
                os.kill(child_pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.05)
        else:
            self.fail("Runner timeout left a runnable child process alive")


if __name__ == "__main__":
    unittest.main()
