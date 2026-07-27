import tempfile
import unittest
from pathlib import Path

from channel.wechat_group.wechat_group_archive import WechatGroupArchive


class WechatGroupMemoryMaterialTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.archive = WechatGroupArchive(str(Path(self.temp_dir.name) / "archive.db"))

    def tearDown(self):
        self.temp_dir.cleanup()

    def _record(self, message_id, room, text, ts, member="wgm_secret", stable=True):
        self.archive.record_message(
            message_id=message_id,
            room_id=room,
            stable_room_id=room if stable else "",
            sender_id="runtime-member",
            stable_member_id=member,
            message_type="text",
            text=text,
            created_at=ts,
        )

    def test_material_is_stable_room_scoped_and_uses_opaque_speakers(self):
        from channel.wechat_group.wechat_group_memory_material import WechatGroupMemoryMaterialBuilder

        self._record("a1", "wgr_a", "Release is every Friday", 100)
        self._record("legacy-a", "wgr_a", "Legacy scoped agreement", 110, stable=False)
        self._record("b1", "wgr_b", "B room secret", 120, member="wgm_b")

        batch = WechatGroupMemoryMaterialBuilder(self.archive).build(
            "wgr_a", after_row_id=0, limit=20, window_minutes=120
        )

        self.assertEqual(["a1", "legacy-a"], batch.evidence_message_ids)
        rendered = "\n".join(item["text"] for item in batch.messages)
        self.assertNotIn("B room secret", rendered)
        self.assertNotIn("wgm_secret", str(batch.messages))
        self.assertNotIn("runtime-member", str(batch.messages))
        self.assertRegex(batch.messages[0]["speaker_token"], r"^speaker_[0-9]{3}$")

    def test_unsafe_transport_and_sensitive_text_are_filtered(self):
        from channel.wechat_group.wechat_group_memory_material import WechatGroupMemoryMaterialBuilder

        self._record("safe", "wgr_a", "The release window is Friday", 100)
        self._record("xml", "wgr_a", "<msg><appmsg>transport</appmsg></msg>", 110)
        self._record("path", "wgr_a", r"Read C:\\Users\\alice\\secret.txt", 120)
        self._record("secret", "wgr_a", "api_key=sk-super-secret-value", 130)
        self._record("base64", "wgr_a", "A" * 300 + "==", 140)
        self._record("url", "wgr_a", "Docs https://example.com/page?token=secret&x=1", 150)

        batch = WechatGroupMemoryMaterialBuilder(self.archive).build(
            "wgr_a", after_row_id=0, limit=20, window_minutes=120
        )

        self.assertEqual(["safe", "url"], batch.evidence_message_ids)
        rendered = "\n".join(item["text"] for item in batch.messages)
        self.assertIn("https://example.com/page", rendered)
        self.assertNotIn("token=", rendered)
        self.assertEqual(6, batch.scanned_count)

    def test_window_starts_at_first_pending_text_and_does_not_skip_later_rows(self):
        from channel.wechat_group.wechat_group_memory_material import WechatGroupMemoryMaterialBuilder

        self._record("first", "wgr_a", "first durable fact", 100)
        self._record("inside", "wgr_a", "inside window", 150)
        self._record("later", "wgr_a", "later window", 1000)

        builder = WechatGroupMemoryMaterialBuilder(self.archive)
        first = builder.build("wgr_a", after_row_id=0, limit=20, window_minutes=2)
        second = builder.build("wgr_a", after_row_id=first.batch_end_row_id, limit=20, window_minutes=2)

        self.assertEqual(["first", "inside"], first.evidence_message_ids)
        self.assertEqual(["later"], second.evidence_message_ids)


if __name__ == "__main__":
    unittest.main()
