import os
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor

from channel.wechat_group.wechat_group_identity_service import WechatGroupIdentityService
from channel.wechat_group.wechat_group_identity_store import WechatGroupIdentityStore


class WechatGroupIdentityServiceTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store = WechatGroupIdentityStore(os.path.join(self._tmp.name, "identity.db"))
        self.service = WechatGroupIdentityService(store=self.store)

    def tearDown(self):
        self._tmp.cleanup()

    def test_account_profile_is_rebound_automatically_after_runtime_id_changes(self):
        first = self.service.resolve_account("self_old", "LightBot", "profile-a", {})
        self.service.confirm_account_binding(first.stable_id, "self_old", actor="test", reason="initial")

        rebound = self.service.resolve_account("self_new", "LightBot", "profile-a", {})

        self.assertEqual(first.stable_id, rebound.stable_id)
        self.assertEqual("confirmed", rebound.status)
        self.assertFalse(rebound.requires_confirmation)

    def test_concurrent_account_profile_resolution_reuses_one_stable_account(self):
        class RacingStore(WechatGroupIdentityStore):
            def __init__(self, db_path):
                super().__init__(db_path)
                self._profile_read_count = 0
                self._profile_read_lock = threading.Lock()
                self._release_first_read = threading.Event()

            def list_account_candidates_by_profile(self, sidecar_memory_path, self_name=""):
                rows = super().list_account_candidates_by_profile(sidecar_memory_path, self_name)
                with self._profile_read_lock:
                    self._profile_read_count += 1
                    read_number = self._profile_read_count
                if read_number == 1:
                    self._release_first_read.wait(timeout=0.2)
                else:
                    self._release_first_read.set()
                return rows

        store = RacingStore(os.path.join(self._tmp.name, "concurrent_identity.db"))
        services = [WechatGroupIdentityService(store), WechatGroupIdentityService(store)]
        with ThreadPoolExecutor(max_workers=2) as executor:
            resolutions = list(executor.map(
                lambda service: service.resolve_account("self_a", "LightBot", "profile-a", {}),
                services,
            ))

        self.assertEqual(1, len({resolution.stable_id for resolution in resolutions}))
        self.assertEqual(1, len(store.list_account_candidates_by_profile("profile-a", "LightBot")))

    def test_same_account_exact_room_name_is_rebound_automatically(self):
        account = self.service.resolve_account("self_old", "LightBot", "profile-a", {})
        self.service.confirm_account_binding(account.stable_id, "self_old", actor="test", reason="initial")
        first = self.service.resolve_room(account.stable_id, "room@@old", "Trusted Room", "self_old", {})
        self.service.confirm_room_binding(first.stable_id, "room@@old", actor="test", reason="initial")

        rebound = self.service.resolve_room(account.stable_id, "room@@new", "Trusted Room", "self_new", {})

        self.assertEqual(first.stable_id, rebound.stable_id)
        self.assertEqual("confirmed", rebound.status)
        self.assertFalse(rebound.requires_confirmation)
        self.assertEqual("room@@new", self.service.get_active_runtime_room_id(first.stable_id))

    def test_exact_room_name_recovers_when_self_runtime_id_is_unchanged(self):
        account = self.service.resolve_account("self_a", "LightBot", "profile-a", {})
        first = self.service.resolve_room(
            account.stable_id,
            "room@@first",
            "Same Room",
            "self_a",
            {},
        )

        second = self.service.resolve_room(
            account.stable_id,
            "room@@second",
            "Same Room",
            "self_a",
            {},
        )

        self.assertEqual(first.stable_id, second.stable_id)
        self.assertEqual("room_name", second.confidence)

    def test_suspected_room_alias_does_not_bypass_ambiguous_name_isolation(self):
        account = self.service.resolve_account("self_a", "LightBot", "profile-a", {})
        first = self.service.resolve_room(account.stable_id, "room@@first", "Same Room", "self_a", {})
        self.store.upsert_room(
            "wgr_second",
            account.stable_id,
            canonical_name="Same Room",
            status="confirmed",
            confidence="manual",
            confirmed_at=1,
        )
        self.store.record_room_alias_candidate(
            account.stable_id,
            first.stable_id,
            "room@@new",
            room_name="Same Room",
            source_kind="suspected",
        )

        resolved = self.service.resolve_room(
            account.stable_id,
            "room@@new",
            "Same Room",
            "self_a",
            {},
        )

        self.assertNotIn(resolved.stable_id, {first.stable_id, "wgr_second"})
        self.assertEqual("auto_isolated", resolved.confidence)
        self.assertEqual("ambiguous_room_name", resolved.metadata.get("isolation_reason"))

    def test_member_wechat_id_is_rebound_automatically_after_runtime_id_changes(self):
        account = self.service.resolve_account("self_a", "LightBot", "profile-a", {})
        self.service.confirm_account_binding(account.stable_id, "self_a", actor="test", reason="account")
        room = self.service.resolve_room(account.stable_id, "room@@a", "Room A", "self_a", {})
        self.service.confirm_room_binding(room.stable_id, "room@@a", actor="test", reason="room")
        first = self.service.resolve_member(
            room.stable_id,
            "sender-old",
            "Alice",
            "Alice",
            {"wechat_id": "alice_wechat"},
        )
        self.service.confirm_member_binding(room.stable_id, first.stable_id, "sender-old", actor="test", reason="member")

        rebound = self.service.resolve_member(
            room.stable_id,
            "sender-new",
            "Alice Changed",
            "Alice Changed",
            {"wechat_id": "alice_wechat"},
        )

        self.assertEqual(first.stable_id, rebound.stable_id)
        self.assertEqual("confirmed", rebound.status)
        self.assertFalse(rebound.requires_confirmation)
        self.assertEqual("sender-new", self.service.get_active_runtime_sender_id(room.stable_id, first.stable_id))

    def test_ambiguous_wechat_id_does_not_reuse_active_member_alias(self):
        account = self.service.resolve_account("self_a", "LightBot", "profile-a", {})
        room = self.service.resolve_room(account.stable_id, "room@@a", "Room A", "self_a", {})
        first = self.service.resolve_member(
            room.stable_id,
            "sender-current",
            "Alice",
            "Alice",
            {"wechat_id": "alice_wechat"},
        )
        self.store.upsert_member(
            "wgm_duplicate",
            room.stable_id,
            account.stable_id,
            display_name="Alice Duplicate",
            status="confirmed",
            confidence="manual",
            metadata={"wechat_id": "alice_wechat"},
            confirmed_at=1,
        )
        self.store.activate_member_alias(
            account.stable_id,
            room.stable_id,
            "wgm_duplicate",
            "sender-duplicate",
            runtime_room_id="room@@a",
            metadata={"wechat_id": "alice_wechat"},
        )

        resolved = self.service.resolve_member(
            room.stable_id,
            "sender-current",
            "Alice",
            "Alice",
            {"wechat_id": "alice_wechat"},
        )

        self.assertNotIn(resolved.stable_id, {first.stable_id, "wgm_duplicate"})
        self.assertEqual("auto_isolated", resolved.confidence)
        self.assertEqual("ambiguous_wechat_id", resolved.metadata.get("isolation_reason"))

        repeated = self.service.resolve_member(
            room.stable_id,
            "sender-current",
            "Alice",
            "Alice",
            {"wechat_id": "alice_wechat"},
        )

        self.assertEqual(resolved.stable_id, repeated.stable_id)
        self.assertEqual("auto_isolated", repeated.confidence)

    def test_same_name_member_without_wechat_id_gets_isolated_identity(self):
        account = self.service.resolve_account("self_a", "LightBot", "profile-a", {})
        self.service.confirm_account_binding(account.stable_id, "self_a", actor="test", reason="account")
        room = self.service.resolve_room(account.stable_id, "room@@a", "Room A", "self_a", {})
        self.service.confirm_room_binding(room.stable_id, "room@@a", actor="test", reason="room")
        first = self.service.resolve_member(room.stable_id, "sender-old", "Alice", "Alice", {})
        self.service.confirm_member_binding(room.stable_id, first.stable_id, "sender-old", actor="test", reason="member")

        isolated = self.service.resolve_member(room.stable_id, "sender-new", "Alice", "Alice", {})

        self.assertNotEqual(first.stable_id, isolated.stable_id)
        self.assertEqual("confirmed", isolated.status)
        self.assertFalse(isolated.requires_confirmation)

    def test_confirmed_room_binding_moves_active_runtime_to_new_login(self):
        account = self.service.resolve_account("self_old", "Bot", "profile-a", {})
        room = self.service.resolve_room(account.stable_id, "room@@old", "测试群", "self_old", {})
        self.service.confirm_account_binding(account.stable_id, "self_old", actor="test", reason="initial login")
        self.service.confirm_room_binding(room.stable_id, "room@@old", actor="test", reason="initial room")

        candidate = self.service.resolve_room(account.stable_id, "room@@new", "测试群", "self_new", {})

        self.assertEqual(room.stable_id, candidate.stable_id)
        self.assertFalse(candidate.requires_confirmation)
        self.assertEqual("confirmed", candidate.status)
        self.assertEqual("room@@new", self.service.get_active_runtime_room_id(room.stable_id))

    def test_same_named_rooms_in_different_accounts_do_not_share_stable_room(self):
        account_a = self.service.resolve_account("self_a", "Bot A", "profile-a", {})
        account_b = self.service.resolve_account("self_b", "Bot B", "profile-b", {})
        self.service.confirm_account_binding(account_a.stable_id, "self_a", actor="test", reason="account a")
        self.service.confirm_account_binding(account_b.stable_id, "self_b", actor="test", reason="account b")

        room_a = self.service.resolve_room(account_a.stable_id, "room@@a", "同名群", "self_a", {})
        self.service.confirm_room_binding(room_a.stable_id, "room@@a", actor="test", reason="room a")
        room_b = self.service.resolve_room(account_b.stable_id, "room@@b", "同名群", "self_b", {})

        self.assertNotEqual(room_a.stable_id, room_b.stable_id)
        self.assertFalse(room_b.requires_confirmation)
        self.assertEqual("confirmed", room_b.status)

    def test_same_name_member_without_strong_id_does_not_inherit_old_identity(self):
        account = self.service.resolve_account("self_a", "Bot", "profile-a", {})
        self.service.confirm_account_binding(account.stable_id, "self_a", actor="test", reason="account")
        room = self.service.resolve_room(account.stable_id, "room@@a", "测试群", "self_a", {})
        self.service.confirm_room_binding(room.stable_id, "room@@a", actor="test", reason="room")
        member = self.service.resolve_member(room.stable_id, "wxid_old", "Alice", "阿狸", {})
        self.service.confirm_member_binding(room.stable_id, member.stable_id, "wxid_old", actor="test", reason="admin")

        candidate = self.service.resolve_member(room.stable_id, "wxid_new", "Alice", "阿狸", {})

        self.assertNotEqual(member.stable_id, candidate.stable_id)
        self.assertFalse(candidate.requires_confirmation)
        self.assertEqual("confirmed", candidate.status)
        self.assertEqual("wxid_new", self.service.get_active_runtime_sender_id(room.stable_id, candidate.stable_id))

    def test_resolve_legacy_runtime_ids_for_web_api(self):
        account = self.service.resolve_account("self_a", "Bot", "profile-a", {})
        self.service.confirm_account_binding(account.stable_id, "self_a", actor="test", reason="account")
        room = self.service.resolve_room(account.stable_id, "room@@runtime", "测试群", "self_a", {})
        self.service.confirm_room_binding(room.stable_id, "room@@runtime", actor="test", reason="room")
        member = self.service.resolve_member(room.stable_id, "wxid_runtime", "Alice", "阿狸", {})
        self.service.confirm_member_binding(room.stable_id, member.stable_id, "wxid_runtime", actor="test", reason="member")

        self.assertEqual(room.stable_id, self.service.resolve_legacy_room_id("room@@runtime"))
        self.assertEqual(
            member.stable_id,
            self.service.resolve_legacy_member_id("room@@runtime", "wxid_runtime"),
        )
        self.assertEqual("", self.service.resolve_legacy_room_id("missing@@runtime"))

    def test_automatic_resolution_leaves_no_pending_room_or_member_candidates(self):
        account = self.service.resolve_account("self_a", "Bot", "profile-a", {})
        self.service.confirm_account_binding(account.stable_id, "self_a", actor="test", reason="account")
        confirmed_room = self.service.resolve_room(account.stable_id, "room@@old", "老群", "self_a", {})
        self.service.confirm_room_binding(confirmed_room.stable_id, "room@@old", actor="test", reason="room")
        self.service.resolve_room(account.stable_id, "room@@new", "老群", "self_new", {})
        self.service.resolve_member(confirmed_room.stable_id, "wxid_new", "Alice", "阿狸", {})

        rooms = self.service.list_binding_candidates("room")
        members = self.service.list_binding_candidates("member", {"stable_room_id": confirmed_room.stable_id})

        self.assertEqual([], rooms)
        self.assertEqual([], members)

    def test_room_resolution_requires_confirmed_account(self):
        self.store.upsert_account(
            "wga_unconfirmed",
            status="legacy_imported",
            confidence="candidate",
        )

        with self.assertRaisesRegex(ValueError, "stable account is not confirmed"):
            self.service.resolve_room(
                "wga_unconfirmed",
                "room@@a",
                "Room A",
                "self_a",
                {},
            )

    def test_room_confirmation_requires_confirmed_account(self):
        self.store.upsert_account("wga_unconfirmed", status="legacy_imported", confidence="candidate")
        self.store.upsert_room(
            "wgr_unconfirmed",
            "wga_unconfirmed",
            canonical_name="Room A",
            status="legacy_imported",
            confidence="candidate",
        )

        with self.assertRaisesRegex(ValueError, "stable account is not confirmed"):
            self.service.confirm_room_binding("wgr_unconfirmed", "room@@a", actor="test", reason="room")

    def test_member_confirmation_rejects_cross_room_member(self):
        account = self.service.resolve_account("self_a", "Bot", "profile-a", {})
        self.service.confirm_account_binding(account.stable_id, "self_a", actor="test", reason="account")
        room_a = self.service.resolve_room(account.stable_id, "room@@a", "Room A", "self_a", {})
        room_b = self.service.resolve_room(account.stable_id, "room@@b", "Room B", "self_a", {})
        self.service.confirm_room_binding(room_a.stable_id, "room@@a", actor="test", reason="room a")
        self.service.confirm_room_binding(room_b.stable_id, "room@@b", actor="test", reason="room b")
        member = self.service.resolve_member(room_a.stable_id, "wxid_a", "Alice", "", {})

        with self.assertRaisesRegex(ValueError, "stable member does not belong to stable room"):
            self.service.confirm_member_binding(
                room_b.stable_id,
                member.stable_id,
                "wxid_a",
                actor="test",
                reason="cross room",
            )

        self.assertEqual(room_a.stable_id, self.store.get_member(member.stable_id)["stable_room_id"])

    def test_confirmation_records_real_timestamp(self):
        before = int(time.time())
        account = self.service.resolve_account("self_a", "Bot", "profile-a", {})

        self.service.confirm_account_binding(account.stable_id, "self_a", actor="test", reason="account")

        self.assertGreaterEqual(int(self.store.get_account(account.stable_id)["confirmed_at"]), before)

    def test_member_confirmation_requires_confirmed_room(self):
        self.store.upsert_account("wga_account", status="confirmed", confidence="manual")
        self.store.upsert_room(
            "wgr_unconfirmed",
            "wga_account",
            canonical_name="Room A",
            status="legacy_imported",
            confidence="candidate",
        )
        self.store.upsert_member(
            "wgm_member",
            "wgr_unconfirmed",
            "wga_account",
            display_name="Alice",
            status="legacy_imported",
            confidence="candidate",
        )

        with self.assertRaisesRegex(ValueError, "stable room is not confirmed"):
            self.service.confirm_member_binding(
                "wgr_unconfirmed",
                "wgm_member",
                "wxid_a",
                actor="test",
                reason="member",
            )

    def test_member_resolution_requires_confirmed_room(self):
        self.store.upsert_account(
            "wga_account",
            status="confirmed",
            confidence="manual",
            confirmed_at=1,
        )
        self.store.upsert_room(
            "wgr_unconfirmed",
            "wga_account",
            canonical_name="Room A",
            status="legacy_imported",
            confidence="candidate",
        )

        with self.assertRaisesRegex(ValueError, "stable room is not confirmed"):
            self.service.resolve_member(
                "wgr_unconfirmed",
                "sender-a",
                "Alice",
                "Alice",
                {"wechat_id": "alice_wechat"},
            )

    def test_member_resolution_requires_confirmed_account(self):
        self.store.upsert_account(
            "wga_unconfirmed",
            status="legacy_imported",
            confidence="candidate",
        )
        self.store.upsert_room(
            "wgr_confirmed",
            "wga_unconfirmed",
            canonical_name="Room A",
            status="confirmed",
            confidence="manual",
            confirmed_at=1,
        )

        with self.assertRaisesRegex(ValueError, "stable account is not confirmed"):
            self.service.resolve_member(
                "wgr_confirmed",
                "sender-a",
                "Alice",
                "Alice",
                {"wechat_id": "alice_wechat"},
            )

    def test_legacy_runtime_resolution_rejects_cross_account_ambiguity(self):
        account_a = self.service.resolve_account("self_a", "Bot A", "profile-a", {})
        account_b = self.service.resolve_account("self_b", "Bot B", "profile-b", {})
        self.service.confirm_account_binding(account_a.stable_id, "self_a", actor="test", reason="account a")
        self.service.confirm_account_binding(account_b.stable_id, "self_b", actor="test", reason="account b")
        room_a = self.service.resolve_room(account_a.stable_id, "room@@same", "Room A", "self_a", {})
        room_b = self.service.resolve_room(account_b.stable_id, "room@@same", "Room B", "self_b", {})
        self.service.confirm_room_binding(room_a.stable_id, "room@@same", actor="test", reason="room a")
        self.service.confirm_room_binding(room_b.stable_id, "room@@same", actor="test", reason="room b")
        member_a = self.service.resolve_member(room_a.stable_id, "wxid_same", "Alice", "", {})
        member_b = self.service.resolve_member(room_b.stable_id, "wxid_same", "Alice", "", {})
        self.service.confirm_member_binding(room_a.stable_id, member_a.stable_id, "wxid_same", actor="test", reason="member a")
        self.service.confirm_member_binding(room_b.stable_id, member_b.stable_id, "wxid_same", actor="test", reason="member b")

        self.assertEqual("", self.service.resolve_legacy_room_id("room@@same"))
        self.assertEqual("", self.service.resolve_legacy_member_id("room@@same", "wxid_same"))

    def test_automatic_room_alias_remains_confirmed_on_repeated_resolution(self):
        account = self.service.resolve_account("self_a", "Bot", "profile-a", {})
        self.service.confirm_account_binding(account.stable_id, "self_a", actor="test", reason="account")
        room = self.service.resolve_room(account.stable_id, "room@@old", "Same Room", "self_a", {})
        self.service.confirm_room_binding(room.stable_id, "room@@old", actor="test", reason="room")

        first = self.service.resolve_room(account.stable_id, "room@@new", "Same Room", "self_a", {})
        repeated = self.service.resolve_room(account.stable_id, "room@@new", "Same Room", "self_a", {})

        self.assertEqual(room.stable_id, first.stable_id)
        self.assertEqual(first.stable_id, repeated.stable_id)
        self.assertFalse(first.requires_confirmation)
        self.assertFalse(repeated.requires_confirmation)
        self.assertEqual("confirmed", repeated.status)

    def test_isolated_member_alias_remains_confirmed_on_repeated_resolution(self):
        account = self.service.resolve_account("self_a", "Bot", "profile-a", {})
        self.service.confirm_account_binding(account.stable_id, "self_a", actor="test", reason="account")
        room = self.service.resolve_room(account.stable_id, "room@@a", "Room A", "self_a", {})
        self.service.confirm_room_binding(room.stable_id, "room@@a", actor="test", reason="room")
        member = self.service.resolve_member(room.stable_id, "wxid_old", "Alice", "Alice", {})
        self.service.confirm_member_binding(room.stable_id, member.stable_id, "wxid_old", actor="test", reason="member")

        first = self.service.resolve_member(room.stable_id, "wxid_new", "Alice", "Alice", {})
        repeated = self.service.resolve_member(room.stable_id, "wxid_new", "Alice", "Alice", {})

        self.assertNotEqual(member.stable_id, first.stable_id)
        self.assertEqual(first.stable_id, repeated.stable_id)
        self.assertFalse(first.requires_confirmation)
        self.assertFalse(repeated.requires_confirmation)
        self.assertEqual("confirmed", repeated.status)

    def test_confirmed_room_scope_includes_automatically_recovered_aliases(self):
        account = self.service.resolve_account("self_a", "Bot", "profile-a", {})
        self.service.confirm_account_binding(account.stable_id, "self_a", actor="test", reason="account")
        room = self.service.resolve_room(account.stable_id, "room@@old", "Room A", "self_a", {})
        self.service.confirm_room_binding(room.stable_id, "room@@old", actor="test", reason="old room")

        recovered = self.service.resolve_room(account.stable_id, "room@@recovered", "Room A", "self_a", {})

        self.assertFalse(recovered.requires_confirmation)
        self.assertEqual(
            [room.stable_id, "room@@old", "room@@recovered"],
            self.service.list_confirmed_room_scope_ids(room.stable_id),
        )

        self.service.confirm_room_binding(room.stable_id, "room@@new", actor="test", reason="new room")

        self.assertEqual(
            [room.stable_id, "room@@old", "room@@recovered", "room@@new"],
            self.service.list_confirmed_room_scope_ids(room.stable_id),
        )

    def test_confirm_historical_room_binding_keeps_active_runtime_room(self):
        account = self.service.resolve_account("self_a", "Bot", "profile-a", {})
        self.service.confirm_account_binding(account.stable_id, "self_a", actor="test", reason="account")
        room = self.service.resolve_room(account.stable_id, "room@@current", "Room A", "self_a", {})
        self.service.confirm_room_binding(room.stable_id, "room@@current", actor="test", reason="current room")

        self.service.confirm_historical_room_binding(
            room.stable_id,
            "room@@history",
            room_name="Room A",
            actor="test",
            reason="profile history",
        )

        self.assertEqual("room@@current", self.service.get_active_runtime_room_id(room.stable_id))
        self.assertEqual(
            [room.stable_id, "room@@current", "room@@history"],
            self.service.list_confirmed_room_scope_ids(room.stable_id),
        )

    def test_confirmed_room_scope_does_not_expand_for_unconfirmed_account(self):
        account = self.service.resolve_account("self_a", "Bot", "profile-a", {})
        self.service.confirm_account_binding(account.stable_id, "self_a", actor="test", reason="account")
        room = self.service.resolve_room(account.stable_id, "room@@current", "Room A", "self_a", {})
        self.service.confirm_room_binding(room.stable_id, "room@@current", actor="test", reason="room")
        self.store.upsert_account(
            account.stable_id,
            display_name="Bot",
            status="legacy_imported",
            confidence="candidate",
        )

        self.assertEqual(
            [room.stable_id],
            self.service.list_confirmed_room_scope_ids(room.stable_id),
        )

    def test_member_redirect_resolves_stable_and_runtime_ids_to_one_canonical_member(self):
        account = self.service.resolve_account("self_a", "Bot", "profile-a", {})
        self.service.confirm_account_binding(account.stable_id, "self_a", actor="test", reason="account")
        room = self.service.resolve_room(account.stable_id, "room@@a", "Room A", "self_a", {})
        self.service.confirm_room_binding(room.stable_id, "room@@a", actor="test", reason="room")
        canonical = self.service.resolve_member(
            room.stable_id,
            "alice-main",
            "Alice",
            "Alice",
            {"wechat_id": "alice-main-wechat"},
        )
        duplicate = self.service.resolve_member(
            room.stable_id,
            "alice-duplicate",
            "Alice New",
            "Alice New",
            {"wechat_id": "alice-duplicate-wechat"},
        )

        resolved = self.service.confirm_member_redirect(
            room.stable_id,
            duplicate.stable_id,
            canonical.stable_id,
            actor="test",
            reason="same member",
        )

        self.assertEqual(canonical.stable_id, resolved)
        self.assertEqual(
            canonical.stable_id,
            self.service.resolve_canonical_member_id(room.stable_id, duplicate.stable_id),
        )
        self.assertEqual(
            canonical.stable_id,
            self.service.resolve_runtime_member_in_stable_room(room.stable_id, "alice-duplicate"),
        )


if __name__ == "__main__":
    unittest.main()
