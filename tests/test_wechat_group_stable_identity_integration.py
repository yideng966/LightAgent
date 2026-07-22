import json
import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from channel.wechat_group.wechat_group_identity_store import WechatGroupIdentityStore
from scripts.migrate_wechat_group_identity import run_migration


class WechatGroupStableIdentityIntegrationTest(unittest.TestCase):
    def test_migration_dry_run_and_apply_keeps_legacy_runtime_snapshots(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.json")
            archive_path = os.path.join(tmpdir, "archive.db")
            identity_path = os.path.join(tmpdir, "identity.db")
            tasks_path = os.path.join(tmpdir, "tasks.json")
            config = {
                "wechat_group_room_ids": ["room@@old"],
                "wechat_group_names": ["测试群"],
                "wechat_group_admin_members": [{
                    "room_id": "room@@old",
                    "sender_id": "wxid_old",
                    "sender_nickname": "Alice",
                }],
                "wechat_group_blocked_sender_ids": ["wxid_old"],
                "wechat_group_free_reply_room_ids": ["room@@old"],
            }
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False)

            self._create_archive(archive_path)
            with open(tasks_path, "w", encoding="utf-8") as f:
                json.dump({
                    "task-1": {
                        "task_id": "task-1",
                        "action": {
                            "channel_type": "wechat_group",
                            "receiver": "room@@old",
                            "notify_session_id": "wechat_group:room@@old",
                        },
                    }
                }, f)

            dry_run = run_migration(
                config_path=config_path,
                identity_db_path=identity_path,
                sqlite_paths=[archive_path],
                scheduler_tasks_path=tasks_path,
                apply=False,
            )
            with open(config_path, "r", encoding="utf-8") as f:
                self.assertNotIn("wechat_group_stable_room_ids", json.load(f))
            self.assertEqual(1, dry_run["summary"]["rooms"])
            self.assertTrue(dry_run["dry_run"])

            applied = run_migration(
                config_path=config_path,
                identity_db_path=identity_path,
                sqlite_paths=[archive_path],
                scheduler_tasks_path=tasks_path,
                apply=True,
            )

            stable_room_id = applied["rooms"][0]["stable_room_id"]
            stable_member_id = applied["members"][0]["stable_member_id"]
            with open(config_path, "r", encoding="utf-8") as f:
                migrated_config = json.load(f)
            self.assertEqual([stable_room_id], migrated_config["wechat_group_stable_room_ids"])
            self.assertEqual([stable_room_id], migrated_config["wechat_group_free_reply_stable_room_ids"])
            self.assertEqual(["room@@old"], migrated_config["wechat_group_free_reply_room_ids"])
            self.assertEqual([stable_member_id], migrated_config["wechat_group_blocked_stable_member_ids"])
            self.assertEqual(["wxid_old"], migrated_config["wechat_group_blocked_sender_ids"])
            self.assertEqual(stable_room_id, migrated_config["wechat_group_admin_members"][0]["stable_room_id"])
            self.assertEqual(stable_member_id, migrated_config["wechat_group_admin_members"][0]["stable_member_id"])
            self.assertEqual("room@@old", migrated_config["wechat_group_admin_members"][0]["legacy_room_id"])
            self.assertEqual("legacy_imported", migrated_config["wechat_group_admin_members"][0]["identity_status"])

            store = WechatGroupIdentityStore(identity_path)
            self.assertEqual("room@@old", store.get_active_runtime_room_id(applied["stable_account_id"], stable_room_id))
            self.assertEqual(
                "wxid_old",
                store.get_active_runtime_sender_id(applied["stable_account_id"], stable_room_id, stable_member_id),
            )

            with closing(sqlite3.connect(archive_path)) as conn:
                row = conn.execute(
                    """
                    SELECT room_id, sender_id, stable_room_id, runtime_room_id, stable_member_id, runtime_sender_id
                    FROM wechat_group_messages
                    WHERE message_id = 'msg-1'
                    """
                ).fetchone()
            self.assertEqual(("room@@old", "wxid_old", stable_room_id, "room@@old", stable_member_id, "wxid_old"), row)

            with open(tasks_path, "r", encoding="utf-8") as f:
                task = json.load(f)["task-1"]
            self.assertEqual("room@@old", task["action"]["receiver"])
            self.assertEqual(stable_room_id, task["action"]["stable_receiver"])
            self.assertEqual("room@@old", task["action"]["runtime_receiver"])
            self.assertEqual("wechat_group:{}".format(stable_room_id), task["action"]["notify_session_id"])

    def test_migration_reports_same_room_name_cross_account_conflict(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.json")
            identity_path = os.path.join(tmpdir, "identity.db")
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump({
                    "wechat_group_room_ids": ["room@@new"],
                    "wechat_group_names": ["同名群"],
                }, f, ensure_ascii=False)

            store = WechatGroupIdentityStore(identity_path)
            store.upsert_account("wga_existing", display_name="Existing")
            store.upsert_room(
                "wgr_existing",
                "wga_existing",
                canonical_name="同名群",
                status="confirmed",
                confidence="manual",
            )

            dry_run = run_migration(
                config_path=config_path,
                identity_db_path=identity_path,
                apply=False,
            )

            self.assertEqual(1, len(dry_run["conflicts"]))
            conflict = dry_run["conflicts"][0]
            self.assertEqual("same_room_name_different_stable_account", conflict["reason"])
            self.assertEqual("wga_existing", conflict["existing_stable_account_id"])
            self.assertEqual("room@@new", conflict["incoming_runtime_room_id"])

    def test_migration_preserves_stable_config_and_reports_unresolved_legacy_ids(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.json")
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump({
                    "wechat_group_room_ids": ["room@@a", "room@@b"],
                    "wechat_group_stable_room_ids": ["wgr_a", "wgr_b", "wgr_detached"],
                    "wechat_group_free_reply_stable_room_ids": ["wgr_existing_free"],
                    "wechat_group_free_reply_room_ids": ["room@@a", "room@@missing"],
                    "wechat_group_blocked_stable_member_ids": ["wgm_existing"],
                    "wechat_group_blocked_sender_ids": ["wxid_shared"],
                    "wechat_group_admin_members": [
                        {"room_id": "room@@a", "sender_id": "wxid_shared"},
                        {"room_id": "room@@b", "sender_id": "wxid_shared"},
                    ],
                }, f, ensure_ascii=False)

            report = run_migration(
                config_path=config_path,
                identity_db_path=os.path.join(tmpdir, "identity.db"),
                apply=False,
            )

            preview = report["config_preview"]
            self.assertEqual(["wgr_a", "wgr_b", "wgr_detached"], preview["wechat_group_stable_room_ids"])
            self.assertEqual(
                ["wgr_existing_free", "wgr_a"],
                preview["wechat_group_free_reply_stable_room_ids"],
            )
            self.assertEqual(["room@@a", "room@@missing"], preview["wechat_group_free_reply_room_ids"])
            self.assertEqual(["wgm_existing"], preview["wechat_group_blocked_stable_member_ids"])
            reasons = {item.get("reason") for item in report["manual_confirmation"]}
            self.assertIn("legacy_free_reply_room_requires_binding", reasons)
            self.assertIn("legacy_blocked_sender_is_ambiguous", reasons)

    def test_migration_reports_missing_media_without_blocking_updates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.json")
            archive_path = os.path.join(tmpdir, "archive.db")
            missing_path = os.path.join(tmpdir, "missing-image.jpg")
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump({"wechat_group_room_ids": ["room@@old"]}, f)
            self._create_archive(archive_path, media_path=missing_path)

            report = run_migration(
                config_path=config_path,
                identity_db_path=os.path.join(tmpdir, "identity.db"),
                sqlite_paths=[archive_path],
                apply=False,
            )

            self.assertEqual(1, report["summary"]["missing_media"])
            self.assertEqual(1, len(report["missing_media"]))
            self.assertEqual("wechat_group_messages", report["missing_media"][0]["table"])
            self.assertEqual(missing_path, report["missing_media"][0]["media_path"])
            self.assertEqual(1, report["summary"]["sqlite_updates"])

    def test_migration_repairs_runtime_id_written_into_stable_room_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.json")
            identity_path = os.path.join(tmpdir, "identity.db")
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump({
                    "wechat_group_room_ids": ["room@@current"],
                    "wechat_group_stable_room_ids": ["room@@current"],
                    "wechat_group_free_reply_stable_room_ids": ["wgr_room"],
                    "wechat_group_free_reply_room_ids": ["room@@current"],
                    "wechat_group_names": ["测试群"],
                }, f, ensure_ascii=False)
            store = WechatGroupIdentityStore(identity_path)
            store.upsert_account("wga_account", status="confirmed", confidence="manual", confirmed_at=1)
            store.upsert_room(
                "wgr_room",
                "wga_account",
                canonical_name="测试群",
                status="confirmed",
                confidence="manual",
                confirmed_at=1,
            )
            store.activate_room_alias(
                "wga_account",
                "wgr_room",
                "room@@current",
                room_name="测试群",
                source_kind="manual",
            )

            dry_run = run_migration(
                config_path=config_path,
                identity_db_path=identity_path,
                apply=False,
            )

            self.assertEqual(["wgr_room"], dry_run["config_preview"]["wechat_group_stable_room_ids"])
            self.assertEqual(["room@@current"], dry_run["config_preview"]["wechat_group_room_ids"])
            self.assertEqual(1, dry_run["summary"]["stable_config_repairs"])
            self.assertNotIn(
                "legacy_free_reply_room_requires_binding",
                {item.get("reason") for item in dry_run["manual_confirmation"]},
            )

    def test_migration_does_not_repair_stable_config_from_suspected_room_alias(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.json")
            identity_path = os.path.join(tmpdir, "identity.db")
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump({
                    "wechat_group_room_ids": [],
                    "wechat_group_stable_room_ids": ["room@@suspected"],
                }, f, ensure_ascii=False)
            store = WechatGroupIdentityStore(identity_path)
            store.upsert_account("wga_account", status="confirmed", confidence="manual", confirmed_at=1)
            store.upsert_room(
                "wgr_room",
                "wga_account",
                canonical_name="测试群",
                status="confirmed",
                confidence="manual",
                confirmed_at=1,
            )
            store.record_room_alias_candidate(
                "wga_account",
                "wgr_room",
                "room@@suspected",
                room_name="测试群",
            )

            report = run_migration(
                config_path=config_path,
                identity_db_path=identity_path,
                apply=False,
            )

            self.assertEqual([], report["config_preview"]["wechat_group_stable_room_ids"])
            self.assertEqual("unresolved", report["stable_config_repairs"][0]["status"])
            self.assertEqual(0, report["summary"]["stable_config_repairs"])

    def test_migration_rerun_keeps_existing_confirmed_room_ownership_and_active_alias(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.json")
            identity_path = os.path.join(tmpdir, "identity.db")
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump({
                    "wechat_group_room_ids": ["room@@current"],
                    "wechat_group_stable_room_ids": ["wgr_room"],
                    "wechat_group_names": ["测试群"],
                    "wechat_group_admin_members": [{
                        "stable_room_id": "wgr_room",
                        "stable_member_id": "wgm_alice",
                        "legacy_room_id": "room@@current",
                        "legacy_sender_id": "wxid_alice",
                        "identity_status": "confirmed",
                    }],
                }, f, ensure_ascii=False)
            store = WechatGroupIdentityStore(identity_path)
            store.upsert_account("wga_confirmed", status="confirmed", confidence="manual", confirmed_at=1)
            store.upsert_room(
                "wgr_room",
                "wga_confirmed",
                canonical_name="测试群",
                status="confirmed",
                confidence="manual",
                confirmed_at=1,
            )
            store.activate_room_alias(
                "wga_confirmed",
                "wgr_room",
                "room@@current",
                room_name="测试群",
                source_kind="manual",
            )
            store.upsert_member(
                "wgm_alice",
                "wgr_room",
                "wga_confirmed",
                display_name="Alice",
                status="confirmed",
                confidence="manual",
                confirmed_at=1,
            )
            store.activate_member_alias(
                "wga_confirmed",
                "wgr_room",
                "wgm_alice",
                "wxid_alice",
                runtime_room_id="room@@current",
                display_name="Alice",
                source_kind="manual",
            )

            dry_run = run_migration(
                config_path=config_path,
                identity_db_path=identity_path,
                apply=False,
            )
            applied = run_migration(
                config_path=config_path,
                identity_db_path=identity_path,
                apply=True,
            )

            self.assertNotIn(
                "legacy_runtime_import_requires_first_relogin_confirmation",
                {item.get("reason") for item in dry_run["manual_confirmation"]},
            )
            self.assertEqual(0, dry_run["summary"]["rooms"])
            self.assertEqual(1, dry_run["summary"]["existing_confirmed_rooms"])
            self.assertEqual("wga_confirmed", store.get_room("wgr_room")["stable_account_id"])
            self.assertEqual(
                "room@@current",
                store.get_active_runtime_room_id("wga_confirmed", "wgr_room"),
            )
            self.assertTrue(applied["rooms"][0]["already_confirmed"])
            self.assertEqual("confirmed", store.get_member("wgm_alice")["status"])
            self.assertEqual(
                "wxid_alice",
                store.get_active_runtime_sender_id("wga_confirmed", "wgr_room", "wgm_alice"),
            )
            self.assertTrue(applied["members"][0]["already_confirmed"])
            with open(config_path, "r", encoding="utf-8") as f:
                migrated_config = json.load(f)
            self.assertEqual(
                "confirmed",
                migrated_config["wechat_group_admin_members"][0]["identity_status"],
            )

    @staticmethod
    def _create_archive(path, media_path=""):
        with closing(sqlite3.connect(path)) as conn:
            conn.execute(
                """
                CREATE TABLE wechat_group_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id TEXT NOT NULL,
                    room_id TEXT NOT NULL,
                    sender_id TEXT,
                    media_path TEXT,
                    stable_room_id TEXT NOT NULL DEFAULT '',
                    runtime_room_id TEXT NOT NULL DEFAULT '',
                    stable_member_id TEXT NOT NULL DEFAULT '',
                    runtime_sender_id TEXT NOT NULL DEFAULT ''
                )
                """
            )
            conn.execute(
                """
                INSERT INTO wechat_group_messages (
                    message_id, room_id, sender_id, media_path, stable_room_id, runtime_room_id,
                    stable_member_id, runtime_sender_id
                ) VALUES ('msg-1', 'room@@old', 'wxid_old', ?, '', '', '', '')
                """,
                (media_path,),
            )
            conn.commit()


if __name__ == "__main__":
    unittest.main()
