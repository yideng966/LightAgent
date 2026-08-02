# encoding:utf-8
import json
import os
import tempfile
import unittest
from unittest.mock import patch


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def read(relative_path):
    with open(os.path.join(ROOT, relative_path), encoding="utf-8") as handle:
        return handle.read()


class TestThinkingConfigUI(unittest.TestCase):
    def test_template_defaults_reasoning_effort_to_low(self):
        with open(os.path.join(ROOT, "config-template.json"), encoding="utf-8") as handle:
            config = json.load(handle)
        self.assertFalse(config["enable_thinking"])
        self.assertEqual("low", config["reasoning_effort"])

    def test_agent_config_renders_four_effort_radios(self):
        html = read("channel/web/chat.html")
        self.assertIn('id="cfg-reasoning-effort-group"', html)
        for effort in ("low", "medium", "high", "max"):
            self.assertIn(
                f'name="cfg-reasoning-effort" value="{effort}"',
                html,
            )

    def test_console_loads_saves_and_disables_effort(self):
        source = read("channel/web/static/js/console.js")
        self.assertIn("reasoning_effort: effortInput ? effortInput.value : 'low'", source)
        self.assertIn("group.disabled = !enabled", source)
        self.assertIn("updateReasoningEffortState()", source)

    def test_custom_provider_modal_uses_controlled_protocol_options(self):
        html = read("channel/web/chat.html")
        self.assertIn('id="custom-provider-thinking-protocol"', html)
        for protocol in (
            "none",
            "thinking_object",
            "deepseek",
            "enable_thinking",
            "openai_reasoning",
        ):
            self.assertIn(f'<option value="{protocol}"', html)

    def test_config_handler_persists_valid_effort(self):
        from channel.web.web_channel import ConfigHandler

        local_config = {}
        payload = json.dumps({
            "updates": {"enable_thinking": True, "reasoning_effort": "medium"}
        }).encode("utf-8")
        with tempfile.TemporaryDirectory() as temp_dir, \
                patch("channel.web.web_channel._require_auth"), \
                patch("channel.web.web_channel.web.header"), \
                patch("channel.web.web_channel.web.data", return_value=payload), \
                patch("channel.web.web_channel.conf", return_value=local_config), \
                patch("channel.web.web_channel.get_data_root", return_value=temp_dir):
            result = json.loads(ConfigHandler().POST())

        self.assertEqual("success", result["status"])
        self.assertTrue(local_config["enable_thinking"])
        self.assertEqual("medium", local_config["reasoning_effort"])

    def test_config_handler_rejects_none_effort(self):
        from channel.web.web_channel import ConfigHandler

        local_config = {"reasoning_effort": "low"}
        payload = json.dumps({
            "updates": {"reasoning_effort": "none"}
        }).encode("utf-8")
        with tempfile.TemporaryDirectory() as temp_dir, \
                patch("channel.web.web_channel._require_auth"), \
                patch("channel.web.web_channel.web.header"), \
                patch("channel.web.web_channel.web.data", return_value=payload), \
                patch("channel.web.web_channel.conf", return_value=local_config), \
                patch("channel.web.web_channel.get_data_root", return_value=temp_dir):
            result = json.loads(ConfigHandler().POST())

        self.assertEqual("error", result["status"])
        self.assertEqual("low", local_config["reasoning_effort"])


if __name__ == "__main__":
    unittest.main()
