import sys
import types
import unittest
from unittest.mock import patch

from agent.tools.scheduler.scheduler_tool import SchedulerTool
from bridge.context import Context, ContextType
from agent.tools.scheduler import integration
from bridge.reply import Reply, ReplyType


class FakeAgentBridge:
    def __init__(self):
        self.remembered = []
        self.contexts = []

    def agent_reply(self, query, context=None, on_event=None, clear_history=False):
        self.contexts.append(context)
        return Reply(ReplyType.TEXT, "scheduled report")

    def remember_scheduled_output(self, session_id, content, channel_type="", task_description=""):
        self.remembered.append({
            "session_id": session_id,
            "content": content,
            "channel_type": channel_type,
            "task_description": task_description,
        })


class RunningWechatGroupChannel:
    def __init__(self, identity_service=None):
        self.sent = []
        self.identity_service = identity_service

    def send(self, reply, context):
        self.sent.append((reply, context))


class FreshWechatGroupChannel:
    def send(self, reply, context):
        raise RuntimeError("wechat group sidecar is not started")


class FakeChannelManager:
    def __init__(self, channel):
        self.channel = channel

    def get_channel(self, name):
        if name == "wechat_group":
            return self.channel
        return None


class FakeTaskStore:
    def __init__(self):
        self.added = []
        self.updates = []

    def add_task(self, task):
        self.added.append(task)
        return True

    def update_task(self, task_id, updates):
        self.updates.append((task_id, updates))
        return True


class FakeIdentityService:
    def __init__(self, runtime_room_id=""):
        self.runtime_room_id = runtime_room_id
        self.requested = []

    def get_active_runtime_room_id(self, stable_room_id):
        self.requested.append(stable_room_id)
        return self.runtime_room_id


class SchedulerWechatGroupDeliveryTest(unittest.TestCase):
    def tearDown(self):
        integration._task_store = None

    def test_create_wechat_group_task_persists_stable_receiver_and_runtime_snapshot(self):
        store = FakeTaskStore()
        tool = SchedulerTool(config={"channel_type": "wechat_group"})
        tool.task_store = store
        context = Context(ContextType.TEXT, "每天9点提醒")
        context["receiver"] = "room@@old"
        context["isgroup"] = True
        context["session_id"] = "wechat_group:wgr_room"
        context["channel_type"] = "wechat_group"
        context["wechat_group_stable_room_id"] = "wgr_room"
        context["wechat_group_stable_receiver"] = "wgr_room"
        context["msg"] = types.SimpleNamespace(other_user_nickname="稳定群")
        tool.current_context = context

        result = tool.execute({
            "action": "create",
            "name": "日报",
            "message": "该看日报了",
            "schedule_type": "once",
            "schedule_value": "+5m",
        })

        self.assertEqual("success", result.status)
        action = store.added[0]["action"]
        self.assertEqual("room@@old", action["receiver"])
        self.assertEqual("room@@old", action["runtime_receiver"])
        self.assertEqual("wgr_room", action["stable_receiver"])
        self.assertEqual("wechat_group", action["receiver_kind"])
        self.assertEqual("wechat_group:wgr_room", action["notify_session_id"])

    def test_agent_task_uses_running_wechat_group_channel(self):
        running_channel = RunningWechatGroupChannel()
        fake_app = types.SimpleNamespace(
            _channel_mgr=FakeChannelManager(running_channel)
        )
        task = {
            "id": "task-1",
            "action": {
                "type": "agent_task",
                "task_description": "send daily report",
                "receiver": "room@@abc",
                "is_group": True,
                "channel_type": "wechat_group",
                "notify_session_id": "room@@abc",
            },
        }

        with patch.dict(sys.modules, {"app": fake_app}):
            with patch("channel.channel_factory.create_channel", return_value=FreshWechatGroupChannel()):
                ok = integration._execute_agent_task(task, FakeAgentBridge())

        self.assertTrue(ok)
        self.assertEqual(1, len(running_channel.sent))
        reply, context = running_channel.sent[0]
        self.assertEqual("scheduled report", reply.content)
        self.assertEqual("room@@abc", context["receiver"])

    def test_agent_task_resolves_stable_receiver_to_active_runtime_room(self):
        identity_service = FakeIdentityService(runtime_room_id="room@@new")
        running_channel = RunningWechatGroupChannel(identity_service=identity_service)
        fake_app = types.SimpleNamespace(
            _channel_mgr=FakeChannelManager(running_channel)
        )
        bridge = FakeAgentBridge()
        task = {
            "id": "task-stable",
            "action": {
                "type": "agent_task",
                "task_description": "send daily report",
                "receiver": "room@@old",
                "runtime_receiver": "room@@old",
                "stable_receiver": "wgr_room",
                "receiver_kind": "wechat_group",
                "is_group": True,
                "channel_type": "wechat_group",
                "notify_session_id": "wechat_group:wgr_room",
            },
        }

        with patch.dict(sys.modules, {"app": fake_app}):
            ok = integration._execute_agent_task(task, bridge)

        self.assertTrue(ok)
        self.assertEqual(["wgr_room"], identity_service.requested)
        reply, context = running_channel.sent[0]
        self.assertEqual("scheduled report", reply.content)
        self.assertEqual("room@@new", context["receiver"])
        self.assertEqual("scheduler_wgr_room_task-stable", bridge.contexts[0]["session_id"])
        self.assertEqual("wechat_group:wgr_room", bridge.remembered[0]["session_id"])

    def test_missing_active_runtime_marks_task_waiting_identity_binding(self):
        integration._task_store = FakeTaskStore()
        identity_service = FakeIdentityService(runtime_room_id="")
        running_channel = RunningWechatGroupChannel(identity_service=identity_service)
        fake_app = types.SimpleNamespace(
            _channel_mgr=FakeChannelManager(running_channel)
        )
        task = {
            "id": "task-waiting",
            "action": {
                "type": "send_message",
                "content": "提醒",
                "receiver": "room@@old",
                "runtime_receiver": "room@@old",
                "stable_receiver": "wgr_room",
                "receiver_kind": "wechat_group",
                "is_group": True,
                "channel_type": "wechat_group",
                "notify_session_id": "wechat_group:wgr_room",
            },
        }

        with patch.dict(sys.modules, {"app": fake_app}):
            ok = integration._execute_send_message(task, FakeAgentBridge())

        self.assertFalse(ok)
        self.assertEqual(0, len(running_channel.sent))
        self.assertEqual(1, len(integration._task_store.updates))
        task_id, updates = integration._task_store.updates[0]
        self.assertEqual("task-waiting", task_id)
        self.assertEqual("waiting_identity_binding", updates["delivery_status"])
        self.assertEqual("waiting_identity_binding", updates["action"]["delivery_status"])


if __name__ == "__main__":
    unittest.main()
