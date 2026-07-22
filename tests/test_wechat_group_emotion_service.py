import os
import tempfile
import unittest

from config import conf


class WechatGroupEmotionServiceTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self._tmp.name, "wechat_group_emotion.db")
        self._original = {
            "wechat_group_emotion_decay_minutes": conf().get("wechat_group_emotion_decay_minutes"),
            "wechat_group_emotion_default_valence": conf().get("wechat_group_emotion_default_valence"),
            "wechat_group_emotion_default_energy": conf().get("wechat_group_emotion_default_energy"),
            "wechat_group_emotion_default_sociability": conf().get("wechat_group_emotion_default_sociability"),
            "wechat_group_free_reply_time_rules_enabled": conf().get("wechat_group_free_reply_time_rules_enabled"),
            "wechat_group_free_reply_time_rules": conf().get("wechat_group_free_reply_time_rules"),
        }

    def tearDown(self):
        for key, value in self._original.items():
            if value is None:
                conf().pop(key, None)
            else:
                conf()[key] = value
        self._tmp.cleanup()

    def test_get_state_uses_configured_defaults(self):
        from channel.wechat_group.wechat_group_emotion_service import WechatGroupEmotionService
        from channel.wechat_group.wechat_group_emotion_store import WechatGroupEmotionStore

        conf()["wechat_group_emotion_default_valence"] = -0.1
        conf()["wechat_group_emotion_default_energy"] = 0.6
        conf()["wechat_group_emotion_default_sociability"] = 0.55
        service = WechatGroupEmotionService(store=WechatGroupEmotionStore(self.db_path))

        state = service.get_state("room@@abc", now=100)

        self.assertEqual("room@@abc", state["room_id"])
        self.assertEqual(-0.1, state["valence"])
        self.assertEqual(0.6, state["energy"])
        self.assertEqual(0.55, state["sociability"])

    def test_observe_message_updates_sociability_and_energy(self):
        from channel.wechat_group.wechat_group_emotion_service import WechatGroupEmotionService
        from channel.wechat_group.wechat_group_emotion_store import WechatGroupEmotionStore

        service = WechatGroupEmotionService(store=WechatGroupEmotionStore(self.db_path))

        engaged = service.observe_message(
            room_id="room@@abc",
            text="@bot 这周五发版可以吗？",
            is_at=True,
            now=100,
        )
        cooled = service.observe_message(
            room_id="room@@abc",
            text="嗯",
            is_at=False,
            now=101,
        )

        self.assertGreater(engaged["sociability"], 0.45)
        self.assertGreater(engaged["energy"], 0.5)
        self.assertLess(cooled["sociability"], engaged["sociability"])

    def test_adjust_free_reply_decision_applies_emotion_and_time_rules(self):
        from channel.wechat_group.wechat_group_emotion_service import WechatGroupEmotionService
        from channel.wechat_group.wechat_group_emotion_store import WechatGroupEmotionStore

        conf()["wechat_group_free_reply_time_rules_enabled"] = True
        conf()["wechat_group_free_reply_time_rules"] = [
            {"start": "09:00", "end": "18:00", "days": ["mon", "tue", "wed", "thu", "fri"]}
        ]
        service = WechatGroupEmotionService(store=WechatGroupEmotionStore(self.db_path))
        service.store.upsert_state(
            room_id="room@@abc",
            valence=0,
            energy=0.1,
            sociability=0.1,
            last_decay_at=0,
            last_reply_at=0,
            reply_count_1h=0,
            updated_at=0,
        )
        decision = {
            "triggered": True,
            "score": 60,
            "threshold": 50,
            "activity_level": "normal",
            "reasons": ["group_question"],
            "suppressions": [],
            "room_id": "room@@abc",
            "room_name": "测试群",
            "sender_id": "wxid_alice",
            "sender_name": "Alice",
            "text_preview": "谁能总结一下？",
            "timestamp": 1710057600,  # 2024-03-10 00:00:00 UTC
        }

        adjusted = service.adjust_free_reply_decision(decision, room_id="room@@abc", now=1710057600)

        self.assertFalse(adjusted["triggered"])
        self.assertIn("emotion_low_sociability", adjusted["suppressions"])
        self.assertIn("emotion_low_energy", adjusted["suppressions"])
        self.assertIn("time_rule_blocked", adjusted["suppressions"])
        self.assertIn("emotion", adjusted)


if __name__ == "__main__":
    unittest.main()
