import unittest
from unittest.mock import patch

from channel.wechat_group.wechat_group_report_link_service import (
    WechatGroupReportLinkService,
    extract_http_urls,
    normalize_http_url,
)


class _Response:
    def __init__(self, status_code, headers, body=b""):
        self.status_code = status_code
        self.headers = headers
        self._body = body
        self.encoding = "utf-8"
        self.is_redirect = status_code in {301, 302, 303, 307, 308}

    def iter_content(self, chunk_size=16384):
        yield self._body

    def close(self):
        return None


class _Session:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


class WechatGroupReportLinksTest(unittest.TestCase):
    def test_extract_and_normalize_keeps_http_order_and_removes_fragment(self):
        urls = extract_http_urls("看 https://EXAMPLE.com:443/path#one，再看 http://a.test/x。ftp://bad")

        self.assertEqual(["https://EXAMPLE.com:443/path#one", "http://a.test/x"], urls)
        self.assertEqual("https://example.com/path", normalize_http_url(urls[0]))

    def test_redirect_targets_are_revalidated_before_fetch(self):
        session = _Session([
            _Response(302, {"Location": "https://public.example/final"}),
            _Response(200, {"Content-Type": "text/html"}, b"<title>Public</title><p>body</p>"),
        ])
        validated = []
        service = WechatGroupReportLinkService(session=session)

        with patch(
            "channel.wechat_group.wechat_group_report_link_service.validate_url_strict",
            side_effect=lambda url: validated.append(url),
        ):
            result = service.enrich_links([{"url": "https://public.example/start"}])

        self.assertEqual(["https://public.example/start", "https://public.example/final"], validated)
        self.assertEqual("ok", result[0]["fetch_status"])
        self.assertEqual("Public", result[0]["summary"])

    def test_ssrf_rejection_keeps_link_without_model_summary(self):
        summary = unittest.mock.Mock(return_value="must not run")
        service = WechatGroupReportLinkService(summary_provider=summary, session=_Session([]))

        with patch(
            "channel.wechat_group.wechat_group_report_link_service.validate_url_strict",
            side_effect=ValueError("private"),
        ):
            result = service.enrich_links([{"url": "http://127.0.0.1/private"}])

        self.assertEqual("blocked", result[0]["fetch_status"])
        summary.assert_not_called()


if __name__ == "__main__":
    unittest.main()
