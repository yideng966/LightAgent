import os
import tempfile
import unittest

from channel.wechat_group.wechat_group_identity_service import WechatGroupIdentityService
from channel.wechat_group.wechat_group_identity_store import WechatGroupIdentityStore
from channel.wechat_group.wechat_group_knowledge_service import WechatGroupKnowledgeService
from channel.wechat_group.wechat_group_knowledge_store import WechatGroupKnowledgeStore
from channel.wechat_group.wechat_group_memory_tools import (
    WechatGroupMemorySearchTool,
    WechatGroupProfileGetTool,
    create_wechat_group_memory_tools,
)
from channel.wechat_group.wechat_group_profile_service import WechatGroupProfileService
from channel.wechat_group.wechat_group_profile_store import WechatGroupProfileStore


class WechatGroupMemoryToolsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.knowledge_service = WechatGroupKnowledgeService(
            WechatGroupKnowledgeStore(os.path.join(self._tmp.name, "knowledge.db"))
        )
        self.identity = WechatGroupIdentityService(
            WechatGroupIdentityStore(os.path.join(self._tmp.name, "identity.db"))
        )
        account = self.identity.resolve_account("self-a", "Bot", "profile-a", {})
        self.identity.confirm_account_binding(account.stable_id, "self-a", actor="test", reason="account")
        self.room_a = self._create_room(account.stable_id, "room@@a", "Group A")
        self.room_b = self._create_room(account.stable_id, "room@@b", "Group B")
        self.alice_a = self._create_member(self.room_a, "alice-a", "Alice", "alice-a-wechat")
        self.bob_a = self._create_member(self.room_a, "bob-a", "Bob", "bob-a-wechat")
        self.bot_a = self._create_member(self.room_a, "bot-a", "Bot", "bot-a-wechat")
        self.bob_b = self._create_member(self.room_b, "bob-b", "Bob B", "bob-b-wechat")
        self.profile_service = WechatGroupProfileService(
            WechatGroupProfileStore(os.path.join(self._tmp.name, "profiles.db")),
            identity_service=self.identity,
        )
        self._manual(self.room_a, self.alice_a, "Alice", "wants risk first", ["release"], ["阿狸"])
        self._manual(self.room_a, self.bob_a, "Bob", "gives concise answers", ["frontend"], ["前端 Bob"])
        self._manual(self.room_a, self.bot_a, "Bot", "bot style", [], [])
        self._manual(self.room_b, self.bob_b, "Cross Room Bob", "database topics", ["database"], ["后端 Bob"])

    def tearDown(self):
        self._tmp.cleanup()

    def _create_room(self, account_id, runtime_room_id, name):
        room = self.identity.resolve_room(account_id, runtime_room_id, name, "self-a", {})
        self.identity.confirm_room_binding(room.stable_id, runtime_room_id, actor="test", reason="room")
        return room.stable_id

    def _create_member(self, room_id, runtime_id, name, wechat_id):
        member = self.identity.resolve_member(
            room_id,
            runtime_id,
            name,
            name,
            {"wechat_id": wechat_id},
        )
        self.identity.confirm_member_binding(room_id, member.stable_id, runtime_id, actor="test", reason="member")
        return member.stable_id

    def _manual(self, room_id, member_id, nickname, style, interests, aliases):
        self.profile_service.upsert_manual_profile(
            sender_id=member_id,
            primary_nickname=nickname,
            speak_style=style,
            interests=interests,
            common_words=[],
            aliases=aliases,
            room_id=room_id,
        )

    def test_memory_search_tool_is_bound_to_current_room(self):
        self.knowledge_service.add_group_memory(self.room_a, "A room release window is Friday night")
        self.knowledge_service.add_group_memory(self.room_b, "B room release window is Saturday morning")

        result = WechatGroupMemorySearchTool(self.knowledge_service, self.room_a).execute({
            "query": "release window",
            "max_results": 5,
        })

        self.assertIn("A room release window is Friday night", result.result)
        self.assertNotIn("B room release window is Saturday morning", result.result)

    def test_profile_tool_resolves_runtime_sender_to_canonical_profile(self):
        tool = WechatGroupProfileGetTool(
            self.profile_service,
            sender_id="alice-a",
            room_id=self.room_a,
            bot_sender_id="bot-a",
        )

        result = tool.execute({})

        self.assertEqual("success", result.status)
        self.assertIn("sender_id: {}".format(self.alice_a), result.result)
        self.assertIn("wants risk first", result.result)

    def test_profile_search_and_list_are_current_room_only(self):
        tools = create_wechat_group_memory_tools(
            self.knowledge_service,
            self.profile_service,
            self.room_a,
            "alice-a",
            "bot-a",
        )
        tool = next(item for item in tools if item.name == "wechat_group_profile_get")

        search = tool.execute({"query": "Bob", "max_results": 5})
        listed = tool.execute({"list_all": True, "max_results": 10})

        self.assertIn("sender_id: {}".format(self.bob_a), search.result)
        self.assertNotIn(self.bob_b, search.result)
        self.assertIn(self.alice_a, listed.result)
        self.assertIn(self.bob_a, listed.result)
        self.assertNotIn(self.bot_a, listed.result)
        self.assertNotIn(self.bob_b, listed.result)

    def test_exact_cross_room_member_id_cannot_escape_bound_room(self):
        tool = WechatGroupProfileGetTool(
            self.profile_service,
            sender_id="alice-a",
            room_id=self.room_a,
        )

        result = tool.execute({"sender_id": self.bob_b})

        self.assertIn("No profile found", result.result)
        self.assertNotIn("database topics", result.result)

    def test_wechat_group_tool_schemas_do_not_accept_room_id(self):
        tools = create_wechat_group_memory_tools(
            self.knowledge_service,
            self.profile_service,
            self.room_a,
            "alice-a",
            "bot-a",
        )

        self.assertEqual(
            ["wechat_group_memory_search", "wechat_group_profile_get"],
            [tool.name for tool in tools],
        )
        for tool in tools:
            self.assertNotIn("room_id", tool.params.get("properties", {}))


if __name__ == "__main__":
    unittest.main()
