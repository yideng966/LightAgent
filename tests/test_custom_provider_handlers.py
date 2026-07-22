# encoding:utf-8
"""
Unit tests for the multi custom-provider management API (issue #2838, web UI).

Covers channel/web/web_channel.py::ModelsHandler:
  - _custom_provider_cards / _provider_overview expansion
  - _handle_set_custom_provider   (create / edit / activate)
  - _handle_delete_custom_provider
  - _handle_set_active_custom_provider

Uses id-based routing (bot_type: "custom:<id>") — no custom_active_provider.
"""
import json
import os
import sys
import types
import unittest

# Add project root to path.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Stub the web.py framework so web_channel imports without the dependency.
if "web" not in sys.modules:
    _web_stub = types.ModuleType("web")
    _web_stub.header = lambda *a, **k: None
    _web_stub.data = lambda: b"{}"
    _web_stub.ctx = types.SimpleNamespace()
    sys.modules["web"] = _web_stub

import config as config_module
from config import Config
from channel.web.web_channel import ModelsHandler


def set_conf(d):
    """Install a fresh Config as the global config used by conf()."""
    config_module.config = Config(d)


class _HandlerHarness:
    """Test double around ModelsHandler that captures persisted config in
    memory instead of touching config.json, and no-ops the Bridge reset."""

    def __init__(self):
        self.handler = ModelsHandler.__new__(ModelsHandler)
        self._file_cfg = {}
        self.bridge_resets = 0
        # Patch the disk + bridge boundary on this instance.
        self.handler._read_file_config = lambda: dict(self._file_cfg)
        self.handler._write_file_config = self._capture_write
        self.handler._reset_bridge = self._capture_reset

    def _capture_write(self, data):
        self._file_cfg = dict(data)

    def _capture_reset(self):
        self.bridge_resets += 1

    def call(self, **payload):
        # Resolve the bound method by action for convenience.
        action = payload.get("action")
        method = {
            "set_custom_provider": self.handler._handle_set_custom_provider,
            "delete_custom_provider": self.handler._handle_delete_custom_provider,
            "set_active_custom_provider": self.handler._handle_set_active_custom_provider,
        }[action]
        return json.loads(method(payload))


