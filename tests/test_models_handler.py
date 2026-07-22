# encoding:utf-8
import json
import os
import sys
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

if "web" not in sys.modules:
    web_stub = types.ModuleType("web")
    web_stub.HTTPError = type("HTTPError", (Exception,), {})
    web_stub.cookies = lambda: {}
    web_stub.header = lambda *args, **kwargs: None
    web_stub.data = lambda: b"{}"
    web_stub.input = lambda **kwargs: types.SimpleNamespace(**kwargs)
    web_stub.setcookie = lambda *args, **kwargs: None
    web_stub.seeother = lambda *args, **kwargs: Exception("seeother")
    web_stub.notfound = lambda *args, **kwargs: Exception("notfound")
    web_stub.badrequest = lambda *args, **kwargs: Exception("badrequest")
    web_stub.application = lambda *args, **kwargs: types.SimpleNamespace(wsgifunc=lambda: None)
    web_stub.httpserver = types.SimpleNamespace(
        LogMiddleware=type("LogMiddleware", (), {"log": lambda *args, **kwargs: None}),
        StaticMiddleware=lambda app: app,
        WSGIServer=lambda *args, **kwargs: types.SimpleNamespace(serve_forever=lambda: None),
    )
    sys.modules["web"] = web_stub


class TestModelsHandler(unittest.TestCase):
    def test_chat_capability_exposes_model_fallbacks_for_ui(self):
        from channel.web.web_channel import ModelsHandler

        cap = ModelsHandler._chat_capability({
            "bot_type": "deepseek",
            "model": "deepseek-v4-flash",
            "model_failover_failure_threshold": 4,
            "model_failover_cooldown_seconds": 120,
            "model_fallbacks": [
                {"bot_type": "custom:backup", "model": "backup-model"},
                {"model": "glm-5"},
                "qwen3-235b-a22b-instruct-2507",
            ],
        })

        self.assertEqual(
            [
                {"provider_id": "custom:backup", "model": "backup-model"},
                {"provider_id": "", "model": "glm-5"},
                {"provider_id": "", "model": "qwen3-235b-a22b-instruct-2507"},
            ],
            cap["model_fallbacks"],
        )
        self.assertEqual(4, cap["model_failover_failure_threshold"])
        self.assertEqual(120, cap["model_failover_cooldown_seconds"])

    def test_set_chat_persists_model_fallbacks(self):
        from channel.web.web_channel import ModelsHandler

        local_config = {
            "bot_type": "deepseek",
            "model": "deepseek-v4-flash",
            "model_fallbacks": [],
        }
        file_config = dict(local_config)
        handler = ModelsHandler()

        with patch("channel.web.web_channel.conf", return_value=local_config), \
                patch.object(ModelsHandler, "_read_file_config", return_value=file_config), \
                patch.object(ModelsHandler, "_write_file_config") as write_file, \
                patch.object(ModelsHandler, "_reset_bridge") as reset_bridge:
            result = json.loads(handler._handle_set_capability({
                "capability": "chat",
                "provider_id": "deepseek",
                "model": "deepseek-v4-flash",
                "fallbacks": [
                    {"provider_id": "custom:backup", "model": "backup-model"},
                    {"provider_id": "", "model": "glm-5"},
                ],
            }))

        self.assertEqual("success", result["status"])
        self.assertEqual(
            [
                {"bot_type": "custom:backup", "model": "backup-model"},
                {"model": "glm-5"},
            ],
            local_config["model_fallbacks"],
        )
        self.assertEqual(local_config["model_fallbacks"], file_config["model_fallbacks"])
        write_file.assert_called_once_with(file_config)
        reset_bridge.assert_called_once()

    def test_image_capability_exposes_custom_providers(self):
        from config import Config
        import config as config_module
        from channel.web.web_channel import ModelsHandler

        local_config = Config({
            "custom_providers": [
                {
                    "id": "img01",
                    "name": "NewAPI Image",
                    "api_key": "sk-test",
                    "api_base": "https://newapi.example.com/v1",
                    "model": "my-image-model",
                }
            ],
            "skills": {
                "image-generation": {
                    "provider": "custom:img01",
                    "model": "my-image-model",
                }
            },
        })

        with patch.object(config_module, "config", local_config):
            cap = ModelsHandler._image_capability(local_config)

        self.assertIn("custom:img01", cap["providers"])
        self.assertEqual(cap["current_provider"], "custom:img01")
        self.assertEqual(cap["current_model"], "my-image-model")
        self.assertTrue(cap["runtime_active"])
        self.assertNotEqual(cap.get("note"), "router_pending")

    def test_set_image_accepts_custom_provider_and_uses_default_model(self):
        from config import Config
        import config as config_module
        from channel.web.web_channel import ModelsHandler

        local_config = Config({
            "custom_providers": [
                {
                    "id": "img01",
                    "name": "NewAPI Image",
                    "api_key": "sk-test",
                    "api_base": "https://newapi.example.com/v1",
                    "model": "my-image-model",
                }
            ],
        })
        file_config = {
            "custom_providers": [
                {
                    "id": "img01",
                    "name": "NewAPI Image",
                    "api_key": "sk-test",
                    "api_base": "https://newapi.example.com/v1",
                    "model": "my-image-model",
                }
            ],
        }
        handler = ModelsHandler()

        with patch.object(config_module, "config", local_config):
            with patch("channel.web.web_channel.conf", return_value=local_config):
                with patch.object(ModelsHandler, "_read_file_config", return_value=file_config):
                    with patch.object(ModelsHandler, "_write_file_config") as write_file:
                        result = json.loads(handler._handle_set_capability({
                            "capability": "image",
                            "provider_id": "custom:img01",
                            "model": "",
                        }))

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["provider"], "custom:img01")
        self.assertEqual(result["model"], "my-image-model")
        self.assertNotIn("router_pending", result)
        self.assertEqual(
            local_config["skills"]["image-generation"]["provider"],
            "custom:img01",
        )
        self.assertEqual(
            local_config["skills"]["image-generation"]["model"],
            "my-image-model",
        )
        write_file.assert_called_once_with(file_config)

    def test_set_image_rejects_unknown_custom_provider(self):
        from config import Config
        import config as config_module
        from channel.web.web_channel import ModelsHandler

        local_config = Config({"custom_providers": []})
        handler = ModelsHandler()

        with patch.object(config_module, "config", local_config):
            with patch("channel.web.web_channel.conf", return_value=local_config):
                result = json.loads(handler._handle_set_capability({
                    "capability": "image",
                    "provider_id": "custom:missing",
                    "model": "my-image-model",
                }))

        self.assertEqual(result["status"], "error")
        self.assertIn("unknown custom provider id", result["message"])

    def test_set_asr_capability_persists_provider_and_model(self):
        from channel.web.web_channel import ModelsHandler

        local_config = {}
        file_config = {}
        handler = ModelsHandler()

        with patch("channel.web.web_channel.conf", return_value=local_config):
            with patch.object(ModelsHandler, "_read_file_config", return_value=file_config):
                with patch.object(ModelsHandler, "_write_file_config") as write_file:
                    with patch.object(ModelsHandler, "_refresh_voice_routing") as refresh_voice:
                        result = json.loads(handler._handle_set_capability({
                            "capability": "asr",
                            "provider_id": "dashscope",
                            "model": "qwen3-asr-flash",
                        }))

        self.assertEqual(result["status"], "success")
        self.assertEqual(local_config["voice_to_text"], "dashscope")
        self.assertEqual(local_config["voice_to_text_model"], "qwen3-asr-flash")
        self.assertEqual(file_config["voice_to_text"], "dashscope")
        self.assertEqual(file_config["voice_to_text_model"], "qwen3-asr-flash")
        write_file.assert_called_once_with(file_config)
        refresh_voice.assert_called_once()

    def test_set_asr_switching_provider_with_empty_model_clears_existing(self):
        from channel.web.web_channel import ModelsHandler

        local_config = {
            "voice_to_text": "dashscope",
            "voice_to_text_model": "qwen3-asr-flash",
        }
        file_config = dict(local_config)
        handler = ModelsHandler()

        with patch("channel.web.web_channel.conf", return_value=local_config):
            with patch.object(ModelsHandler, "_read_file_config", return_value=file_config):
                with patch.object(ModelsHandler, "_write_file_config"):
                    with patch.object(ModelsHandler, "_refresh_voice_routing"):
                        result = json.loads(handler._handle_set_capability({
                            "capability": "asr",
                            "provider_id": "zhipu",
                            "model": "",
                        }))

        self.assertEqual(result["status"], "success")
        self.assertEqual(local_config["voice_to_text"], "zhipu")
        self.assertEqual(local_config["voice_to_text_model"], "")
        self.assertEqual(file_config["voice_to_text_model"], "")
        self.assertEqual(result["model"], "")

    def test_set_asr_empty_provider_clears_model_when_switching_from_provider(self):
        from channel.web.web_channel import ModelsHandler

        local_config = {
            "voice_to_text": "dashscope",
            "voice_to_text_model": "qwen3-asr-flash",
        }
        file_config = dict(local_config)
        handler = ModelsHandler()

        with patch("channel.web.web_channel.conf", return_value=local_config), \
                patch.object(ModelsHandler, "_read_file_config", return_value=file_config), \
                patch.object(ModelsHandler, "_write_file_config") as write_file, \
                patch.object(ModelsHandler, "_refresh_voice_routing") as refresh_voice:
            result = json.loads(handler._handle_set_capability({
                "capability": "asr",
                "provider_id": "",
                "model": "mimo-v2.5",
            }))

        self.assertEqual("success", result["status"])
        self.assertEqual("", result["provider"])
        self.assertEqual("", result["model"])
        self.assertEqual("", local_config["voice_to_text"])
        self.assertEqual("", local_config["voice_to_text_model"])
        self.assertEqual("", file_config["voice_to_text"])
        self.assertEqual("", file_config["voice_to_text_model"])
        write_file.assert_called_once_with(file_config)
        refresh_voice.assert_called_once()

    def test_set_asr_empty_provider_clears_stale_model_even_when_request_supplies_model(self):
        from channel.web.web_channel import ModelsHandler

        local_config = {
            "voice_to_text": "",
            "voice_to_text_model": "stale-asr-model",
        }
        file_config = dict(local_config)
        handler = ModelsHandler()

        with patch("channel.web.web_channel.conf", return_value=local_config), \
                patch.object(ModelsHandler, "_read_file_config", return_value=file_config), \
                patch.object(ModelsHandler, "_write_file_config") as write_file, \
                patch.object(ModelsHandler, "_refresh_voice_routing") as refresh_voice:
            result = json.loads(handler._handle_set_capability({
                "capability": "asr",
                "provider_id": "",
                "model": "mimo-v2.5",
            }))

        self.assertEqual("success", result["status"])
        self.assertEqual("", result["provider"])
        self.assertEqual("", result["model"])
        self.assertEqual("", local_config["voice_to_text_model"])
        self.assertEqual("", file_config["voice_to_text_model"])
        write_file.assert_called_once_with(file_config)
        refresh_voice.assert_called_once()

    def test_set_asr_same_provider_with_empty_model_keeps_existing(self):
        from channel.web.web_channel import ModelsHandler

        local_config = {
            "voice_to_text": "zhipu",
            "voice_to_text_model": "custom-zhipu-asr",
        }
        file_config = dict(local_config)
        handler = ModelsHandler()

        with patch("channel.web.web_channel.conf", return_value=local_config), \
                patch.object(ModelsHandler, "_read_file_config", return_value=file_config), \
                patch.object(ModelsHandler, "_write_file_config"), \
                patch.object(ModelsHandler, "_refresh_voice_routing"):
            result = json.loads(handler._handle_set_capability({
                "capability": "asr",
                "provider_id": "zhipu",
                "model": "",
            }))

        self.assertEqual(result["status"], "success")
        self.assertEqual(local_config["voice_to_text_model"], "custom-zhipu-asr")
        self.assertEqual(file_config["voice_to_text_model"], "custom-zhipu-asr")

    def test_set_asr_accepts_configured_custom_provider(self):
        from channel.web.web_channel import ModelsHandler

        local_config = {
            "voice_to_text": "dashscope",
            "voice_to_text_model": "qwen3-asr-flash",
            "custom_providers": [{
                "id": "voice01",
                "api_key": "secret-api-key",
                "api_base": "https://secret.example/v1",
            }],
        }
        file_config = dict(local_config)
        handler = ModelsHandler()

        with patch("channel.web.web_channel.conf", return_value=local_config), \
                patch.object(ModelsHandler, "_read_file_config", return_value=file_config), \
                patch.object(ModelsHandler, "_write_file_config") as write_file, \
                patch.object(ModelsHandler, "_refresh_voice_routing") as refresh_voice:
            raw_result = handler._handle_set_capability({
                "capability": "asr",
                "provider_id": "custom:voice01",
                "model": "TeleAI/TeleSpeechASR",
            })
            result = json.loads(raw_result)

        self.assertEqual(result["status"], "success")
        self.assertEqual("custom:voice01", local_config["voice_to_text"])
        self.assertEqual("TeleAI/TeleSpeechASR", local_config["voice_to_text_model"])
        self.assertEqual("custom:voice01", file_config["voice_to_text"])
        self.assertEqual("TeleAI/TeleSpeechASR", file_config["voice_to_text_model"])
        self.assertNotIn("secret-api-key", raw_result)
        self.assertNotIn("https://secret.example/v1", raw_result)
        write_file.assert_called_once_with(file_config)
        refresh_voice.assert_called_once()

    def test_set_asr_rejects_unknown_provider(self):
        from channel.web.web_channel import ModelsHandler

        local_config = {}
        file_config = {}
        handler = ModelsHandler()
        with patch("channel.web.web_channel.conf", return_value=local_config) as get_config, \
                patch.object(ModelsHandler, "_read_file_config", return_value=file_config) as read_file, \
                patch.object(ModelsHandler, "_write_file_config") as write_file, \
                patch.object(ModelsHandler, "_refresh_voice_routing") as refresh_voice:
            result = json.loads(handler._handle_set_capability({
                "capability": "asr",
                "provider_id": "unknown-asr",
                "model": "unknown-model",
            }))

        self.assertEqual(result["status"], "error")
        self.assertIn("asr", result["message"].lower())
        self.assertIn("unknown-asr", result["message"])
        self.assertEqual({}, local_config)
        self.assertEqual({}, file_config)
        get_config.assert_not_called()
        read_file.assert_not_called()
        write_file.assert_not_called()
        refresh_voice.assert_not_called()

    def test_set_asr_rejects_custom_provider_without_model(self):
        from channel.web.web_channel import ModelsHandler

        local_config = {
            "custom_providers": [{
                "id": "voice01",
                "api_key": "secret-api-key",
                "api_base": "https://secret.example/v1",
            }],
        }
        file_config = dict(local_config)
        handler = ModelsHandler()

        with patch("channel.web.web_channel.conf", return_value=local_config), \
                patch.object(ModelsHandler, "_read_file_config") as read_file, \
                patch.object(ModelsHandler, "_write_file_config") as write_file, \
                patch.object(ModelsHandler, "_refresh_voice_routing") as refresh_voice:
            result = json.loads(handler._handle_set_capability({
                "capability": "asr",
                "provider_id": "custom:voice01",
                "model": "",
            }))

        self.assertEqual("error", result["status"])
        self.assertIn("requires a model", result["message"])
        self.assertEqual(file_config, local_config)
        read_file.assert_not_called()
        write_file.assert_not_called()
        refresh_voice.assert_not_called()

    def test_set_tts_capability_persists_provider_model_and_voice(self):
        from channel.web.web_channel import ModelsHandler

        local_config = {}
        file_config = {}
        handler = ModelsHandler()

        with patch("channel.web.web_channel.conf", return_value=local_config), \
                patch.object(ModelsHandler, "_read_file_config", return_value=file_config), \
                patch.object(ModelsHandler, "_write_file_config") as write_file, \
                patch.object(ModelsHandler, "_refresh_voice_routing") as refresh_voice:
            result = json.loads(handler._handle_set_capability({
                "capability": "tts",
                "provider_id": "mimo",
                "model": "mimo-v2.5-tts",
                "voice": "default",
            }))

        expected = {
            "text_to_voice": "mimo",
            "text_to_voice_model": "mimo-v2.5-tts",
            "tts_voice_id": "default",
        }
        self.assertEqual("success", result["status"])
        self.assertEqual("mimo", result["provider"])
        self.assertEqual("mimo-v2.5-tts", result["model"])
        self.assertEqual("default", result["voice"])
        self.assertEqual(expected, local_config)
        self.assertEqual(expected, file_config)
        write_file.assert_called_once_with(file_config)
        refresh_voice.assert_called_once()

    def test_set_tts_accepts_configured_custom_provider(self):
        from channel.web.web_channel import ModelsHandler

        local_config = {
            "text_to_voice": "mimo",
            "text_to_voice_model": "mimo-v2.5-tts",
            "custom_providers": [{
                "id": "voice01",
                "api_key": "secret-api-key",
                "api_base": "https://secret.example/v1",
            }],
        }
        file_config = dict(local_config)
        handler = ModelsHandler()

        with patch("channel.web.web_channel.conf", return_value=local_config), \
                patch.object(ModelsHandler, "_read_file_config", return_value=file_config), \
                patch.object(ModelsHandler, "_write_file_config") as write_file, \
                patch.object(ModelsHandler, "_refresh_voice_routing") as refresh_voice:
            result = json.loads(handler._handle_set_capability({
                "capability": "tts",
                "provider_id": "custom:voice01",
                "model": "mimo-v2.5-tts",
                "voice": "冰糖",
            }))

        self.assertEqual(result["status"], "success")
        self.assertEqual("custom:voice01", local_config["text_to_voice"])
        self.assertEqual("mimo-v2.5-tts", local_config["text_to_voice_model"])
        self.assertEqual("冰糖", local_config["tts_voice_id"])
        self.assertEqual(local_config, file_config)
        write_file.assert_called_once_with(file_config)
        refresh_voice.assert_called_once()

    def test_set_tts_rejects_custom_provider_without_model(self):
        from channel.web.web_channel import ModelsHandler

        local_config = {
            "custom_providers": [{
                "id": "voice01",
                "api_key": "secret-api-key",
                "api_base": "https://secret.example/v1",
            }],
        }
        file_config = dict(local_config)
        handler = ModelsHandler()

        with patch("channel.web.web_channel.conf", return_value=local_config), \
                patch.object(ModelsHandler, "_read_file_config") as read_file, \
                patch.object(ModelsHandler, "_write_file_config") as write_file, \
                patch.object(ModelsHandler, "_refresh_voice_routing") as refresh_voice:
            result = json.loads(handler._handle_set_capability({
                "capability": "tts",
                "provider_id": "custom:voice01",
                "model": "",
                "voice": "",
            }))

        self.assertEqual("error", result["status"])
        self.assertIn("requires a model", result["message"])
        self.assertEqual(file_config, local_config)
        read_file.assert_not_called()
        write_file.assert_not_called()
        refresh_voice.assert_not_called()

    def test_set_tts_rejects_unknown_provider_without_side_effects(self):
        from channel.web.web_channel import ModelsHandler

        local_config = {
            "text_to_voice": "mimo",
            "text_to_voice_model": "mimo-v2.5-tts",
            "tts_voice_id": "default",
        }
        file_config = dict(local_config)
        handler = ModelsHandler()

        with patch("channel.web.web_channel.conf", return_value=local_config) as get_config, \
                patch.object(ModelsHandler, "_read_file_config", return_value=file_config) as read_file, \
                patch.object(ModelsHandler, "_write_file_config") as write_file, \
                patch.object(ModelsHandler, "_refresh_voice_routing") as refresh_voice:
            result = json.loads(handler._handle_set_capability({
                "capability": "tts",
                "provider_id": "unknown-tts",
                "model": "unknown-model",
                "voice": "unknown-voice",
            }))

        self.assertEqual("error", result["status"])
        self.assertIn("tts", result["message"].lower())
        self.assertIn("unknown-tts", result["message"])
        self.assertEqual("mimo", local_config["text_to_voice"])
        self.assertEqual("mimo-v2.5-tts", local_config["text_to_voice_model"])
        self.assertEqual("default", local_config["tts_voice_id"])
        self.assertEqual(local_config, file_config)
        get_config.assert_not_called()
        read_file.assert_not_called()
        write_file.assert_not_called()
        refresh_voice.assert_not_called()

    def test_set_tts_rejects_empty_provider_without_side_effects(self):
        from channel.web.web_channel import ModelsHandler

        local_config = {"text_to_voice": "mimo", "text_to_voice_model": "mimo-v2.5-tts"}
        file_config = dict(local_config)
        handler = ModelsHandler()

        with patch("channel.web.web_channel.conf", return_value=local_config) as get_config, \
                patch.object(ModelsHandler, "_read_file_config", return_value=file_config) as read_file, \
                patch.object(ModelsHandler, "_write_file_config") as write_file, \
                patch.object(ModelsHandler, "_refresh_voice_routing") as refresh_voice:
            result = json.loads(handler._handle_set_capability({
                "capability": "tts",
                "provider_id": "",
                "model": "",
                "voice": "",
            }))

        self.assertEqual("error", result["status"])
        self.assertIn("tts", result["message"].lower())
        self.assertIn("''", result["message"])
        self.assertEqual("mimo", local_config["text_to_voice"])
        self.assertEqual(local_config, file_config)
        get_config.assert_not_called()
        read_file.assert_not_called()
        write_file.assert_not_called()
        refresh_voice.assert_not_called()

    def test_asr_capability_exposes_provider_models(self):
        from channel.web.web_channel import ModelsHandler

        cap = ModelsHandler._asr_capability({
            "voice_to_text": "dashscope",
            "voice_to_text_model": "qwen3-asr-flash",
        })

        self.assertTrue(cap["editable"])
        self.assertEqual(cap["current_provider"], "dashscope")
        self.assertEqual(cap["current_model"], "qwen3-asr-flash")
        self.assertIn("provider_models", cap)
        self.assertIn("dashscope", cap["provider_models"])
        self.assertEqual("", cap["invalid_configured_provider"])
        self.assertEqual("", cap.get("legacy_configured_provider"))
        self.assertNotIn("api_key", cap)
        self.assertNotIn("api_base", cap)

    def test_voice_capabilities_expose_configured_custom_providers(self):
        from channel.web.web_channel import ModelsHandler

        config = {
            "voice_to_text": "custom:voice01",
            "voice_to_text_model": "TeleAI/TeleSpeechASR",
            "text_to_voice": "custom:voice01",
            "text_to_voice_model": "mimo-v2.5-tts",
            "custom_providers": [{
                "id": "voice01",
                "api_key": "secret-api-key",
                "api_base": "https://secret.example/v1",
            }],
        }
        asr = ModelsHandler._asr_capability(config)
        tts = ModelsHandler._tts_capability(config)

        self.assertEqual("custom:voice01", asr["current_provider"])
        self.assertEqual("TeleAI/TeleSpeechASR", asr["current_model"])
        self.assertEqual("", asr["invalid_configured_provider"])
        self.assertEqual("", asr.get("legacy_configured_provider"))
        self.assertIn("custom:voice01", asr["providers"])
        self.assertEqual([], asr["provider_models"]["custom"])
        self.assertEqual("custom:voice01", tts["current_provider"])
        self.assertEqual("mimo-v2.5-tts", tts["current_model"])
        self.assertEqual("", tts["invalid_configured_provider"])
        self.assertEqual("", tts.get("legacy_configured_provider"))
        self.assertIn("custom:voice01", tts["providers"])
        self.assertEqual([], tts["provider_models"]["custom"])
        self.assertEqual([], tts["provider_voices"]["custom"])
        for capability in (asr, tts):
            self.assertNotIn("api_key", capability)
            self.assertNotIn("api_base", capability)

    def test_voice_capabilities_preserve_supported_legacy_providers(self):
        from channel.web.web_channel import ModelsHandler

        asr = ModelsHandler._asr_capability({
            "voice_to_text": "baidu",
            "voice_to_text_model": "legacy-baidu-asr",
        })
        tts = ModelsHandler._tts_capability({
            "text_to_voice": "edge",
            "text_to_voice_model": "legacy-edge-tts",
            "tts_voice_id": "zh-CN-XiaoxiaoNeural",
        })

        self.assertEqual("baidu", asr["current_provider"])
        self.assertEqual("legacy-baidu-asr", asr["current_model"])
        self.assertEqual("", asr["invalid_configured_provider"])
        self.assertEqual("baidu", asr.get("legacy_configured_provider"))
        self.assertNotIn("baidu", asr["providers"])
        self.assertEqual("edge", tts["current_provider"])
        self.assertEqual("legacy-edge-tts", tts["current_model"])
        self.assertEqual("zh-CN-XiaoxiaoNeural", tts["current_voice"])
        self.assertEqual("", tts["invalid_configured_provider"])
        self.assertEqual("edge", tts.get("legacy_configured_provider"))
        self.assertNotIn("edge", tts["providers"])

    def test_voice_capabilities_mark_unknown_providers_invalid(self):
        from channel.web.web_channel import ModelsHandler

        asr = ModelsHandler._asr_capability({
            "voice_to_text": "unknown-asr",
            "voice_to_text_model": "unknown-asr-model",
        })
        tts = ModelsHandler._tts_capability({
            "text_to_voice": "unknown-tts",
            "text_to_voice_model": "unknown-tts-model",
            "tts_voice_id": "unknown-voice",
        })

        for capability, provider in ((asr, "unknown-asr"), (tts, "unknown-tts")):
            self.assertEqual("", capability["current_provider"])
            self.assertEqual("", capability["current_model"])
            self.assertEqual(provider, capability["invalid_configured_provider"])
            self.assertEqual("", capability.get("legacy_configured_provider"))
            self.assertNotIn("api_key", capability)
            self.assertNotIn("api_base", capability)

    def test_voice_capabilities_return_empty_legacy_marker_without_provider(self):
        from channel.web.web_channel import ModelsHandler

        asr = ModelsHandler._asr_capability({})
        tts = ModelsHandler._tts_capability({})

        self.assertEqual("", asr.get("legacy_configured_provider"))
        self.assertEqual("", tts.get("legacy_configured_provider"))

    def test_search_capability_exposes_serper_and_jina_as_dedicated_key_providers(self):
        from channel.web.web_channel import ModelsHandler

        cap = ModelsHandler._search_capability({
            "tools": {
                "web_search": {
                    "serper_api_key": "serper-key",
                    "jina_api_key": "jina-key",
                }
            }
        })

        provider_map = {item["id"]: item for item in cap["providers"]}
        self.assertIn("serper", provider_map)
        self.assertIn("jina", provider_map)
        self.assertTrue(provider_map["serper"]["configured"])
        self.assertTrue(provider_map["jina"]["configured"])
        self.assertTrue(provider_map["serper"]["needs_dedicated_key"])
        self.assertTrue(provider_map["jina"]["needs_dedicated_key"])

    def test_set_search_credential_persists_selected_provider_key(self):
        from channel.web.web_channel import ModelsHandler

        local_config = {"tools": {"web_search": {}}}
        file_config = {"tools": {"web_search": {}}}
        handler = ModelsHandler()

        with patch("channel.web.web_channel.conf", return_value=local_config):
            with patch.object(ModelsHandler, "_read_file_config", return_value=file_config):
                with patch.object(ModelsHandler, "_write_file_config") as write_file:
                    result = json.loads(handler._handle_set_search_credential({
                        "provider": "serper",
                        "api_key": "serper-key",
                    }))

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["provider"], "serper")
        self.assertEqual(local_config["tools"]["web_search"]["serper_api_key"], "serper-key")
        self.assertEqual(file_config["tools"]["web_search"]["serper_api_key"], "serper-key")
        write_file.assert_called_once_with(file_config)


if __name__ == "__main__":
    unittest.main()
