import os
import tempfile
import unittest

from channel.wechat_group.wechat_group_archive import WechatGroupArchive
from channel.wechat_group.wechat_group_identity_service import WechatGroupIdentityService
from channel.wechat_group.wechat_group_identity_store import WechatGroupIdentityStore
from channel.wechat_group.wechat_group_knowledge_service import WechatGroupKnowledgeService
from channel.wechat_group.wechat_group_knowledge_store import WechatGroupKnowledgeStore
from channel.wechat_group.wechat_group_learner import WechatGroupLearner
from channel.wechat_group.wechat_group_profile_service import WechatGroupProfileService
from channel.wechat_group.wechat_group_profile_store import WechatGroupProfileStore


LONG_WECHAT_IMAGE_TRANSPORT_XML = """<?xml version="1.0"?>
<msg><img aeskey="{}" cdnthumburl="masked" hevc_mid_size="31347" /></msg>
""".format("a" * 240)


class WechatGroupLearnerTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.archive = WechatGroupArchive(os.path.join(self._tmp.name, "archive.db"))
        self.profile_store = WechatGroupProfileStore(os.path.join(self._tmp.name, "profiles.db"))
        self.knowledge_store = WechatGroupKnowledgeStore(os.path.join(self._tmp.name, "knowledge.db"))
        self.identity = WechatGroupIdentityService(
            WechatGroupIdentityStore(os.path.join(self._tmp.name, "identity.db"))
        )
        account = self.identity.resolve_account("self-a", "Bot", "profile-a", {})
        self.identity.confirm_account_binding(account.stable_id, "self-a", actor="test", reason="account")
        room = self.identity.resolve_room(account.stable_id, "room@@a", "Group A", "self-a", {})
        self.identity.confirm_room_binding(room.stable_id, "room@@a", actor="test", reason="room")
        self.room_id = room.stable_id
        self.alice_id = self._create_member("alice-runtime", "Alice", "alice-wechat")
        self.bob_id = self._create_member("bob-runtime", "Bob", "bob-wechat")
        self.profile_service = WechatGroupProfileService(
            self.profile_store,
            archive=self.archive,
            identity_service=self.identity,
        )
        self.knowledge_service = WechatGroupKnowledgeService(self.knowledge_store)
        self.learner = WechatGroupLearner(
            archive=self.archive,
            profile_service=self.profile_service,
            knowledge_service=self.knowledge_service,
            knowledge_store=self.knowledge_store,
            config_getter=lambda key, default=None: {
                "wechat_group_learning_batch_message_limit": 50,
                "wechat_group_learning_profile_min_messages": 1,
                "wechat_group_learning_profile_sample_limit": 10,
                "wechat_group_learning_group_memory_min_messages": 2,
            }.get(key, default),
        )

    def tearDown(self):
        self._tmp.cleanup()

    def _create_member(self, runtime_sender_id, name, wechat_id):
        member = self.identity.resolve_member(
            self.room_id,
            runtime_sender_id,
            name,
            name,
            {"wechat_id": wechat_id},
        )
        self.identity.confirm_member_binding(
            self.room_id,
            member.stable_id,
            runtime_sender_id,
            actor="test",
            reason="member",
        )
        return member.stable_id

    def _record(
        self,
        message_id,
        runtime_sender_id,
        stable_member_id,
        nickname,
        text,
        created_at,
        metadata=None,
        message_type="text",
    ):
        self.archive.record_message(
            message_id=message_id,
            room_id="room@@a",
            room_name="Group A",
            sender_id=runtime_sender_id,
            sender_nickname=nickname,
            message_type=message_type,
            text=text,
            metadata=metadata,
            created_at=created_at,
            stable_room_id=self.room_id,
            runtime_room_id="room@@a",
            stable_member_id=stable_member_id,
            runtime_sender_id=runtime_sender_id,
        )

    def _enable_profile_history_from_zero(self):
        self.profile_store.update_learning_state(
            self.room_id,
            pipeline="heuristic",
            last_archive_row_id=0,
            latest_observed_row_id=0,
        )

    def test_profile_and_group_memory_use_independent_cursors(self):
        self._enable_profile_history_from_zero()
        self._record("m1", "alice-runtime", self.alice_id, "Alice", "本群周六统一发版", 100)
        self._record("m2", "bob-runtime", self.bob_id, "Bob", "确认，本群周六统一发版", 101)

        profile_result = self.learner.run_once(self.room_id, mode="profile")
        knowledge_cursor_before = self.knowledge_store.get_cursor(self.room_id)["last_archive_row_id"]
        memory_result = self.learner.run_once(self.room_id, mode="memory")

        self.assertEqual(2, profile_result["profile_batch_message_count"])
        self.assertGreater(self.profile_store.get_learning_state(self.room_id, "heuristic")["last_archive_row_id"], 0)
        self.assertEqual(0, knowledge_cursor_before)
        self.assertEqual(2, memory_result["memory_batch_message_count"])
        self.assertEqual(1, memory_result["group_memory_upsert_count"])

    def test_first_profile_run_uses_archive_high_water_without_replay(self):
        self._record("old", "alice-runtime", self.alice_id, "Alice", "old profile text", 100)

        result = self.learner.run_once(self.room_id, mode="profile")

        self.assertEqual(0, result["profile_batch_message_count"])
        self.assertIsNone(self.profile_service.get_profile(self.alice_id, self.room_id))
        self.assertEqual(
            self.archive.get_max_row_id(self.room_id),
            self.profile_store.get_learning_state(self.room_id, "heuristic")["last_archive_row_id"],
        )

    def test_learner_writes_one_canonical_profile_after_runtime_change(self):
        rebound = self.identity.resolve_member(
            self.room_id,
            "alice-new-runtime",
            "Alice",
            "Alice",
            {"wechat_id": "alice-wechat"},
        )
        self._enable_profile_history_from_zero()
        self._record("m1", "alice-runtime", self.alice_id, "Alice", "release checklist", 100)
        self._record("m2", "alice-new-runtime", rebound.stable_id, "Alice", "release notes", 101)

        result = self.learner.run_once(self.room_id, mode="profile")

        self.assertEqual(1, result["profile_update_count"])
        self.assertEqual(1, self.profile_service.count_profiles(self.room_id))
        self.assertEqual(self.alice_id, self.profile_service.get_profile("alice-new-runtime", self.room_id)["stable_member_id"])

    def test_learner_does_not_create_profile_for_unanchored_identity(self):
        isolated = self.identity.resolve_member(
            self.room_id,
            "isolated-runtime",
            "Unknown",
            "Unknown",
            {},
        )
        self._enable_profile_history_from_zero()
        self._record("m1", "isolated-runtime", isolated.stable_id, "Unknown", "hello", 100)

        result = self.learner.run_once(self.room_id, mode="profile")

        self.assertEqual(0, result["profile_update_count"])
        self.assertIsNone(self.profile_service.get_profile(isolated.stable_id, self.room_id))

    def test_learner_ignores_legacy_image_transport_xml(self):
        self._enable_profile_history_from_zero()
        self._record(
            "image",
            "alice-runtime",
            self.alice_id,
            "Alice",
            LONG_WECHAT_IMAGE_TRANSPORT_XML,
            100,
        )

        result = self.learner.run_once(self.room_id, mode="profile")

        self.assertEqual(0, result["profile_update_count"])

    def test_learner_filters_transport_noise_from_common_words(self):
        noise_id = self._create_member("noise-runtime", "Noise", "noise-wechat")
        noisy_text = (
            "<msg biztype='1' size='123'><emoji duration='2' /></msg> "
            "今天继续聊 NAS、API 和 Docker 部署，NAS 方案继续确认，API 接口继续确认。 "
            "&amp;nbsp; fffcab"
        )
        self._enable_profile_history_from_zero()
        self._record("noise", "noise-runtime", noise_id, "Noise", noisy_text, 100)

        self.learner.run_once(self.room_id, mode="profile")
        profile = self.profile_service.get_profile(noise_id, self.room_id)

        self.assertTrue(set(profile["common_words"]).issubset({"nas", "api", "docker", "接口"}))
        self.assertNotIn("biztype", profile["common_words"])

    def test_learner_resolves_runtime_mention_before_alias_write(self):
        self._enable_profile_history_from_zero()
        self._record(
            "mention",
            "alice-runtime",
            self.alice_id,
            "Alice",
            "@LightBot\u2005请@张总\u2005看下发布安排",
            100,
            metadata={
                "at_list": ["bot-runtime", "bob-runtime"],
                "self_id": "bot-runtime",
                "self_display_name": "LightBot",
            },
        )

        result = self.learner.run_once(self.room_id, mode="profile")
        bob = self.profile_service.get_profile(self.bob_id, self.room_id)

        self.assertEqual(2, result["profile_update_count"])
        self.assertIn("张总", [bob.get("primary_nickname")] + list(bob.get("aliases") or []))


if __name__ == "__main__":
    unittest.main()
