# encoding:utf-8
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestModelsConsole(unittest.TestCase):
    def test_models_page_uses_searchable_editable_model_comboboxes(self):
        console_js = Path("channel/web/static/js/console.js").read_text(encoding="utf-8")
        console_css = Path("channel/web/static/css/console.css").read_text(encoding="utf-8")

        self.assertIn("function initModelCombobox", console_js)
        self.assertIn("function fetchProviderModels", console_js)
        self.assertIn("function normalizeModelSearchText", console_js)
        self.assertIn("models_fetch_models", console_js)
        self.assertIn("models_model_search_placeholder", console_js)
        self.assertIn("models_model_no_matches", console_js)
        self.assertIn("action: 'fetch_provider_models'", console_js)
        self.assertIn('role="combobox"', console_js)
        self.assertIn('aria-expanded="false"', console_js)
        self.assertIn('role="listbox"', console_js)
        self.assertIn("model-combobox", console_css)
        self.assertIn("model-fetch-button", console_css)
        self.assertIn("min-height: 44px", console_css)

    def test_all_requested_capabilities_share_model_fetch_controls(self):
        console_js = Path("channel/web/static/js/console.js").read_text(encoding="utf-8")

        for capability in ("chat", "scorer", "vision", "image", "asr", "tts", "embedding"):
            with self.subTest(capability=capability):
                self.assertIn(f"{{ id: '{capability}'", console_js)
        self.assertIn("MODELS_CAPABILITY_DEFS.filter(def => def.needsModel)", console_js)

    def test_models_page_exposes_scorer_capability(self):
        console_js = Path("channel/web/static/js/console.js").read_text(encoding="utf-8")

        self.assertIn("{ id: 'scorer'", console_js)
        self.assertIn("models_capability_scorer", console_js)
        self.assertIn("models_capability_scorer_desc", console_js)
        self.assertIn("models_scorer_prompt_only_hint", console_js)
        self.assertIn("!currentProvider.startsWith('custom')", console_js)
        self.assertIn("saveCapability(capId)", console_js)

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
        self.assertIn("handleChatFallbackDragStart", console_js)
        self.assertIn("moveChatFallbackRow", console_js)
        self.assertIn("refreshChatFallbackPriorities", console_js)
        self.assertIn("cap-chat-failover-threshold", console_js)
        self.assertIn("payload.failover_failure_threshold", console_js)

    def test_chat_fallbacks_share_searchable_provider_model_catalogs(self):
        console_js = Path("channel/web/static/js/console.js").read_text(encoding="utf-8")

        self.assertIn("data-chat-fallback-model-combobox", console_js)
        self.assertIn("data-chat-fallback-fetch-models", console_js)
        self.assertIn("function fetchChatFallbackModels", console_js)
        self.assertIn("function rebuildChatFallbackModelDropdown", console_js)
        self.assertIn("function updateChatFallbackFetchButton", console_js)

    def test_remote_model_catalog_cache_is_shared_by_provider(self):
        console_js = Path("channel/web/static/js/console.js").read_text(encoding="utf-8")

        self.assertIn("function modelCatalogKey(providerId)", console_js)
        self.assertIn("modelsCatalogState.entries.get(modelCatalogKey(providerId))", console_js)
        self.assertIn("function refreshProviderModelCatalogConsumers", console_js)
        self.assertIn("function requestProviderModelCatalog", console_js)
        self.assertIn("function invalidateProviderModelCatalog", console_js)
        self.assertNotIn("`${capabilityId}:${providerId}`", console_js)


if __name__ == "__main__":
    unittest.main()
