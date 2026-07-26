import hashlib
import io
import json
import os
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from agent.skills.lifecycle import SkillLifecycleError, SkillLifecycleManager
from agent.skills.registry import RegistrySecurityError


class _Registry:
    def __init__(self, entry, revocations=None):
        self.entry = entry
        self.revocations = list(revocations or [])

    def get_skill(self, name):
        if name != self.entry["name"]:
            raise RuntimeError("missing")
        return dict(self.entry)

    def list_skills(self, query="", include_unavailable=False):
        return [dict(self.entry)]

    def load(self):
        return SimpleNamespace(data={"revocations": list(self.revocations)})


class _LegacyRegistry:
    def __init__(self, entry):
        self.entry = entry

    def get_skill(self, name):
        if name != self.entry["name"]:
            raise RuntimeError("missing")
        return dict(self.entry)

    def list_skills(self, query=""):
        return [dict(self.entry)]


class _Response:
    def __init__(self, content):
        self.content = content

    def raise_for_status(self):
        return None


class _Session:
    def __init__(self, content):
        self.content = content

    def get(self, *_args, **_kwargs):
        return _Response(self.content)


class _LegacySession(_Session):
    def post(self, *_args, **_kwargs):
        response = _Response(self.content)
        response.headers = {"Content-Type": "application/zip"}
        return response


class _FallbackResponse(_Response):
    def __init__(self, content=b"", data=None, content_type="application/zip"):
        super().__init__(content)
        self._data = data
        self.headers = {"Content-Type": content_type}

    def json(self):
        return self._data


class _FallbackSession:
    def __init__(self, package, source_url):
        self.package = package
        self.source_url = source_url

    def get(self, *_args, **_kwargs):
        raise OSError("primary unavailable")

    def post(self, _url, json=None, **_kwargs):
        if json and json.get("mirror"):
            return _FallbackResponse(self.package)
        return _FallbackResponse(
            data={"source_url": self.source_url, "has_mirror": True},
            content_type="application/json",
        )


def _package(name="sample-skill", version="1.0.0", extra="one"):
    stream = io.BytesIO()
    skill = f"""---
name: {name}
version: {version}
description: A test skill package for LightAgent lifecycle tests.
---
# Test
{extra}
""".encode()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr(f"{name}/SKILL.md", skill)
        archive.writestr(f"{name}/asset.txt", extra.encode())
    return stream.getvalue()


def _entry(package, name="sample-skill", version="1.0.0"):
    return {
        "name": name,
        "version": version,
        "description": "A test skill package for lifecycle tests.",
        "repository": "https://example.test/repo",
        "source_commit": "abc123",
        "download_url": "https://example.test/package.zip",
        "sha256": hashlib.sha256(package).hexdigest(),
        "status": "active",
        "min_lightagent_version": "1.0.0",
        "max_lightagent_version": None,
        "requirements": {"env": [], "bins": [], "python": [], "npm": [], "downloads": []},
        "lightagent": {"network_domains": [], "file_paths": [], "tools": [], "docker_notes": ""},
    }


class SkillLifecycleManagerTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = self.temp.name
        self.skills = os.path.join(self.workspace, "skills")
        os.makedirs(self.skills)
        self.refresh_patch = patch.object(SkillLifecycleManager, "_refresh", return_value=None)
        self.refresh_patch.start()

    def tearDown(self):
        self.refresh_patch.stop()
        self.temp.cleanup()

    def _manager(self, package, entry=None):
        entry = entry or _entry(package)
        return SkillLifecycleManager(
            skills_dir=self.skills,
            workspace=self.workspace,
            registry=_Registry(entry),
            session=_Session(package),
        )

    def test_install_verify_update_rollback_and_uninstall_preserve_data(self):
        first = _package()
        manager = self._manager(first)
        record = manager.install("sample-skill")
        self.assertEqual("1.0.0", record["version"])
        self.assertTrue(manager.verify("sample-skill")[0]["ok"])
        Path(self.workspace, "skill-data", "sample-skill", "keep.txt").write_text("keep")

        second = _package(version="1.1.0", extra="two")
        manager.registry.entry = _entry(second, version="1.1.0")
        manager.session.content = second
        updated = manager.update("sample-skill")
        self.assertEqual("1.1.0", updated["version"])
        self.assertEqual("two", Path(self.skills, "sample-skill", "asset.txt").read_text())

        restored = manager.rollback("sample-skill")
        self.assertEqual("1.0.0", restored["version"])
        self.assertEqual("one", Path(self.skills, "sample-skill", "asset.txt").read_text())
        manager.uninstall("sample-skill")
        self.assertFalse(Path(self.skills, "sample-skill").exists())
        self.assertEqual("keep", Path(self.workspace, "skill-data", "sample-skill", "keep.txt").read_text())

    def test_download_dependency_installs_without_extra_approval(self):
        package = _package()
        entry = _entry(package)
        entry["requirements"]["downloads"] = [{
            "url": "https://example.test/dependency.bin",
            "sha256": hashlib.sha256(package).hexdigest(),
        }]
        manager = self._manager(package, entry)
        manager.install("sample-skill")
        dependency = Path(
            self.workspace, ".skill-envs", "sample-skill", "downloads", "dependency.bin"
        )
        self.assertEqual(package, dependency.read_bytes())

    def test_original_marketplace_is_browse_only_and_cannot_install(self):
        package = _package(version="1.2.3")
        entry = _entry(package, version="1.2.3")
        entry.update({
            "registry_source": "cowagent-skillhub",
            "registry_url": "https://skills.cowagent.ai/api",
        })
        entry.pop("sha256")
        entry.pop("download_url")
        manager = SkillLifecycleManager(
            skills_dir=self.skills,
            workspace=self.workspace,
            registry=_Registry(_entry(package)),
            legacy_registry=_LegacyRegistry(entry),
            session=_LegacySession(package),
        )
        with self.assertRaisesRegex(SkillLifecycleError, "仅提供技能介绍页"):
            manager.install("sample-skill", source="cowagent-skillhub")
        results = manager.batch("install", [{
            "name": "sample-skill",
            "version": "1.2.3",
            "source": "cowagent-skillhub",
        }])
        self.assertEqual("skipped", results[0]["status"])
        self.assertEqual("catalog_only", results[0]["reason"])
        self.assertFalse(Path(self.skills, "sample-skill").exists())
        self.assertNotIn("sample-skill", manager.installed())

    def test_missing_system_binary_rejects_install_without_lock_record(self):
        package = _package()
        entry = _entry(package)
        entry["requirements"]["bins"] = ["missing-skill-command"]
        manager = self._manager(package, entry)
        with patch("agent.skills.lifecycle.shutil.which", return_value=None):
            with self.assertRaisesRegex(Exception, "missing-skill-command"):
                manager.install("sample-skill")
        self.assertNotIn("sample-skill", manager.installed())
        self.assertFalse(Path(self.skills, "sample-skill").exists())

    def test_python_and_npm_dependencies_are_isolated_and_linked(self):
        package = _package()
        entry = _entry(package)
        entry["requirements"].update({
            "python": ["defusedxml>=0.7.1"],
            "npm": ["docx@9.5.1"],
        })
        manager = self._manager(package, entry)

        def install(command, **_kwargs):
            if command[0] == "npm":
                prefix = command[command.index("--prefix") + 1]
                Path(prefix, "node_modules", "docx").mkdir(parents=True)
            else:
                target = command[command.index("--target") + 1]
                Path(target, "defusedxml").mkdir(parents=True)
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        with patch("agent.skills.lifecycle.shutil.which", return_value="/usr/bin/tool"), \
                patch("agent.skills.lifecycle.subprocess.run", side_effect=install) as run:
            record = manager.install("sample-skill")

        self.assertEqual(2, run.call_count)
        self.assertEqual(["defusedxml>=0.7.1"], record["requirements"]["python"])
        self.assertTrue(Path(manager.envs_dir, "sample-skill", "python", "defusedxml").is_dir())
        modules = Path(self.skills, "sample-skill", "node_modules")
        self.assertTrue(modules.is_symlink() or modules.is_dir())
        self.assertTrue(Path(modules, "docx").is_dir())

    def test_dependency_failure_does_not_install_skill(self):
        package = _package()
        entry = _entry(package)
        entry["requirements"]["python"] = ["broken-package"]
        manager = self._manager(package, entry)
        failure = subprocess.CalledProcessError(1, ["pip"], stderr="not found")
        with patch("agent.skills.lifecycle.subprocess.run", side_effect=failure):
            with self.assertRaisesRegex(Exception, "Python 依赖失败"):
                manager.install("sample-skill")
        self.assertNotIn("sample-skill", manager.installed())
        self.assertFalse(Path(self.skills, "sample-skill").exists())

    def test_changed_dependency_manifest_updates_without_extra_approval(self):
        first = _package()
        entry = _entry(first)
        manager = self._manager(first, entry)
        manager.install("sample-skill")

        second = _package(version="1.1.0", extra="changed manifest")
        changed = _entry(second, version="1.1.0")
        changed["lightagent"]["tools"] = ["bash"]
        manager.registry.entry = changed
        manager.session.content = second
        updated = manager.update("sample-skill")
        self.assertEqual("1.1.0", updated["version"])

    def test_checksum_mismatch_does_not_replace_existing_skill(self):
        first = _package()
        manager = self._manager(first)
        manager.install("sample-skill")
        manager.registry.entry = _entry(_package(version="1.1.0"), version="1.1.0")
        manager.session.content = b"tampered"
        with self.assertRaises(RegistrySecurityError):
            manager.update("sample-skill")
        self.assertEqual("one", Path(self.skills, "sample-skill", "asset.txt").read_text())

    def test_legacy_mirror_uses_signed_hash_and_matching_source_identity(self):
        package = _package()
        entry = _entry(package)
        manager = SkillLifecycleManager(
            skills_dir=self.skills,
            workspace=self.workspace,
            registry=_Registry(entry),
            session=_FallbackSession(package, entry["repository"]),
        )
        record = manager.install("sample-skill")
        self.assertEqual(entry["sha256"], record["artifact_sha256"])

    def test_legacy_mirror_rejects_mismatched_source_identity(self):
        package = _package()
        entry = _entry(package)
        manager = SkillLifecycleManager(
            skills_dir=self.skills,
            workspace=self.workspace,
            registry=_Registry(entry),
            session=_FallbackSession(package, "https://example.test/other"),
        )
        with self.assertRaisesRegex(Exception, "源码身份"):
            manager.install("sample-skill")

    def test_commit_failure_restores_previous_code_and_lock(self):
        first = _package()
        manager = self._manager(first)
        manager.install("sample-skill")

        second = _package(version="1.1.0", extra="two")
        manager.registry.entry = _entry(second, version="1.1.0")
        manager.session.content = second
        with patch.object(manager, "_register_skills_config", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                manager.update("sample-skill")
        self.assertEqual("one", Path(self.skills, "sample-skill", "asset.txt").read_text())
        self.assertEqual("1.0.0", manager.installed()["sample-skill"]["version"])

    def test_path_traversal_is_rejected(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr("../../outside", b"bad")
        package = stream.getvalue()
        manager = self._manager(package, _entry(package))
        with self.assertRaises(RegistrySecurityError):
            manager.install("sample-skill")
        self.assertFalse(Path(self.workspace, "outside").exists())

    def test_builtin_name_is_protected(self):
        package = _package(name="skill-creator")
        manager = self._manager(package, _entry(package, name="skill-creator"))
        with self.assertRaises(RegistrySecurityError):
            manager.install("skill-creator")

    def test_local_same_name_skill_is_never_overwritten(self):
        package = _package()
        Path(self.skills, "sample-skill").mkdir()
        Path(self.skills, "sample-skill", "SKILL.md").write_text("local", encoding="utf-8")
        manager = self._manager(package)
        with self.assertRaisesRegex(Exception, "同名技能"):
            manager.install("sample-skill")
        self.assertEqual("local", Path(self.skills, "sample-skill", "SKILL.md").read_text(encoding="utf-8"))

    def test_installed_revoked_version_is_reported(self):
        package = _package()
        manager = self._manager(package)
        manager.install("sample-skill")
        manager.registry.revocations = [{
            "name": "sample-skill",
            "version": "1.0.0",
            "status": "revoked",
            "reason": "security incident",
        }]
        notices = manager.outdated()
        self.assertEqual(1, len(notices))
        self.assertEqual("revoked", notices[0]["status"])
        self.assertEqual("security incident", notices[0]["reason"])

    def test_batch_continues_after_failure_and_deduplicates_names(self):
        package = _package()
        manager = self._manager(package)
        with patch.object(manager, "install", side_effect=[{"version": "1.0.0"}, RuntimeError("broken")]) as install:
            results = manager.batch("install", [
                {"name": "first-skill", "version": "1.0.0"},
                {"name": "first-skill", "version": "1.0.0"},
                {"name": "second-skill", "version": "1.0.0"},
            ])
        self.assertEqual(["success", "failed"], [item["status"] for item in results])
        self.assertEqual(2, install.call_count)
        self.assertIn("broken", results[1]["reason"])

    def test_batch_rejects_more_than_one_hundred_items(self):
        manager = self._manager(_package())
        with self.assertRaisesRegex(Exception, "100"):
            manager.batch("install", [{"name": f"skill-{index}"} for index in range(101)])

    def test_batch_update_skips_latest_version(self):
        package = _package()
        manager = self._manager(package)
        manager.install("sample-skill")
        results = manager.batch("update", [{"name": "sample-skill", "version": "1.0.0"}])
        self.assertEqual("skipped", results[0]["status"])
        self.assertEqual("already_latest", results[0]["reason"])

    def test_purge_uninstall_removes_package_environment_versions_config_and_data(self):
        package = _package()
        manager = self._manager(package)
        manager.install("sample-skill")
        Path(manager.versions_dir, "sample-skill", "old").mkdir(parents=True)
        Path(manager.data_dir, "sample-skill", "data.txt").write_text("data", encoding="utf-8")
        Path(manager.config_dir, "sample-skill", "secret.txt").write_text("secret", encoding="utf-8")

        manager.uninstall("sample-skill", purge_data=True)

        for root in (
            manager.skills_dir, manager.envs_dir, manager.versions_dir,
            manager.data_dir, manager.config_dir,
        ):
            self.assertFalse(Path(root, "sample-skill").exists())
        self.assertNotIn("sample-skill", manager.installed())
        config = json.loads(Path(self.skills, "skills_config.json").read_text(encoding="utf-8"))
        self.assertNotIn("sample-skill", config)


if __name__ == "__main__":
    unittest.main()
