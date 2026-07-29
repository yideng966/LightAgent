import sqlite3
import tempfile
import time
import unittest
from pathlib import Path

from agent.memory.conversation_store import ConversationStore
from channel.wechat_group.wechat_group_session_policy import (
    ACTION_NEW_THREAD,
    ACTION_OBSERVE_ONLY,
    ACTION_RESUME_THREAD,
    WechatGroupSessionPolicy,
    build_wechat_group_owner_session_id,
)
from config import conf


class WechatGroupConversationThreadStoreTest(unittest.TestCase):
    def test_thread_messages_are_isolated_without_advancing_context_boundary(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ConversationStore(Path(tmpdir) / "conversations.db")
            session_id = "wechat_group:wgr_room:wgm_alice"
            store.append_messages(
                session_id,
                [{"role": "user", "content": "legacy"}],
                channel_type="wechat_group",
            )
            before = store.get_context_start_seq(session_id)

            store.create_thread(
                session_id,
                "wgt_one",
                stable_room_id="wgr_room",
                stable_member_id="wgm_alice",
            )
            store.append_messages(
                session_id,
                [
                    {"role": "user", "content": "first question"},
                    {"role": "assistant", "content": "first answer"},
                ],
                channel_type="wechat_group",
                thread_id="wgt_one",
            )
            store.create_thread(
                session_id,
                "wgt_two",
                stable_room_id="wgr_room",
                stable_member_id="wgm_alice",
            )
            store.append_messages(
                session_id,
                [
                    {"role": "user", "content": "second question"},
                    {"role": "assistant", "content": "second answer"},
                ],
                channel_type="wechat_group",
                thread_id="wgt_two",
            )

            self.assertEqual(before, store.get_context_start_seq(session_id))
            self.assertEqual(
                ["first question", "first answer"],
                [item["content"] for item in store.load_messages(
                    session_id, thread_id="wgt_one"
                )],
            )
            self.assertEqual(
                ["second question", "second answer"],
                [item["content"] for item in store.load_messages(
                    session_id, thread_id="wgt_two"
                )],
            )
            self.assertEqual("wgt_two", store.get_active_thread(session_id)["thread_id"])
            self.assertEqual("closed", store.get_thread(session_id, "wgt_one")["status"])

    def test_existing_database_migrates_thread_column(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "legacy.db"
            conn = sqlite3.connect(str(db_path))
            conn.executescript(
                """
                CREATE TABLE sessions (
                    session_id TEXT PRIMARY KEY,
                    channel_type TEXT NOT NULL DEFAULT '',
                    title TEXT NOT NULL DEFAULT '',
                    context_start_seq INTEGER NOT NULL DEFAULT 0,
                    created_at INTEGER NOT NULL,
                    last_active INTEGER NOT NULL,
                    msg_count INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    seq INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    extras TEXT NOT NULL DEFAULT '',
                    UNIQUE (session_id, seq)
                );
                """
            )
            conn.close()

            store = ConversationStore(db_path)
            store.append_messages(
                "session",
                [{"role": "user", "content": "threaded"}],
                thread_id="wgt_migrated",
            )
            check = sqlite3.connect(str(db_path))
            columns = {
                row[1] for row in check.execute("PRAGMA table_info(messages)").fetchall()
            }
            check.close()

            self.assertIn("thread_id", columns)
            self.assertEqual(
                ["threaded"],
                [item["content"] for item in store.load_messages(
                    "session", thread_id="wgt_migrated"
                )],
            )

    def test_cleanup_old_sessions_deletes_thread_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "conversations.db"
            store = ConversationStore(db_path)
            store.append_messages(
                "old-session",
                [{"role": "user", "content": "old"}],
                channel_type="wechat_group",
            )
            store.create_thread("old-session", "wgt_old")
            conn = sqlite3.connect(str(db_path))
            try:
                conn.execute(
                    "UPDATE sessions SET last_active = ? WHERE session_id = ?",
                    (int(time.time()) - 10 * 86400, "old-session"),
                )
                conn.commit()
            finally:
                conn.close()

            deleted = store.cleanup_old_sessions(max_age_days=1)

            self.assertEqual(1, deleted)
            self.assertIsNone(store.get_thread("old-session", "wgt_old"))


class WechatGroupSessionPolicyTest(unittest.TestCase):
    def setUp(self):
        self.original = {
            "wechat_group_session_scope": conf().get("wechat_group_session_scope"),
            "group_shared_session": conf().get("group_shared_session"),
            "wechat_group_thread_followup_ttl_minutes": conf().get(
                "wechat_group_thread_followup_ttl_minutes"
            ),
        }
        conf()["wechat_group_session_scope"] = "member"
        conf()["group_shared_session"] = False
        conf()["wechat_group_thread_followup_ttl_minutes"] = 15
        self.tempdir = tempfile.TemporaryDirectory()
        self.store = ConversationStore(Path(self.tempdir.name) / "conversations.db")
        self.policy = WechatGroupSessionPolicy(store=self.store)

    def tearDown(self):
        self.tempdir.cleanup()
        for key, value in self.original.items():
            if value is None:
                conf().pop(key, None)
            else:
                conf()[key] = value

    def test_independent_request_then_explicit_followup_reuses_thread(self):
        first = self.policy.resolve(
            "wgr_room",
            "wgm_alice",
            trigger_source="direct_reply",
            text="2+2 等于几",
        )
        self.assertEqual(ACTION_NEW_THREAD, first.action)
        self.policy.ensure_thread(
            first,
            stable_room_id="wgr_room",
            stable_member_id="wgm_alice",
            message_id="msg-1",
        )

        followup = self.policy.resolve(
            "wgr_room",
            "wgm_alice",
            trigger_source="direct_reply",
            text="继续刚才你说的",
        )

        self.assertEqual(ACTION_RESUME_THREAD, followup.action)
        self.assertEqual(first.thread_id, followup.thread_id)

    def test_ambient_group_message_is_observe_only(self):
        decision = self.policy.resolve(
            "wgr_room",
            "wgm_alice",
            trigger_source="free_reply",
            text="大家觉得呢",
            is_free_reply=True,
            local_decision={"addressee": {"target_kind": "group"}},
            llm_decision={"target": "group", "is_followup_to_bot": False},
        )

        self.assertEqual(ACTION_OBSERVE_ONLY, decision.action)
        self.assertEqual("", decision.thread_id)

    def test_other_member_cannot_resume_active_thread(self):
        alice = self.policy.resolve(
            "wgr_room",
            "wgm_alice",
            trigger_source="direct_reply",
            text="查一下天气",
        )
        self.policy.ensure_thread(alice, "wgr_room", "wgm_alice", "msg-1")

        bob = self.policy.resolve(
            "wgr_room",
            "wgm_bob",
            trigger_source="direct_reply",
            text="继续刚才你说的",
        )

        self.assertEqual(ACTION_NEW_THREAD, bob.action)
        self.assertNotEqual(alice.thread_id, bob.thread_id)

    def test_owner_scope_can_explicitly_use_room(self):
        conf()["wechat_group_session_scope"] = "room"
        self.assertEqual(
            "wechat_group:wgr_room",
            build_wechat_group_owner_session_id("wgr_room", "wgm_alice"),
        )


if __name__ == "__main__":
    unittest.main()
