import threading
import time
import unittest
from types import SimpleNamespace

from channel.wechat_group.wechat_group_channel import WechatGroupChannel
from channel.wechat_group.wechat_group_reply_coordinator import (
    WechatGroupReplyCoordinator,
)
from channel.wechat_group.wechat_group_session_policy import (
    ACTION_NEW_THREAD,
    ACTION_OBSERVE_ONLY,
    ACTION_RESUME_THREAD,
)


class WechatGroupReplyCoordinatorTest(unittest.TestCase):
    def test_explicit_request_overtakes_waiting_ambient(self):
        coordinator = WechatGroupReplyCoordinator()
        release = threading.Event()
        holder_started = threading.Event()
        order = []

        def holder():
            with coordinator.turn("room", priority=0):
                holder_started.set()
                release.wait(timeout=2)

        def run(label, priority):
            with coordinator.turn("room", priority=priority):
                order.append(label)

        holder_thread = threading.Thread(target=holder)
        holder_thread.start()
        self.assertTrue(holder_started.wait(timeout=1))
        ambient = threading.Thread(target=run, args=("ambient", 10))
        direct = threading.Thread(target=run, args=("direct", 0))
        ambient.start()
        time.sleep(0.02)
        direct.start()
        time.sleep(0.02)
        release.set()
        for thread in (holder_thread, ambient, direct):
            thread.join(timeout=2)

        self.assertEqual(["direct", "ambient"], order)

    def test_same_room_is_single_flight_but_different_rooms_can_overlap(self):
        coordinator = WechatGroupReplyCoordinator()
        state_lock = threading.Lock()
        active_by_room = {}
        same_room_max = 0
        total_active = 0
        total_max = 0

        def run(room):
            nonlocal same_room_max, total_active, total_max
            with coordinator.turn(room, priority=0):
                with state_lock:
                    active_by_room[room] = active_by_room.get(room, 0) + 1
                    same_room_max = max(same_room_max, active_by_room[room])
                    total_active += 1
                    total_max = max(total_max, total_active)
                time.sleep(0.05)
                with state_lock:
                    active_by_room[room] -= 1
                    total_active -= 1

        threads = [
            threading.Thread(target=run, args=("room-a",)),
            threading.Thread(target=run, args=("room-a",)),
            threading.Thread(target=run, args=("room-b",)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=2)

        self.assertEqual(1, same_room_max)
        self.assertGreaterEqual(total_max, 2)


class WechatGroupStaleAmbientTest(unittest.TestCase):
    def test_ambient_is_suppressed_when_room_revision_changes(self):
        channel = WechatGroupChannel.__new__(WechatGroupChannel)
        channel.archive = SimpleNamespace(
            get_room_revision=lambda _room: {
                "inbound_cursor": 3,
                "assistant_cursor": 1,
            }
        )
        context = {
            "wechat_group_is_free_reply": True,
            "wechat_group_session_action": ACTION_OBSERVE_ONLY,
            "wechat_group_stable_room_id": "wgr_room",
            "wechat_group_room_revision_before": {
                "inbound_cursor": 2,
                "assistant_cursor": 1,
            },
        }

        with self.assertLogs("log", level="INFO") as captured:
            self.assertTrue(channel._should_suppress_stale_ambient(context))
        self.assertTrue(context["wechat_group_stale_suppressed"])
        self.assertIn("action=observe_only", "\n".join(captured.output))

    def test_bot_targeted_free_reply_is_not_suppressed_when_room_revision_changes(self):
        channel = WechatGroupChannel.__new__(WechatGroupChannel)
        channel.archive = SimpleNamespace(
            get_room_revision=lambda _room: self.fail(
                "bot-targeted free replies must bypass ambient revision checks"
            )
        )

        for session_action in (ACTION_NEW_THREAD, ACTION_RESUME_THREAD):
            with self.subTest(session_action=session_action):
                context = {
                    "wechat_group_is_free_reply": True,
                    "wechat_group_session_action": session_action,
                    "wechat_group_stable_room_id": "wgr_room",
                    "wechat_group_room_revision_before": {
                        "inbound_cursor": 2,
                        "assistant_cursor": 1,
                    },
                }

                self.assertFalse(channel._should_suppress_stale_ambient(context))
                self.assertNotIn("wechat_group_stale_suppressed", context)

    def test_missing_session_action_is_not_treated_as_ambient(self):
        channel = WechatGroupChannel.__new__(WechatGroupChannel)
        channel.archive = SimpleNamespace(
            get_room_revision=lambda _room: self.fail(
                "missing classification must not silently suppress a reply"
            )
        )
        context = {
            "wechat_group_is_free_reply": True,
            "wechat_group_stable_room_id": "wgr_room",
            "wechat_group_room_revision_before": {
                "inbound_cursor": 2,
                "assistant_cursor": 1,
            },
        }

        self.assertFalse(channel._should_suppress_stale_ambient(context))
        self.assertNotIn("wechat_group_stale_suppressed", context)

    def test_direct_request_is_never_suppressed_by_revision_change(self):
        channel = WechatGroupChannel.__new__(WechatGroupChannel)
        channel.archive = SimpleNamespace(get_room_revision=lambda _room: {})
        context = {
            "wechat_group_is_free_reply": False,
            "wechat_group_room_revision_before": {"inbound_cursor": 1},
        }

        self.assertFalse(channel._should_suppress_stale_ambient(context))


if __name__ == "__main__":
    unittest.main()