class TestSetCustomProvider(unittest.TestCase):
    def setUp(self):
        set_conf({"bot_type": "custom", "custom_providers": []})
        self.h = _HandlerHarness()

    def test_create_provider_does_not_hijack_bot_type(self):
        """Creating a provider without make_active must not change bot_type."""
        res = self.h.call(action="set_custom_provider", name="my-provider",
                          api_base="https://api.example.com/v1", api_key="key-a")
        self.assertEqual(res["status"], "success")
        self.assertTrue(res["created"])
        self.assertIn("id", res)
        # bot_type must remain unchanged — no auto-activation.
        bot_type = config_module.conf().get("bot_type")
        self.assertEqual(bot_type, "custom")  # unchanged from setUp
        providers = config_module.conf().get("custom_providers")
        self.assertEqual(len(providers), 1)
        self.assertEqual(providers[0]["id"], res["id"])
        self.assertEqual(providers[0]["name"], "my-provider")
        self.assertEqual(self.h.bridge_resets, 1)

    def test_create_with_make_active_switches_bot_type(self):
        """Creating a provider with make_active=true must switch bot_type."""
        res = self.h.call(action="set_custom_provider", name="my-provider",
                          api_base="https://api.example.com/v1", api_key="key-a",
                          make_active=True)
        self.assertEqual(res["status"], "success")
        bot_type = config_module.conf().get("bot_type")
        self.assertEqual(bot_type, f"custom:{res['id']}")

    def test_create_requires_api_base(self):
        res = self.h.call(action="set_custom_provider", name="x", api_key="k")
        self.assertEqual(res["status"], "error")
        self.assertIn("api_base", res["message"])

    def test_create_requires_name(self):
        res = self.h.call(action="set_custom_provider", name="", api_base="https://x/v1")
        self.assertEqual(res["status"], "error")

    def test_second_provider_does_not_steal_active(self):
        # Explicitly activate the first provider.
        res1 = self.h.call(action="set_custom_provider", name="a",
                           api_base="https://a/v1", api_key="ak", make_active=True)
        res2 = self.h.call(action="set_custom_provider", name="b",
                           api_base="https://b/v1", api_key="bk")
        self.assertTrue(res2["created"])
        # First provider stays active — second creation doesn't steal it.
        bot_type = config_module.conf().get("bot_type")
        self.assertEqual(bot_type, f"custom:{res1['id']}")

    def test_make_active_flag(self):
        self.h.call(action="set_custom_provider", name="a",
                    api_base="https://a/v1", api_key="ak")
        res2 = self.h.call(action="set_custom_provider", name="b",
                           api_base="https://b/v1", api_key="bk", make_active=True)
        bot_type = config_module.conf().get("bot_type")
        self.assertEqual(bot_type, f"custom:{res2['id']}")

    def test_edit_keeps_key_when_omitted(self):
        res = self.h.call(action="set_custom_provider", name="a",
                          api_base="https://a/v1", api_key="secret")
        pid = res["id"]
        # Edit only the base; omit api_key.
        res2 = self.h.call(action="set_custom_provider", name="a",
                           id=pid, api_base="https://a2/v1")
        self.assertEqual(res2["status"], "success")
        self.assertFalse(res2["created"])
        providers = config_module.conf().get("custom_providers")
        self.assertEqual(providers[0]["api_base"], "https://a2/v1")
        self.assertEqual(providers[0]["api_key"], "secret")  # preserved

    def test_edit_can_rename(self):
        res = self.h.call(action="set_custom_provider", name="old",
                          api_base="https://a/v1", api_key="ak")
        pid = res["id"]
        res2 = self.h.call(action="set_custom_provider", name="new",
                           id=pid, api_base="https://a/v1")
        self.assertEqual(res2["status"], "success")
        providers = config_module.conf().get("custom_providers")
        self.assertEqual(providers[0]["name"], "new")
        # ID stays the same
        self.assertEqual(providers[0]["id"], pid)

    def test_edit_clears_model_when_empty(self):
        res = self.h.call(action="set_custom_provider", name="a",
                          api_base="https://a/v1", api_key="ak", model="m1")
        pid = res["id"]
        self.assertEqual(config_module.conf().get("custom_providers")[0]["model"], "m1")
        self.h.call(action="set_custom_provider", name="a", id=pid,
                    api_base="https://a/v1", model="")
        self.assertNotIn("model", config_module.conf().get("custom_providers")[0])


class TestDeleteCustomProvider(unittest.TestCase):
    def setUp(self):
        set_conf({"bot_type": "custom", "custom_providers": []})
        self.h = _HandlerHarness()
        self.res_a = self.h.call(action="set_custom_provider", name="a",
                                 api_base="https://a/v1", api_key="ak",
                                 make_active=True)
        self.res_b = self.h.call(action="set_custom_provider", name="b",
                                 api_base="https://b/v1", api_key="bk")

    def test_delete_unknown(self):
        res = self.h.call(action="delete_custom_provider", id="ghost")
        self.assertEqual(res["status"], "error")

    def test_delete_non_active(self):
        res = self.h.call(action="delete_custom_provider", id=self.res_b["id"])
        self.assertEqual(res["status"], "success")
        ids = [p["id"] for p in config_module.conf().get("custom_providers")]
        self.assertEqual(ids, [self.res_a["id"]])
        # bot_type unchanged (still pointing to a)
        self.assertEqual(config_module.conf().get("bot_type"), f"custom:{self.res_a['id']}")

    def test_delete_active_falls_back_to_first_remaining(self):
        # 'a' is active (created first); deleting it should re-point to 'b'.
        self.assertEqual(config_module.conf().get("bot_type"), f"custom:{self.res_a['id']}")
        res = self.h.call(action="delete_custom_provider", id=self.res_a["id"])
        self.assertEqual(res["status"], "success")
        self.assertEqual(config_module.conf().get("bot_type"), f"custom:{self.res_b['id']}")

    def test_delete_last_reverts_to_legacy(self):
        self.h.call(action="delete_custom_provider", id=self.res_a["id"])
        self.h.call(action="delete_custom_provider", id=self.res_b["id"])
        self.assertEqual(config_module.conf().get("custom_providers"), [])
        # When all providers deleted, reverts to legacy "custom"
        self.assertEqual(config_module.conf().get("bot_type"), "custom")


