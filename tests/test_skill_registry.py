import base64
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from agent.skills.registry import (
    LegacySkillRegistryClient,
    REGISTRY_PUBLIC_KEYS,
    RegistrySecurityError,
    SkillRegistryClient,
    _canonical_json,
)


class _Response:
    def __init__(self, document):
        self.document = document

    def raise_for_status(self):
        return None

    def json(self):
        return self.document


class _Session:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error

    def get(self, *_args, **_kwargs):
        if self.error:
            raise self.error
        return _Response(self.response)


class SkillRegistryClientTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.private = Ed25519PrivateKey.generate()
        public = self.private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        self.key_patch = patch.dict(REGISTRY_PUBLIC_KEYS, {"test-key": base64.b64encode(public).decode()})
        self.key_patch.start()

    def tearDown(self):
        self.key_patch.stop()
        self.temp.cleanup()

    def _document(self):
        payload = {
            "registry_version": 1,
            "repository": "https://example.test/hub",
            "source_commit": "abc",
            "skills": [{"name": "sample", "status": "active", "tags": []}],
        }
        signature = self.private.sign(_canonical_json(payload))
        return {
            **payload,
            "signature": {
                "algorithm": "ed25519",
                "key_id": "test-key",
                "value": base64.b64encode(signature).decode(),
            },
        }

    def test_valid_registry_is_cached_and_cache_survives_network_failure(self):
        document = self._document()
        client = SkillRegistryClient("https://example.test/registry.json", self.temp.name, _Session(document))
        snapshot = client.load()
        self.assertFalse(snapshot.cached)
        self.assertEqual(["sample"], [item["name"] for item in client.list_skills()])

        offline = SkillRegistryClient("https://example.test/registry.json", self.temp.name, _Session(error=OSError("offline")))
        cached = offline.load()
        self.assertTrue(cached.cached)
        self.assertEqual("sample", cached.data["skills"][0]["name"])

    def test_tampered_registry_never_falls_back_to_cache(self):
        document = self._document()
        SkillRegistryClient("https://example.test/registry.json", self.temp.name, _Session(document)).load()
        document["skills"][0]["name"] = "tampered"
        client = SkillRegistryClient("https://example.test/registry.json", self.temp.name, _Session(document))
        with self.assertRaises(RegistrySecurityError):
            client.load()

    def test_revoked_skill_is_not_installable(self):
        document = self._document()
        document["skills"][0]["status"] = "revoked"
        payload = dict(document)
        payload.pop("signature")
        document["signature"]["value"] = base64.b64encode(self.private.sign(_canonical_json(payload))).decode()
        client = SkillRegistryClient("https://example.test/registry.json", self.temp.name, _Session(document))
        with self.assertRaises(RegistrySecurityError):
            client.get_skill("sample")

    def test_concurrent_cache_writes_keep_complete_verified_json(self):
        document = self._document()
        client = SkillRegistryClient(
            "https://example.test/registry.json", self.temp.name, _Session(document)
        )
        threads = [
            threading.Thread(target=client._write_cache, args=(document,))
            for _ in range(12)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        cached = client._read_cache()
        self.assertEqual(document, cached)

    def test_original_marketplace_catalog_is_normalized_and_cached(self):
        document = {
            "skills": [{
                "name": "legacy-skill", "display_name": "Legacy", "version": "1.2.3",
                "description": "old hub", "author": "tester", "status": "published",
                "requires_env": ["TOKEN"], "requires_bins": ["curl"],
            }],
            "total": 1, "page": 1, "limit": 50,
        }
        client = LegacySkillRegistryClient(
            "https://legacy.test/api", self.temp.name, _Session(document)
        )
        item = client.list_skills()[0]
        self.assertEqual("cowagent-skillhub", item["registry_source"])
        self.assertEqual("active", item["status"])
        self.assertEqual(["TOKEN"], item["requirements"]["env"])
        self.assertEqual("https://skills.cowagent.ai/legacy-skill", item["detail_url"])

        offline = LegacySkillRegistryClient(
            "https://legacy.test/api", self.temp.name, _Session(error=OSError("offline"))
        )
        cached_item = offline.list_skills()[0]
        self.assertEqual("legacy-skill", cached_item["name"])
        self.assertEqual("https://skills.cowagent.ai/legacy-skill", cached_item["detail_url"])

    def test_original_marketplace_adds_reviewed_dependency_manifest(self):
        document = {
            "skills": [{
                "name": "docx", "version": "1.0.0", "status": "published",
                "requires_env": [], "requires_bins": [],
            }],
            "total": 1, "page": 1, "limit": 50,
        }
        client = LegacySkillRegistryClient(
            "https://legacy.test/api", self.temp.name, _Session(document)
        )
        requirements = client.list_skills()[0]["requirements"]
        self.assertEqual(["defusedxml>=0.7.1"], requirements["python"])
        self.assertEqual(["docx@9.5.1"], requirements["npm"])

        cached = json.loads((Path(self.temp.name) / "cowagent-catalog.last-good.json").read_text())
        cached[0]["requirements"] = {
            "env": [], "bins": [], "python": [], "npm": [], "downloads": [],
        }
        (Path(self.temp.name) / "cowagent-catalog.last-good.json").write_text(
            json.dumps(cached), encoding="utf-8"
        )
        offline = LegacySkillRegistryClient(
            "https://legacy.test/api", self.temp.name, _Session(error=OSError("offline"))
        )
        self.assertEqual(["docx@9.5.1"], offline.list_skills()[0]["requirements"]["npm"])


if __name__ == "__main__":
    unittest.main()
