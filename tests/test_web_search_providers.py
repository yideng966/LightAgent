# encoding:utf-8
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class FakeResponse:
    def __init__(self, status_code=200, data=None, text=""):
        self.status_code = status_code
        self._data = data or {}
        self.text = text

    def json(self):
        return self._data


class WebSearchProviderTest(unittest.TestCase):
    def _fake_conf(self, overrides=None):
        cfg = {
            "tools": {
                "web_search": {
                    "serper_api_key": "serper-key",
                    "jina_api_key": "jina-key",
                }
            }
        }
        if overrides:
            cfg.update(overrides)
        return cfg

    def test_configured_providers_include_serper_and_jina(self):
        from agent.tools.web_search import web_search

        with patch("agent.tools.web_search.web_search.conf", return_value=self._fake_conf()):
            self.assertIn("serper", web_search.configured_providers())
            self.assertIn("jina", web_search.configured_providers())
            self.assertTrue(web_search.WebSearch.is_available())

    def test_serper_search_uses_dedicated_key_and_normalizes_results(self):
        from agent.tools.web_search.web_search import WebSearch

        response = FakeResponse(data={
            "organic": [{
                "title": "Serper result",
                "link": "https://example.com/serper",
                "snippet": "Serper snippet",
                "source": "Example",
                "date": "2026-07-03",
            }]
        })

        with patch("agent.tools.web_search.web_search.conf", return_value=self._fake_conf()):
            with patch("agent.tools.web_search.web_search.requests.post", return_value=response) as post:
                result = WebSearch().execute({"query": "test query", "provider": "serper", "count": 3})

        self.assertEqual(result.status, "success")
        self.assertEqual(result.result["backend"], "serper")
        self.assertEqual(result.result["results"][0]["url"], "https://example.com/serper")
        url, kwargs = post.call_args.args[0], post.call_args.kwargs
        self.assertEqual(url, "https://google.serper.dev/search")
        self.assertEqual(kwargs["headers"]["X-API-KEY"], "serper-key")
        self.assertEqual(kwargs["json"]["q"], "test query")
        self.assertEqual(kwargs["json"]["num"], 3)

    def test_jina_search_uses_dedicated_key_and_parses_text_results(self):
        from agent.tools.web_search.web_search import WebSearch

        text = (
            "[1] Jina result\n"
            "URL: https://example.com/jina\n"
            "Description: Jina snippet with enough text to avoid short body checks.\n"
        )
        response = FakeResponse(text=text)

        with patch("agent.tools.web_search.web_search.conf", return_value=self._fake_conf()):
            with patch("agent.tools.web_search.web_search.requests.get", return_value=response) as get:
                result = WebSearch().execute({"query": "test/query", "provider": "jina", "count": 2})

        self.assertEqual(result.status, "success")
        self.assertEqual(result.result["backend"], "jina")
        self.assertEqual(result.result["results"][0]["url"], "https://example.com/jina")
        url, kwargs = get.call_args.args[0], get.call_args.kwargs
        self.assertEqual(url, "https://s.jina.ai/test%2Fquery")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer jina-key")
        self.assertEqual(kwargs["headers"]["X-Respond-With"], "no-references")


if __name__ == "__main__":
    unittest.main()
