import tempfile
import unittest
from pathlib import Path

from channel.wechat_group.wechat_group_continuation_store import (
    WechatGroupContinuationStore,
    build_safe_continuation_capsule,
)


def tool_messages(name, arguments, result):
    return [
        {
            "role": "assistant",
            "content": [{
                "type": "tool_use",
                "id": "tool-1",
                "name": name,
                "input": arguments,
            }],
        },
        {
            "role": "user",
            "content": [{
                "type": "tool_result",
                "tool_use_id": "tool-1",
                "content": result,
            }],
        },
    ]


class WechatGroupContinuationTest(unittest.TestCase):
    def test_read_only_result_is_scoped_and_sanitized(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = WechatGroupContinuationStore(
                str(Path(tmpdir) / "continuations.db")
            )
            saved = store.save_from_messages(
                "owner-a",
                "thread-a",
                tool_messages(
                    "web_fetch",
                    {"url": "https://example.com?a=secret"},
                    "saved at C:\\private\\result.txt token=abc123 useful result",
                ),
                stable_room_id="room-a",
                stable_member_id="member-a",
            )

            block = store.get_prompt_block(
                "owner-a",
                "thread-a",
                "room-a",
                "member-a",
            )
            wrong_scope = store.get_prompt_block(
                "owner-a",
                "thread-a",
                "room-b",
                "member-a",
            )

        self.assertTrue(saved)
        self.assertIn("web_fetch", block)
        self.assertIn("[local-path]", block)
        self.assertIn("token=[redacted]", block)
        self.assertNotIn("abc123", block)
        self.assertEqual("", wrong_scope)

    def test_write_and_interactive_browser_calls_never_create_capsule(self):
        self.assertIsNone(
            build_safe_continuation_capsule(
                tool_messages("write", {"path": "a"}, "ok")
            )
        )
        self.assertIsNone(
            build_safe_continuation_capsule(
                tool_messages("browser", {"action": "click", "ref": "e1"}, "ok")
            )
        )
        self.assertIsNone(
            build_safe_continuation_capsule(
                tool_messages(
                    "browser",
                    {"action": "navigate", "url": "https://example.com"},
                    "ok",
                )
            )
        )
        self.assertIsNone(
            build_safe_continuation_capsule(
                tool_messages("wechat_group_report", {"action": "generate"}, "ok")
            )
        )


if __name__ == "__main__":
    unittest.main()
