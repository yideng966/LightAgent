import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from agent.skills.capabilities import capability_status
from agent.skills.legacy_compat import legacy_compat_entry, merge_legacy_requirements
from agent.skills.lifecycle import SkillLifecycleError, SkillLifecycleManager
from scripts.audit_legacy_skills import fetch_catalog


def package(name="sample-skill", version="1.0.0", schema_version=1):
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        archive.writestr(
            f"{name}/SKILL.md",
            f"---\nname: {name}\nversion: {version}\nschema_version: {schema_version}\n---\nbody\n",
        )
    return data.getvalue()


class _LegacyRegistry:
    def __init__(self, entry):
        self.entry = entry

    def get_skill(self, _name):
        return dict(self.entry)

    def list_skills(self, **_kwargs):
        return [dict(self.entry)]


class _Response:
    def __init__(self, content):
        self.content = content
        self.headers = {"Content-Type": "application/zip"}

    def raise_for_status(self):
        return None


class _Session:
    def __init__(self, content):
        self.content = content

    def post(self, *_args, **_kwargs):
        return _Response(self.content)


class _CatalogSession:
    def __init__(self):
        self.pages = []

    def get(self, _url, params=None, **_kwargs):
        self.pages.append(params["page"])
        page = params["page"]
        values = [{"name": f"skill-{index}"} for index in range((page - 1) * 100, min(page * 100, 205))]

        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {"skills": values, "total": 205}

        return Response()


class SkillV2IntegrityTest(unittest.TestCase):
    def test_docx_compatibility_manifest_is_versioned_and_pinned(self):
        entry = legacy_compat_entry("docx", "1.0.0")
        self.assertEqual(1, entry["manifest_version"])
        self.assertEqual(64, len(entry["artifact_sha256"]))
        requirements, _ = merge_legacy_requirements({"name": "docx", "version": "1.0.0"})
        self.assertIn("docx@9.5.1", requirements["npm"])
        self.assertIn("office-documents", requirements["capabilities"])

    def test_unknown_capability_is_reported_unavailable(self):
        self.assertFalse(capability_status(["not-real"])[0]["available"])

    def test_capability_pack_contract_is_declared_in_dockerfile(self):
        dockerfile = Path(__file__).resolve().parents[1].joinpath("docker", "Dockerfile.latest").read_text()
        self.assertIn('ARG SKILL_CAPABILITY_PACKS=""', dockerfile)
        self.assertIn('office) CAPABILITY_PACKAGES=', dockerfile)
        self.assertIn('browser) ENABLE_BROWSER=true', dockerfile)
        self.assertIn('Unknown SKILL_CAPABILITY_PACKS entry', dockerfile)

    def test_legacy_audit_reads_every_catalog_page_without_downloading(self):
        session = _CatalogSession()
        catalog = fetch_catalog(session)
        self.assertEqual(205, len(catalog))
        self.assertEqual([1, 2, 3], session.pages)

    def test_legacy_catalog_cannot_be_used_as_install_source(self):
        entry = {
            "name": "sample-skill", "version": "1.0.0", "status": "active",
            "registry_source": "cowagent-skillhub", "requirements": {
                "env": [], "bins": [], "python": [], "npm": [], "downloads": [], "capabilities": [],
            },
        }
        with tempfile.TemporaryDirectory() as workspace:
            skills = Path(workspace, "skills")
            manager = SkillLifecycleManager(
                workspace=workspace, skills_dir=str(skills), legacy_registry=_LegacyRegistry(entry),
                session=_Session(package()),
            )
            with self.assertRaisesRegex(SkillLifecycleError, "仅提供技能介绍页"):
                manager.install("sample-skill", source="cowagent-skillhub")
            self.assertFalse(Path(workspace, "skills.lock.json").exists())
            self.assertFalse(Path(skills, "sample-skill").exists())


if __name__ == "__main__":
    unittest.main()
