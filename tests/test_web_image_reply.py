import unittest
from queue import Queue
from unittest.mock import patch
from urllib.parse import quote

from bridge.context import Context, ContextType
from bridge.reply import Reply, ReplyType
from channel.web.web_channel import WebChannel


class WebImageReplyTest(unittest.TestCase):
    def setUp(self):
        self.channel = WebChannel()
        self.channel.request_to_session.clear()
        self.channel.sse_queues.clear()
        self.channel.session_queues.clear()

    def tearDown(self):
        self.channel.request_to_session.clear()
        self.channel.sse_queues.clear()
        self.channel.session_queues.clear()

    def test_image_create_sends_local_image_and_done_over_sse(self):
        request_id = "image-request"
        session_id = "image-session"
        image_path = "/home/agent/lightagent/images/generated image.png"
        events = Queue()
        self.channel.request_to_session[request_id] = session_id
        self.channel.sse_queues[request_id] = events
        context = Context(ContextType.IMAGE_CREATE, "draw a cat")
        context["request_id"] = request_id

        with patch.object(
            self.channel,
            "_fetch_latest_pair_seqs",
            return_value={"user_seq": 10, "bot_seq": 11},
        ):
            self.channel.send(Reply(ReplyType.IMAGE, image_path), context)

        image_event = events.get_nowait()
        done_event = events.get_nowait()
        self.assertTrue(events.empty())
        self.assertEqual("image", image_event["type"])
        self.assertEqual(
            f"/api/file?path={quote(image_path)}",
            image_event["content"],
        )
        self.assertEqual("done", done_event["type"])
        self.assertEqual("", done_event["content"])
        self.assertEqual(10, done_event["user_seq"])
        self.assertEqual(11, done_event["bot_seq"])


if __name__ == "__main__":
    unittest.main()
