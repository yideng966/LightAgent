import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from agent.memory.conversation_store import ConversationStore

from agent.chat.history_migration import (
    LegacyConversationRow,
    build_migration_plan,
    import_migration_plan,
    run_legacy_chat_history_migration,
)


class ChatHistoryMigrationPlanTest(unittest.TestCase):
    def test_build_migration_plan_groups_rows_by_channel_and_party(self):
        rows = [
            LegacyConversationRow(
                id=1,
                role="user",
                from_id="ID:000001",
                to_id=None,
                content="hello feishu",
                channel="FEISHU",
                timestamp="2026-06-06T19:19:45+08:00",
                external_party_id="feishu:open_id:ou_smoke",
            ),
            LegacyConversationRow(
                id=2,
                role="user",
                from_id="ID:000001",
                to_id=None,
                content="hello again",
                channel="FEISHU",
                timestamp="2026-06-06T19:20:45+08:00",
                external_party_id="feishu:open_id:ou_smoke",
            ),
            LegacyConversationRow(
                id=3,
                role="user",
                from_id="ID:000001",
                to_id=None,
                content="hello wecom",
                channel="WECOM",
                timestamp="2026-06-06T19:21:45+08:00",
                external_party_id="wecom:webhook:default",
            ),
        ]

        plan = build_migration_plan(rows)

        self.assertEqual(2, len(plan.sessions))
        self.assertEqual(3, plan.source_row_count)
        self.assertEqual(3, plan.message_count)

        session = plan.sessions[0]
        self.assertTrue(session.session_id.startswith("session_migrated_blmp_"))
        self.assertEqual("web", session.channel_type)
        self.assertIn("FEISHU", session.title)
        self.assertEqual(["user", "user"], [item.role for item in session.messages])

    def test_build_migration_plan_adds_placeholder_for_assistant_only_session(self):
        rows = [
            LegacyConversationRow(
                id=1,
                role="jarvis",
                from_id="jarvis",
                to_id="wechaty:room:%40%40room:member:%40member",
                content="explicit wechaty route regression",
                channel="WECHAT",
                timestamp="2026-06-07T17:14:29+08:00",
                external_party_id="wechaty:room:%40%40room:member:%40member",
            )
        ]

        plan = build_migration_plan(rows)

        self.assertEqual(1, len(plan.sessions))
        session = plan.sessions[0]
        self.assertEqual(["user", "assistant"], [item.role for item in session.messages])
        self.assertIn("迁移占位", session.messages[0].content)
        self.assertIn("WECHAT", session.title)


class ChatHistoryMigrationImportTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self._tmp.name)
        self.source_db = self.tmpdir / "jarvis.db"
        self.target_db = self.tmpdir / "index.db"
        self._create_source_db(self.source_db)
        self.store = ConversationStore(self.target_db)

    def tearDown(self):
        self._tmp.cleanup()

    def _create_source_db(self, db_path: Path):
        conn = sqlite3.connect(db_path)
        conn.execute(
            """
            CREATE TABLE conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                from_id TEXT NOT NULL,
                to_id TEXT,
                content TEXT NOT NULL,
                channel TEXT NOT NULL DEFAULT '',
                timestamp TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT '',
                external_party_id TEXT DEFAULT '',
                focus_absorbed INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO conversations
            (role, from_id, to_id, content, channel, timestamp, created_at, external_party_id, focus_absorbed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "user",
                    "ID:000001",
                    None,
                    "hello feishu",
                    "FEISHU",
                    "2026-06-06T19:19:45+08:00",
                    "2026-06-06 11:19:45",
                    "feishu:open_id:ou_smoke",
                    0,
                ),
                (
                    "jarvis",
                    "jarvis",
                    "feishu:open_id:ou_smoke",
                    "roger that",
                    "FEISHU",
                    "2026-06-06T19:19:50+08:00",
                    "2026-06-06 11:19:50",
                    "feishu:open_id:ou_smoke",
                    0,
                ),
            ],
        )
        conn.commit()
        conn.close()

    def test_import_migration_plan_preserves_timestamps_and_channel_type(self):
        result = run_legacy_chat_history_migration(
            source_db_path=self.source_db,
            target_db_path=self.target_db,
            dry_run=False,
            create_backup=False,
        )

        self.assertEqual(1, result.imported_sessions)
        self.assertEqual(2, result.imported_messages)

        conn = sqlite3.connect(self.target_db)
        session_row = conn.execute(
            "SELECT session_id, channel_type, title, created_at, last_active, msg_count FROM sessions"
        ).fetchone()
        message_rows = conn.execute(
            "SELECT seq, role, content, created_at FROM messages ORDER BY seq ASC"
        ).fetchall()
        conn.close()

        self.assertEqual("web", session_row[1])
        self.assertIn("FEISHU", session_row[2])
        self.assertEqual(2, session_row[5])
        self.assertEqual(
            int(datetime.fromisoformat("2026-06-06T19:19:45+08:00").timestamp()),
            session_row[3],
        )
        self.assertEqual(
            int(datetime.fromisoformat("2026-06-06T19:19:50+08:00").timestamp()),
            session_row[4],
        )
        self.assertEqual(["user", "assistant"], [row[1] for row in message_rows])
        self.assertEqual(
            int(datetime.fromisoformat("2026-06-06T19:19:45+08:00").timestamp()),
            message_rows[0][3],
        )
        self.assertIn("hello feishu", message_rows[0][2])

    def test_import_migration_plan_fails_without_duplicate_messages(self):
        plan = build_migration_plan(
            [
                LegacyConversationRow(
                    id=1,
                    role="user",
                    from_id="ID:000001",
                    to_id=None,
                    content="hello feishu",
                    channel="FEISHU",
                    timestamp="2026-06-06T19:19:45+08:00",
                    external_party_id="feishu:open_id:ou_smoke",
                )
            ]
        )
        import_migration_plan(plan, self.target_db, create_backup=False)

        with self.assertRaisesRegex(ValueError, "already exists"):
            import_migration_plan(plan, self.target_db, create_backup=False)

        conn = sqlite3.connect(self.target_db)
        self.assertEqual(1, conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0])
        self.assertEqual(1, conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0])
        conn.close()

    def test_migration_script_runs_as_standalone_file(self):
        script_path = (
            Path(__file__).resolve().parents[1]
            / "scripts"
            / "migrate_legacy_chat_history.py"
        )

        completed = subprocess.run(
            [
                sys.executable,
                str(script_path),
                "--source-db",
                str(self.source_db),
                "--target-db",
                str(self.target_db),
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertIn('"dry_run": true', completed.stdout)


if __name__ == "__main__":
    unittest.main()
