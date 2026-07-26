import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from agent.skills.update_checker import (
    DEFAULT_CHECK_INTERVAL_SECONDS,
    SkillUpdateChecker,
)


class _Registry:
    def __init__(self, snapshot=None, error=None):
        self.snapshot = snapshot
        self.error = error

    def load(self):
        if self.error:
            raise self.error
        return self.snapshot


def _snapshot(version="1.1.0", cached=False):
    return SimpleNamespace(
        source="cache.json" if cached else "https://example.test/registry.json",
        cached=cached,
        data={
            "skills": [{"name": "sample-skill", "version": version, "status": "active"}],
            "revocations": [],
        },
    )


class SkillUpdateCheckerTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = self.temp.name
        Path(self.workspace, "skills").mkdir()
        Path(self.workspace, "skills.lock.json").write_text(
            json.dumps({"lock_version": 1, "skills": {"sample-skill": {"version": "1.0.0"}}}),
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_check_persists_update_and_cache_source(self):
        checker = SkillUpdateChecker(
            self.workspace, registry=_Registry(_snapshot(cached=True))
        )
        state = checker.check()
        self.assertTrue(state["cached"])
        self.assertEqual("cache.json", state["source"])
        self.assertEqual(1, state["update_count"])
        self.assertTrue(state["skills"]["sample-skill"]["update_available"])
        self.assertEqual(state, checker.read_status())

    def test_failed_check_keeps_last_verified_update_result(self):
        checker = SkillUpdateChecker(
            self.workspace, registry=_Registry(_snapshot())
        )
        previous = checker.check()
        checker.registry = _Registry(error=RuntimeError("signature invalid"))
        failed = checker.check()
        self.assertEqual(previous["skills"], failed["skills"])
        self.assertEqual(1, failed["update_count"])
        self.assertIn("signature invalid", failed["error"])

    def test_single_skill_check_preserves_other_statuses(self):
        checker = SkillUpdateChecker(
            self.workspace, registry=_Registry(_snapshot())
        )
        state = checker.check()
        state["skills"]["other-skill"] = {
            "name": "other-skill", "update_available": True,
            "update_status": "update_available",
        }
        checker._write_status(state)
        refreshed = checker.check(name="sample-skill", snapshot=_snapshot("1.2.0"))
        self.assertIn("other-skill", refreshed["skills"])
        self.assertEqual("1.2.0", refreshed["skills"]["sample-skill"]["available_version"])

    def test_background_loop_checks_immediately_then_waits_six_hours(self):
        checker = SkillUpdateChecker(self.workspace, registry=_Registry(_snapshot()))
        checker.check = MagicMock(return_value={})
        checker._stop_event = MagicMock()
        checker._stop_event.is_set.side_effect = [False, False, False]
        checker._stop_event.wait.side_effect = [False, True]
        checker._run()
        self.assertEqual(2, checker.check.call_count)
        checker._stop_event.wait.assert_called_with(DEFAULT_CHECK_INTERVAL_SECONDS)

    def test_update_status_includes_manual_decision_changes(self):
        snapshot = _snapshot("1.2.0")
        snapshot.data["skills"][0].update({
            "release_notes": "修复转换失败",
            "breaking_changes": ["输出目录参数改名"],
            "requirements": {"python": ["new-package"], "capabilities": ["office-documents"]},
            "lightagent": {"network_domains": ["example.test"], "file_paths": [], "tools": ["skill_run"]},
        })
        checker = SkillUpdateChecker(self.workspace, registry=_Registry(snapshot))
        state = checker.check()
        changes = state["skills"]["sample-skill"]["changes"]
        self.assertTrue(changes["release_notes_available"])
        self.assertEqual(["输出目录参数改名"], changes["breaking_changes"])
        self.assertTrue(changes["requirements_changed"])
        self.assertTrue(changes["permissions_changed"])

    def test_original_marketplace_install_is_not_checked_for_online_updates(self):
        Path(self.workspace, "skills.lock.json").write_text(
            json.dumps({
                "lock_version": 2,
                "skills": {
                    "sample-skill": {
                        "version": "1.0.0",
                        "source": "cowagent-skillhub",
                    }
                },
            }),
            encoding="utf-8",
        )
        checker = SkillUpdateChecker(
            self.workspace, registry=_Registry(_snapshot("9.9.9"))
        )
        state = checker.check()
        status = state["skills"]["sample-skill"]
        self.assertFalse(status["update_available"])
        self.assertEqual("catalog_only", status["update_status"])
        self.assertEqual(0, state["update_count"])


if __name__ == "__main__":
    unittest.main()
