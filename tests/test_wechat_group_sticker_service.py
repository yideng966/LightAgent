import json
import os
import tempfile
import threading
import time
import unittest

from config import conf


class WechatGroupStickerServiceTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self._tmp.name, "wechat_group_sticker.db")
        self.image_path = os.path.join(self._tmp.name, "happy-cat.png")
        with open(self.image_path, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\nfake-sticker-data")
        self._original = {
            "wechat_group_sticker_max_size_mb": conf().get("wechat_group_sticker_max_size_mb"),
            "wechat_group_sticker_daily_send_limit": conf().get("wechat_group_sticker_daily_send_limit"),
            "wechat_group_sticker_storage_dir": conf().get("wechat_group_sticker_storage_dir"),
            "wechat_group_sticker_online_search_enabled": conf().get("wechat_group_sticker_online_search_enabled"),
            "wechat_group_sticker_online_provider": conf().get("wechat_group_sticker_online_provider"),
            "wechat_group_sticker_online_endpoint": conf().get("wechat_group_sticker_online_endpoint"),
            "wechat_group_sticker_online_allowed_domains": conf().get("wechat_group_sticker_online_allowed_domains"),
            "wechat_group_sticker_online_allow_gif": conf().get("wechat_group_sticker_online_allow_gif"),
            "wechat_group_sticker_online_search_count": conf().get("wechat_group_sticker_online_search_count"),
            "wechat_group_sticker_cooldown_seconds": conf().get("wechat_group_sticker_cooldown_seconds"),
        }

    def tearDown(self):
        for key, value in self._original.items():
            if value is None:
                conf().pop(key, None)
            else:
                conf()[key] = value
        self._tmp.cleanup()

    def test_collect_from_message_persists_active_sticker(self):
        from channel.wechat_group.wechat_group_sticker_service import WechatGroupStickerService
        from channel.wechat_group.wechat_group_sticker_store import WechatGroupStickerStore

        service = WechatGroupStickerService(store=WechatGroupStickerStore(self.db_path))

        row = service.collect_from_message(
            room_id="room@@abc",
            media_path=self.image_path,
            source_message_id="msg-1",
            description="happy cat reaction",
            now=100,
        )

        self.assertEqual("room@@abc", row["room_id"])
        self.assertEqual("active", row["status"])
        self.assertEqual("happy cat reaction", row["description"])
        self.assertEqual(0, row["use_count"])
        self.assertTrue(row["file_hash"])

    def test_collect_from_message_skips_empty_sticker_file(self):
        from channel.wechat_group.wechat_group_sticker_service import WechatGroupStickerService
        from channel.wechat_group.wechat_group_sticker_store import WechatGroupStickerStore

        empty_path = os.path.join(self._tmp.name, "empty.gif")
        open(empty_path, "wb").close()
        service = WechatGroupStickerService(store=WechatGroupStickerStore(self.db_path))

        row = service.collect_from_message(
            room_id="room@@abc",
            media_path=empty_path,
            source_message_id="msg-empty",
            description="empty reaction",
            now=100,
        )

        self.assertEqual({}, row)
        self.assertEqual([], service.list_stickers("room@@abc", status=""))

    def test_collect_from_message_replaces_transport_xml_description(self):
        from channel.wechat_group.wechat_group_sticker_service import WechatGroupStickerService
        from channel.wechat_group.wechat_group_sticker_store import WechatGroupStickerStore

        service = WechatGroupStickerService(store=WechatGroupStickerStore(self.db_path))

        row = service.collect_from_message(
            room_id="room@@abc",
            media_path=self.image_path,
            source_message_id="msg-xml",
            description="<msg><emoji md5='abc' /></msg>",
            now=100,
        )

        self.assertEqual("happy-cat", row["description"])

    def test_collect_from_message_replaces_xml_description_and_numeric_file_name(self):
        from channel.wechat_group.wechat_group_sticker_service import WechatGroupStickerService
        from channel.wechat_group.wechat_group_sticker_store import WechatGroupStickerStore

        numeric_path = os.path.join(self._tmp.name, "4504068834255361684.gif")
        with open(numeric_path, "wb") as f:
            f.write(b"GIF89a")
        service = WechatGroupStickerService(store=WechatGroupStickerStore(self.db_path))

        row = service.collect_from_message(
            room_id="room@@abc",
            media_path=numeric_path,
            source_message_id="msg-xml-numeric",
            description="<msg><emoji md5='abc' /></msg>",
            now=100,
        )

        self.assertEqual("群聊表情包", row["description"])

    def test_collect_from_message_replaces_numeric_description(self):
        from channel.wechat_group.wechat_group_sticker_service import WechatGroupStickerService
        from channel.wechat_group.wechat_group_sticker_store import WechatGroupStickerStore

        numeric_path = os.path.join(self._tmp.name, "6217140779453413879.gif")
        with open(numeric_path, "wb") as f:
            f.write(b"GIF89a")
        service = WechatGroupStickerService(store=WechatGroupStickerStore(self.db_path))

        row = service.collect_from_message(
            room_id="room@@abc",
            media_path=numeric_path,
            source_message_id="msg-numeric",
            description="6217140779453413879",
            now=100,
        )

        self.assertEqual("群聊表情包", row["description"])

    def test_collect_from_message_dedupes_same_file_in_same_room(self):
        from channel.wechat_group.wechat_group_sticker_service import WechatGroupStickerService
        from channel.wechat_group.wechat_group_sticker_store import WechatGroupStickerStore

        service = WechatGroupStickerService(store=WechatGroupStickerStore(self.db_path))
        first = service.collect_from_message(
            room_id="room@@abc",
            media_path=self.image_path,
            source_message_id="msg-1",
            description="happy cat reaction",
            now=100,
        )
        second = service.collect_from_message(
            room_id="room@@abc",
            media_path=self.image_path,
            source_message_id="msg-2",
            description="happy cat reaction",
            now=101,
        )
        rows = service.search_stickers("room@@abc", query="happy", limit=5)

        self.assertEqual(first["sticker_id"], second["sticker_id"])
        self.assertEqual(1, len(rows))

    def test_prepare_send_result_honors_daily_limit_after_record_sent(self):
        from channel.wechat_group.wechat_group_sticker_service import WechatGroupStickerService
        from channel.wechat_group.wechat_group_sticker_store import WechatGroupStickerStore

        conf()["wechat_group_sticker_daily_send_limit"] = 1
        service = WechatGroupStickerService(store=WechatGroupStickerStore(self.db_path))
        row = service.collect_from_message(
            room_id="room@@abc",
            media_path=self.image_path,
            source_message_id="msg-1",
            description="happy cat reaction",
            now=100,
        )

        result = service.prepare_send_result("room@@abc", row["sticker_id"], message="send this", now=100)
        service.record_sent("room@@abc", row["sticker_id"], now=101)

        self.assertEqual("file_to_send", result["type"])
        self.assertEqual(row["sticker_id"], result["sticker_id"])
        self.assertEqual(self.image_path, result["path"])
        with self.assertRaises(ValueError):
            service.prepare_send_result("room@@abc", row["sticker_id"], now=102)

    def test_disable_sticker_excludes_it_from_active_search(self):
        from channel.wechat_group.wechat_group_sticker_service import WechatGroupStickerService
        from channel.wechat_group.wechat_group_sticker_store import WechatGroupStickerStore

        service = WechatGroupStickerService(store=WechatGroupStickerStore(self.db_path))
        row = service.collect_from_message(
            room_id="room@@abc",
            media_path=self.image_path,
            source_message_id="msg-1",
            description="happy cat reaction",
            now=100,
        )

        updated = service.disable_sticker("room@@abc", row["sticker_id"])
        rows = service.search_stickers("room@@abc", query="happy", limit=5)

        self.assertEqual("disabled", updated["status"])
        self.assertEqual([], rows)

    def test_manual_description_update_is_room_scoped_and_survives_recollect(self):
        from channel.wechat_group.wechat_group_sticker_service import WechatGroupStickerService
        from channel.wechat_group.wechat_group_sticker_store import WechatGroupStickerStore

        service = WechatGroupStickerService(store=WechatGroupStickerStore(self.db_path))
        row = service.collect_from_message(
            room_id="room@@abc",
            media_path=self.image_path,
            source_message_id="msg-1",
            description="群聊表情包",
            now=100,
        )

        updated = service.update_description(
            "room@@abc",
            row["sticker_id"],
            "  猫咪举手\n表示赞同  ",
            expected_description="群聊表情包",
        )
        recollected = service.collect_from_message(
            room_id="room@@abc",
            media_path=self.image_path,
            source_message_id="msg-2",
            description="happy-cat",
            now=101,
        )

        self.assertEqual("猫咪举手 表示赞同", updated["description"])
        self.assertEqual("猫咪举手 表示赞同", recollected["description"])
        self.assertEqual(1, len(service.search_stickers("room@@abc", query="赞同")))
        with self.assertRaises(ValueError):
            service.update_description("room@@other", row["sticker_id"], "不应跨群更新")

    def test_manual_description_rejects_unsafe_or_stale_values(self):
        from channel.wechat_group.wechat_group_sticker_service import WechatGroupStickerService
        from channel.wechat_group.wechat_group_sticker_store import WechatGroupStickerStore

        service = WechatGroupStickerService(store=WechatGroupStickerStore(self.db_path))
        row = service.collect_from_message(
            room_id="room@@abc",
            media_path=self.image_path,
            description="群聊表情包",
            now=100,
        )

        for value in ("", "群聊表情包", "6217140779453413879", "<msg><emoji /></msg>"):
            with self.assertRaises(ValueError):
                service.update_description("room@@abc", row["sticker_id"], value)
        with self.assertRaises(ValueError):
            service.update_description(
                "room@@abc",
                row["sticker_id"],
                "有效描述",
                expected_description="已经变化的旧值",
            )

    def test_manual_description_uses_current_value_when_expected_is_omitted(self):
        from channel.wechat_group.wechat_group_sticker_service import WechatGroupStickerService

        class FakeStore:
            def __init__(self):
                self.expected_description = None

            def get_sticker(self, room_id, sticker_id):
                return {"room_id": room_id, "sticker_id": sticker_id, "description": "原描述"}

            def update_description(self, room_id, sticker_id, description, expected_description=None):
                self.expected_description = expected_description
                return {"room_id": room_id, "sticker_id": sticker_id, "description": description}

        store = FakeStore()
        service = WechatGroupStickerService(store=store)

        updated = service.update_description("room@@abc", "sticker-1", "人工修正")

        self.assertEqual("人工修正", updated["description"])
        self.assertEqual("原描述", store.expected_description)

    def test_description_status_and_background_job_are_isolated(self):
        from channel.wechat_group.wechat_group_sticker_service import WechatGroupStickerService
        from channel.wechat_group.wechat_group_sticker_store import WechatGroupStickerStore

        service = WechatGroupStickerService(store=WechatGroupStickerStore(self.db_path))
        row = service.collect_from_message(
            room_id="room@@abc",
            media_path=self.image_path,
            description="群聊表情包",
            now=100,
        )
        started = threading.Event()
        release = threading.Event()

        def labeler(_):
            started.set()
            release.wait(2)
            return "猫咪开心挥手"

        initial = service.get_description_status("room@@abc")
        job = service.start_description_labeling("room@@abc", workers=1, labeler=labeler)
        self.assertTrue(started.wait(2))

        self.assertEqual(1, initial["pending"])
        self.assertEqual("running", job["status"])
        self.assertEqual("busy", service.get_description_job_status("room@@other")["status"])
        with self.assertRaises(ValueError):
            service.start_description_labeling("room@@abc", workers=1, labeler=labeler)

        release.set()
        deadline = time.time() + 3
        completed = service.get_description_job_status("room@@abc")
        while completed["status"] == "running" and time.time() < deadline:
            time.sleep(0.02)
            completed = service.get_description_job_status("room@@abc")

        self.assertEqual("completed", completed["status"])
        self.assertEqual(1, completed["processed"])
        self.assertEqual(1, completed["updated"])
        self.assertTrue(completed["backup_created"])
        self.assertEqual("猫咪开心挥手", service.store.get_sticker("room@@abc", row["sticker_id"])["description"])

    def test_search_mixed_stickers_prefers_local_and_fills_from_online(self):
        from channel.wechat_group.wechat_group_sticker_service import WechatGroupStickerService
        from channel.wechat_group.wechat_group_sticker_store import WechatGroupStickerStore

        service = WechatGroupStickerService(store=WechatGroupStickerStore(self.db_path))
        local = service.collect_from_message(
            room_id="room@@abc",
            media_path=self.image_path,
            source_message_id="msg-1",
            description="开心猫",
            now=100,
        )

        def opener(request, timeout=0):
            return _FakeResponse({
                "data": [
                    {
                        "img_url": "https://biaoqing.gtimg.com/online.png",
                        "img_width": 240,
                        "img_height": 180,
                        "img_size": 123,
                    }
                ]
            })

        conf()["wechat_group_sticker_online_search_enabled"] = True
        conf()["wechat_group_sticker_online_allowed_domains"] = ["biaoqing.gtimg.com"]
        results = service.search_mixed_stickers(
            "room@@abc",
            query="开心",
            limit=2,
            seed="room:alice",
            online_opener=opener,
        )

        self.assertEqual(2, len(results))
        self.assertEqual("local", results[0]["source"])
        self.assertEqual(local["sticker_id"], results[0]["sticker_id"])
        self.assertEqual("online", results[1]["source"])
        self.assertTrue(results[1]["online_id"])
        self.assertNotIn("url", results[1])
        self.assertEqual("https://biaoqing.gtimg.com/online.png", results[1]["_url"])

    def test_prepare_online_send_result_downloads_to_cache_without_exposing_url(self):
        from channel.wechat_group.wechat_group_sticker_service import WechatGroupStickerService
        from channel.wechat_group.wechat_group_sticker_store import WechatGroupStickerStore

        conf()["wechat_group_sticker_storage_dir"] = self._tmp.name
        conf()["wechat_group_sticker_online_allowed_domains"] = ["biaoqing.gtimg.com"]
        service = WechatGroupStickerService(store=WechatGroupStickerStore(self.db_path))
        item = {
            "source": "online",
            "online_id": "online-1",
            "_url": "https://biaoqing.gtimg.com/happy.png",
            "description": "开心",
            "size": 0,
        }

        def opener(request, timeout=0):
            self.assertEqual("https://biaoqing.gtimg.com/happy.png", request.full_url)
            return _FakeResponse(b"\x89PNG\r\n\x1a\nonline")

        result = service.prepare_online_send_result(
            "room@@abc",
            item,
            message="send online",
            now=100,
            opener=opener,
        )

        self.assertEqual("file_to_send", result["type"])
        self.assertEqual("online", result["wechat_group_sticker_source"])
        self.assertEqual("online-1", result["online_id"])
        self.assertNotIn("url", result)
        self.assertTrue(os.path.isfile(result["path"]))
        self.assertTrue(result["path"].startswith(os.path.join(self._tmp.name, "online")))

    def test_prepare_online_send_result_enforces_size_limit(self):
        from channel.wechat_group.wechat_group_sticker_service import WechatGroupStickerService
        from channel.wechat_group.wechat_group_sticker_store import WechatGroupStickerStore

        conf()["wechat_group_sticker_storage_dir"] = self._tmp.name
        conf()["wechat_group_sticker_max_size_mb"] = 1
        service = WechatGroupStickerService(store=WechatGroupStickerStore(self.db_path))

        def opener(request, timeout=0):
            return _FakeResponse(b"x" * (1024 * 1024 + 1))

        with self.assertRaises(ValueError):
            service.prepare_online_send_result(
                "room@@abc",
                {
                    "source": "online",
                    "online_id": "online-1",
                    "_url": "https://biaoqing.gtimg.com/too-large.png",
                },
                now=100,
                opener=opener,
            )

    def test_prepare_online_send_result_honors_cooldown(self):
        from channel.wechat_group.wechat_group_sticker_service import WechatGroupStickerService
        from channel.wechat_group.wechat_group_sticker_store import WechatGroupStickerStore

        conf()["wechat_group_sticker_storage_dir"] = self._tmp.name
        conf()["wechat_group_sticker_cooldown_seconds"] = 30
        service = WechatGroupStickerService(store=WechatGroupStickerStore(self.db_path))
        item = {
            "source": "online",
            "online_id": "online-1",
            "_url": "https://biaoqing.gtimg.com/happy.png",
        }

        def opener(request, timeout=0):
            return _FakeResponse(b"\x89PNG\r\n\x1a\nonline")

        service.prepare_online_send_result("room@@abc", item, now=100, opener=opener)

        with self.assertRaises(ValueError):
            service.prepare_online_send_result("room@@abc", item, now=120, opener=opener)


class _FakeResponse:
    def __init__(self, payload, status=200, headers=None):
        self.payload = payload
        self.status = status
        self.headers = headers or {}

    def read(self):
        if isinstance(self.payload, bytes):
            return self.payload
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


if __name__ == "__main__":
    unittest.main()
