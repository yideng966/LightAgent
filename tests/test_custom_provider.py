# encoding:utf-8
"""
Unit tests for multiple custom (OpenAI-compatible) provider support (issue #2838).

Covers models/custom_provider.py:
  - Backward compatibility: legacy custom_api_key / custom_api_base fallback
  - Multi-provider selection via bot_type "custom:<id>" routing
  - parse_custom_bot_type helper
  - Robustness against malformed config (missing id, non-dict, non-list)
"""
import sys
import os
import unittest

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config as config_module
from config import Config


def set_conf(d):
    """Install a fresh Config as the global config used by conf()."""
    config_module.config = Config(d)


class TestParseCustomBotType(unittest.TestCase):
    """parse_custom_bot_type() parsing logic."""

    def setUp(self):
        from models.custom_provider import parse_custom_bot_type
        self.parse = parse_custom_bot_type

    def test_legacy_custom(self):
        is_custom, pid = self.parse("custom")
        self.assertTrue(is_custom)
        self.assertEqual(pid, "")

    def test_custom_with_id(self):
        is_custom, pid = self.parse("custom:3f2a9c1b")
        self.assertTrue(is_custom)
        self.assertEqual(pid, "3f2a9c1b")

    def test_non_custom(self):
        is_custom, pid = self.parse("openai")
        self.assertFalse(is_custom)
        self.assertEqual(pid, "")

    def test_empty(self):
        is_custom, pid = self.parse("")
        self.assertFalse(is_custom)
        self.assertEqual(pid, "")

    def test_none(self):
        is_custom, pid = self.parse(None)
        self.assertFalse(is_custom)
        self.assertEqual(pid, "")


class TestResolveCustomCredentials(unittest.TestCase):
    """resolve_custom_credentials() resolution order and fallbacks."""

    def setUp(self):
        from models.custom_provider import resolve_custom_credentials, get_custom_providers
        self.resolve = resolve_custom_credentials
        self.get_providers = get_custom_providers

    # --- Backward compatibility ---

    def test_legacy_fallback_when_no_providers(self):
        set_conf({
            "bot_type": "custom",
            "custom_api_key": "legacy-key",
            "custom_api_base": "https://legacy.example.com/v1",
        })
        self.assertEqual(
            self.resolve(),
            ("legacy-key", "https://legacy.example.com/v1", None),
        )

    def test_empty_config(self):
        set_conf({"bot_type": "custom"})
        self.assertEqual(self.resolve(), ("", None, None))

    # --- Multi-provider selection via bot_type ---

    def test_provider_selected_by_id(self):
        set_conf({
            "bot_type": "custom:abc12345",
            "custom_providers": [
                {"id": "sf001", "name": "provider-a", "api_key": "key-a",
                 "api_base": "https://api.example.com/v1", "model": "model-a"},
                {"id": "abc12345", "name": "provider-b", "api_key": "key-b",
                 "api_base": "https://api.example.org/v1", "model": "model-b"},
            ],
        })
        self.assertEqual(
            self.resolve(),
            ("key-b", "https://api.example.org/v1", "model-b"),
        )

    def test_id_not_found_falls_back_to_legacy(self):
        set_conf({
            "bot_type": "custom:ghost",
            "custom_api_key": "legacy-key",
            "custom_api_base": "https://legacy.example.com/v1",
            "custom_providers": [
                {"id": "sf001", "name": "provider-a", "api_key": "key-a",
                 "api_base": "https://api.example.com/v1"},
            ],
        })
        self.assertEqual(
            self.resolve(),
            ("legacy-key", "https://legacy.example.com/v1", None),
        )

    def test_provider_without_model_returns_none_model(self):
        set_conf({
            "bot_type": "custom:local01",
            "custom_providers": [
                {"id": "local01", "name": "local", "api_key": "", "api_base": "http://localhost:11434/v1"},
            ],
        })
        self.assertEqual(
            self.resolve(),
            ("", "http://localhost:11434/v1", None),
        )

    # --- Robustness against malformed config ---

    def test_malformed_entries_filtered_and_fallback(self):
        set_conf({
            "bot_type": "custom:nope",
            "custom_api_key": "legacy-key",
            "custom_api_base": "https://legacy.example.com/v1",
            "custom_providers": [
                {"name": "no-id", "api_key": "no-id-key"},   # invalid: no id
                "not-a-dict",                                  # invalid: wrong type
            ],
        })
        # All entries invalid -> treated as empty -> legacy fallback
        self.assertEqual(
            self.resolve(),
            ("legacy-key", "https://legacy.example.com/v1", None),
        )

    def test_get_custom_providers_filters_invalid(self):
        set_conf({
            "bot_type": "custom",
            "custom_providers": [
                {"id": "ok1", "name": "ok", "api_key": "k", "api_base": "https://x/v1"},
                {"name": "no-id", "api_key": "no-id"},   # dropped: no id
                123,                                       # dropped
            ],
        })
        providers = self.get_providers()
        self.assertEqual(len(providers), 1)
        self.assertEqual(providers[0]["id"], "ok1")

    def test_custom_providers_not_a_list_falls_back(self):
        set_conf({
            "bot_type": "custom",
            "custom_api_key": "legacy-key",
            "custom_api_base": "https://legacy.example.com/v1",
            "custom_providers": "oops-a-string",
        })
        self.assertEqual(
            self.resolve(),
            ("legacy-key", "https://legacy.example.com/v1", None),
        )


