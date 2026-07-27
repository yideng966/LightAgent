import tempfile
import unittest
from pathlib import Path

from scripts.stamp_release_version import stamp_release_version


ROOT = Path(__file__).resolve().parents[1]


class ReleaseVersionStampTest(unittest.TestCase):
    def _create_fixture(self, root: Path) -> None:
        (root / "cli").mkdir()
        (root / "cli" / "VERSION").write_text("1.0.0\n", encoding="utf-8")
        (root / "pyproject.toml").write_text(
            """[build-system]
requires = ["setuptools"]

[project]
name = "lightagent"
version = "1.0.0"

[tool.example]
version = "keep-me"
""",
            encoding="utf-8",
        )

    def test_stamps_both_python_version_sources(self):
        for version in ("2.1.7", "2.1.7-rc.1", "0.0.0-dev"):
            with self.subTest(version=version):
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    self._create_fixture(root)

                    stamp_release_version(root, version)

                    self.assertEqual(
                        f"{version}\n",
                        (root / "cli" / "VERSION").read_text(encoding="utf-8"),
                    )
                    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
                    self.assertIn(f'version = "{version}"', pyproject)
                    self.assertIn('version = "keep-me"', pyproject)

    def test_invalid_version_does_not_modify_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._create_fixture(root)
            original_cli = (root / "cli" / "VERSION").read_bytes()
            original_pyproject = (root / "pyproject.toml").read_bytes()

            for invalid_version in ("v2.1.7", "1.0.0-test"):
                with self.subTest(version=invalid_version):
                    with self.assertRaises(ValueError):
                        stamp_release_version(root, invalid_version)

            self.assertEqual(original_cli, (root / "cli" / "VERSION").read_bytes())
            self.assertEqual(
                original_pyproject,
                (root / "pyproject.toml").read_bytes(),
            )

    def test_release_workflows_stamp_before_packaging(self):
        docker_workflow = (
            ROOT / ".github" / "workflows" / "deploy-image.yml"
        ).read_text(encoding="utf-8")
        desktop_workflow = (
            ROOT / ".github" / "workflows" / "release.yml"
        ).read_text(encoding="utf-8")

        self.assertLess(
            docker_workflow.index("scripts/stamp_release_version.py"),
            docker_workflow.index("docker/build-push-action"),
        )
        self.assertLess(
            desktop_workflow.index("scripts/stamp_release_version.py"),
            desktop_workflow.index("pyinstaller desktop/build/lightagent-backend.spec"),
        )


if __name__ == "__main__":
    unittest.main()
