import json
import io
import os
import secrets
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from agent.skills.backup import (
    create_download_token,
    create_encrypted_backup,
    consume_download_token,
    restore_encrypted_backup,
    MAGIC,
    _derive_key,
)
from agent.skills.lifecycle import SkillLifecycleError


class SkillBackupTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name)
        self.workspace.joinpath("skills.lock.json").write_text(
            json.dumps({"lock_version": 2, "skills": {"sample-skill": {"version": "1.0.0"}}}),
            encoding="utf-8",
        )
        self.workspace.joinpath("skill-config/sample-skill").mkdir(parents=True)
        self.workspace.joinpath("skill-data/sample-skill").mkdir(parents=True)
        self.workspace.joinpath("skill-config/sample-skill/secret.txt").write_text("secret", encoding="utf-8")
        self.workspace.joinpath("skill-data/sample-skill/data.txt").write_text("data", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_encrypted_backup_round_trip(self):
        content = create_encrypted_backup(str(self.workspace), "sample-skill", "long-passphrase")
        self.assertNotIn(b"secret", content)
        self.workspace.joinpath("skill-config/sample-skill/secret.txt").write_text("changed", encoding="utf-8")
        result = restore_encrypted_backup(str(self.workspace), content, "long-passphrase")
        self.assertEqual("sample-skill", result["name"])
        self.assertEqual("secret", self.workspace.joinpath("skill-config/sample-skill/secret.txt").read_text())

    def test_wrong_password_and_tampering_are_rejected(self):
        content = create_encrypted_backup(str(self.workspace), "sample-skill", "long-passphrase")
        with self.assertRaisesRegex(SkillLifecycleError, "口令错误|篡改"):
            restore_encrypted_backup(str(self.workspace), content, "wrong-password")
        with self.assertRaisesRegex(SkillLifecycleError, "口令错误|篡改"):
            restore_encrypted_backup(str(self.workspace), content[:-1] + bytes([content[-1] ^ 1]), "long-passphrase")

    def test_download_token_is_one_time(self):
        token = create_download_token(str(self.workspace), "sample-skill", "long-passphrase")
        name, content = consume_download_token(token["token"])
        self.assertEqual("sample-skill", name)
        self.assertTrue(content)
        with self.assertRaisesRegex(SkillLifecycleError, "无效|过期"):
            consume_download_token(token["token"])

    def test_path_traversal_is_rejected_before_extraction(self):
        content = self._encrypted_zip({"manifest.json": json.dumps({"skill_name": "sample-skill"}), "../outside.txt": "bad"})
        with self.assertRaisesRegex(SkillLifecycleError, "路径穿越"):
            restore_encrypted_backup(str(self.workspace), content, "long-passphrase")
        self.assertFalse(self.workspace.parent.joinpath("outside.txt").exists())

    def test_excessive_uncompressed_archive_is_rejected(self):
        from agent.skills import backup as backup_module
        content = self._encrypted_zip({"manifest.json": json.dumps({"skill_name": "sample-skill"}), "data/large.bin": "x" * 4096})
        original = backup_module.MAX_BACKUP_UNCOMPRESSED_BYTES
        backup_module.MAX_BACKUP_UNCOMPRESSED_BYTES = 1024
        try:
            with self.assertRaisesRegex(SkillLifecycleError, "解压数据"):
                restore_encrypted_backup(str(self.workspace), content, "long-passphrase")
        finally:
            backup_module.MAX_BACKUP_UNCOMPRESSED_BYTES = original

    def test_restore_rolls_back_config_when_data_commit_fails(self):
        content = create_encrypted_backup(str(self.workspace), "sample-skill", "long-passphrase")
        self.workspace.joinpath("skill-config/sample-skill/secret.txt").write_text("current-config")
        self.workspace.joinpath("skill-data/sample-skill/data.txt").write_text("current-data")
        real_replace = os.replace

        def fail_data(source, target):
            if Path(source).name == "ready-data" and Path(target) == self.workspace / "skill-data/sample-skill":
                raise OSError("simulated data commit failure")
            return real_replace(source, target)

        with mock.patch("agent.skills.backup.os.replace", side_effect=fail_data):
            with self.assertRaisesRegex(OSError, "simulated"):
                restore_encrypted_backup(str(self.workspace), content, "long-passphrase")
        self.assertEqual("current-config", self.workspace.joinpath("skill-config/sample-skill/secret.txt").read_text())
        self.assertEqual("current-data", self.workspace.joinpath("skill-data/sample-skill/data.txt").read_text())

    @staticmethod
    def _encrypted_zip(files):
        payload = io.BytesIO()
        with zipfile.ZipFile(payload, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, value in files.items():
                archive.writestr(name, value)
        salt = secrets.token_bytes(16)
        nonce = secrets.token_bytes(12)
        header = json.dumps({
            "format": "laskill-backup", "version": 1,
            "skill_name": "sample-skill", "kdf": "scrypt-n16384-r8-p1",
            "cipher": "aes-256-gcm", "salt": salt.hex(), "nonce": nonce.hex(),
        }, sort_keys=True, separators=(",", ":")).encode()
        prefix = MAGIC + struct.pack(">I", len(header)) + header
        return prefix + AESGCM(_derive_key("long-passphrase", salt)).encrypt(nonce, payload.getvalue(), prefix)


if __name__ == "__main__":
    unittest.main()
