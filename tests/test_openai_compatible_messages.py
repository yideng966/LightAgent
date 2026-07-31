# encoding:utf-8
import os
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.openai_compatible_bot import OpenAICompatibleBot


class TestOpenAICompatibleMessageConversion(unittest.TestCase):
    def test_user_text_blocks_are_converted_to_string_content(self):
        bot = OpenAICompatibleBot()
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "hello"},
                    {"type": "text", "text": "world"},
                ],
            }
        ]

        converted = bot._convert_messages_to_openai_format(messages)

        self.assertEqual(converted, [{"role": "user", "content": "hello world"}])
        self.assertIsInstance(converted[0]["content"], str)

    def test_request_options_are_allowlisted_and_forwarded(self):
        bot = OpenAICompatibleBot()
        bot.get_api_config = Mock(return_value={
            "api_key": "test-key",
            "api_base": "https://example.test/v1",
            "model": "test-model",
        })
        bot._handle_sync_response = Mock(return_value={
            "choices": [{"message": {"content": '{"ok":true}'}}],
        })

        bot.call_with_tools(
            [{"role": "user", "content": "score"}],
            request_options={
                "reasoning_effort": "none",
                "response_format": {"type": "json_object"},
                "unsupported": "must-not-forward",
            },
        )

        request_params = bot._handle_sync_response.call_args.args[0]
        self.assertEqual("none", request_params["reasoning_effort"])
        self.assertEqual(
            {"type": "json_object"},
            request_params["response_format"],
        )
        self.assertNotIn("unsupported", request_params)
        self.assertNotIn("request_options", request_params)

    def test_custom_none_reasoning_effort_is_sent_as_low(self):
        bot = OpenAICompatibleBot()
        bot.get_api_config = Mock(return_value={
            "api_key": "test-key",
            "api_base": "https://example.test/v1",
            "model": "test-model",
        })
        bot._handle_sync_response = Mock(return_value={
            "choices": [{"message": {"content": "answer"}}],
        })
        request_options = {"reasoning_effort": "none"}

        bot.call_with_tools(
            [{"role": "user", "content": "describe image"}],
            provider_type="custom:provider01",
            channel_type="wechat_group",
            thinking={"type": "disabled"},
            request_options=request_options,
        )

        request_params = bot._handle_sync_response.call_args.args[0]
        self.assertEqual("low", request_params["reasoning_effort"])
        self.assertEqual({"type": "disabled"}, request_params["thinking"])
        self.assertEqual({"reasoning_effort": "none"}, request_options)

    def test_request_options_are_absent_from_regular_calls(self):
        bot = OpenAICompatibleBot()
        bot.get_api_config = Mock(return_value={
            "api_key": "test-key",
            "api_base": "https://example.test/v1",
            "model": "test-model",
        })
        bot._handle_sync_response = Mock(return_value={
            "choices": [{"message": {"content": "answer"}}],
        })

        bot.call_with_tools([{"role": "user", "content": "hello"}])

        request_params = bot._handle_sync_response.call_args.args[0]
        self.assertNotIn("reasoning_effort", request_params)
        self.assertNotIn("response_format", request_params)

    def test_custom_request_forwards_thinking_control_to_wire_payload(self):
        bot = OpenAICompatibleBot()
        bot.get_api_config = Mock(return_value={
            "api_key": "test-key",
            "api_base": "https://example.test/v1",
            "model": "test-model",
        })
        bot._handle_sync_response = Mock(return_value={
            "choices": [{"message": {"content": "answer"}}],
        })

        for state in ("enabled", "disabled"):
            with self.subTest(state=state):
                bot.call_with_tools(
                    [{"role": "user", "content": "hello"}],
                    provider_type="custom:provider01",
                    channel_type="wechat_group",
                    thinking={"type": state},
                )

                request_params = bot._handle_sync_response.call_args.args[0]
                self.assertEqual({"type": state}, request_params["thinking"])

    def test_non_custom_provider_does_not_receive_generic_thinking_field(self):
        bot = OpenAICompatibleBot()
        bot.get_api_config = Mock(return_value={
            "api_key": "test-key",
            "api_base": "https://example.test/v1",
            "model": "test-model",
        })
        bot._handle_sync_response = Mock(return_value={
            "choices": [{"message": {"content": "answer"}}],
        })

        bot.call_with_tools(
            [{"role": "user", "content": "hello"}],
            provider_type="openai",
            channel_type="wechat_group",
            thinking={"type": "disabled"},
        )

        request_params = bot._handle_sync_response.call_args.args[0]
        self.assertNotIn("thinking", request_params)


if __name__ == "__main__":
    unittest.main()
