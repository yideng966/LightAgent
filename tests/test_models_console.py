# encoding:utf-8
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestModelsConsole(unittest.TestCase):
    def test_models_page_exposes_chat_fallback_controls(self):
        console_js = Path("channel/web/static/js/console.js").read_text(encoding="utf-8")

        self.assertIn("models_chat_fallbacks", console_js)
        self.assertIn("models_chat_fallback_add", console_js)
        self.assertIn("models_chat_failover_immediate", console_js)
        self.assertIn("models_chat_failover_circuit", console_js)
        self.assertIn("models_chat_failover_recovery", console_js)
        self.assertIn("model_failover_failure_threshold", console_js)
        self.assertIn("model_failover_cooldown_seconds", console_js)
        self.assertIn("function renderChatFallbacksSection", console_js)
        self.assertIn("function addChatFallbackRow", console_js)
        self.assertIn("function readChatFallbackRows", console_js)
        self.assertIn("renderChatFallbacksSection(cap)", console_js)
        self.assertIn("payload.fallbacks = extras.fallbacks;", console_js)


if __name__ == "__main__":
    unittest.main()
