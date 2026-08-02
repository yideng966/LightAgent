# encoding:utf-8
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestThinkingProviderRequests(unittest.TestCase):
    def test_deepseek_low_maps_to_lowest_supported_effort(self):
        from models.deepseek.deepseek_bot import DeepSeekBot

        bot = DeepSeekBot.__new__(DeepSeekBot)
        bot.args = {"model": "deepseek-v4-flash"}
        bot._handle_sync_response = MagicMock(return_value={"choices": []})

        bot.call_with_tools(
            [{"role": "user", "content": "hello"}],
            thinking={"type": "enabled"},
            reasoning_effort="low",
        )

        body = bot._handle_sync_response.call_args.args[0]
        self.assertEqual({"type": "enabled"}, body["thinking"])
        self.assertEqual("high", body["reasoning_effort"])

    def test_claude_uses_adaptive_thinking_and_effort(self):
        from models.claudeapi.claude_api_bot import ClaudeAPIBot

        bot = ClaudeAPIBot.__new__(ClaudeAPIBot)
        bot._handle_sync_response = MagicMock(return_value={"choices": []})
        config = {"model": "claude-sonnet-4-6", "character_desc": ""}

        with patch("models.claudeapi.claude_api_bot.conf", return_value=config):
            bot.call_with_tools(
                [{"role": "user", "content": "hello"}],
                thinking={"type": "enabled"},
                reasoning_effort="max",
            )

        body = bot._handle_sync_response.call_args.args[0]
        self.assertEqual({"type": "adaptive"}, body["thinking"])
        self.assertEqual({"effort": "max"}, body["output_config"])

    def test_claude_sends_explicit_disabled(self):
        from models.claudeapi.claude_api_bot import ClaudeAPIBot

        bot = ClaudeAPIBot.__new__(ClaudeAPIBot)
        bot._handle_sync_response = MagicMock(return_value={"choices": []})
        config = {"model": "claude-sonnet-4-6", "character_desc": ""}

        with patch("models.claudeapi.claude_api_bot.conf", return_value=config):
            bot.call_with_tools(
                [{"role": "user", "content": "hello"}],
                thinking={"type": "disabled"},
            )

        body = bot._handle_sync_response.call_args.args[0]
        self.assertEqual({"type": "disabled"}, body["thinking"])
        self.assertNotIn("output_config", body)

    def test_gemini3_maps_max_to_highest_supported_level(self):
        from models.gemini.google_gemini_bot import GoogleGeminiBot

        bot = GoogleGeminiBot.__new__(GoogleGeminiBot)
        bot._handle_gemini_rest_sync_response = MagicMock(return_value={"choices": []})
        response = MagicMock(status_code=200)
        config = {
            "gemini_api_key": "test-key",
            "gemini_api_base": "https://generativelanguage.googleapis.com",
        }

        with patch("models.gemini.google_gemini_bot.conf", return_value=config), \
                patch("models.gemini.google_gemini_bot.requests.post", return_value=response) as post:
            bot.call_with_tools(
                [{"role": "user", "content": "hello"}],
                model="gemini-3.5-flash",
                thinking={"type": "enabled"},
                reasoning_effort="max",
            )

        thinking_config = post.call_args.kwargs["json"]["generationConfig"]["thinkingConfig"]
        self.assertEqual({"thinkingLevel": "high"}, thinking_config)

    def test_gemini25_disables_with_zero_budget(self):
        from models.gemini.google_gemini_bot import GoogleGeminiBot

        bot = GoogleGeminiBot.__new__(GoogleGeminiBot)
        bot._handle_gemini_rest_sync_response = MagicMock(return_value={"choices": []})
        response = MagicMock(status_code=200)
        config = {
            "gemini_api_key": "test-key",
            "gemini_api_base": "https://generativelanguage.googleapis.com",
        }

        with patch("models.gemini.google_gemini_bot.conf", return_value=config), \
                patch("models.gemini.google_gemini_bot.requests.post", return_value=response) as post:
            bot.call_with_tools(
                [{"role": "user", "content": "hello"}],
                model="gemini-2.5-flash",
                thinking={"type": "disabled"},
            )

        thinking_config = post.call_args.kwargs["json"]["generationConfig"]["thinkingConfig"]
        self.assertEqual({"thinkingBudget": 0}, thinking_config)

    def test_dashscope_maps_medium_to_budget(self):
        from models.dashscope.dashscope_bot import DashscopeBot

        bot = DashscopeBot.__new__(DashscopeBot)
        bot.model_name = "qwen3.7-plus"
        bot._handle_sync_response = MagicMock(return_value={"choices": []})

        bot.call_with_tools(
            [{"role": "user", "content": "hello"}],
            thinking={"type": "enabled"},
            reasoning_effort="medium",
        )

        parameters = bot._handle_sync_response.call_args.args[2]
        self.assertTrue(parameters["enable_thinking"])
        self.assertEqual(4096, parameters["thinking_budget"])


if __name__ == "__main__":
    unittest.main()
