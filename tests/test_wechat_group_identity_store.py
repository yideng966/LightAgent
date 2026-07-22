import os
import tempfile
import unittest

from channel.wechat_group.wechat_group_identity_store import WechatGroupIdentityStore


class WechatGroupIdentityStoreTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self._tmp.name, "identity.db")
        self.store = WechatGroupIdentityStore(self.db_path)

    def tearDown(self):
        self._tmp.cleanup()

    def test_room_alias_activation_keeps_one_active_runtime(self):
        self.store.upsert_account("wga_account", display_name="Bot", status="confirmed", confidence="manual")
        self.store.upsert_room("wgr_room", "wga_account", canonical_name="测试群", status="confirmed", confidence="manual")

        self.store.activate_room_alias("wga_account", "wgr_room", "room@@old", room_name="测试群", actor="test")
        self.store.activate_room_alias("wga_account", "wgr_room", "room@@new", room_name="测试群", actor="test")

        self.assertEqual("room@@new", self.store.get_active_runtime_room_id("wga_account", "wgr_room"))
        aliases = self.store.list_room_aliases("wga_account", "wgr_room", include_inactive=True)
        self.assertEqual(
            {"room@@old": 0, "room@@new": 1},
            {item["runtime_room_id"]: item["is_active"] for item in aliases},
        )
        events = self.store.list_binding_events(entity_type="room")
        self.assertEqual("activate_room_alias", events[-1]["action"])
        self.assertEqual("room@@old", events[-1]["old_runtime_id"])
        self.assertEqual("room@@new", events[-1]["new_runtime_id"])

    def test_member_alias_activation_is_scoped_by_account_and_room(self):
        for account_id, room_id, member_id in (
            ("wga_a", "wgr_a", "wgm_a"),
            ("wga_b", "wgr_b", "wgm_b"),
        ):
            self.store.upsert_account(account_id, display_name=account_id, status="confirmed", confidence="manual")
            self.store.upsert_room(room_id, account_id, canonical_name="同名群", status="confirmed", confidence="manual")
            self.store.upsert_member(member_id, room_id, account_id, display_name="Alice", status="confirmed", confidence="manual")

        self.store.activate_member_alias("wga_a", "wgr_a", "wgm_a", "wxid_same", runtime_room_id="room@@a")
        self.store.activate_member_alias("wga_b", "wgr_b", "wgm_b", "wxid_same", runtime_room_id="room@@b")

        self.assertEqual("wxid_same", self.store.get_active_runtime_sender_id("wga_a", "wgr_a", "wgm_a"))
        self.assertEqual("wxid_same", self.store.get_active_runtime_sender_id("wga_b", "wgr_b", "wgm_b"))

    def test_member_alias_activation_deactivates_previous_runtime(self):
        self.store.upsert_account("wga_account", display_name="Bot", status="confirmed", confidence="manual")
        self.store.upsert_room("wgr_room", "wga_account", canonical_name="测试群", status="confirmed", confidence="manual")
        self.store.upsert_member("wgm_alice", "wgr_room", "wga_account", display_name="Alice", status="confirmed", confidence="manual")

        self.store.activate_member_alias("wga_account", "wgr_room", "wgm_alice", "wxid_old", runtime_room_id="room@@old")
        self.store.activate_member_alias("wga_account", "wgr_room", "wgm_alice", "wxid_new", runtime_room_id="room@@new")

        self.assertEqual("wxid_new", self.store.get_active_runtime_sender_id("wga_account", "wgr_room", "wgm_alice"))
        aliases = self.store.list_member_aliases("wga_account", "wgr_room", "wgm_alice", include_inactive=True)
        self.assertEqual(
            {"wxid_old": 0, "wxid_new": 1},
            {item["runtime_sender_id"]: item["is_active"] for item in aliases},
        )

    def test_find_alias_by_runtime_supports_legacy_web_api_conversion(self):
        self.store.upsert_account("wga_account", display_name="Bot", status="confirmed", confidence="manual")
        self.store.upsert_room("wgr_room", "wga_account", canonical_name="测试群", status="confirmed", confidence="manual")
        self.store.upsert_member("wgm_alice", "wgr_room", "wga_account", display_name="Alice", status="confirmed", confidence="manual")
        self.store.activate_room_alias("wga_account", "wgr_room", "room@@runtime", room_name="测试群")
        self.store.activate_member_alias(
            "wga_account",
            "wgr_room",
            "wgm_alice",
            "wxid_runtime",
            runtime_room_id="room@@runtime",
        )

        room_alias = self.store.find_room_alias_by_runtime("room@@runtime")
        member_alias = self.store.find_member_alias_by_runtime("room@@runtime", "wxid_runtime")

        self.assertEqual("wgr_room", room_alias["stable_room_id"])
        self.assertEqual("wgm_alice", member_alias["stable_member_id"])


if __name__ == "__main__":
    unittest.main()
