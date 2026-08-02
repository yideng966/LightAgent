import os
import tempfile
import unittest
from types import SimpleNamespace

from config import conf


class WechatGroupPermissionsTest(unittest.TestCase):
    def setUp(self):
        self._original = {
            "wechat_group_admin_members": conf().get("wechat_group_admin_members"),
            "wechat_group_admin_sender_ids": conf().get("wechat_group_admin_sender_ids"),
            "wechat_group_admin_required_permissions": conf().get("wechat_group_admin_required_permissions"),
            "wechat_group_blacklist_members": conf().get("wechat_group_blacklist_members"),
            "wechat_group_blocked_stable_member_ids": conf().get("wechat_group_blocked_stable_member_ids"),
            "wechat_group_blocked_sender_ids": conf().get("wechat_group_blocked_sender_ids"),
        }

    def tearDown(self):
        for key, value in self._original.items():
            if value is None:
                conf().pop(key, None)
            else:
                conf()[key] = value

    def test_admin_is_scoped_by_room_and_sender(self):
        from channel.wechat_group.wechat_group_permissions import is_wechat_group_admin

        conf()["wechat_group_admin_members"] = [
            {
                "room_id": "room@@a",
                "room_name": "A 群",
                "sender_id": "wxid_admin",
                "sender_nickname": "Alice",
                "wechat_id": "alice_wechat",
            }
        ]
        conf()["wechat_group_admin_sender_ids"] = []

        self.assertTrue(is_wechat_group_admin("room@@a", "wxid_admin"))
        self.assertFalse(is_wechat_group_admin("room@@b", "wxid_admin"))
        self.assertFalse(is_wechat_group_admin("room@@a", "wxid_other"))

    def test_admin_can_be_scoped_by_stable_room_and_member(self):
        from channel.wechat_group.wechat_group_permissions import (
            get_blocked_admin_permissions_for_text,
            is_wechat_group_admin,
        )

        conf()["wechat_group_admin_members"] = [
            {
                "stable_room_id": "wgr_room",
                "stable_member_id": "wgm_admin",
                "room_name": "A 群",
                "member_name": "Alice",
                "legacy_room_id": "room@@old",
                "legacy_sender_id": "wxid_old",
            }
        ]
        conf()["wechat_group_admin_sender_ids"] = []

        self.assertTrue(is_wechat_group_admin("wgr_room", "wgm_admin"))
        self.assertTrue(is_wechat_group_admin("room@@old", "wxid_old"))
        self.assertFalse(is_wechat_group_admin("wgr_other", "wgm_admin"))
        self.assertEqual([], get_blocked_admin_permissions_for_text("每天提醒我", "wgr_room", "wgm_admin"))

    def test_suspected_stable_admin_member_does_not_inherit_permission(self):
        from channel.wechat_group.wechat_group_permissions import is_wechat_group_admin

        conf()["wechat_group_admin_members"] = [
            {
                "stable_room_id": "wgr_room",
                "stable_member_id": "wgm_admin",
                "identity_status": "suspected",
                "legacy_room_id": "room@@old",
                "legacy_sender_id": "wxid_old",
            }
        ]
        conf()["wechat_group_admin_sender_ids"] = []

        self.assertFalse(is_wechat_group_admin("wgr_room", "wgm_admin"))
        self.assertFalse(is_wechat_group_admin("room@@old", "wxid_old"))

    def test_pending_runtime_alias_for_confirmed_admin_renders_member_policy(self):
        from channel.wechat_group.wechat_group_permissions import build_wechat_group_admin_policy_block

        conf()["wechat_group_admin_members"] = [{
            "stable_room_id": "wgr_room",
            "stable_member_id": "wgm_admin",
            "identity_status": "confirmed",
        }]

        block = build_wechat_group_admin_policy_block(
            "wgr_room",
            "wgm_admin",
            identity_confirmed=False,
        )

        self.assertIn("current_sender_role: member", block)

    def test_legacy_sender_ids_are_used_only_when_new_members_empty(self):
        from channel.wechat_group.wechat_group_permissions import is_wechat_group_admin

        conf()["wechat_group_admin_members"] = []
        conf()["wechat_group_admin_sender_ids"] = ["wxid_legacy"]

        self.assertTrue(is_wechat_group_admin("room@@any", "wxid_legacy"))
        self.assertFalse(is_wechat_group_admin("room@@any", "wxid_other"))

        conf()["wechat_group_admin_members"] = [{"room_id": "room@@a", "sender_id": "wxid_admin"}]
        self.assertFalse(is_wechat_group_admin("room@@any", "wxid_legacy"))

    def test_normalize_admin_members_deduplicates_room_sender_pairs(self):
        from channel.wechat_group.wechat_group_permissions import normalize_wechat_group_admin_members

        members = normalize_wechat_group_admin_members([
            {"room_id": " room@@a ", "sender_id": " wxid_admin ", "sender_nickname": "Alice"},
            {"room_id": "room@@a", "sender_id": "wxid_admin", "sender_nickname": "Alice 2"},
            {"room_id": "", "sender_id": "wxid_empty"},
            {"room_id": "room@@b", "sender_id": ""},
        ])

        self.assertEqual(1, len(members))
        self.assertEqual("room@@a", members[0]["room_id"])
        self.assertEqual("wxid_admin", members[0]["sender_id"])
        self.assertEqual("Alice", members[0]["sender_nickname"])

    def test_blacklist_member_is_scoped_by_stable_room_and_member(self):
        from channel.wechat_group.wechat_group_permissions import is_wechat_group_blacklisted

        conf()["wechat_group_blacklist_members"] = [{
            "stable_room_id": "wgr_room",
            "stable_member_id": "wgm_blocked",
            "identity_status": "confirmed",
            "legacy_room_id": "room@@old",
            "legacy_sender_id": "wxid_old",
        }]
        conf()["wechat_group_blocked_stable_member_ids"] = []
        conf()["wechat_group_blocked_sender_ids"] = []

        self.assertTrue(is_wechat_group_blacklisted("wgr_room", "wgm_blocked"))
        self.assertTrue(is_wechat_group_blacklisted("room@@old", "wxid_old"))
        self.assertFalse(is_wechat_group_blacklisted("wgr_other", "wgm_blocked"))
        self.assertFalse(is_wechat_group_blacklisted("wgr_room", "wgm_other"))

    def test_suspected_blacklist_member_is_ignored(self):
        from channel.wechat_group.wechat_group_permissions import is_wechat_group_blacklisted

        conf()["wechat_group_blacklist_members"] = [{
            "stable_room_id": "wgr_room",
            "stable_member_id": "wgm_blocked",
            "identity_status": "suspected",
        }]

        self.assertFalse(is_wechat_group_blacklisted("wgr_room", "wgm_blocked"))

    def test_blacklist_keeps_legacy_flat_fallback(self):
        from channel.wechat_group.wechat_group_permissions import is_wechat_group_blacklisted

        conf()["wechat_group_blacklist_members"] = []
        conf()["wechat_group_blocked_stable_member_ids"] = ["wgm_blocked"]
        conf()["wechat_group_blocked_sender_ids"] = ["wxid_legacy"]

        self.assertTrue(is_wechat_group_blacklisted("wgr_room", "wgm_blocked"))
        self.assertTrue(is_wechat_group_blacklisted("wgr_room", "wgm_other", runtime_sender_id="wxid_legacy"))
        self.assertFalse(is_wechat_group_blacklisted("wgr_room", "wgm_other", runtime_sender_id="wxid_other"))

    def test_blacklist_flat_fallback_still_applies_with_structured_members(self):
        from channel.wechat_group.wechat_group_permissions import is_wechat_group_blacklisted

        conf()["wechat_group_blacklist_members"] = [{
            "stable_room_id": "wgr_other",
            "stable_member_id": "wgm_other",
            "identity_status": "confirmed",
        }]
        conf()["wechat_group_blocked_sender_ids"] = ["wxid_legacy"]

        self.assertTrue(is_wechat_group_blacklisted("wgr_room", "wgm_alice", runtime_sender_id="wxid_legacy"))

    def test_blocked_sender_ids_only_adds_current_structured_blacklist_sender(self):
        from channel.wechat_group.wechat_group_permissions import build_wechat_group_blocked_sender_ids

        conf()["wechat_group_blacklist_members"] = [{
            "stable_room_id": "wgr_other",
            "stable_member_id": "wgm_other",
            "identity_status": "confirmed",
        }]
        conf()["wechat_group_blocked_stable_member_ids"] = []
        conf()["wechat_group_blocked_sender_ids"] = []

        blocked = build_wechat_group_blocked_sender_ids("wgr_room", "wgm_alice", runtime_sender_id="wxid_alice")

        self.assertNotIn("wgm_other", blocked)
        self.assertNotIn("wgm_alice", blocked)

    def test_default_required_permissions_are_enabled(self):
        from channel.wechat_group.wechat_group_permissions import (
            get_wechat_group_admin_permission_definitions,
            get_wechat_group_admin_required_permissions,
        )

        conf().pop("wechat_group_admin_required_permissions", None)
        permissions = get_wechat_group_admin_required_permissions()
        definitions = get_wechat_group_admin_permission_definitions()

        self.assertTrue(permissions["knowledge_write"])
        self.assertTrue(permissions["memory_write"])
        self.assertTrue(permissions["wechat_group_memory_write"])
        self.assertTrue(permissions["skill_manage"])
        self.assertTrue(permissions["workspace_write"])
        self.assertEqual(11, len(definitions))
        first = definitions[0]
        self.assertIn("id", first)
        self.assertIn("label", first)
        self.assertIn("summary", first)
        self.assertIn("blocked_behavior", first)
        self.assertIn("allowed_behavior", first)
        self.assertIn("examples", first)
        self.assertIn("guard_layers", first)
        self.assertIn("affected_objects", first)
        self.assertIn("default_enabled", first)
        self.assertIn("enabled", first)

    def test_detects_persistent_write_intent(self):
        from channel.wechat_group.wechat_group_permissions import detect_wechat_group_admin_required_permissions

        detected = detect_wechat_group_admin_required_permissions(
            "整理成 md 文档存入永久记忆以及知识库中"
        )

        self.assertIn("knowledge_write", detected)
        self.assertIn("memory_write", detected)
        self.assertIn("workspace_write", detected)

    def test_detects_skill_mutations_but_keeps_skill_queries_read_only(self):
        from channel.wechat_group.wechat_group_permissions import (
            detect_wechat_group_admin_required_permissions,
        )

        for text in (
            "安装技能 image-generation",
            "帮我修改 SKILL.md",
            "卸载这个技能",
            "/skill update sample",
            "lightagent skill disable sample",
        ):
            with self.subTest(text=text):
                self.assertIn(
                    "skill_manage",
                    detect_wechat_group_admin_required_permissions(text),
                )

        for text in ("有哪些技能", "/skill list", "/skill info sample", "/skill verify sample"):
            with self.subTest(text=text):
                self.assertNotIn(
                    "skill_manage",
                    detect_wechat_group_admin_required_permissions(text),
                )

    def test_skill_management_gate_uses_stable_admin_and_config_switch(self):
        from channel.wechat_group.wechat_group_permissions import (
            can_manage_wechat_group_skills,
        )

        config = {
            "wechat_group_admin_members": [{
                "stable_room_id": "wgr_room",
                "stable_member_id": "wgm_admin",
                "identity_status": "confirmed",
            }],
            "wechat_group_admin_required_permissions": {"skill_manage": True},
        }
        self.assertTrue(can_manage_wechat_group_skills("wgr_room", "wgm_admin", config))
        self.assertFalse(can_manage_wechat_group_skills("wgr_room", "wgm_member", config))
        self.assertFalse(can_manage_wechat_group_skills(
            "wgr_room", "wgm_admin", config, identity_confirmed=False
        ))

        config["wechat_group_admin_required_permissions"]["skill_manage"] = False
        self.assertTrue(can_manage_wechat_group_skills("wgr_room", "wgm_member", config))

    def test_skill_mutation_tool_detection_is_scoped_to_skill_storage(self):
        from channel.wechat_group.wechat_group_permissions import (
            is_wechat_group_skill_mutation_tool_call,
        )

        with tempfile.TemporaryDirectory() as workspace:
            skills_dir = os.path.join(workspace, "skills")
            os.makedirs(skills_dir)
            self.assertTrue(is_wechat_group_skill_mutation_tool_call(
                "write", {"path": "skills/sample/SKILL.md"}, skills_dir, cwd=workspace
            ))
            self.assertTrue(is_wechat_group_skill_mutation_tool_call(
                "edit", {"path": os.path.join(skills_dir, "skills_config.json")}, skills_dir, cwd=workspace
            ))
            self.assertTrue(is_wechat_group_skill_mutation_tool_call(
                "bash", {"command": "python skills/skill-creator/init.py --path skills"}, skills_dir, cwd=workspace
            ))
            self.assertTrue(is_wechat_group_skill_mutation_tool_call(
                "bash", {"command": "lightagent skill uninstall sample"}, skills_dir, cwd=workspace
            ))
            self.assertFalse(is_wechat_group_skill_mutation_tool_call(
                "write", {"path": "notes/result.md"}, skills_dir, cwd=workspace
            ))
            self.assertFalse(is_wechat_group_skill_mutation_tool_call(
                "bash", {"command": "Get-ChildItem skills"}, skills_dir, cwd=workspace
            ))

    def test_agent_runtime_blocks_non_admin_skill_directory_write(self):
        from agent.protocol.agent_stream import AgentStreamExecutor

        class FakeWriteTool:
            name = "write"

            def __init__(self, cwd):
                self.cwd = cwd

        with tempfile.TemporaryDirectory() as workspace:
            skills_dir = os.path.join(workspace, "skills")
            os.makedirs(skills_dir)
            conf()["wechat_group_admin_members"] = [{
                "stable_room_id": "wgr_room",
                "stable_member_id": "wgm_admin",
                "identity_status": "confirmed",
            }]
            conf()["wechat_group_admin_required_permissions"] = {
                "workspace_write": False,
                "skill_manage": True,
            }
            context = {
                "channel_type": "wechat_group",
                "wechat_group_stable_room_id": "wgr_room",
                "wechat_group_stable_member_id": "wgm_member",
            }
            executor = AgentStreamExecutor(
                agent=SimpleNamespace(
                    skill_manager=SimpleNamespace(custom_dir=skills_dir)
                ),
                model=None,
                system_prompt="",
                tools=[FakeWriteTool(workspace)],
                context=context,
            )

            result = executor._execute_tool({
                "id": "tool-1",
                "name": "write",
                "arguments": {
                    "path": "skills/sample/SKILL.md",
                    "content": "instructions",
                },
            })

            self.assertEqual("critical_error", result["status"])
            self.assertIn("新增、修改或删除技能", result["result"])
            self.assertTrue(context["wechat_group_silent_admin_guard"])

            conf()["wechat_group_admin_required_permissions"]["skill_manage"] = False
            self.assertEqual(
                "",
                executor._guard_wechat_group_skill_management_tool(
                    "write", {"path": "skills/sample/SKILL.md"}
                ),
            )

    def test_tool_filter_removes_non_admin_write_tools(self):
        from channel.wechat_group.wechat_group_permissions import filter_wechat_group_tools_for_permissions

        class FakeTool:
            def __init__(self, name):
                self.name = name

        tools = [FakeTool("read"), FakeTool("write"), FakeTool("edit"), FakeTool("scheduler")]
        filtered = filter_wechat_group_tools_for_permissions(
            tools,
            room_id="room@@a",
            sender_id="wxid_normal",
            config={
                "wechat_group_admin_members": [{"room_id": "room@@a", "sender_id": "wxid_admin"}],
                "wechat_group_admin_required_permissions": {
                    "workspace_write": True,
                    "scheduler_write": True,
                },
            },
        )

        self.assertEqual(["read"], [tool.name for tool in filtered])

    def test_tool_filter_keeps_admin_tools(self):
        from channel.wechat_group.wechat_group_permissions import filter_wechat_group_tools_for_permissions

        class FakeTool:
            def __init__(self, name):
                self.name = name

        tools = [FakeTool("read"), FakeTool("write"), FakeTool("edit"), FakeTool("scheduler")]
        filtered = filter_wechat_group_tools_for_permissions(
            tools,
            room_id="room@@a",
            sender_id="wxid_admin",
            config={
                "wechat_group_admin_members": [{"room_id": "room@@a", "sender_id": "wxid_admin"}],
                "wechat_group_admin_required_permissions": {
                    "workspace_write": True,
                    "scheduler_write": True,
                },
            },
        )

        self.assertEqual(["read", "write", "edit", "scheduler"], [tool.name for tool in filtered])

    def test_agent_bridge_applies_wechat_group_permission_filter(self):
        root = os.path.dirname(os.path.dirname(__file__))
        path = os.path.join(root, "bridge", "agent_bridge.py")
        with open(path, "r", encoding="utf-8") as f:
            source = f.read()

        self.assertIn("filter_wechat_group_tools_for_permissions", source)
        self.assertIn("wechat_group_stable_room_id", source)
        self.assertIn("wechat_group_stable_member_id", source)


if __name__ == "__main__":
    unittest.main()
