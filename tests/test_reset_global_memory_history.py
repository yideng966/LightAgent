import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from agent.memory.conversation_store import ConversationStore
from agent.memory.storage import MemoryStorage


class ResetGlobalMemoryHistoryTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name) / "workspace"
        self.workspace.mkdir()
        (self.workspace / "MEMORY.md").write_text("polluted global memory", encoding="utf-8")
        memory_dir = self.workspace / "memory"
        (memory_dir / "dreams").mkdir(parents=True)
        (memory_dir / "evolution").mkdir()
        (memory_dir / ".evolution_backups" / "backup-1").mkdir(parents=True)
        (memory_dir / "users" / "user-a").mkdir(parents=True)
        (self.workspace / "knowledge").mkdir()
        (memory_dir / "2026-07-27.md").write_text("polluted daily", encoding="utf-8")
        (memory_dir / "dreams" / "2026-07-27.md").write_text("polluted dream", encoding="utf-8")
        (memory_dir / "evolution" / "2026-07-27.md").write_text("polluted evolution", encoding="utf-8")
        (memory_dir / ".evolution_backups" / "backup-1" / "0.bak").write_text("secret", encoding="utf-8")
        (memory_dir / "users" / "user-a" / "MEMORY.md").write_text("keep user memory", encoding="utf-8")
        (self.workspace / "knowledge" / "keep.md").write_text("keep knowledge", encoding="utf-8")

        self.db_path = memory_dir / "long-term" / "index.db"
        self.db_path.parent.mkdir(parents=True)
        storage = MemoryStorage(self.db_path)
        with storage._lock:
            storage.conn.execute(
                """
                INSERT INTO chunks (
                    id, user_id, scope, source, path, start_line, end_line,
                    text, embedding, hash, scope_type, scope_id, channel_type,
                    subject_id, status
                ) VALUES (?, ?, ?, ?, ?, 1, 1, ?, NULL, ?, ?, ?, ?, ?, 'active')
                """,
                ("shared", None, "shared", "memory", "MEMORY.md", "polluted", "h1", "shared", "", "", ""),
            )
            storage.conn.execute(
                """
                INSERT INTO chunks (
                    id, user_id, scope, source, path, start_line, end_line,
                    text, embedding, hash, scope_type, scope_id, channel_type,
                    subject_id, status
                ) VALUES (?, ?, ?, ?, ?, 1, 1, ?, NULL, ?, ?, ?, ?, ?, 'active')
                """,
                ("user", "user-a", "user", "memory", "memory/users/user-a/MEMORY.md", "keep user", "h2", "user", "user-a", "", "user-a"),
            )
            storage.conn.execute(
                """
                INSERT INTO chunks (
                    id, user_id, scope, source, path, start_line, end_line,
                    text, embedding, hash, scope_type, scope_id, channel_type,
                    subject_id, status
                ) VALUES (?, ?, ?, ?, ?, 1, 1, ?, NULL, ?, ?, ?, ?, ?, 'active')
                """,
                ("knowledge", None, "shared", "knowledge", "knowledge/keep.md", "keep knowledge", "h3", "shared", "", "", ""),
            )
            for path, source in (
                ("MEMORY.md", "memory"),
                ("memory/users/user-a/MEMORY.md", "memory"),
                ("knowledge/keep.md", "knowledge"),
                ("memory/2026-07-26.md", "memory"),
            ):
                storage.conn.execute(
                    "INSERT INTO files(path, source, hash, mtime, size) VALUES (?, ?, 'hash', 1, 1)",
                    (path, source),
                )
            storage.conn.commit()
        storage.close()

        store = ConversationStore(self.db_path)
        store.append_messages(
            "wechat_group:wgr_room:wgm_member",
            [
                {"role": "user", "content": "ordinary group message"},
                {"role": "assistant", "content": "ordinary answer"},
                {"role": "user", "content": [{"type": "text", "text": "[SCHEDULED] self-evolution"}]},
                {"role": "assistant", "content": [{"type": "text", "text": "[EVOLUTION] polluted result"}]},
            ],
            channel_type="wechat_group",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_dry_run_reports_without_modifying(self):
        from scripts.reset_global_memory_history import reset_global_memory_history

        report = reset_global_memory_history(str(self.workspace), apply=False)

        self.assertEqual("planned", report["status"])
        self.assertEqual("polluted global memory", (self.workspace / "MEMORY.md").read_text(encoding="utf-8"))
        self.assertTrue((self.workspace / "memory" / "2026-07-27.md").exists())
        self.assertGreaterEqual(report["planned_file_count"], 4)
        self.assertEqual(1, report["shared_memory_chunk_count"])
        self.assertEqual(2, report["evolution_message_count"])

    def test_apply_only_removes_global_memory_and_evolution(self):
        from scripts.reset_global_memory_history import reset_global_memory_history

        report = reset_global_memory_history(str(self.workspace), apply=True)

        self.assertEqual("success", report["status"])
        self.assertNotIn("polluted", (self.workspace / "MEMORY.md").read_text(encoding="utf-8"))
        self.assertFalse((self.workspace / "memory" / "2026-07-27.md").exists())
        self.assertFalse((self.workspace / "memory" / "dreams").exists())
        self.assertFalse((self.workspace / "memory" / "evolution").exists())
        self.assertFalse((self.workspace / "memory" / ".evolution_backups").exists())
        self.assertEqual("keep user memory", (self.workspace / "memory" / "users" / "user-a" / "MEMORY.md").read_text(encoding="utf-8"))
        self.assertEqual("keep knowledge", (self.workspace / "knowledge" / "keep.md").read_text(encoding="utf-8"))

        with closing(sqlite3.connect(self.db_path)) as conn:
            chunks = dict(conn.execute("SELECT id, text FROM chunks").fetchall())
            files = {row[0] for row in conn.execute("SELECT path FROM files").fetchall()}
            messages = [json.loads(row[0]) for row in conn.execute(
                "SELECT content FROM messages WHERE session_id = ? ORDER BY seq",
                ("wechat_group:wgr_room:wgm_member",),
            ).fetchall()]
            msg_count = conn.execute(
                "SELECT msg_count FROM sessions WHERE session_id = ?",
                ("wechat_group:wgr_room:wgm_member",),
            ).fetchone()[0]

        self.assertNotIn("shared", chunks)
        self.assertIn("user", chunks)
        self.assertIn("knowledge", chunks)
        self.assertNotIn("MEMORY.md", files)
        self.assertNotIn("memory/2026-07-26.md", files)
        self.assertIn("memory/users/user-a/MEMORY.md", files)
        self.assertIn("knowledge/keep.md", files)
        self.assertEqual(["ordinary group message", "ordinary answer"], messages)
        self.assertEqual(2, msg_count)

        second = reset_global_memory_history(str(self.workspace), apply=True)
        self.assertEqual("success", second["status"])
        self.assertEqual(0, second["shared_memory_chunk_count"])
        self.assertEqual(0, second["evolution_message_count"])


if __name__ == "__main__":
    unittest.main()
