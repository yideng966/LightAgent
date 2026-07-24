import os
import tempfile
import types
import unittest
from unittest.mock import patch

from agent.protocol.agent_stream import AgentStreamExecutor
from agent.skills.manager import SkillManager
from channel.wechat_group.wechat_group_identity_service import (
    WechatGroupIdentityService,
)
from channel.wechat_group.wechat_group_identity_store import (
    WechatGroupIdentityStore,
)
from channel.wechat_group.wechat_group_skill_access import (
    MODE_RESTRICTED,
    MODE_UNRESTRICTED,
    WechatGroupSkillAccessService,
    WechatGroupSkillAccessStore,
)


class _FakeManager:
    def __init__(self):
        self.skills = {}
        self.skills_config = {}

    def add(self, name, source_identity="", content="instructions"):
        skill = types.SimpleNamespace(
            name=name,
            description=f"{name} description",
            source="custom",
            base_dir=os.path.join("/workspace/skills", name),
            content=content,
            frontmatter={},
        )
        metadata = types.SimpleNamespace(
            skill_key=name,
            homepage=None,
        )
        self.skills[name] = types.SimpleNamespace(skill=skill, metadata=metadata)
        self.skills_config[name] = {
            "name": name,
            "description": skill.description,
            "source": "custom",
            "source_identity": source_identity or f"local:{name}",
            "enabled": True,
            "category": "skill",
        }

    def get_skills_config(self):
        return dict(self.skills_config)

    def is_skill_enabled(self, name):
        return bool(self.skills_config.get(name, {}).get("enabled", True))

    def _load_skills_config(self):
        return self.skills_config


class WechatGroupSkillAccessTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        acl_path = os.path.join(self.tmp.name, "acl.db")
        identity_path = os.path.join(self.tmp.name, "identity.db")
        identity_store = WechatGroupIdentityStore(identity_path)
        identity_store.upsert_account(
            "account-1", status="confirmed", confidence="manual", confirmed_at=1
        )
        identity_store.upsert_room(
            "room-1",
            "account-1",
            status="confirmed",
            confidence="manual",
            confirmed_at=1,
        )
        identity_store.upsert_member(
            "member-old",
            "room-1",
            "account-1",
            status="confirmed",
            confidence="manual",
            confirmed_at=1,
        )
        identity_store.upsert_member(
            "member-new",
            "room-1",
            "account-1",
            status="confirmed",
            confidence="manual",
            confirmed_at=1,
        )
        self.identity_service = WechatGroupIdentityService(identity_store)
        self.service = WechatGroupSkillAccessService(
            WechatGroupSkillAccessStore(acl_path),
            identity_service=self.identity_service,
        )
        self.manager = _FakeManager()

    def tearDown(self):
        self.tmp.cleanup()

    def test_bootstrap_keeps_existing_skills_and_new_skill_is_restricted(self):
        self.manager.add("existing")
        self.service.sync_skill_catalog(self.manager)
        self.assertEqual(
            self.service.get_access("existing")["mode"], MODE_UNRESTRICTED
        )
        self.assertFalse(self.service.get_access("existing")["is_new"])

        self.manager.add("future")
        self.service.sync_skill_catalog(self.manager)
        self.assertEqual(
            self.service.get_access("future")["mode"], MODE_RESTRICTED
        )
        self.assertTrue(self.service.get_access("future")["is_new"])

    def test_source_change_does_not_inherit_access(self):
        self.manager.add("sample", source_identity="repo-a")
        self.service.sync_skill_catalog(self.manager)
        current = self.service.get_access("sample")
        self.service.save_access(
            "sample",
            MODE_UNRESTRICTED,
            [],
            current["version"],
        )

        self.manager.skills_config["sample"]["source_identity"] = "repo-b"
        self.service.sync_skill_catalog(self.manager)
        replacement = self.service.get_access("sample")
        self.assertEqual(replacement["mode"], MODE_RESTRICTED)
        self.assertTrue(replacement["is_new"])

    def test_member_grant_follows_canonical_redirect(self):
        self.manager.add("restricted-skill")
        self.service.sync_skill_catalog(self.manager)
        policy = self.service.get_access("restricted-skill")
        self.service.save_access(
            "restricted-skill",
            MODE_RESTRICTED,
            [{
                "stable_room_id": "room-1",
                "grant_type": "member",
                "stable_member_id": "member-old",
            }],
            policy["version"],
        )
        self.identity_service.store.upsert_member_redirect(
            "room-1", "member-old", "member-new"
        )
        allowed, reason = self.service.check_access(
            "restricted-skill", "room-1", "member-new"
        )
        self.assertTrue(allowed)
        self.assertEqual(reason, "member_grant")

    def test_default_template_is_applied_only_to_later_skills(self):
        self.manager.add("existing")
        self.service.sync_skill_catalog(self.manager)
        self.service.save_template({
            "template_id": "admins",
            "name": "Admins",
            "mode": MODE_RESTRICTED,
            "grants": [{
                "stable_room_id": "room-1",
                "grant_type": "member",
                "stable_member_id": "member-new",
            }],
            "is_default": True,
        })
        self.manager.add("later")
        self.service.sync_skill_catalog(self.manager)
        policy = self.service.get_access("later")
        self.assertEqual(policy["mode"], MODE_RESTRICTED)
        self.assertEqual(len(policy["grants"]), 1)

    def test_stale_version_is_rejected(self):
        self.manager.add("versioned")
        self.service.sync_skill_catalog(self.manager)
        policy = self.service.get_access("versioned")
        self.service.save_access(
            "versioned", MODE_RESTRICTED, [], policy["version"]
        )
        with self.assertRaisesRegex(RuntimeError, "version conflict"):
            self.service.save_access(
                "versioned", MODE_UNRESTRICTED, [], policy["version"]
            )

    def test_explicit_empty_skill_filter_stays_empty(self):
        self.assertIsNone(SkillManager._normalize_skill_filter(None))
        self.assertEqual(SkillManager._normalize_skill_filter([]), [])
        self.assertEqual(SkillManager._normalize_skill_filter(["", []]), [])

    def test_symlink_path_resolves_to_skill_root(self):
        skill_root = os.path.join(self.tmp.name, "skill")
        outside = os.path.join(self.tmp.name, "outside")
        os.makedirs(skill_root)
        os.makedirs(outside)
        script = os.path.join(skill_root, "run.py")
        with open(script, "w", encoding="utf-8") as handle:
            handle.write("print('ok')")
        link = os.path.join(outside, "linked.py")
        os.symlink(script, link)
        detected = AgentStreamExecutor._skill_referenced_by_arguments(
            {"path": link}, {"sample": skill_root}
        )
        self.assertEqual(detected, "sample")

    def test_denial_aborts_tool_and_every_followup_tool(self):
        skill_root = os.path.join(self.tmp.name, "restricted")
        os.makedirs(skill_root)
        self.manager.add("restricted")
        self.manager.skills["restricted"].skill.base_dir = skill_root
        agent = types.SimpleNamespace(skill_manager=self.manager)
        context = {
            "wechat_group_skill_access_enabled": True,
            "wechat_group_allowed_skill_names": [],
            "wechat_group_skill_roots": {"restricted": skill_root},
            "wechat_group_stable_room_id": "room-1",
            "wechat_group_stable_member_id": "member-new",
            "request_id": "request-1",
        }
        executor = AgentStreamExecutor(
            agent=agent,
            model=None,
            system_prompt="",
            tools=[],
            context=context,
        )
        with patch(
            "channel.wechat_group.wechat_group_skill_access."
            "get_wechat_group_skill_access_service",
            return_value=self.service,
        ):
            denied = executor._execute_tool({
                "id": "tool-1",
                "name": "restricted",
                "arguments": {},
            })
            followup = executor._execute_tool({
                "id": "tool-2",
                "name": "send",
                "arguments": {"path": "/tmp/image.jpg"},
            })
        self.assertEqual(denied["status"], "critical_error")
        self.assertEqual(followup["status"], "critical_error")
        self.assertIn("没有使用「restricted」的权限", denied["result"])


if __name__ == "__main__":
    unittest.main()
