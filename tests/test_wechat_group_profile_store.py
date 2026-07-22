import os
import tempfile
import unittest

from channel.wechat_group.wechat_group_profile_store import WechatGroupProfileStore


class WechatGroupProfileStoreTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self._tmp.name, "profiles.db")
        self.store = WechatGroupProfileStore(self.db_path)

    def tearDown(self):
        self._tmp.cleanup()

    def test_profile_key_is_unique_per_stable_room_and_member(self):
        self.store.upsert_profile("wgr_a", "wgm_alice", primary_nickname="Alice A")
        self.store.upsert_profile("wgr_a", "wgm_alice", primary_nickname="Alice A2")
        self.store.upsert_profile("wgr_b", "wgm_alice", primary_nickname="Alice B")

        room_a = self.store.list_profiles("wgr_a")
        room_b = self.store.list_profiles("wgr_b")

        self.assertEqual(1, len(room_a))
        self.assertEqual("Alice A2", room_a[0]["primary_nickname"])
        self.assertEqual("Alice B", room_b[0]["primary_nickname"])

    def test_name_records_are_idempotent_inside_member_scope(self):
        self.store.upsert_profile("wgr_a", "wgm_alice", primary_nickname="Alice")
        self.store.upsert_name_record(
            "wgr_a",
            "wgm_alice",
            "阿狸",
            source_kind="observed",
            evidence_message_ids=["m1"],
            last_seen_at=100,
        )
        self.store.upsert_name_record(
            "wgr_a",
            "wgm_alice",
            "阿狸",
            source_kind="observed",
            evidence_message_ids=["m2"],
            last_seen_at=200,
        )

        names = self.store.list_name_records("wgr_a", "wgm_alice")

        self.assertEqual(1, len(names))
        self.assertEqual(2, names[0]["seen_count"])
        self.assertEqual(200, names[0]["last_seen_at"])
        self.assertEqual(["m1", "m2"], names[0]["evidence_message_ids"])

    def test_evolution_rollback_restores_profile_names_and_claims(self):
        self.store.upsert_profile("wgr_a", "wgm_alice", interests=["旧兴趣"])
        self.store.upsert_name_record(
            "wgr_a",
            "wgm_alice",
            "Alice",
            source_kind="manual_primary",
        )
        run_id = self.store.create_run("wgr_a", "manual", 10)
        self.store.apply_evolution_update(
            "wgr_a",
            "wgm_alice",
            fields={"interests": ["旧兴趣", "新兴趣"]},
            aliases=[{
                "value": "阿狸",
                "confidence": 0.95,
                "evidence_message_ids": ["m11"],
            }],
            claims=[{
                "dimension": "interest",
                "value": "新兴趣",
                "confidence": 0.9,
                "evidence_message_ids": ["m11"],
            }],
            run_id=run_id,
            evidence_message_ids=["m11"],
        )
        self.store.finish_run(run_id, status="success", batch_end_row_id=11)

        result = self.store.rollback_run("wgr_a", run_id)

        self.assertEqual(["旧兴趣"], self.store.get_profile("wgr_a", "wgm_alice")["interests"])
        self.assertEqual(["Alice"], [item["display_name"] for item in self.store.list_name_records("wgr_a", "wgm_alice")])
        self.assertEqual([], self.store.list_claims("wgr_a", "wgm_alice"))
        self.assertEqual(1, result["rolled_back"])
        self.assertTrue(self.store.rollback_run("wgr_a", run_id)["already_rolled_back"])

    def test_only_latest_evolution_run_can_be_rolled_back(self):
        first = self.store.create_run("wgr_a", "manual", 0)
        self.store.finish_run(first, status="success")
        second = self.store.create_run("wgr_a", "manual", 0)
        self.store.finish_run(second, status="success")

        with self.assertRaisesRegex(ValueError, "latest evolution run"):
            self.store.rollback_run("wgr_a", first)

    def test_evolution_update_rejects_run_from_another_room(self):
        run_id = self.store.create_run("wgr_a", "manual", 0)

        with self.assertRaisesRegex(ValueError, "does not belong"):
            self.store.apply_evolution_update(
                "wgr_b",
                "wgm_alice",
                fields={},
                aliases=[],
                claims=[],
                run_id=run_id,
            )

    def test_learning_state_is_isolated_by_pipeline(self):
        self.store.update_learning_state("wgr_a", pipeline="heuristic", last_archive_row_id=20)
        self.store.update_learning_state("wgr_a", pipeline="evolution", last_archive_row_id=30)

        self.assertEqual(20, self.store.get_learning_state("wgr_a", "heuristic")["last_archive_row_id"])
        self.assertEqual(30, self.store.get_learning_state("wgr_a", "evolution")["last_archive_row_id"])

    def test_merge_profile_subjects_leaves_one_canonical_profile(self):
        self.store.upsert_profile("wgr_a", "wgm_old", interests=["Python"], msg_count=3)
        self.store.upsert_profile("wgr_a", "wgm_main", interests=["架构"], msg_count=5)
        self.store.upsert_name_record("wgr_a", "wgm_old", "Alice", source_kind="observed")

        profile = self.store.merge_profile_subjects("wgr_a", "wgm_old", "wgm_main")

        self.assertEqual(["架构", "Python"], profile["interests"])
        self.assertEqual(5, profile["msg_count"])
        self.assertIsNone(self.store.get_profile("wgr_a", "wgm_old"))
        self.assertEqual(1, self.store.count_profiles("wgr_a"))
        self.assertEqual("wgm_main", self.store.list_name_records("wgr_a", "wgm_main")[0]["stable_member_id"])
        self.assertEqual("ok", self.store.integrity_check())


if __name__ == "__main__":
    unittest.main()