class TestSetActiveCustomProvider(unittest.TestCase):
    def setUp(self):
        set_conf({"bot_type": "custom", "custom_providers": []})
        self.h = _HandlerHarness()
        self.res_a = self.h.call(action="set_custom_provider", name="a",
                                 api_base="https://a/v1", api_key="ak",
                                 make_active=True)
        self.res_b = self.h.call(action="set_custom_provider", name="b",
                                 api_base="https://b/v1", api_key="bk")

    def test_set_active_valid(self):
        res = self.h.call(action="set_active_custom_provider", id=self.res_b["id"])
        self.assertEqual(res["status"], "success")
        self.assertEqual(config_module.conf().get("bot_type"), f"custom:{self.res_b['id']}")

    def test_set_active_unknown(self):
        res = self.h.call(action="set_active_custom_provider", id="ghost")
        self.assertEqual(res["status"], "error")
        # bot_type unchanged
        self.assertEqual(config_module.conf().get("bot_type"), f"custom:{self.res_a['id']}")

    def test_activation_syncs_model_to_global(self):
        """Activating a provider must write its model into global model field."""
        set_conf({"bot_type": "custom", "custom_providers": [], "model": "gpt-4o"})
        h = _HandlerHarness()
        res = h.call(action="set_custom_provider", name="sf",
                     api_base="https://sf/v1", api_key="k", model="deepseek-v3",
                     make_active=True)
        # Global model field should now be the provider's model.
        self.assertEqual(config_module.conf().get("model"), "deepseek-v3")
        self.assertEqual(config_module.conf().get("bot_type"), f"custom:{res['id']}")

    def test_activation_without_model_keeps_global_model(self):
        """Activating a provider with no model must not overwrite global model."""
        set_conf({"bot_type": "custom", "custom_providers": [], "model": "gpt-4o"})
        h = _HandlerHarness()
        h.call(action="set_custom_provider", name="local",
               api_base="http://localhost:11434/v1", api_key="",
               make_active=True)
        # Global model field should remain unchanged.
        self.assertEqual(config_module.conf().get("model"), "gpt-4o")


class TestProviderOverviewExpansion(unittest.TestCase):
    """_provider_overview / _custom_provider_cards should expand the list."""

    def test_no_custom_providers_keeps_single_card(self):
        set_conf({"bot_type": "custom", "custom_providers": []})
        cards = ModelsHandler._custom_provider_cards(config_module.conf())
        self.assertEqual(cards, [])
        overview = ModelsHandler._provider_overview()
        custom_cards = [c for c in overview if c.get("id") == "custom"]
        # Legacy single custom card remains present.
        self.assertEqual(len(custom_cards), 1)

    def test_multi_providers_expand_into_cards(self):
        set_conf({
            "bot_type": "custom:id_b",
            "custom_providers": [
                {"id": "id_a", "name": "a", "api_key": "ak", "api_base": "https://a/v1"},
                {"id": "id_b", "name": "b", "api_key": "bk", "api_base": "https://b/v1", "model": "m"},
            ],
        })
        overview = ModelsHandler._provider_overview()
        custom_cards = [c for c in overview if c.get("is_custom")]
        self.assertEqual(len(custom_cards), 2)
        by_id = {c["custom_id"]: c for c in custom_cards}
        self.assertEqual(by_id["id_a"]["id"], "custom:id_a")
        self.assertFalse(by_id["id_a"]["active"])
        self.assertTrue(by_id["id_b"]["active"])
        self.assertEqual(by_id["id_b"]["model"], "m")
        # No single legacy "custom" card when expanded.
        self.assertFalse(any(c.get("id") == "custom" for c in overview))

    def test_no_active_shows_none_active(self):
        """When bot_type is plain 'custom', no card is marked active."""
        set_conf({
            "bot_type": "custom",
            "custom_providers": [
                {"id": "id_a", "name": "a", "api_key": "ak", "api_base": "https://a/v1"},
                {"id": "id_b", "name": "b", "api_key": "bk", "api_base": "https://b/v1"},
            ],
        })
        cards = ModelsHandler._custom_provider_cards(config_module.conf())
        active_cards = [c for c in cards if c.get("active")]
        self.assertEqual(len(active_cards), 0)


if __name__ == "__main__":
    unittest.main()
