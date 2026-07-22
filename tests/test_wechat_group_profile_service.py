import os
import tempfile
import unittest

from channel.wechat_group.wechat_group_archive import WechatGroupArchive
from channel.wechat_group.wechat_group_identity_service import WechatGroupIdentityService
from channel.wechat_group.wechat_group_identity_store import WechatGroupIdentityStore
from channel.wechat_group.wechat_group_profile_service import WechatGroupProfileService
from channel.wechat_group.wechat_group_profile_store import WechatGroupProfileStore


class WechatGroupProfileServiceTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store = WechatGroupProfileStore(os.path.join(self._tmp.name, "profiles.db"))
        self.archive = WechatGroupArchive(os.path.join(self._tmp.name, "archive.db"))
        self.identity = WechatGroupIdentityService(
            WechatGroupIdentityStore(os.path.join(self._tmp.name, "identity.db"))
        )
        account = self.identity.resolve_account("self_a", "LightBot", "profile-a", {})
        self.identity.confirm_account_binding(account.stable_id, "self_a", actor="test", reason="account")
        self.room_a = self._create_room(account.stable_id, "room@@a", "Group A")
        self.room_b = self._create_room(account.stable_id, "room@@b", "Group B")
        self.alice_a = self._create_member(self.room_a, "alice-a", "Alice A", "alice-wechat")
        self.alice_b = self._create_member(self.room_b, "alice-b", "Alice B", "alice-wechat")
        self.bob_a = self._create_member(self.room_a, "bob-a", "Bob", "bob-wechat")
        self.bot_a = self._create_member(self.room_a, "bot-a", "LightBot", "bot-wechat")
        self.service = WechatGroupProfileService(
            self.store,
            self.archive,
            identity_service=self.identity,
        )

    def tearDown(self):
        self._tmp.cleanup()

    def _create_room(self, account_id, runtime_room_id, room_name):
        room = self.identity.resolve_room(account_id, runtime_room_id, room_name, "self_a", {})
        self.identity.confirm_room_binding(room.stable_id, runtime_room_id, actor="test", reason="room")
        return room.stable_id

    def _create_member(self, room_id, runtime_sender_id, display_name, wechat_id=""):
        member = self.identity.resolve_member(
            room_id,
            runtime_sender_id,
            display_name,
            display_name,
            {"wechat_id": wechat_id},
        )
        self.identity.confirm_member_binding(
            room_id,
            member.stable_id,
            runtime_sender_id,
            actor="test",
            reason="member",
        )
        return member.stable_id

    def _manual_profile(self, room_id, member_id, nickname, **fields):
        return self.service.upsert_manual_profile(
            sender_id=member_id,
            primary_nickname=nickname,
            speak_style=fields.get("speak_style", "direct"),
            interests=fields.get("interests", []),
            common_words=fields.get("common_words", []),
            aliases=fields.get("aliases", []),
            room_id=room_id,
            room_name="",
        )

    def test_same_person_can_have_different_profiles_in_different_rooms(self):
        self._manual_profile(
            self.room_a,
            self.alice_a,
            "Alice A",
            speak_style="短句",
            interests=["Python"],
            aliases=["阿狸"],
        )
        self._manual_profile(
            self.room_b,
            self.alice_b,
            "Alice B",
            speak_style="说明式",
            interests=["设计"],
            aliases=["Alice姐"],
        )

        room_a_profile = self.service.get_profile(self.alice_a, room_id=self.room_a)
        room_b_profile = self.service.get_profile(self.alice_b, room_id=self.room_b)

        self.assertEqual(["Python"], room_a_profile["interests"])
        self.assertEqual(["设计"], room_b_profile["interests"])
        self.assertNotIn("Alice姐", room_a_profile["content"])
        self.assertEqual([], self.service.list_profiles(room_id=self.room_a, query="Alice姐"))

    def test_runtime_and_stable_ids_update_one_profile(self):
        self._manual_profile(self.room_a, self.alice_a, "Alice")

        profile = self.service.merge_learned_profile(
            sender_id="alice-a",
            primary_nickname="Alice",
            aliases=["阿狸"],
            speak_style="短句，偏直接",
            interests=["Python"],
            common_words=["收到"],
            msg_delta=6,
            activity_delta=6,
            intimacy_delta=1,
            room_id=self.room_a,
            room_name="Group A",
            last_seen_at=100,
        )

        self.assertEqual(self.alice_a, profile["stable_member_id"])
        self.assertEqual(1, self.service.count_profiles(self.room_a))
        self.assertEqual(profile["stable_member_id"], self.service.get_profile("alice-a", self.room_a)["stable_member_id"])

    def test_unanchored_identity_is_not_auto_created_but_manual_profile_is_allowed(self):
        isolated = self.identity.resolve_member(
            self.room_a,
            "isolated-runtime",
            "No Strong ID",
            "No Strong ID",
            {},
        )

        learned = self.service.merge_learned_profile(
            sender_id=isolated.stable_id,
            primary_nickname="No Strong ID",
            aliases=[],
            speak_style="direct",
            interests=[],
            common_words=[],
            msg_delta=10,
            activity_delta=10,
            intimacy_delta=0,
            room_id=self.room_a,
            room_name="Group A",
            last_seen_at=100,
        )

        self.assertEqual({}, learned)
        manual = self._manual_profile(self.room_a, isolated.stable_id, "人工确认昵称")
        self.assertEqual(isolated.stable_id, manual["stable_member_id"])
        self.assertEqual(1, self.service.count_profiles(self.room_a))

    def test_manual_primary_name_wins_over_live_archive_name(self):
        self._manual_profile(self.room_a, self.alice_a, "人工昵称", aliases=["别名"])
        self.archive.record_message(
            message_id="m1",
            room_id="room@@a",
            stable_room_id=self.room_a,
            runtime_room_id="room@@a",
            sender_id="alice-a",
            stable_member_id=self.alice_a,
            runtime_sender_id="alice-a",
            sender_nickname="实时群昵称",
            text="hello",
            created_at=100,
        )

        profile = self.service.get_profile(self.alice_a, self.room_a)

        self.assertEqual("人工昵称", profile["primary_nickname"])
        self.assertIn("reply_name: 人工昵称", profile["content"])

    def test_manual_save_replaces_removed_manual_aliases(self):
        self._manual_profile(self.room_a, self.alice_a, "Alice", aliases=["旧别名", "保留别名"])

        profile = self._manual_profile(self.room_a, self.alice_a, "Alice", aliases=["保留别名"])

        self.assertEqual(["保留别名"], profile["aliases"])
        self.assertNotIn("旧别名", profile["content"])

    def test_runtime_mentions_resolve_to_current_room_canonical_profiles(self):
        self._manual_profile(self.room_a, self.alice_a, "Alice")
        self._manual_profile(self.room_a, self.bob_a, "Bob")
        self._manual_profile(self.room_a, self.bot_a, "LightBot")

        result = self.service.resolve_profiles_for_prompt(
            room_id=self.room_a,
            sender_id="alice-a",
            mentioned_sender_ids=["bot-a", "alice-a", "bob-a", "bob-a"],
            query="提醒 Bob",
            bot_sender_id="bot-a",
        )

        self.assertEqual(self.alice_a, result["speaker_profile"]["stable_member_id"])
        self.assertEqual([self.bob_a], [item["stable_member_id"] for item in result["mentioned_profiles"]])

    def test_transport_metadata_common_words_are_omitted_from_prompt(self):
        self._manual_profile(
            self.room_a,
            self.alice_a,
            "Alice",
            common_words=["收到", "aeskey", "cdnthumburl"],
        )

        profile = self.service.get_profile(self.alice_a, self.room_a)

        self.assertNotIn("common_words:", profile["content"])
        self.assertNotIn("aeskey", profile["content"])

    def test_member_redirect_merges_existing_profiles_and_runtime_aliases(self):
        duplicate = self._create_member(self.room_a, "alice-new-runtime", "Alice New", "alice-new-wechat")
        self._manual_profile(self.room_a, self.alice_a, "Alice", interests=["Python"])
        self._manual_profile(self.room_a, duplicate, "Alice New", interests=["架构"])

        profile = self.service.confirm_member_redirect(
            self.room_a,
            duplicate,
            self.alice_a,
            actor="test",
            reason="same member confirmed",
        )

        self.assertEqual(self.alice_a, profile["stable_member_id"])
        self.assertEqual(["Python", "架构"], profile["interests"])
        self.assertEqual(self.alice_a, self.service.resolve_canonical_member_id(self.room_a, "alice-new-runtime"))
        self.assertEqual(1, self.service.count_profiles(self.room_a))

    def test_profile_operations_require_stable_room_scope(self):
        self.assertEqual([], self.service.list_profiles())
        self.assertIsNone(self.service.get_profile(self.alice_a))
        with self.assertRaisesRegex(ValueError, "stable_room_id"):
            self._manual_profile("", self.alice_a, "Alice")


if __name__ == "__main__":
    unittest.main()
