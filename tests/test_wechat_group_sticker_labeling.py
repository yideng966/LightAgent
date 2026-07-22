import os
import sqlite3
import tempfile
import unittest

from scripts.label_wechat_group_stickers import normalize_semantic_label, prepare_sticker_image, run_labeling
from channel.wechat_group.wechat_group_sticker_labeling import (
    inspect_labeling_candidates,
    is_pending_sticker_description,
)


class WechatGroupStickerLabelingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "stickers.db")
        self.image_path = os.path.join(self.tmp.name, "sticker.gif")
        with open(self.image_path, "wb") as f:
            f.write(b"GIF89a")
        conn = sqlite3.connect(self.db_path)
        with conn:
            conn.execute(
                """
                CREATE TABLE wechat_group_stickers (
                    sticker_id TEXT PRIMARY KEY,
                    media_path TEXT NOT NULL,
                    description TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active'
                )
                """
            )
            conn.execute(
                "INSERT INTO wechat_group_stickers (sticker_id, media_path, description) VALUES (?, ?, ?)",
                ("sticker-1", self.image_path, "<msg><emoji md5='abc' /></msg>"),
            )
            conn.execute(
                "INSERT INTO wechat_group_stickers (sticker_id, media_path, description) VALUES (?, ?, ?)",
                ("sticker-2", self.image_path, "猫咪开心挥手"),
            )
            conn.execute(
                "INSERT INTO wechat_group_stickers (sticker_id, media_path, description) VALUES (?, ?, ?)",
                ("sticker-3", self.image_path, "6217140779453413879"),
            )
        conn.close()

    def tearDown(self):
        self.tmp.cleanup()

    def test_normalize_semantic_label_removes_wrappers(self):
        self.assertEqual("熊猫头捂脸偷笑", normalize_semantic_label('```text\n描述："熊猫头捂脸偷笑"\n```'))
        self.assertEqual("", normalize_semantic_label("<msg><emoji /></msg>"))
        self.assertEqual("", normalize_semantic_label("这是一张群聊表情包。只输出一条中文短语"))
        self.assertEqual("", normalize_semantic_label("这是一个表情包，主体表情丰富，表情丰富"))

    def test_prepare_sticker_image_converts_gif_to_png_contact_sheet(self):
        from PIL import Image

        gif_path = os.path.join(self.tmp.name, "animated.gif")
        frames = [Image.new("RGB", (12, 10), color) for color in ("red", "green", "blue")]
        frames[0].save(gif_path, save_all=True, append_images=frames[1:], duration=50, loop=0)

        prepared, cleanup = prepare_sticker_image(gif_path)
        try:
            self.assertTrue(prepared.endswith(".png"))
            self.assertEqual(prepared, cleanup)
            with Image.open(prepared) as image:
                self.assertEqual("PNG", image.format)
                self.assertGreaterEqual(image.width, 12)
        finally:
            if os.path.isfile(cleanup):
                os.remove(cleanup)

    def test_run_labeling_updates_only_legacy_xml_and_creates_backup(self):
        report = run_labeling(
            self.db_path,
            apply=True,
            delay_seconds=0,
            labeler=lambda _: "熊猫头捂脸偷笑",
        )

        self.assertEqual(1, report["candidates"])
        self.assertEqual(1, report["updated"])
        self.assertEqual(0, report["failed"])
        self.assertTrue(os.path.isfile(report["backup_path"]))
        conn = sqlite3.connect(self.db_path)
        rows = dict(conn.execute("SELECT sticker_id, description FROM wechat_group_stickers"))
        conn.close()
        self.assertEqual("熊猫头捂脸偷笑", rows["sticker-1"])
        self.assertEqual("猫咪开心挥手", rows["sticker-2"])
        self.assertEqual("6217140779453413879", rows["sticker-3"])

    def test_run_labeling_can_target_only_opaque_descriptions(self):
        report = run_labeling(
            self.db_path,
            apply=True,
            delay_seconds=0,
            description_type="opaque",
            workers=2,
            labeler=lambda _: "小猫捂嘴偷笑",
        )

        self.assertEqual(1, report["candidates"])
        self.assertEqual(1, report["updated"])
        conn = sqlite3.connect(self.db_path)
        rows = dict(conn.execute("SELECT sticker_id, description FROM wechat_group_stickers"))
        conn.close()
        self.assertIn("<emoji", rows["sticker-1"])
        self.assertEqual("小猫捂嘴偷笑", rows["sticker-3"])

    def test_failed_label_remains_resumable(self):
        report = run_labeling(
            self.db_path,
            apply=True,
            delay_seconds=0,
            labeler=lambda _: "",
        )

        self.assertEqual(0, report["updated"])
        self.assertEqual(1, report["failed"])
        conn = sqlite3.connect(self.db_path)
        description = conn.execute(
            "SELECT description FROM wechat_group_stickers WHERE sticker_id = 'sticker-1'"
        ).fetchone()[0]
        conn.close()
        self.assertIn("<emoji", description)

    def test_empty_image_is_not_sent_to_labeler(self):
        empty_path = os.path.join(self.tmp.name, "empty.jpg")
        open(empty_path, "wb").close()
        conn = sqlite3.connect(self.db_path)
        with conn:
            conn.execute(
                "UPDATE wechat_group_stickers SET media_path = ? WHERE sticker_id = 'sticker-1'",
                (empty_path,),
            )
        conn.close()
        calls = []

        report = run_labeling(
            self.db_path,
            apply=True,
            delay_seconds=0,
            labeler=lambda path: calls.append(path) or "不应调用",
        )

        self.assertEqual(1, report["empty_files"])
        self.assertEqual([], calls)
        self.assertEqual(0, report["updated"])

    def test_pending_description_detection_is_explicit(self):
        self.assertTrue(is_pending_sticker_description(""))
        self.assertTrue(is_pending_sticker_description("群聊表情包"))
        self.assertTrue(is_pending_sticker_description("<msg><emoji md5='abc' /></msg>"))
        self.assertTrue(is_pending_sticker_description("6217140779453413879"))
        self.assertTrue(is_pending_sticker_description("0123456789abcdef0123456789abcdef"))
        self.assertFalse(is_pending_sticker_description("熊猫头捂脸偷笑"))

    def test_pending_status_is_room_scoped_and_reports_file_health(self):
        from channel.wechat_group.wechat_group_sticker_store import WechatGroupStickerStore

        scoped_db = os.path.join(self.tmp.name, "scoped.db")
        store = WechatGroupStickerStore(scoped_db)
        empty_path = os.path.join(self.tmp.name, "empty.png")
        open(empty_path, "wb").close()
        missing_path = os.path.join(self.tmp.name, "missing.png")
        store.upsert_sticker("room-a", "hash-a", self.image_path, "群聊表情包", created_at=1)
        store.upsert_sticker("room-a", "hash-normal", self.image_path, "猫咪开心挥手", created_at=1)
        store.upsert_sticker("room-a", "hash-empty", empty_path, "表情包", created_at=1)
        store.upsert_sticker("room-a", "hash-missing", missing_path, "sticker", created_at=1)
        store.upsert_sticker("room-a", "hash-disabled", self.image_path, "群聊表情包", status="disabled", created_at=1)
        store.upsert_sticker("room-b", "hash-b", self.image_path, "群聊表情包", created_at=1)

        report = inspect_labeling_candidates(scoped_db, room_id="room-a")

        self.assertEqual(3, report["pending"])
        self.assertEqual(1, report["processable"])
        self.assertEqual(1, report["missing_files"])
        self.assertEqual(1, report["empty_files"])

    def test_pending_labeling_updates_only_selected_room(self):
        from channel.wechat_group.wechat_group_sticker_store import WechatGroupStickerStore

        scoped_db = os.path.join(self.tmp.name, "room-labeling.db")
        store = WechatGroupStickerStore(scoped_db)
        first = store.upsert_sticker("room-a", "hash-a", self.image_path, "群聊表情包", created_at=1)
        second = store.upsert_sticker("room-b", "hash-b", self.image_path, "群聊表情包", created_at=1)

        report = run_labeling(
            scoped_db,
            apply=True,
            delay_seconds=0,
            description_type="pending",
            room_id="room-a",
            progress_output=False,
            labeler=lambda _: "熊猫头捂脸偷笑",
        )

        self.assertEqual(1, report["updated"])
        self.assertEqual("熊猫头捂脸偷笑", store.get_sticker("room-a", first["sticker_id"])["description"])
        self.assertEqual("群聊表情包", store.get_sticker("room-b", second["sticker_id"])["description"])

    def test_batch_label_does_not_overwrite_concurrent_manual_edit(self):
        from channel.wechat_group.wechat_group_sticker_store import WechatGroupStickerStore

        scoped_db = os.path.join(self.tmp.name, "concurrent.db")
        store = WechatGroupStickerStore(scoped_db)
        row = store.upsert_sticker("room-a", "hash-a", self.image_path, "群聊表情包", created_at=1)

        def labeler(_):
            store.update_description(
                "room-a",
                row["sticker_id"],
                "人工修正后的描述",
                expected_description="群聊表情包",
            )
            return "Vision 返回的描述"

        report = run_labeling(
            scoped_db,
            apply=True,
            delay_seconds=0,
            description_type="pending",
            room_id="room-a",
            progress_output=False,
            labeler=labeler,
        )

        self.assertEqual(0, report["updated"])
        self.assertEqual(1, report["skipped_changed"])
        self.assertEqual("人工修正后的描述", store.get_sticker("room-a", row["sticker_id"])["description"])


if __name__ == "__main__":
    unittest.main()
