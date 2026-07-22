"""Vision raw HTTP provider must force non-streaming JSON responses."""

import unittest
from unittest.mock import MagicMock, patch

from agent.tools.vision.vision import Vision, VisionAPIError, VisionProvider


class VisionStreamPayloadTest(unittest.TestCase):
    def _provider(self) -> VisionProvider:
        return VisionProvider(
            name="newapi",
            api_key="sk-test",
            api_base="https://example.com/v1",
        )

    def test_call_api_sends_stream_false(self):
        tool = Vision()
        image_content = {
            "type": "image_url",
            "image_url": {"url": "data:image/png;base64,aaa"},
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "application/json"}
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "red"}}],
            "usage": {
                "prompt_tokens": 1,
                "completion_tokens": 1,
                "total_tokens": 2,
            },
        }

        with patch("agent.tools.vision.vision.requests.post", return_value=mock_resp) as post:
            result = tool._call_api(
                self._provider(),
                "grok-4.20-fast",
                "what color?",
                image_content,
            )

        self.assertEqual(result.status, "success")
        self.assertEqual(result.result["content"], "red")
        kwargs = post.call_args.kwargs
        self.assertEqual(kwargs["json"]["stream"], False)
        self.assertEqual(kwargs["json"]["model"], "grok-4.20-fast")
        self.assertTrue(str(post.call_args.args[0]).endswith("/chat/completions"))

    def test_call_api_invalid_json_raises_vision_error_with_preview(self):
        tool = Vision()
        image_content = {
            "type": "image_url",
            "image_url": {"url": "data:image/png;base64,aaa"},
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "text/event-stream"}
        mock_resp.text = 'data: {"error":{"message":"boom"}}\n\n'
        mock_resp.json.side_effect = ValueError("Expecting value: line 1 column 1 (char 0)")

        with patch("agent.tools.vision.vision.requests.post", return_value=mock_resp):
            with self.assertRaises(VisionAPIError) as ctx:
                tool._call_api(
                    self._provider(),
                    "grok-4.20-fast",
                    "what color?",
                    image_content,
                )

        message = str(ctx.exception)
        self.assertIn("Invalid JSON response", message)
        self.assertIn("text/event-stream", message)
        self.assertIn("data:", message)


if __name__ == "__main__":
    unittest.main()
