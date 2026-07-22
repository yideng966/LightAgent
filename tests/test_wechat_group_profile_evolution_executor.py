import os
import tempfile
import unittest

from channel.wechat_group.wechat_group_archive import WechatGroupArchive
from channel.wechat_group.wechat_group_identity_service import WechatGroupIdentityService
from channel.wechat_group.wechat_group_identity_store import WechatGroupIdentityStore
from channel.wechat_group.wechat_group_profile_evolution_executor import (
    WechatGroupProfileEvolutionExecutor,
)
from channel.wechat_group.wechat_group_profile_evolution_store import (
    WechatGroupProfileEvolutionStore,
)
from channel.wechat_group.wechat_group_profile_llm_extractor import (
    WechatGroupProfileExtractionError,
)
from channel.wechat_group.wechat_group_profile_service import WechatGroupProfileService
from channel.wechat_group.wechat_group_profile_store import WechatGroupProfileStore


class FakeExtractor:
    def __init__(self):
        self.calls = []

    def extract(self, room_id, room_name, messages, existing_profiles):
        self.calls.append((room_id, room_name, messages, existing_profiles))
        token = messages[0]["member_token"]
        return {
            "profiles": [{
                "member_token": token,
                "aliases": [{"value": "Alice Lead", "confidence": 0.92, "evidence_message_ids": ["m1"]}],
            }],
        }


class FakeMerger:
    def __init__(self):
        self.calls = []

    def merge(self, room_id, run_id, payload, room_name="", member_by_token=None, evidence_by_token=None):
        self.calls.append((room_id, run_id, payload, room_name, member_by_token, evidence_by_token))
        return {
            "profile_update_count": 1,
            "alias_update_count": 1,
            "role_hint_update_count": 0,
        }


class WechatGroupProfileEvolutionExecutorTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.archive = WechatGroupArchive(os.path.join(self._tmp.name, "archive.db"))
        profile_store = WechatGroupProfileStore(os.path.join(self._tmp.name, "profiles.db"))
        self.store = WechatGroupProfileEvolutionStore(profile_store=profile_store)
        self.identity = WechatGroupIdentityService(
            WechatGroupIdentityStore(os.path.join(self._tmp.name, "identity.db"))
        )
        account = self.identity.resolve_account("self-a", "Bot", "profile-a", {})
        self.identity.confirm_account_binding(account.stable_id, "self-a", actor="test", reason="account")
        room = self.identity.resolve_room(account.stable_id, "room@@a", "Group A", "self-a", {})
        self.identity.confirm_room_binding(room.stable_id, "room@@a", actor="test", reason="room")
        self.room_id = room.stable_id
        member = self.identity.resolve_member(
            self.room_id,
            "alice-old",
            "Alice",
            "Alice",
            {"wechat_id": "alice-wechat"},
        )
        self.identity.confirm_member_binding(
            self.room_id,
            member.stable_id,
            "alice-old",
            actor="test",
            reason="member",
        )
        self.member_id = member.stable_id
        self.profile_service = WechatGroupProfileService(
            profile_store,
            self.archive,
            identity_service=self.identity,
        )
        self.extractor = FakeExtractor()
        self.merger = FakeMerger()
        self.executor = WechatGroupProfileEvolutionExecutor(
            archive=self.archive,
            evolution_store=self.store,
            profile_service=self.profile_service,
            extractor=self.extractor,
            merger=self.merger,
            batch_message_limit=20,
        )

    def tearDown(self):
        self._tmp.cleanup()

    def _enable_history_from_zero(self):
        self.store.update_status(self.room_id, last_archive_row_id=0, latest_observed_row_id=0)

    def _record(self, message_id, runtime_sender_id="alice-old", stable_member_id=None, created_at=100):
        self.archive.record_message(
            message_id=message_id,
            room_id="room@@a",
            room_name="Group A",
            sender_id=runtime_sender_id,
            sender_nickname="Alice",
            text="hello",
            stable_room_id=self.room_id,
            runtime_room_id="room@@a",
            stable_member_id=stable_member_id if stable_member_id is not None else self.member_id,
            runtime_sender_id=runtime_sender_id,
            created_at=created_at,
        )

    def test_executor_passes_only_opaque_batch_subjects_to_extractor_and_merger(self):
        self._enable_history_from_zero()
        self._record("m1")

        result = self.executor.run_once(self.room_id, trigger_source="manual")
        status = self.store.get_status(self.room_id)
        projected = self.extractor.calls[0][2][0]
        merger_call = self.merger.calls[0]

        self.assertEqual("success", result["status"])
        self.assertEqual("member_001", projected["member_token"])
        self.assertNotIn("sender_id", projected)
        self.assertNotIn("stable_member_id", projected)
        self.assertEqual({"member_001": self.member_id}, merger_call[4])
        self.assertEqual({"member_001": ["m1"]}, merger_call[5])
        self.assertGreater(status["last_archive_row_id"], 0)

    def test_executor_counts_one_member_after_runtime_sender_changes(self):
        self.identity.resolve_member(
            self.room_id,
            "alice-new",
            "Alice",
            "Alice",
            {"wechat_id": "alice-wechat"},
        )
        self._enable_history_from_zero()
        self._record("m1", "alice-old", created_at=100)
        self._record("m2", "alice-new", created_at=101)

        self.executor.run_once(self.room_id, trigger_source="manual")
        runs = self.store.list_runs(self.room_id)

        self.assertEqual(1, runs[0]["analyzed_member_count"])
        self.assertEqual({"member_001": self.member_id}, self.merger.calls[0][4])

    def test_first_run_initializes_archive_high_water_without_replay(self):
        self._record("old-message")

        result = self.executor.run_once(self.room_id, trigger_source="manual")

        self.assertEqual("skipped", result["status"])
        self.assertEqual([], self.extractor.calls)
        self.assertEqual(self.archive.get_max_row_id(self.room_id), self.store.get_status(self.room_id)["last_archive_row_id"])

    def test_unanchored_member_is_skipped_while_cursor_advances(self):
        isolated = self.identity.resolve_member(
            self.room_id,
            "isolated-runtime",
            "Unknown",
            "Unknown",
            {},
        )
        self._enable_history_from_zero()
        self._record("m-isolated", "isolated-runtime", isolated.stable_id)

        result = self.executor.run_once(self.room_id, trigger_source="manual")

        self.assertEqual("success", result["status"])
        self.assertEqual([], self.extractor.calls)
        self.assertGreater(self.store.get_status(self.room_id)["last_archive_row_id"], 0)

    def test_transient_llm_failure_does_not_advance_cursor(self):
        class TransientExtractor:
            def extract(self, room_id, room_name, messages, existing_profiles):
                raise WechatGroupProfileExtractionError(
                    "LLM provider temporarily unavailable (HTTP 503)",
                    status_code=503,
                    transient=True,
                )

        self._enable_history_from_zero()
        self._record("m1")
        self.executor.extractor = TransientExtractor()

        with self.assertRaises(WechatGroupProfileExtractionError):
            self.executor.run_once(self.room_id, trigger_source="idle")

        status = self.store.get_status(self.room_id)
        runs = self.store.list_runs(self.room_id)
        self.assertEqual(0, status["last_archive_row_id"])
        self.assertFalse(status["running"])
        self.assertEqual("failed", runs[0]["status"])
        self.assertEqual([], self.merger.calls)


if __name__ == "__main__":
    unittest.main()
