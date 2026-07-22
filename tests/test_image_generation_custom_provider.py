# encoding:utf-8
import base64
import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config as config_module
from config import Config


def set_conf(d):
    config_module.config = Config(d)


def load_generate_module():
    path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "skills",
        "image-generation",
        "scripts",
        "generate.py",
    )
    spec = importlib.util.spec_from_file_location("image_generation_generate_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Response:
    status_code = 200
    text = ""
    reason = "OK"
    url = ""

    def json(self):
        return {
            "data": [
                {"b64_json": base64.b64encode(b"fake-png-bytes").decode("ascii")}
            ]
        }


class TestImageGenerationCustomProvider(unittest.TestCase):
    def setUp(self):
        self.generate = load_generate_module()

    def tearDown(self):
        set_conf({})

    def test_load_cli_args_keeps_inline_json_compatibility(self):
        args = self.generate._load_cli_args([
            '{"prompt": "draw a cow", "size": "2K"}'
        ])

        self.assertEqual("draw a cow", args["prompt"])
        self.assertEqual("2K", args["size"])

    def test_load_cli_args_reads_utf8_json_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            request_path = os.path.join(tmp, "image-request.json")
            with open(request_path, "w", encoding="utf-8-sig") as f:
                json.dump(
                    {"prompt": "画一条蛇 & 保留 100% 细节", "aspect_ratio": "9:16"},
                    f,
                    ensure_ascii=False,
                )

            args = self.generate._load_cli_args(["--json-file", request_path])

        self.assertEqual("画一条蛇 & 保留 100% 细节", args["prompt"])
        self.assertEqual("9:16", args["aspect_ratio"])

    def test_load_cli_args_reports_invalid_json_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            request_path = os.path.join(tmp, "invalid.json")
            with open(request_path, "w", encoding="utf-8") as f:
                f.write("not-json")

            with self.assertRaisesRegex(ValueError, "Invalid JSON"):
                self.generate._load_cli_args(["--json-file", request_path])

    def test_load_cli_args_explains_windows_split_arguments(self):
        with self.assertRaisesRegex(ValueError, "On Windows, use --json-file"):
            self.generate._load_cli_args(["'{prompt:", "draw a cow}'"])

    def test_skill_uses_json_file_instead_of_windows_unsafe_inline_json(self):
        skill_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "skills",
            "image-generation",
            "SKILL.md",
        )
        with open(skill_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("--json-file", content)
        self.assertIn("never pass inline JSON wrapped in single quotes", content)
        self.assertNotIn("python <base_dir>/scripts/generate.py '<json_args>'", content)

    def test_build_providers_uses_explicit_custom_provider(self):
        set_conf({
            "custom_providers": [
                {
                    "id": "img01",
                    "name": "NewAPI Image",
                    "api_key": "sk-custom",
                    "api_base": "https://newapi.example.com/v1",
                    "model": "newapi-image-model",
                }
            ]
        })

        providers = self.generate._build_providers("", provider_id="custom:img01")

        self.assertEqual(len(providers), 1)
        label, provider = providers[0]
        self.assertEqual(label, "Custom:NewAPI Image")
        self.assertIsInstance(provider, self.generate.OpenAIProvider)
        self.assertEqual(provider.api_key, "sk-custom")
        self.assertEqual(provider.api_base, "https://newapi.example.com/v1")
        self.assertEqual(provider.model, "newapi-image-model")

    def test_build_providers_loads_custom_provider_from_config_file_when_conf_is_empty(self):
        set_conf({})
        with tempfile.TemporaryDirectory() as tmp:
            config_path = os.path.join(tmp, "config.json")
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "custom_providers": [
                            {
                                "id": "img01",
                                "name": "NewAPI Image",
                                "api_key": "sk-custom",
                                "api_base": "https://newapi.example.com/v1",
                                "model": "newapi-image-model",
                            }
                        ]
                    },
                    f,
                )

            with patch.dict(os.environ, {"LIGHTAGENT_DATA_DIR": tmp}):
                providers = self.generate._build_providers("", provider_id="custom:img01")

        self.assertEqual(len(providers), 1)
        label, provider = providers[0]
        self.assertEqual(label, "Custom:NewAPI Image")
        self.assertEqual(provider.api_key, "sk-custom")
        self.assertEqual(provider.api_base, "https://newapi.example.com/v1")
        self.assertEqual(provider.model, "newapi-image-model")

    def test_custom_provider_generation_hits_custom_images_endpoint(self):
        set_conf({
            "custom_providers": [
                {
                    "id": "img01",
                    "name": "NewAPI Image",
                    "api_key": "sk-custom",
                    "api_base": "https://newapi.example.com/v1",
                    "model": "newapi-image-model",
                }
            ]
        })
        provider = self.generate._build_providers(
            "override-image-model",
            provider_id="custom:img01",
        )[0][1]

        calls = []

        def fake_post(url, **kwargs):
            calls.append((url, kwargs))
            resp = _Response()
            resp.url = url
            return resp

        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(self.generate, "requests", types.SimpleNamespace(post=fake_post)):
                paths = provider.generate("draw a cow", output_dir=tmp)

        self.assertEqual(len(paths), 1)
        self.assertEqual(calls[0][0], "https://newapi.example.com/v1/images/generations")
        self.assertEqual(calls[0][1]["headers"]["Authorization"], "Bearer sk-custom")
        self.assertEqual(calls[0][1]["json"]["model"], "override-image-model")
        self.assertEqual(calls[0][1]["json"]["prompt"], "draw a cow")

    def test_custom_provider_generation_uses_url_when_b64_json_is_null(self):
        set_conf({
            "custom_providers": [
                {
                    "id": "img01",
                    "name": "NewAPI Image",
                    "api_key": "sk-custom",
                    "api_base": "https://newapi.example.com/v1",
                    "model": "newapi-image-model",
                }
            ]
        })
        provider = self.generate._build_providers("", provider_id="custom:img01")[0][1]

        class UrlResponse(_Response):
            def json(self):
                return {
                    "data": [
                        {
                            "b64_json": None,
                            "url": "https://cdn.example.com/rabbit.png",
                        }
                    ]
                }

        def fake_post(url, **kwargs):
            resp = UrlResponse()
            resp.url = url
            return resp

        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(self.generate, "requests", types.SimpleNamespace(post=fake_post)):
                with patch.object(self.generate, "_load_image", return_value=b"fake-png-bytes") as load_image:
                    paths = provider.generate("draw a rabbit", output_dir=tmp)

                    self.assertEqual(len(paths), 1)
                    load_image.assert_called_once_with("https://cdn.example.com/rabbit.png")
                    with open(paths[0], "rb") as f:
                        self.assertEqual(b"fake-png-bytes", f.read())

    def test_custom_provider_generation_proxies_result_download_only(self):
        set_conf({
            "custom_providers": [
                {
                    "id": "img01",
                    "name": "NewAPI Image",
                    "api_key": "sk-custom",
                    "api_base": "https://newapi.example.com/v1",
                    "model": "newapi-image-model",
                }
            ]
        })
        provider = self.generate._build_providers("", provider_id="custom:img01")[0][1]

        class UrlResponse(_Response):
            content = b"fake-png-bytes"

            def json(self):
                return {
                    "data": [
                        {
                            "b64_json": None,
                            "url": "https://assets.grok.com/rabbit.png",
                        }
                    ]
                }

            def raise_for_status(self):
                return None

        post_calls = []
        get_calls = []

        def fake_post(url, **kwargs):
            post_calls.append((url, kwargs))
            resp = UrlResponse()
            resp.url = url
            return resp

        def fake_get(url, **kwargs):
            get_calls.append((url, kwargs))
            return UrlResponse()

        proxy = "http://127.0.0.1:7890"
        self.generate._set_image_download_proxy(proxy, ["assets.grok.com"])
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(self.generate, "requests", types.SimpleNamespace(post=fake_post, get=fake_get)):
                paths = provider.generate("draw a rabbit", output_dir=tmp)

        self.assertEqual(len(paths), 1)
        self.assertNotIn("proxies", post_calls[0][1])
        self.assertEqual({"http": proxy, "https": proxy}, get_calls[0][1]["proxies"])

    def test_load_image_uses_proxy_when_domain_matches(self):
        calls = []

        class ImageResponse:
            content = b"fake-image"

            def raise_for_status(self):
                return None

        def fake_get(url, **kwargs):
            calls.append((url, kwargs))
            return ImageResponse()

        proxy = "http://127.0.0.1:7890"
        with patch.object(self.generate, "requests", types.SimpleNamespace(get=fake_get)):
            data = self.generate._load_image(
                "https://assets.grok.com/users/1/generated/image.jpg",
                proxy=proxy,
                proxy_domains=["assets.grok.com", "*.grok.com"],
            )

        self.assertEqual(b"fake-image", data)
        self.assertEqual("https://assets.grok.com/users/1/generated/image.jpg", calls[0][0])
        self.assertEqual({"http": proxy, "https": proxy}, calls[0][1]["proxies"])

    def test_load_image_skips_proxy_when_domain_does_not_match(self):
        calls = []

        class ImageResponse:
            content = b"fake-image"

            def raise_for_status(self):
                return None

        def fake_get(url, **kwargs):
            calls.append((url, kwargs))
            return ImageResponse()

        with patch.object(self.generate, "requests", types.SimpleNamespace(get=fake_get)):
            data = self.generate._load_image(
                "https://cdn.example.com/rabbit.png",
                proxy="http://127.0.0.1:7890",
                proxy_domains=["assets.grok.com", "*.grok.com"],
            )

        self.assertEqual(b"fake-image", data)
        self.assertNotIn("proxies", calls[0][1])

    def test_load_image_accepts_env_style_domain_list_string(self):
        calls = []

        class ImageResponse:
            content = b"fake-image"

            def raise_for_status(self):
                return None

        def fake_get(url, **kwargs):
            calls.append((url, kwargs))
            return ImageResponse()

        proxy = "http://127.0.0.1:7890"
        with patch.object(self.generate, "requests", types.SimpleNamespace(get=fake_get)):
            data = self.generate._load_image(
                "https://assets.grok.com/users/1/generated/image.jpg",
                proxy=proxy,
                proxy_domains="['assets.grok.com', '*.grok.com']",
            )

        self.assertEqual(b"fake-image", data)
        self.assertEqual({"http": proxy, "https": proxy}, calls[0][1]["proxies"])

    def test_load_image_proxy_config_merges_mixed_legacy_namespaces(self):
        set_conf({})
        with tempfile.TemporaryDirectory() as tmp:
            config_path = os.path.join(tmp, "config.json")
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "tools": {
                            "web_search": {"strategy": "auto"},
                        },
                        "tool": {
                            "web_fetch": {"proxy": "http://127.0.0.1:7890"},
                        },
                        "skills": {
                            "other-skill": {"enabled": True},
                        },
                        "skill": {
                            "image-generation": {
                                "proxy_enabled": True,
                                "proxy_domains": ["assets.grok.com"],
                            },
                        },
                    },
                    f,
                )

            with patch.dict(os.environ, {"LIGHTAGENT_DATA_DIR": tmp}):
                proxy_cfg = self.generate._load_image_proxy_config_from_config_file()

        self.assertEqual("http://127.0.0.1:7890", proxy_cfg["proxy"])
        self.assertTrue(proxy_cfg["proxy_enabled"])
        self.assertEqual(["assets.grok.com"], proxy_cfg["proxy_domains"])

    def test_custom_provider_requires_api_key_base_and_model(self):
        set_conf({
            "custom_providers": [
                {"id": "no-key", "name": "No Key", "api_base": "https://x/v1", "model": "m"},
                {"id": "no-base", "name": "No Base", "api_key": "sk", "model": "m"},
                {"id": "no-model", "name": "No Model", "api_key": "sk", "api_base": "https://x/v1"},
            ]
        })

        with self.assertRaisesRegex(ValueError, "api_key"):
            self.generate._build_providers("", provider_id="custom:no-key")
        with self.assertRaisesRegex(ValueError, "api_base"):
            self.generate._build_providers("", provider_id="custom:no-base")
        with self.assertRaisesRegex(ValueError, "model"):
            self.generate._build_providers("", provider_id="custom:no-model")
        with self.assertRaisesRegex(ValueError, "unknown custom provider id"):
            self.generate._build_providers("", provider_id="custom:missing")


if __name__ == "__main__":
    unittest.main()