class TestResolveExplicitCustomProvider(unittest.TestCase):
    def setUp(self):
        from models.custom_provider import resolve_custom_provider_config

        self.resolve = resolve_custom_provider_config

    def test_resolves_provider_independently_from_active_chat_provider(self):
        set_conf({
            "bot_type": "openai",
            "custom_providers": [
                {
                    "id": "voice01",
                    "name": "voice-gateway",
                    "api_key": "voice-key",
                    "api_base": "https://voice.example/v1",
                    "model": "chat-model",
                },
            ],
        })

        provider = self.resolve("custom:voice01")

        self.assertEqual("voice01", provider["id"])
        self.assertEqual("voice-key", provider["api_key"])
        self.assertEqual("https://voice.example/v1", provider["api_base"])

    def test_unknown_id_does_not_fall_back_to_legacy_credentials(self):
        set_conf({
            "custom_api_key": "legacy-key",
            "custom_api_base": "https://legacy.example/v1",
            "custom_providers": [],
        })

        self.assertIsNone(self.resolve("custom:missing"))

    def test_non_custom_provider_returns_none(self):
        set_conf({})
        self.assertIsNone(self.resolve("openai"))


class TestGenerateProviderId(unittest.TestCase):
    """generate_provider_id() produces valid short ids."""

    def test_length_and_hex(self):
        from models.custom_provider import generate_provider_id
        pid = generate_provider_id()
        self.assertEqual(len(pid), 8)
        # Must be valid hex characters
        int(pid, 16)

    def test_uniqueness(self):
        from models.custom_provider import generate_provider_id
        ids = {generate_provider_id() for _ in range(100)}
        self.assertEqual(len(ids), 100)


class TestConfigDefaults(unittest.TestCase):
    """The new config fields must exist with safe defaults."""

    def test_default_config_has_custom_providers(self):
        from config import available_setting
        self.assertIn("custom_providers", available_setting)
        self.assertEqual(available_setting["custom_providers"], [])

    def test_default_config_no_custom_active_provider(self):
        """custom_active_provider was removed — replaced by bot_type routing."""
        from config import available_setting
        self.assertNotIn("custom_active_provider", available_setting)


class TestDragSensitiveNested(unittest.TestCase):
    """drag_sensitive() must mask api_key in nested structures."""

    def test_nested_api_key_masked(self):
        from config import drag_sensitive
        import json
        test_config = {
            "open_ai_api_key": "sk-1234567890abcdef",
            "custom_providers": [
                {"id": "x1", "name": "test", "api_key": "sk-nested-secret-key-long", "api_base": "https://x/v1"}
            ],
        }
        result = drag_sensitive(test_config)
        # Top-level key should be masked
        self.assertNotIn("1234567890abcdef", str(result))
        # Nested key should also be masked
        self.assertNotIn("nested-secret-key-long", str(result))
        # But the id/name/api_base should not be masked
        self.assertIn("x1", str(result))
        self.assertIn("test", str(result))
        self.assertIn("https://x/v1", str(result))

    def test_string_config_masked(self):
        from config import drag_sensitive
        import json
        test_str = json.dumps({
            "open_ai_api_key": "sk-1234567890abcdef",
            "custom_providers": [
                {"id": "x1", "api_key": "sk-nested-very-long-secret"}
            ],
        })
        result = drag_sensitive(test_str)
        self.assertNotIn("1234567890abcdef", result)
        self.assertNotIn("nested-very-long-secret", result)


if __name__ == "__main__":
    unittest.main()
