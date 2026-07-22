import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing

from channel.wechat_group.wechat_group_archive import WechatGroupArchive
from channel.wechat_group.wechat_group_profile_store import WechatGroupProfileStore
from scripts.reset_wechat_group_profiles import reset_wechat_group_profiles


class ResetWechatGroupProfilesTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.data_root = self._tmp.name
        self.group_dir = os.path.join(self.data_root, "wechat_group")
        os.makedirs(self.group_dir, exist_ok=True)
        with open(os.path.join(self.data_root, "config.json"), "w", encoding="utf-8") as handle:
            json.dump({"wechat_group_stable_room_ids": ["wgr_a"]}, handle)

        archive = WechatGroupArchive(os.path.join(self.group_dir, "wechat_group_archive.db"))
        archive.record_message(
            message_id="m1",
            room_id="room@@a",
            stable_room_id="wgr_a",
            sender_id="alice-runtime",
            stable_member_id="wgm_alice",
            text="old message",
        )
        archive.record_message(
            message_id="m2",
            room_id="room@@b",
            stable_room_id="wgr_b",
            sender_id="bob-runtime",
            stable_member_id="wgm_bob",
            text="other room",
        )
        self.expected_high_water = archive.get_max_row_id("wgr_a")
        self._create_legacy_profile_db(os.path.join(self.group_dir, "wechat_group_profiles.db"))
        self._create_sentinel_db(
            os.path.join(self.group_dir, "wechat_group_profile_evolution.db"),
            "legacy_evolution",
        )
        self._create_sentinel_db(
            os.path.join(self.group_dir, "wechat_group_identity.db"),
            "identity_sentinel",
        )
        self._create_sentinel_db(
            os.path.join(self.group_dir, "wechat_group_knowledge.db"),
            "knowledge_sentinel",
        )

    def tearDown(self):
        self._tmp.cleanup()

    @staticmethod
    def _create_legacy_profile_db(path):
        with closing(sqlite3.connect(path)) as conn:
            with conn:
                conn.execute("CREATE TABLE wechat_group_global_profiles (sender_id TEXT PRIMARY KEY)")
                conn.execute("INSERT INTO wechat_group_global_profiles VALUES ('runtime-alice')")
                conn.execute("CREATE TABLE wechat_group_profile_name_records (sender_id TEXT, room_id TEXT)")
                conn.execute("INSERT INTO wechat_group_profile_name_records VALUES ('runtime-alice', 'room@@a')")

    @staticmethod
    def _create_sentinel_db(path, table):
        with closing(sqlite3.connect(path)) as conn:
            with conn:
                conn.execute(f"CREATE TABLE {table} (value TEXT)")
                conn.execute(f"INSERT INTO {table} VALUES ('keep')")

    @staticmethod
    def _table_exists(path, table):
        with closing(sqlite3.connect(path)) as conn:
            row = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                (table,),
            ).fetchone()
        return bool(row)

    def test_apply_rebuilds_only_profile_data_and_sets_pipeline_baselines(self):
        report = reset_wechat_group_profiles(self.data_root, apply=True, timestamp="20260720_120000")

        profile_path = os.path.join(self.group_dir, "wechat_group_profiles.db")
        store = WechatGroupProfileStore(profile_path)
        self.assertEqual("success", report["status"])
        self.assertEqual("ok", report["integrity_check"])
        self.assertEqual(0, store.count_profiles("wgr_a"))
        self.assertEqual(
            self.expected_high_water,
            store.get_learning_state("wgr_a", "heuristic")["last_archive_row_id"],
        )
        self.assertEqual(
            self.expected_high_water,
            store.get_learning_state("wgr_a", "evolution")["last_archive_row_id"],
        )
        self.assertFalse(self._table_exists(profile_path, "wechat_group_global_profiles"))
        self.assertFalse(os.path.exists(os.path.join(self.group_dir, "wechat_group_profile_evolution.db")))
        self.assertTrue(self._table_exists(os.path.join(self.group_dir, "wechat_group_identity.db"), "identity_sentinel"))
        self.assertTrue(self._table_exists(os.path.join(self.group_dir, "wechat_group_knowledge.db"), "knowledge_sentinel"))
        self.assertTrue(os.path.exists(report["manifest_path"]))

    def test_dry_run_does_not_replace_legacy_profile_database(self):
        report = reset_wechat_group_profiles(self.data_root, apply=False)

        profile_path = os.path.join(self.group_dir, "wechat_group_profiles.db")
        self.assertEqual("planned", report["status"])
        self.assertTrue(self._table_exists(profile_path, "wechat_group_global_profiles"))
        self.assertEqual(self.expected_high_water, report["archive_high_water"]["wgr_a"])

    def test_apply_rejects_empty_stable_room_scope(self):
        config_path = os.path.join(self.data_root, "config.json")
        with open(config_path, "w", encoding="utf-8") as handle:
            json.dump({"wechat_group_stable_room_ids": []}, handle)

        with self.assertRaisesRegex(ValueError, "at least one stable room id"):
            reset_wechat_group_profiles(self.data_root, apply=True, timestamp="20260720_120003")

        profile_path = os.path.join(self.group_dir, "wechat_group_profiles.db")
        self.assertTrue(self._table_exists(profile_path, "wechat_group_global_profiles"))

    def test_rebuild_is_repeatable_with_a_new_backup_timestamp(self):
        reset_wechat_group_profiles(self.data_root, apply=True, timestamp="20260720_120001")
        report = reset_wechat_group_profiles(self.data_root, apply=True, timestamp="20260720_120002")

        self.assertEqual("success", report["status"])
        self.assertEqual(2, report["table_counts"]["wechat_group_member_profile_learning_state"])


if __name__ == "__main__":
    unittest.main()
