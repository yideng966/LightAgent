# encoding:utf-8
import unittest

from models.thinking_policy import (
    apply_openai_compatible_thinking,
    normalize_reasoning_effort,
    normalize_thinking_protocol,
)


class TestThinkingPolicy(unittest.TestCase):
    def test_reasoning_effort_defaults_to_low(self):
        for value in (None, "", "invalid"):
            self.assertEqual("low", normalize_reasoning_effort(value))

    def test_reasoning_effort_accepts_four_levels(self):
        for effort in ("low", "medium", "high", "max"):
            self.assertEqual(effort, normalize_reasoning_effort(effort))

    def test_unknown_protocol_defaults_to_none(self):
        self.assertEqual("none", normalize_thinking_protocol("unknown"))

    def test_deepseek_maps_four_levels_monotonically(self):
        expected = {"low": "high", "medium": "high", "high": "high", "max": "max"}
        for effort, upstream in expected.items():
            body = {}
            apply_openai_compatible_thinking(
                body, "deepseek", {"type": "enabled"}, effort
            )
            self.assertEqual({"type": "enabled"}, body["thinking"])
            self.assertEqual(upstream, body["reasoning_effort"])

    def test_deepseek_disabled_omits_effort(self):
        body = {}
        apply_openai_compatible_thinking(
            body, "deepseek", {"type": "disabled"}, "max"
        )
        self.assertEqual({"type": "disabled"}, body["thinking"])
        self.assertNotIn("reasoning_effort", body)

    def test_openai_converts_disabled_to_none(self):
        body = {}
        apply_openai_compatible_thinking(
            body, "openai_reasoning", {"type": "disabled"}, "high"
        )
        self.assertEqual("none", body["reasoning_effort"])


if __name__ == "__main__":
    unittest.main()
