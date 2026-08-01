# encoding:utf-8
import json
import unittest
from unittest.mock import patch

import requests


class _Response:
    def __init__(self, payload=None, status_code=200, headers=None, raw=None):
        self.status_code = status_code
        self.headers = headers or {}
        if raw is None:
            raw = json.dumps(payload if payload is not None else {}).encode("utf-8")
        self._raw = raw

    def iter_content(self, chunk_size=65536):
        for start in range(0, len(self._raw), chunk_size):
            yield self._raw[start:start + chunk_size]


class _BrokenStreamResponse(_Response):
    def iter_content(self, chunk_size=65536):
        raise requests.ConnectionError("stream interrupted")
        yield b""  # pragma: no cover


class TestModelCatalogService(unittest.TestCase):
    def setUp(self):
        self.provider_meta = {
            "openai": {
                "api_key_field": "open_ai_api_key",
                "api_base_key": "open_ai_api_base",
                "api_base_default": "https://api.openai.com/v1",
            },
            "claudeAPI": {
                "api_key_field": "claude_api_key",
                "api_base_key": "claude_api_base",
                "api_base_default": "https://api.anthropic.com/v1",
            },
            "gemini": {
                "api_key_field": "gemini_api_key",
                "api_base_key": "gemini_api_base",
                "api_base_default": "https://generativelanguage.googleapis.com",
            },
            "custom": {
                "api_key_field": "custom_api_key",
                "api_base_key": "custom_api_base",
                "api_base_default": "",
            },
        }

    def _service(self, config):
        from channel.web.model_catalog import ModelCatalogService

        return ModelCatalogService(config, self.provider_meta)

    def test_openai_compatible_fetches_models_with_bounded_request(self):
        response = _Response({
            "data": [
                {"id": "gpt-5", "owned_by": "openai"},
                {"id": "gpt-5"},
                {"id": "gpt-image-1"},
            ]
        })
        config = {
            "open_ai_api_key": "sk-test",
            "open_ai_api_base": "https://gateway.example/v1/",
            "proxy": "http://127.0.0.1:7890",
        }

        with patch("channel.web.model_catalog.validate_url_safe") as validate_url, \
                patch("channel.web.model_catalog.requests.get", return_value=response) as get:
            models = self._service(config).fetch("openai")

        self.assertEqual(["gpt-5", "gpt-image-1"], [item["id"] for item in models])
        validate_url.assert_called_once_with("https://gateway.example/v1/models")
        _, kwargs = get.call_args
        self.assertEqual("Bearer sk-test", kwargs["headers"]["Authorization"])
        self.assertEqual({"http": config["proxy"], "https": config["proxy"]}, kwargs["proxies"])
        self.assertEqual((5, 10), kwargs["timeout"])
        self.assertFalse(kwargs["allow_redirects"])
        self.assertTrue(kwargs["stream"])

    def test_anthropic_uses_vendor_headers_and_cursor_pagination(self):
        responses = [
            _Response({
                "data": [{"id": "claude-a", "display_name": "Claude A"}],
                "has_more": True,
                "last_id": "claude-a",
            }),
            _Response({
                "data": [{"id": "claude-b", "display_name": "Claude B"}],
                "has_more": False,
            }),
        ]
        config = {"claude_api_key": "anthropic-key"}

        with patch("channel.web.model_catalog.validate_url_safe"), \
                patch("channel.web.model_catalog.requests.get", side_effect=responses) as get:
            models = self._service(config).fetch("claudeAPI")

        self.assertEqual(["claude-a", "claude-b"], [item["id"] for item in models])
        self.assertEqual("Claude A", models[0]["hint"])
        first_kwargs = get.call_args_list[0].kwargs
        second_kwargs = get.call_args_list[1].kwargs
        self.assertEqual("anthropic-key", first_kwargs["headers"]["x-api-key"])
        self.assertEqual("2023-06-01", first_kwargs["headers"]["anthropic-version"])
        self.assertEqual({"limit": 100}, first_kwargs["params"])
        self.assertEqual("claude-a", second_kwargs["params"]["after_id"])

    def test_gemini_normalizes_resource_names_and_page_tokens(self):
        responses = [
            _Response({
                "models": [{
                    "name": "models/gemini-2.5-flash",
                    "displayName": "Gemini 2.5 Flash",
                    "supportedGenerationMethods": ["generateContent"],
                }],
                "nextPageToken": "next-token",
            }),
            _Response({
                "models": [{
                    "name": "models/text-embedding-004",
                    "displayName": "Text Embedding 004",
                    "supportedActions": ["embedContent"],
                }]
            }),
        ]
        config = {"gemini_api_key": "gemini-key"}

        with patch("channel.web.model_catalog.validate_url_safe"), \
                patch("channel.web.model_catalog.requests.get", side_effect=responses) as get:
            models = self._service(config).fetch("gemini")

        self.assertEqual(
            ["gemini-2.5-flash", "text-embedding-004"],
            [item["id"] for item in models],
        )
        self.assertEqual(["generateContent"], models[0]["capabilities"])
        self.assertEqual("next-token", get.call_args_list[1].kwargs["params"]["pageToken"])
        self.assertEqual("gemini-key", get.call_args_list[0].kwargs["headers"]["x-goog-api-key"])

    def test_custom_provider_is_resolved_by_exact_id(self):
        config = {
            "custom_api_key": "legacy-key",
            "custom_api_base": "https://legacy.example/v1",
            "custom_providers": [{
                "id": "chosen01",
                "api_key": "chosen-key",
                "api_base": "https://chosen.example/v1",
            }],
        }
        response = _Response({"data": [{"id": "chosen-model"}]})

        with patch("channel.web.model_catalog.validate_url_safe"), \
                patch("channel.web.model_catalog.requests.get", return_value=response) as get:
            models = self._service(config).fetch("custom:chosen01")

        self.assertEqual("chosen-model", models[0]["id"])
        self.assertEqual(
            "https://chosen.example/v1/models",
            get.call_args.args[0],
        )
        self.assertEqual("Bearer chosen-key", get.call_args.kwargs["headers"]["Authorization"])

    def test_unknown_custom_provider_does_not_fall_back_to_legacy(self):
        from channel.web.model_catalog import ModelCatalogError

        config = {
            "custom_api_key": "legacy-key",
            "custom_api_base": "https://legacy.example/v1",
            "custom_providers": [],
        }
        with patch("channel.web.model_catalog.requests.get") as get:
            with self.assertRaises(ModelCatalogError) as raised:
                self._service(config).fetch("custom:missing")

        self.assertEqual("provider_not_found", raised.exception.code)
        get.assert_not_called()

    def test_builtin_provider_requires_configured_api_key(self):
        from channel.web.model_catalog import ModelCatalogError

        with patch("channel.web.model_catalog.requests.get") as get:
            with self.assertRaises(ModelCatalogError) as raised:
                self._service({}).fetch("openai")

        self.assertEqual("provider_not_configured", raised.exception.code)
        get.assert_not_called()

    def test_http_errors_are_mapped_without_response_body(self):
        from channel.web.model_catalog import ModelCatalogError

        config = {"open_ai_api_key": "secret-key"}
        with patch("channel.web.model_catalog.validate_url_safe"), \
                patch("channel.web.model_catalog.requests.get", return_value=_Response(
                    status_code=401,
                    raw=b'{"error":"secret upstream details"}',
                )):
            with self.assertRaises(ModelCatalogError) as raised:
                self._service(config).fetch("openai")

        self.assertEqual("models_api_unauthorized", raised.exception.code)
        self.assertNotIn("secret-key", str(raised.exception))
        self.assertNotIn("upstream details", str(raised.exception))

    def test_timeout_is_mapped_to_stable_error_code(self):
        from channel.web.model_catalog import ModelCatalogError

        config = {"open_ai_api_key": "secret-key"}
        with patch("channel.web.model_catalog.validate_url_safe"), \
                patch("channel.web.model_catalog.requests.get", side_effect=requests.Timeout()):
            with self.assertRaises(ModelCatalogError) as raised:
                self._service(config).fetch("openai")

        self.assertEqual("models_api_timeout", raised.exception.code)

    def test_stream_read_failure_is_mapped_to_unavailable(self):
        from channel.web.model_catalog import ModelCatalogError

        config = {"open_ai_api_key": "secret-key"}
        with patch("channel.web.model_catalog.validate_url_safe"), \
                patch(
                    "channel.web.model_catalog.requests.get",
                    return_value=_BrokenStreamResponse(),
                ):
            with self.assertRaises(ModelCatalogError) as raised:
                self._service(config).fetch("openai")

        self.assertEqual("models_api_unavailable", raised.exception.code)

    def test_redirect_is_not_followed_and_is_rejected(self):
        from channel.web.model_catalog import ModelCatalogError

        config = {"open_ai_api_key": "secret-key"}
        with patch("channel.web.model_catalog.validate_url_safe"), \
                patch("channel.web.model_catalog.requests.get", return_value=_Response(
                    status_code=302,
                    headers={"Location": "https://other.example/models"},
                )) as get:
            with self.assertRaises(ModelCatalogError) as raised:
                self._service(config).fetch("openai")

        self.assertEqual("models_api_invalid_response", raised.exception.code)
        self.assertFalse(get.call_args.kwargs["allow_redirects"])

    def test_oversized_response_is_rejected_before_json_parsing(self):
        from channel.web.model_catalog import MAX_RESPONSE_BYTES, ModelCatalogError

        config = {"open_ai_api_key": "secret-key"}
        response = _Response(raw=b"x" * (MAX_RESPONSE_BYTES + 1))
        with patch("channel.web.model_catalog.validate_url_safe"), \
                patch("channel.web.model_catalog.requests.get", return_value=response):
            with self.assertRaises(ModelCatalogError) as raised:
                self._service(config).fetch("openai")

        self.assertEqual("models_api_invalid_response", raised.exception.code)


if __name__ == "__main__":
    unittest.main()
