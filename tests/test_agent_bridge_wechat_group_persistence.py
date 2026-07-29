import tempfile
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from pathlib import Path

from bridge.agent_bridge import AgentBridge
from bridge.context import Context, ContextType
from bridge.reply import ReplyType
from agent.memory.conversation_store import ConversationStore
from config import conf


class AgentBridgeWechatGroupPersistenceTest(unittest.TestCase):
    def setUp(self):
        self._original_config = {
            "wechat_group_context_persist_raw_user_only": conf().get("wechat_group_context_persist_raw_user_only"),
            "conversation_persistence": conf().get("conversation_persistence"),
        }
        conf()["wechat_group_context_persist_raw_user_only"] = True
        conf()["conversation_persistence"] = True

    def tearDown(self):
        for key, value in self._original_config.items():
            if value is None:
                conf().pop(key, None)
            else:
                conf()[key] = value

    def _bridge(self):
        return AgentBridge.__new__(AgentBridge)

    @staticmethod
    def _observe_context():
        context = Context(ContextType.TEXT, "enhanced prompt")
        context["channel_type"] = "wechat_group"
        context["session_id"] = "wechat_group:wgr_room:wgm_alice"
        context["receiver"] = "room@@runtime"
        context["isgroup"] = True
        context["wechat_group_user_content"] = "有用吗"
        context["wechat_group_stable_room_id"] = "wgr_room"
        context["wechat_group_stable_member_id"] = "wgm_alice"
        context["wechat_group_agent_history_mode"] = "observe_only"
        return context

    def test_select_persisted_user_query_uses_wechat_group_raw_content(self):
        context = Context(ContextType.TEXT, "enhanced")
        context["channel_type"] = "wechat_group"
        context["wechat_group_user_content"] = "raw user text"

        result = self._bridge()._select_persisted_user_query("enhanced prompt", context)

        self.assertEqual("raw user text", result)

    def test_select_persisted_user_query_can_be_disabled(self):
        conf()["wechat_group_context_persist_raw_user_only"] = False
        context = Context(ContextType.TEXT, "enhanced")
        context["channel_type"] = "wechat_group"
        context["wechat_group_user_content"] = "raw user text"

        result = self._bridge()._select_persisted_user_query("enhanced prompt", context)

        self.assertEqual("enhanced prompt", result)

    def test_thread_persistence_keeps_only_first_user_and_final_assistant(self):
        messages = [
            {"role": "user", "content": "raw question"},
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "intermediate"},
                    {"type": "tool_use", "id": "call-1", "name": "web_fetch"},
                ],
            },
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": "call-1", "content": "result"}
                ],
            },
            {
                "role": "assistant",
                "content": [{"type": "text", "text": "final answer"}],
            },
        ]

        result = self._bridge()._thread_text_only_messages(messages)

        self.assertEqual(["user", "assistant"], [item["role"] for item in result])
        self.assertEqual("raw question", result[0]["content"][0]["text"])
        self.assertEqual("final answer", result[1]["content"][0]["text"])
        self.assertNotIn("tool_use", str(result))
        self.assertNotIn("tool_result", str(result))

    def test_thread_turn_is_staged_pending_and_hidden_from_restore(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ConversationStore(Path(tmpdir) / "conversations.db")
            bridge = self._bridge()
            messages = [
                {"role": "user", "content": "raw question"},
                {"role": "assistant", "content": "final answer"},
            ]

            with patch("agent.memory.get_conversation_store", return_value=store):
                persisted = bridge._persist_messages(
                    "wechat_group:wgr_room:wgm_alice",
                    messages,
                    channel_type="wechat_group",
                    thread_id="wgt_thread",
                    delivery_request_id="request-1",
                    inbound_source_event_id="inbound:3",
                )

            self.assertTrue(persisted)
            self.assertEqual(
                [],
                store.load_messages(
                    "wechat_group:wgr_room:wgm_alice",
                    thread_id="wgt_thread",
                ),
            )
            self.assertEqual(
                [],
                store.load_history_page(
                    "wechat_group:wgr_room:wgm_alice"
                )["messages"],
            )
            self.assertEqual([], store.get_thread_source_event_ids(
                "wechat_group:wgr_room:wgm_alice",
                "wgt_thread",
            ))

    def test_sanitize_wechat_group_runtime_messages_replaces_current_user_turn(self):
        enhanced = "<wechat-group-reply-policy>\ninternal\n</wechat-group-reply-policy>\n\nraw user text"
        raw = "raw user text"

        class FakeAgent:
            def __init__(self):
                self.messages_lock = threading.Lock()
                self.messages = [
                    {"role": "user", "content": [{"type": "text", "text": "older"}]},
                    {"role": "assistant", "content": [{"type": "text", "text": "older reply"}]},
                    {"role": "user", "content": [{"type": "text", "text": enhanced}]},
                ]
                self._last_run_new_messages = [
                    {"role": "user", "content": [{"type": "text", "text": enhanced}]},
                    {"role": "assistant", "content": [{"type": "text", "text": "answer"}]},
                ]

        agent = FakeAgent()

        changed = self._bridge()._sanitize_wechat_group_runtime_messages(agent, enhanced, raw)

        self.assertTrue(changed)
        self.assertEqual(raw, agent.messages[-1]["content"][0]["text"])
        self.assertEqual(raw, agent._last_run_new_messages[0]["content"][0]["text"])
        self.assertEqual("older", agent.messages[0]["content"][0]["text"])

    def test_observe_only_snapshot_restores_messages_last_run_and_executor(self):
        previous_executor = object()

        class FakeAgent:
            def __init__(self):
                self.messages_lock = threading.Lock()
                self.messages = [{"role": "user", "content": "旧投屏历史"}]
                self._last_run_new_messages = [{"role": "assistant", "content": "旧回复"}]
                self.stream_executor = previous_executor

        agent = FakeAgent()
        bridge = self._bridge()

        snapshot = bridge._prepare_agent_history_for_mode(agent, "observe_only")
        self.assertEqual([], agent.messages)
        self.assertEqual([], agent._last_run_new_messages)

        agent.messages = [{"role": "user", "content": "当前增强消息"}]
        agent._last_run_new_messages = [{"role": "assistant", "content": "当前回复"}]
        agent.stream_executor = object()
        bridge._restore_agent_history_snapshot(agent, snapshot)

        self.assertEqual([{"role": "user", "content": "旧投屏历史"}], agent.messages)
        self.assertEqual([{"role": "assistant", "content": "旧回复"}], agent._last_run_new_messages)
        self.assertIs(previous_executor, agent.stream_executor)

    def test_fresh_mode_discards_runtime_history_and_advances_store_boundary(self):
        class FakeAgent:
            def __init__(self):
                self.messages_lock = threading.Lock()
                self.messages = [{"role": "user", "content": "数小时前旧话题"}]
                self._last_run_new_messages = []

        agent = FakeAgent()
        bridge = self._bridge()
        context = self._observe_context()
        context["wechat_group_agent_history_mode"] = "fresh"
        store = Mock()

        snapshot = bridge._prepare_agent_history_for_mode(agent, "fresh")
        with patch("agent.memory.get_conversation_store", return_value=store):
            bridge._start_fresh_persistent_context("session", context)

        self.assertIsNone(snapshot)
        self.assertEqual([], agent.messages)
        store.clear_context.assert_called_once_with("session")

    def test_conversation_store_filters_observe_only_for_model_but_keeps_ui_history(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ConversationStore(Path(tmpdir) / "conversations.db")
            store.append_messages("session", [
                {"role": "user", "content": "旧交互问题"},
                {"role": "assistant", "content": "旧交互回复"},
                {
                    "role": "user",
                    "content": "观察问题",
                    "extras": {"history_visibility": "observe_only"},
                },
                {
                    "role": "assistant",
                    "content": "观察回复",
                    "extras": {"history_visibility": "observe_only"},
                },
            ], channel_type="wechat_group")

            model_messages = store.load_messages("session", max_turns=10)
            audit_messages = store.load_messages(
                "session",
                max_turns=10,
                include_observe_only=True,
            )
            history = store.load_history_page("session", page=1, page_size=20)

        self.assertEqual(
            ["旧交互问题", "旧交互回复"],
            [message["content"] for message in model_messages],
        )
        self.assertEqual(4, len(audit_messages))
        self.assertIn("观察问题", [item["content"] for item in history["messages"]])
        self.assertIn("观察回复", [item["content"] for item in history["messages"]])

    def test_observe_only_persistence_writes_scoped_visibility_and_final_text_only(self):
        bridge = self._bridge()
        context = self._observe_context()
        store = Mock()

        with patch("agent.memory.get_conversation_store", return_value=store):
            persisted = bridge._pre_persist_user_message(
                "wechat_group:wgr_room:wgm_alice",
                "有用吗",
                context,
                clear_history=False,
            )
            bridge._persist_observe_only_assistant(
                "wechat_group:wgr_room:wgm_alice",
                "当前最终回复",
                context,
            )

        self.assertTrue(persisted)
        user_message = store.append_messages.call_args_list[0].args[1][0]
        assistant_message = store.append_messages.call_args_list[1].args[1][0]
        for message in (user_message, assistant_message):
            self.assertEqual("observe_only", message["extras"]["history_visibility"])
            self.assertEqual("wgr_room", message["extras"]["stable_room_id"])
            self.assertEqual("wgm_alice", message["extras"]["stable_member_id"])
        self.assertEqual("有用吗", user_message["content"][0]["text"])
        self.assertEqual("当前最终回复", assistant_message["content"][0]["text"])
        self.assertNotIn("thinking", str(assistant_message))
        self.assertNotIn("tool_use", str(assistant_message))

    def test_agent_reply_observe_only_restores_history_on_success_and_error(self):
        class FakeRegistry:
            def register(self, key, session_id=None):
                return threading.Event()

            def unregister(self, key):
                return None

        class FakeAgent:
            def __init__(self, fail=False):
                self.messages_lock = threading.Lock()
                self.execution_lock = threading.RLock()
                self.messages = [{"role": "user", "content": "旧投屏历史"}]
                self._last_run_new_messages = [{"role": "assistant", "content": "旧回复"}]
                self.tools = []
                self.extra_system_suffix = ""
                self.skill_manager = None
                self.model = SimpleNamespace()
                self.fail = fail
                self.starts = []

            def run_stream(self, user_message, **kwargs):
                with self.messages_lock:
                    self.starts.append(list(self.messages))
                if self.fail:
                    raise RuntimeError("model failed")
                with self.messages_lock:
                    self.messages = [
                        {"role": "user", "content": user_message},
                        {"role": "assistant", "content": "当前回复"},
                    ]
                    self._last_run_new_messages = list(self.messages)
                self.stream_executor = SimpleNamespace(files_to_send=[])
                return "当前回复"

        def run(agent):
            bridge = self._bridge()
            bridge.get_agent = lambda session_id=None: agent
            bridge._create_wechat_group_memory_tools = lambda *_args: []
            bridge._schedule_mcp_hot_reload = lambda *_args: None
            bridge._pre_persist_user_message = lambda *_args: False
            bridge._persist_observe_only_assistant = Mock()
            with patch("bridge.agent_bridge.get_cancel_registry", return_value=FakeRegistry()):
                return bridge.agent_reply("enhanced prompt", self._observe_context())

        success_agent = FakeAgent()
        success = run(success_agent)
        failed_agent = FakeAgent(fail=True)
        failed = run(failed_agent)

        self.assertEqual(ReplyType.TEXT, success.type)
        self.assertEqual(ReplyType.ERROR, failed.type)
        self.assertEqual([[]], success_agent.starts)
        self.assertEqual([[]], failed_agent.starts)
        self.assertEqual([], getattr(success_agent, "_evo_observed_messages", []))
        for agent in (success_agent, failed_agent):
            self.assertEqual([{"role": "user", "content": "旧投屏历史"}], agent.messages)
            self.assertEqual([{"role": "assistant", "content": "旧回复"}], agent._last_run_new_messages)

    def test_agent_execution_lock_serializes_two_observe_only_runs(self):
        class FakeRegistry:
            def register(self, key, session_id=None):
                return threading.Event()

            def unregister(self, key):
                return None

        class ConcurrentAgent:
            def __init__(self):
                self.messages_lock = threading.Lock()
                self.execution_lock = threading.RLock()
                self.messages = [{"role": "user", "content": "旧历史"}]
                self._last_run_new_messages = []
                self.tools = []
                self.extra_system_suffix = ""
                self.skill_manager = None
                self.model = SimpleNamespace()
                self.active = 0
                self.max_active = 0
                self.state_lock = threading.Lock()

            def run_stream(self, user_message, **kwargs):
                with self.messages_lock:
                    if self.messages:
                        raise AssertionError("observe-only run saw old history")
                with self.state_lock:
                    self.active += 1
                    self.max_active = max(self.max_active, self.active)
                time.sleep(0.03)
                with self.messages_lock:
                    self.messages = [{"role": "user", "content": user_message}]
                    self._last_run_new_messages = list(self.messages)
                self.stream_executor = SimpleNamespace(files_to_send=[])
                with self.state_lock:
                    self.active -= 1
                return "ok"

        agent = ConcurrentAgent()
        bridge = self._bridge()
        bridge.get_agent = lambda session_id=None: agent
        bridge._create_wechat_group_memory_tools = lambda *_args: []
        bridge._schedule_mcp_hot_reload = lambda *_args: None
        bridge._pre_persist_user_message = lambda *_args: False
        bridge._persist_observe_only_assistant = lambda *_args: None
        replies = []

        def invoke(index):
            context = self._observe_context()
            context["request_id"] = "request-{}".format(index)
            replies.append(bridge.agent_reply("enhanced {}".format(index), context))

        with patch("bridge.agent_bridge.get_cancel_registry", return_value=FakeRegistry()):
            threads = [threading.Thread(target=invoke, args=(index,)) for index in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=2)

        self.assertEqual(1, agent.max_active)
        self.assertEqual(2, len(replies))
        self.assertEqual([{"role": "user", "content": "旧历史"}], agent.messages)

    def test_observe_only_cancelled_file_run_restores_snapshot(self):
        class CancelledRegistry:
            def register(self, key, session_id=None):
                event = threading.Event()
                event.set()
                return event

            def unregister(self, key):
                return None

        previous_executor = SimpleNamespace(files_to_send=[])

        class FileAgent:
            def __init__(self):
                self.messages_lock = threading.Lock()
                self.execution_lock = threading.RLock()
                self.messages = [{"role": "user", "content": "旧历史"}]
                self._last_run_new_messages = []
                self.stream_executor = previous_executor
                self.tools = []
                self.extra_system_suffix = ""
                self.skill_manager = None
                self.model = SimpleNamespace()

            def run_stream(self, user_message, cancel_event=None, **kwargs):
                self.assert_cancelled = cancel_event is not None and cancel_event.is_set()
                with self.messages_lock:
                    self.messages = [{"role": "user", "content": user_message}]
                    self._last_run_new_messages = list(self.messages)
                self.stream_executor = SimpleNamespace(
                    files_to_send=[{"path": "D:/tmp/result.txt", "file_type": "file"}]
                )
                return "已取消后的部分结果"

        agent = FileAgent()
        bridge = self._bridge()
        bridge.get_agent = lambda session_id=None: agent
        bridge._create_wechat_group_memory_tools = lambda *_args: []
        bridge._schedule_mcp_hot_reload = lambda *_args: None
        bridge._pre_persist_user_message = lambda *_args: False
        bridge._persist_observe_only_assistant = lambda *_args: None
        bridge._create_file_reply = Mock(return_value=SimpleNamespace(type=ReplyType.FILE))

        with patch("bridge.agent_bridge.get_cancel_registry", return_value=CancelledRegistry()):
            reply = bridge.agent_reply("enhanced prompt", self._observe_context())

        self.assertTrue(agent.assert_cancelled)
        self.assertEqual(ReplyType.FILE, reply.type)
        self.assertEqual([{"role": "user", "content": "旧历史"}], agent.messages)
        self.assertIs(previous_executor, agent.stream_executor)
        bridge._create_file_reply.assert_called_once()


if __name__ == "__main__":
    unittest.main()
