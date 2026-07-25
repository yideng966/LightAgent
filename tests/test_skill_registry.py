import base64
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from agent.skills.registry import (
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


if __name__ == "__main__":
    unittest.main()
