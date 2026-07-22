import os
import tempfile
import unittest

from channel.wechat_group.wechat_group_archive import WechatGroupArchive
from config import conf


LONG_WECHAT_IMAGE_TRANSPORT_XML = """<?xml version="1.0"?>
<msg>
  <img aeskey="{}" cdnthumburl="masked" md5="masked" hevc_mid_size="31347" />
</msg>
""".format("a" * 240)


class WechatGroupStyleServiceTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.style_db_path = os.path.join(self._tmp.name, "wechat_group_style.db")
        self.archive_db_path = os.path.join(self._tmp.name, "wechat_group_archive.db")
        self._original = {
            "wechat_group_style_context_limit": conf().get("wechat_group_style_context_limit"),
            "wechat_group_style_candidate_min_evidence": conf().get("wechat_group_style_candidate_min_evidence"),
            "wechat_group_style_auto_apply_enabled": conf().get("wechat_group_style_auto_apply_enabled"),
            "wechat_group_style_learning_batch_limit": conf().get("wechat_group_style_learning_batch_limit"),
        }

    def tearDown(self):
        for key, value in self._original.items():
            if value is None:
                conf().pop(key, None)
            else:
                conf()[key] = value
        self._tmp.cleanup()

    def test_refresh_candidates_from_archive_creates_reviewable_cards(self):
        from channel.wechat_group.wechat_group_style_service import WechatGroupStyleService
        from channel.wechat_group.wechat_group_style_store import WechatGroupStyleStore

        conf()["wechat_group_style_candidate_min_evidence"] = 2
        archive = WechatGroupArchive(self.archive_db_path)
        archive.record_message(
            message_id="msg-1",
            room_id="room@@abc",
            room_name="测试群",
            sender_id="wxid_alice",
            sender_nickname="Alice",
            message_type="text",
            text="先别发版，回归过了我再同步。",
            created_at=100,
        )
        archive.record_message(
            message_id="msg-2",
            room_id="room@@abc",
            room_name="测试群",
            sender_id="wxid_bob",
            sender_nickname="Bob",
            message_type="text",
            text="结论先放这：今晚不发，明早再看。",
            created_at=101,
        )
        archive.record_message(
            message_id="msg-3",
            room_id="room@@abc",
            room_name="测试群",
            sender_id="wxid_alice",
            sender_nickname="Alice",
            message_type="text",
            text="收到，我明早补一句最终安排。",
            created_at=102,
        )
        service = WechatGroupStyleService(store=WechatGroupStyleStore(self.style_db_path))

        cards = service.refresh_candidates_from_archive(archive, "room@@abc", now=103)

        self.assertEqual(1, len(cards))
        self.assertEqual("room@@abc", cards[0]["room_id"])
        self.assertEqual("candidate", cards[0]["status"])
        self.assertGreaterEqual(cards[0]["evidence_count"], 2)
        self.assertTrue(cards[0]["example"])

    def test_review_candidate_activates_prompt_block(self):
        from channel.wechat_group.wechat_group_style_service import WechatGroupStyleService
        from channel.wechat_group.wechat_group_style_store import WechatGroupStyleStore

        store = WechatGroupStyleStore(self.style_db_path)
        service = WechatGroupStyleService(store=store)
        card = store.upsert_style_card(
            room_id="room@@abc",
            intent="coordination",
            tone="direct",
            trigger_rule="适合讨论排期和执行动作时",
            avoid_rule="避免长篇铺垫和照抄群友原话",
            example="今晚先别发，等回归过了再说。",
            evidence_count=3,
            status="candidate",
        )

        active = service.review_style("room@@abc", card["style_id"], action="approve")
        block = service.build_prompt_block("room@@abc")

        self.assertEqual("active", active["status"])
        self.assertIn("<wechat-group-style>", block)
        self.assertIn("intent: coordination", block)
        self.assertIn("tone: direct", block)
        self.assertIn("今晚先别发，等回归过了再说。", block)

    def test_style_learning_ignores_legacy_text_transport_xml(self):
        from channel.wechat_group.wechat_group_style_service import WechatGroupStyleService
        from channel.wechat_group.wechat_group_style_store import WechatGroupStyleStore

        conf()["wechat_group_style_candidate_min_evidence"] = 1
        archive = WechatGroupArchive(self.archive_db_path)
        archive.record_message(
            message_id="legacy-image-as-text",
            room_id="room@@abc",
            room_name="测试群",
            sender_id="wxid_alice",
            sender_nickname="Alice",
            message_type="text",
            text=LONG_WECHAT_IMAGE_TRANSPORT_XML,
            created_at=100,
        )
        service = WechatGroupStyleService(store=WechatGroupStyleStore(self.style_db_path))

        cards = service.refresh_candidates_from_archive(archive, "room@@abc", now=101)

        self.assertEqual([], cards)

    def test_style_prompt_omits_legacy_transport_xml_example(self):
        from channel.wechat_group.wechat_group_style_service import WechatGroupStyleService
        from channel.wechat_group.wechat_group_style_store import WechatGroupStyleStore

        store = WechatGroupStyleStore(self.style_db_path)
        store.upsert_style_card(
            room_id="room@@abc",
            intent="general",
            tone="steady",
            trigger_rule="普通交流",
            avoid_rule="避免复述",
            example=LONG_WECHAT_IMAGE_TRANSPORT_XML,
            evidence_count=1,
            status="active",
        )
        service = WechatGroupStyleService(store=store)

        block = service.build_prompt_block("room@@abc")

        self.assertNotIn("example:", block)
        for transport_fragment in ("<?xml", "<img", "hevc_mid_size", "aeskey", "cdnthumburl"):
            self.assertNotIn(transport_fragment, block)


if __name__ == "__main__":
    unittest.main()
