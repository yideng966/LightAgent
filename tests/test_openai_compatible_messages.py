# encoding:utf-8
import os
import sys
import unittest

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


if __name__ == "__main__":
    unittest.main()
