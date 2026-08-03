# encoding:utf-8
import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.prompt.builder import _build_workspace_section
from agent.prompt.workspace import (
    _AGENT_TEMPLATE_EN,
    _AGENT_TEMPLATE_ZH,
    _BOOTSTRAP_TEMPLATE_EN,
    _BOOTSTRAP_TEMPLATE_ZH,
)
from channel.wechat_group.wechat_group_persona import WECHAT_GROUP_PERSONA_PRESETS
from config import available_setting


ROOT = Path(__file__).resolve().parents[1]


class DefaultReplyStyleTest(unittest.TestCase):
    def test_default_agent_and_bootstrap_prompts_do_not_request_emoji(self):
        prompts = (
            _AGENT_TEMPLATE_ZH,
            _AGENT_TEMPLATE_EN,
            _BOOTSTRAP_TEMPLATE_ZH,
            _BOOTSTRAP_TEMPLATE_EN,
            "\n".join(_build_workspace_section("C:/workspace", "zh")),
            "\n".join(_build_workspace_section("C:/workspace", "en")),
        )

        for prompt in prompts:
            self.assertNotIn("适当使用 emoji", prompt)
            self.assertNotIn("Use emoji to make expression", prompt)
            self.assertNotIn("with a few emoji", prompt)

    def test_builtin_wechat_group_personas_do_not_seed_text_emoji(self):
        text_emoji = ("[捂脸]", "[吃瓜]", "[呲牙]", "[破涕为笑]", "[Emm]", "[抠鼻]")

        for preset in WECHAT_GROUP_PERSONA_PRESETS:
            for token in text_emoji:
                self.assertNotIn(token, preset["prompt"])

    def test_sticker_defaults_remain_independent_from_text_emoji_style(self):
        template = json.loads((ROOT / "config-template.json").read_text(encoding="utf-8"))
        self.assertEqual("", template["wechat_group_persona_prompt"])
        self.assertEqual(20, template["wechat_group_sticker_reply_percent"])
        self.assertEqual(20, available_setting["wechat_group_sticker_reply_percent"])
        self.assertTrue(any("表情包" in preset["prompt"] for preset in WECHAT_GROUP_PERSONA_PRESETS))


if __name__ == "__main__":
    unittest.main()
