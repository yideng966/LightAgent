import sys
import types
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from agent.tools.scheduler.scheduler_tool import SchedulerTool
from agent.tools.scheduler.scheduler_service import SchedulerService
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
        self.deleted = []
        self.tasks = {}

    def add_task(self, task):
        self.added.append(task)
        self.tasks[task["id"]] = task
        return True

    def get_task(self, task_id):
        return self.tasks.get(task_id)

    def update_task(self, task_id, updates):
        self.updates.append((task_id, updates))
        if task_id in self.tasks:
            self.tasks[task_id].update(updates)
        return True

    def delete_task(self, task_id):
        self.deleted.append(task_id)
        self.tasks.pop(task_id, None)
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

    def test_enqueue_github_message_uses_stable_receiver_and_is_idempotent(self):
        store = FakeTaskStore()
        integration._task_store = store
        identity_service = FakeIdentityService(runtime_room_id="room@@current")
        running_channel = RunningWechatGroupChannel(identity_service=identity_service)
        fake_app = types.SimpleNamespace(
            _channel_mgr=FakeChannelManager(running_channel)
        )

        with patch.dict(sys.modules, {"app": fake_app}):
            first = integration.enqueue_wechat_group_message(
                task_id="github-task",
                name="GitHub notification",
                content="commit notification",
                stable_receiver="wgr_room",
                max_lateness_seconds=72 * 3600,
                metadata={
                    "source": "github_webhook",
                    "external_delivery_id": "delivery-1",
                    "repository": "owner/repository",
                    "ref": "refs/heads/main",
                },
            )
            second = integration.enqueue_wechat_group_message(
                task_id="github-task",
                name="GitHub notification",
                content="commit notification",
                stable_receiver="wgr_room",
            )

        self.assertEqual("enqueued", first)
        self.assertEqual("existing", second)
        self.assertEqual(1, len(store.added))
        task = store.added[0]
        action = task["action"]
        self.assertEqual(72 * 3600, task["max_lateness_seconds"])
        self.assertEqual("wgr_room", action["stable_receiver"])
        self.assertEqual("room@@current", action["runtime_receiver"])
        self.assertTrue(action["suppress_mention"])
        self.assertTrue(action["no_need_at"])
        self.assertEqual("github_webhook", action["source"])
        self.assertEqual("delivery-1", action["external_delivery_id"])

    def test_github_message_marks_delivery_and_suppresses_mention(self):
        store = FakeTaskStore()
        integration._task_store = store
        identity_service = FakeIdentityService(runtime_room_id="room@@current")
        running_channel = RunningWechatGroupChannel(identity_service=identity_service)
        fake_app = types.SimpleNamespace(
            _channel_mgr=FakeChannelManager(running_channel)
        )

        with patch.dict(sys.modules, {"app": fake_app}):
            integration.enqueue_wechat_group_message(
                task_id="github-send",
                name="GitHub notification",
                content="commit notification",
                stable_receiver="wgr_room",
                metadata={
                    "source": "github_webhook",
                    "external_delivery_id": "delivery-send",
                },
            )
            task = store.get_task("github-send")
            with patch(
                "channel.web.github_commit_webhook.mark_github_delivery_delivered",
                return_value=True,
            ) as mark_delivered:
                ok = integration._execute_send_message(task, FakeAgentBridge())

        self.assertTrue(ok)
        mark_delivered.assert_called_once_with("delivery-send")
        reply, context = running_channel.sent[0]
        self.assertEqual("commit notification", reply.content)
        self.assertTrue(context["suppress_mention"])
        self.assertTrue(context["no_need_at"])
        self.assertEqual("wgr_room", context["wechat_group_stable_room_id"])

    def test_scheduler_honors_task_specific_lateness_window(self):
        store = FakeTaskStore()
        service = SchedulerService(store, lambda task: True)
        now = datetime(2026, 7, 23, 12, 0, 0)
        task = {
            "id": "github-late",
            "enabled": True,
            "next_run_at": (now - timedelta(minutes=20)).isoformat(),
            "max_lateness_seconds": 3600,
            "schedule": {
                "type": "once",
                "run_at": (now - timedelta(minutes=20)).isoformat(),
            },
        }
        store.tasks[task["id"]] = task

        self.assertTrue(service._is_task_due(task, now))
        self.assertEqual([], store.deleted)

        legacy_task = dict(task)
        legacy_task["id"] = "legacy-late"
        legacy_task.pop("max_lateness_seconds")
        store.tasks[legacy_task["id"]] = legacy_task
        self.assertFalse(service._is_task_due(legacy_task, now))
        self.assertEqual(["legacy-late"], store.deleted)

    def test_wechat_group_readiness_requires_logged_in_status(self):
        class StatusChannel:
            STATUS_LOGGED_IN = "logged_in"
            STATUS_CONNECTED = "connected"

            def __init__(self, status):
                self.status = status

            def get_login_status(self):
                return self.status

        with patch.object(integration, "_get_running_channel", return_value=StatusChannel("qr_ready")):
            self.assertFalse(integration._is_channel_ready("wechat_group", ""))
        with patch.object(integration, "_get_running_channel", return_value=StatusChannel("connected")):
            self.assertTrue(integration._is_channel_ready("wechat_group", ""))


if __name__ == "__main__":
    unittest.main()
