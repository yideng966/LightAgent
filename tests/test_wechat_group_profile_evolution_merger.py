import os
import tempfile
import unittest

from channel.wechat_group.wechat_group_identity_service import WechatGroupIdentityService
from channel.wechat_group.wechat_group_identity_store import WechatGroupIdentityStore
from channel.wechat_group.wechat_group_profile_evolution_merger import (
    WechatGroupProfileEvolutionMerger,
)
from channel.wechat_group.wechat_group_profile_evolution_store import (
    WechatGroupProfileEvolutionStore,
)
from channel.wechat_group.wechat_group_profile_service import WechatGroupProfileService
from channel.wechat_group.wechat_group_profile_store import WechatGroupProfileStore


class WechatGroupProfileEvolutionMergerTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.profile_store = WechatGroupProfileStore(os.path.join(self._tmp.name, "profiles.db"))
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
            "bob-runtime",
            "Bob",
            "Bob",
            {"wechat_id": "bob-wechat"},
        )
        self.identity.confirm_member_binding(
            self.room_id,
            member.stable_id,
            "bob-runtime",
            actor="test",
            reason="member",
        )
        self.member_id = member.stable_id
        self.profile_service = WechatGroupProfileService(
            self.profile_store,
            identity_service=self.identity,
        )
        self.evolution_store = WechatGroupProfileEvolutionStore(profile_store=self.profile_store)
        self.merger = WechatGroupProfileEvolutionMerger(
            profile_service=self.profile_service,
            min_confidence=0.72,
            alias_min_confidence=0.85,
        )

    def tearDown(self):
        self._tmp.cleanup()

    def _merge(self, payload, evidence=None, member_by_token=None):
        run_id = self.evolution_store.create_run(self.room_id, "manual", 0)
        result = self.merger.merge(
            room_id=self.room_id,
            run_id=run_id,
            payload=payload,
            member_by_token=member_by_token or {"member_001": self.member_id},
            evidence_by_token=evidence or {"member_001": ["m1", "m2"]},
        )
        return run_id, result

    def test_merger_applies_only_evidenced_allowlisted_claims_atomically(self):
        run_id, result = self._merge({
            "profiles": [{
                "member_token": "member_001",
                "aliases": [{"value": "Bob Lead", "confidence": 0.93, "evidence_message_ids": ["m1"]}],
                "interests": [{"value": "release planning", "confidence": 0.81, "evidence_message_ids": ["m2"]}],
                "role_hints": [{"value": "release owner", "confidence": 0.88, "evidence_message_ids": ["m2"]}],
                "common_terms": [{"value": "rollback", "confidence": 0.8, "evidence_message_ids": ["m1"]}],
                "speak_style": {"value": "concise", "confidence": 0.9, "evidence_message_ids": ["m1"]},
            }],
        })

        profile = self.profile_service.get_profile(self.member_id, self.room_id)
        revisions = self.evolution_store.list_diffs(self.room_id, sender_id=self.member_id)

        self.assertEqual(1, result["profile_update_count"])
        self.assertEqual(1, result["alias_update_count"])
        self.assertEqual(["release planning"], profile["interests"])
        self.assertEqual(["release owner"], profile["role_hints"])
        self.assertEqual(["rollback"], profile["common_words"])
        self.assertEqual("concise", profile["speak_style"])
        self.assertEqual(run_id, revisions[0]["run_id"])
        self.assertEqual(["m1", "m2"], revisions[0]["evidence_message_ids"])

    def test_merger_rejects_unknown_tokens_runtime_ids_and_cross_member_evidence(self):
        _, result = self._merge({
            "profiles": [
                {
                    "member_token": "member_999",
                    "aliases": [{"value": "Unknown", "confidence": 0.99, "evidence_message_ids": ["m1"]}],
                },
                {
                    "member_token": "member_001",
                    "sender_id": "bob-runtime",
                    "aliases": [{"value": "Runtime", "confidence": 0.99, "evidence_message_ids": ["m1"]}],
                },
                {
                    "member_token": "member_001",
                    "interests": [{"value": "secret", "confidence": 0.99, "evidence_message_ids": ["other-member-message"]}],
                },
            ],
        })

        self.assertEqual(3, result["rejected_profile_count"])
        self.assertIsNone(self.profile_service.get_profile(self.member_id, self.room_id))

    def test_merger_rejects_ambiguous_low_confidence_and_unevidenced_claims(self):
        _, result = self._merge({
            "profiles": [{
                "member_token": "member_001",
                "aliases": [
                    {"value": "all", "confidence": 0.99, "evidence_message_ids": ["m1"]},
                    {"value": "Maybe Bob", "confidence": 0.5, "evidence_message_ids": ["m1"]},
                ],
                "common_terms": ["bare-string"],
            }],
        })

        self.assertEqual(0, result["profile_update_count"])
        self.assertEqual(3, result["rejected_claim_count"])


if __name__ == "__main__":
    unittest.main()
