import importlib.util
import io
import os
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from agent.skills.service import SkillService
from cli.commands.skill import (
    InstallResult,
    SkillInstallError,
    _batch_install_skills,
    _install_from_repo_root,
    _install_github,
    _install_targz_bytes,
    _install_zip_bytes,
)


ROOT = Path(__file__).resolve().parents[1]


def _write_skill(root: Path, name: str, marker: str = "marker") -> Path:
    skill_dir = root / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {marker}\n---\n\n{marker}\n",
        encoding="utf-8",
    )
    return skill_dir


def _zip_skill(name: str) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr(
            f"{name}/SKILL.md",
            f"---\nname: {name}\ndescription: zip skill\n---\n",
        )
    return stream.getvalue()


def _targz_skill(name: str) -> bytes:
    stream = io.BytesIO()
    content = f"---\nname: {name}\ndescription: tar skill\n---\n".encode()
    with tarfile.open(fileobj=stream, mode="w:gz") as archive:
        info = tarfile.TarInfo(f"{name}/SKILL.md")
        info.size = len(content)
        archive.addfile(info, io.BytesIO(content))
    return stream.getvalue()


def _load_init_skill_module():
    path = ROOT / "skills" / "skill-creator" / "scripts" / "init_skill.py"
    spec = importlib.util.spec_from_file_location("lightagent_skill_creator_init", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _ServiceManager:
    def __init__(self, custom_dir):
        self.custom_dir = str(custom_dir)
        self.skills_config = {}

    def _load_skills_config(self):
        return {}

    def _save_skills_config(self):
        return None

    def refresh_skills(self):
        return None


class SkillInstallSourceProtectionTest(unittest.TestCase):
    def test_cloud_install_rejects_builtin_name_before_download(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = _ServiceManager(Path(tmp) / "skills")
            service = SkillService(manager)
            with patch.object(service, "_download_file") as download:
                with self.assertRaisesRegex(ValueError, "builtin"):
                    service.add({
                        "name": "skill-creator",
                        "type": "url",
                        "files": [{
                            "url": "https://example.com/SKILL.md",
                            "path": "SKILL.md",
                        }],
                    })
            download.assert_not_called()
            self.assertFalse(Path(manager.custom_dir, "skill-creator").exists())

    def test_cloud_url_rejects_builtin_name_declared_by_downloaded_skill(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = _ServiceManager(Path(tmp) / "skills")
            service = SkillService(manager)

            def download(_url, dest):
                Path(dest).parent.mkdir(parents=True, exist_ok=True)
                Path(dest).write_text(
                    "---\nname: skill-creator\ndescription: conflict\n---\n",
                    encoding="utf-8",
                )

            with patch.object(service, "_download_file", side_effect=download):
                with self.assertRaisesRegex(ValueError, "builtin"):
                    service.add({
                        "name": "remote-alias",
                        "type": "url",
                        "files": [{
                            "url": "https://example.com/SKILL.md",
                            "path": "SKILL.md",
                        }],
                    })

            self.assertFalse(Path(manager.custom_dir, "remote-alias").exists())

    def test_cloud_package_rejects_builtin_name_declared_by_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = _ServiceManager(Path(tmp) / "skills")
            service = SkillService(manager)
            package = _zip_skill("knowledge-wiki")

            def download(_url, dest):
                Path(dest).write_bytes(package)

            with patch.object(service, "_download_file", side_effect=download):
                with self.assertRaisesRegex(ValueError, "builtin"):
                    service.add({
                        "name": "package-alias",
                        "type": "package",
                        "files": [{"url": "https://example.com/skill.zip"}],
                    })

            self.assertFalse(Path(manager.custom_dir, "package-alias").exists())

    def test_repository_install_rejects_builtin_name_before_workspace_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            skills = root / "workspace" / "skills"
            _write_skill(repo, "skill-creator")
            result = InstallResult()

            with patch("cli.commands.skill._register_installed_skill") as register:
                with self.assertRaisesRegex(SkillInstallError, "builtin"):
                    _install_from_repo_root(
                        str(repo / "skill-creator"),
                        "owner/repo",
                        None,
                        None,
                        str(skills),
                        "github",
                        result,
                    )

            register.assert_not_called()
            self.assertFalse((skills / "skill-creator").exists())

    def test_zip_install_rejects_builtin_name_before_workspace_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            skills = Path(tmp) / "skills"
            result = InstallResult()

            with patch("cli.commands.skill._register_installed_skill") as register:
                with self.assertRaisesRegex(SkillInstallError, "builtin"):
                    _install_zip_bytes(
                        _zip_skill("image-generation"),
                        "archive",
                        str(skills),
                        result=result,
                    )

            register.assert_not_called()
            self.assertFalse((skills / "image-generation").exists())

    def test_targz_install_rejects_builtin_name_before_workspace_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            skills = Path(tmp) / "skills"
            result = InstallResult()

            with patch("cli.commands.skill._register_installed_skill") as register:
                with self.assertRaisesRegex(SkillInstallError, "builtin"):
                    _install_targz_bytes(
                        _targz_skill("knowledge-wiki"),
                        "archive",
                        str(skills),
                        result,
                    )

            register.assert_not_called()
            self.assertFalse((skills / "knowledge-wiki").exists())

    def test_github_contents_rejects_builtin_frontmatter_before_workspace_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            skills = Path(tmp) / "skills"
            result = InstallResult()

            def download(_owner, _repo, _branch, _subpath, dest):
                Path(dest, "SKILL.md").write_text(
                    "---\nname: skill-creator\ndescription: conflict\n---\n",
                    encoding="utf-8",
                )

            with patch("cli.commands.skill.get_skills_dir", return_value=str(skills)), \
                    patch("cli.commands.skill._download_repo_zip", side_effect=RuntimeError("zip unavailable")), \
                    patch("cli.commands.skill._download_github_dir", side_effect=download), \
                    patch("cli.commands.skill._register_installed_skill") as register:
                with self.assertRaisesRegex(SkillInstallError, "builtin"):
                    _install_github("owner/repo", result, subpath="skills/alias")

            register.assert_not_called()
            self.assertFalse((skills / "alias").exists())

    def test_batch_install_skips_builtin_and_installs_non_conflicting_skill(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            skills = root / "workspace" / "skills"
            builtin = _write_skill(source, "knowledge-wiki")
            custom = _write_skill(source, "weather-helper")
            result = InstallResult()

            with patch("cli.commands.skill._register_installed_skill") as register:
                _batch_install_skills(
                    [
                        ("knowledge-wiki", str(builtin)),
                        ("weather-helper", str(custom)),
                    ],
                    "owner/repo",
                    str(skills),
                    "github",
                    result,
                )

            self.assertEqual(["weather-helper"], result.installed)
            self.assertTrue((skills / "weather-helper" / "SKILL.md").is_file())
            self.assertFalse((skills / "knowledge-wiki").exists())
            self.assertTrue(any("builtin" in message for message in result.messages))
            register.assert_called_once()

    def test_skill_creator_rejects_builtin_name_before_directory_creation(self):
        module = _load_init_skill_module()
        with tempfile.TemporaryDirectory() as tmp:
            with patch("builtins.print"):
                result = module.init_skill("image-generation", tmp)

            self.assertIsNone(result)
            self.assertFalse(Path(tmp, "image-generation").exists())

    def test_skill_creator_still_creates_non_conflicting_skill(self):
        module = _load_init_skill_module()
        with tempfile.TemporaryDirectory() as tmp:
            with patch("builtins.print"):
                result = module.init_skill("weather-helper", tmp)

            self.assertEqual(Path(tmp, "weather-helper"), result)
            self.assertTrue(Path(result, "SKILL.md").is_file())


if __name__ == "__main__":
    unittest.main()
