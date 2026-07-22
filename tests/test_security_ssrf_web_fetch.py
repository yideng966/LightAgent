# encoding:utf-8
"""
Regression tests for web_fetch SSRF protection.

The web_fetch tool fetches model-supplied URLs. Without a guard, a model
(including one under prompt injection) can point it at loopback, RFC1918,
link-local or cloud-metadata (169.254.169.254) endpoints, or use a public
URL that 3xx-redirects into such a target. These tests ensure web_fetch
refuses the request instead of connecting to the internal address.

No real network is used: DNS resolution and ``requests.get`` are stubbed.
"""
import os
import sys
import types
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Stub 'requests' if not installed so the module can be imported for testing.
if "requests" not in sys.modules:
    _requests_stub = types.ModuleType("requests")
    _requests_stub.get = lambda *a, **k: None

    class _Exc(Exception):
        pass

    _requests_stub.Timeout = type("Timeout", (_Exc,), {})
    _requests_stub.ConnectionError = type("ConnectionError", (_Exc,), {})
    _requests_stub.HTTPError = type("HTTPError", (_Exc,), {})
    _requests_stub.Response = object
    _compat = types.SimpleNamespace(urljoin=__import__("urllib.parse", fromlist=["urljoin"]).urljoin)
    _requests_stub.compat = _compat
    sys.modules["requests"] = _requests_stub


def _gai(ip_str):
    """Build a socket.getaddrinfo return value for a single IPv4 address."""
    return [(2, 1, 6, "", (ip_str, 0))]


class _FakeRedirect:
    """Minimal stand-in for a requests redirect Response."""

    def __init__(self, location):
        self.is_redirect = True
        self.is_permanent_redirect = False
        self.headers = {"Location": location}
        self.closed = False

    def close(self):
        self.closed = True


def _fake_ok_response(body=b"<html><head><title>internal</title></head><body>secret</body></html>"):
    """A well-formed non-redirect response.

    Returned by the mocked ``requests.get`` so that on UNPATCHED code the
    fetch path runs to completion and the test fails specifically on the
    ``assert_not_called`` guard (proving a request reached the internal
    target), rather than on an incidental error.
    """
    resp = MagicMock()
    resp.is_redirect = False
    resp.is_permanent_redirect = False
    resp.status_code = 200
    resp.headers = {"Content-Type": "text/html; charset=utf-8"}
    resp.content = body
    resp.text = body.decode("utf-8")
    resp.apparent_encoding = "utf-8"
    resp.raise_for_status = lambda: None
    return resp


def _fake_http_error_response(status_code, body=b""):
    """Build a response whose raise_for_status raises requests.HTTPError."""
    import requests

    resp = MagicMock()
    resp.is_redirect = False
    resp.is_permanent_redirect = False
    resp.status_code = status_code
    resp.headers = {"Content-Type": "text/html; charset=utf-8"}
    resp.content = body
    resp.text = body.decode("utf-8")
    resp.apparent_encoding = "utf-8"

    def raise_for_status():
        exc = requests.HTTPError(f"{status_code} Client Error")
        exc.response = resp
        raise exc

    resp.raise_for_status = raise_for_status
    return resp


class TestWebFetchSSRF(unittest.TestCase):
    """web_fetch must refuse internal targets and never connect to them.

    SSRF protection is opt-in (disabled by default), so these tests enable it
    via the WEB_SECURITY_SSRF_PROTECTION env var for the duration of the test.
    """

    def setUp(self):
        self._prev_ssrf_env = os.environ.get("WEB_SECURITY_SSRF_PROTECTION")
        os.environ["WEB_SECURITY_SSRF_PROTECTION"] = "true"
        from agent.tools.web_fetch.web_fetch import WebFetch
        self.tool = WebFetch()

    def tearDown(self):
        if self._prev_ssrf_env is None:
            os.environ.pop("WEB_SECURITY_SSRF_PROTECTION", None)
        else:
            os.environ["WEB_SECURITY_SSRF_PROTECTION"] = self._prev_ssrf_env

    # --- Literal internal IPs: rejected before any socket call ---

    def test_loopback_literal_blocked(self):
        """http://127.0.0.1:<port>/x must be refused, no request issued."""
        with patch("requests.get", return_value=_fake_ok_response()) as mock_get:
            result = self.tool.execute({"url": "http://127.0.0.1:8080/canary"})
        self.assertEqual(result.status, "error")
        self.assertIn("non-public", result.result)
        mock_get.assert_not_called()

    def test_cloud_metadata_literal_blocked(self):
        """http://169.254.169.254/latest/meta-data/ must be refused."""
        with patch("requests.get", return_value=_fake_ok_response()) as mock_get:
            result = self.tool.execute(
                {"url": "http://169.254.169.254/latest/meta-data/"}
            )
        self.assertEqual(result.status, "error")
        self.assertIn("non-public", result.result)
        mock_get.assert_not_called()

    def test_ipv6_loopback_literal_blocked(self):
        """http://[::1]/x must be refused."""
        with patch("requests.get", return_value=_fake_ok_response()) as mock_get:
            result = self.tool.execute({"url": "http://[::1]/canary"})
        self.assertEqual(result.status, "error")
        self.assertIn("non-public", result.result)
        mock_get.assert_not_called()

    # --- RFC1918 host resolved via DNS: rejected after resolution ---

    def test_rfc1918_hostname_blocked(self):
        """A hostname that resolves to 10.x.x.x must be refused, no request."""
        with patch("socket.getaddrinfo", return_value=_gai("10.1.2.3")), \
                patch("requests.get", return_value=_fake_ok_response()) as mock_get:
            result = self.tool.execute({"url": "http://internal.corp/secret"})
        self.assertEqual(result.status, "error")
        self.assertIn("non-public", result.result)
        mock_get.assert_not_called()

    def test_192_168_hostname_blocked(self):
        """A hostname that resolves to 192.168.x.x must be refused."""
        with patch("socket.getaddrinfo", return_value=_gai("192.168.0.5")), \
                patch("requests.get", return_value=_fake_ok_response()) as mock_get:
            result = self.tool.execute({"url": "http://router.local/admin"})
        self.assertEqual(result.status, "error")
        self.assertIn("non-public", result.result)
        mock_get.assert_not_called()

    # --- Redirect bounce: public entry URL 302 -> loopback ---

    def test_public_to_loopback_redirect_blocked(self):
        """A public URL that redirects to a loopback target must be refused.

        The first hop resolves to a public IP and returns a 302 pointing at
        127.0.0.1; the guard must re-validate the redirect target and refuse
        instead of fetching the internal address.
        """
        redirect = _FakeRedirect("http://127.0.0.1:8080/canary")

        def fake_getaddrinfo(host, *a, **k):
            # Public entry host resolves to a public IP; the loopback literal
            # echoes back (as the real getaddrinfo does for an IP literal).
            if host == "evil.example.com":
                return _gai("93.184.216.34")
            return _gai(host)

        with patch("socket.getaddrinfo", side_effect=fake_getaddrinfo), \
                patch("requests.get", return_value=redirect) as mock_get:
            result = self.tool.execute({"url": "http://evil.example.com/start"})

        self.assertEqual(result.status, "error")
        self.assertIn("non-public", result.result)
        # The first (public) hop is issued exactly once; the loopback hop is
        # rejected by the guard BEFORE a second requests.get to the internal
        # target is made.
        self.assertEqual(mock_get.call_count, 1)
        first_call_url = mock_get.call_args[0][0]
        self.assertEqual(first_call_url, "http://evil.example.com/start")
        # The follow-up request to the internal target was never issued.
        for call in mock_get.call_args_list:
            self.assertNotIn("127.0.0.1", call[0][0])

    # --- Sanity: a public URL is allowed to proceed to the fetch path ---

    def test_public_url_allowed_through_guard(self):
        """A public URL passes the guard and a (mocked) request is issued."""
        ok = MagicMock()
        ok.is_redirect = False
        ok.is_permanent_redirect = False
        ok.headers = {"Content-Type": "text/html; charset=utf-8"}
        ok.content = b"<html><head><title>Hi</title></head><body>ok</body></html>"
        ok.text = "<html><head><title>Hi</title></head><body>ok</body></html>"
        ok.apparent_encoding = "utf-8"
        ok.raise_for_status = lambda: None

        with patch("socket.getaddrinfo", return_value=_gai("93.184.216.34")), \
                patch("requests.get", return_value=ok) as mock_get:
            result = self.tool.execute({"url": "http://example.com/page"})

        self.assertEqual(result.status, "success")
        mock_get.assert_called_once()
        self.assertEqual(mock_get.call_args[0][0], "http://example.com/page")


class TestWebFetchSSRFDisabledByDefault(unittest.TestCase):
    """With protection disabled (default), local/internal targets are reachable."""

    def setUp(self):
        self._prev_ssrf_env = os.environ.get("WEB_SECURITY_SSRF_PROTECTION")
        os.environ.pop("WEB_SECURITY_SSRF_PROTECTION", None)
        from agent.tools.web_fetch.web_fetch import WebFetch
        self.tool = WebFetch()

    def tearDown(self):
        if self._prev_ssrf_env is None:
            os.environ.pop("WEB_SECURITY_SSRF_PROTECTION", None)
        else:
            os.environ["WEB_SECURITY_SSRF_PROTECTION"] = self._prev_ssrf_env

    def test_loopback_allowed_when_disabled(self):
        """http://127.0.0.1/x must be fetched when protection is off (default)."""
        with patch("socket.getaddrinfo", return_value=_gai("127.0.0.1")), \
                patch("requests.get", return_value=_fake_ok_response()) as mock_get:
            result = self.tool.execute({"url": "http://127.0.0.1:8080/local"})
        self.assertEqual(result.status, "success")
        mock_get.assert_called_once()


class TestWebFetchProxy(unittest.TestCase):
    """web_fetch should honor configured proxy settings."""

    def test_tool_proxy_config_is_passed_to_requests(self):
        from agent.tools.web_fetch.web_fetch import WebFetch

        proxy = "http://127.0.0.1:7890"
        tool = WebFetch(config={"proxy": proxy})

        with patch("requests.get", return_value=_fake_ok_response()) as mock_get:
            result = tool.execute({"url": "http://example.com/page"})

        self.assertEqual(result.status, "success")
        self.assertEqual(mock_get.call_args.kwargs.get("proxies"), {"http": proxy, "https": proxy})

    def test_global_proxy_config_is_passed_to_requests(self):
        from agent.tools.web_fetch.web_fetch import WebFetch

        proxy = "http://127.0.0.1:7890"
        fake_conf = MagicMock()
        fake_conf.get.side_effect = lambda key, default=None: proxy if key == "proxy" else default

        with patch("config.conf", return_value=fake_conf), \
                patch("requests.get", return_value=_fake_ok_response()) as mock_get:
            result = WebFetch().execute({"url": "http://example.com/page"})

        self.assertEqual(result.status, "success")
        self.assertEqual(mock_get.call_args.kwargs.get("proxies"), {"http": proxy, "https": proxy})


class TestWebFetchNotFoundRecovery(unittest.TestCase):
    """404/410 responses should include bounded same-site navigation hints."""

    def setUp(self):
        self._prev_ssrf_env = os.environ.get("WEB_SECURITY_SSRF_PROTECTION")
        os.environ["WEB_SECURITY_SSRF_PROTECTION"] = "true"
        from agent.tools.web_fetch.web_fetch import WebFetch
        self.tool = WebFetch()

    def tearDown(self):
        if self._prev_ssrf_env is None:
            os.environ.pop("WEB_SECURITY_SSRF_PROTECTION", None)
        else:
            os.environ["WEB_SECURITY_SSRF_PROTECTION"] = self._prev_ssrf_env

    def test_410_includes_same_site_parent_navigation_candidates_only(self):
        parent_html = b"""
        <html><body>
          <a href="/symedia/process/">Process</a>
          <a href="../guide/">Guide</a>
          <a href="https://docs.example.com/symedia/api/">API</a>
          <a href="https://docs.example.com/symedia/missing-too">Broken</a>
          <a href="https://evil.example.net/phish">External</a>
          <a href="javascript:alert(1)">JS</a>
          <a href="mailto:ops@example.com">Mail</a>
          <a href="http://127.0.0.1/admin">Internal</a>
        </body></html>
        """
        responses = {
            "https://docs.example.com/symedia/process/missing": _fake_http_error_response(410),
            "https://docs.example.com/symedia/process/": _fake_ok_response(parent_html),
            "https://docs.example.com/symedia/guide/": _fake_ok_response(),
            "https://docs.example.com/symedia/api/": _fake_ok_response(),
            "https://docs.example.com/symedia/missing-too": _fake_http_error_response(404),
        }

        with patch("socket.getaddrinfo", return_value=_gai("93.184.216.34")), \
                patch("requests.get", side_effect=lambda url, **kwargs: responses[url]):
            result = self.tool.execute({"url": "https://docs.example.com/symedia/process/missing"})

        self.assertEqual(result.status, "error")
        self.assertIn("Error: HTTP 410 for URL: https://docs.example.com/symedia/process/missing", result.result)
        self.assertIn("Try parent paths:", result.result)
        self.assertIn("https://docs.example.com/symedia/process/", result.result)
        self.assertIn("https://docs.example.com/symedia/", result.result)
        self.assertIn("Navigation candidates from https://docs.example.com/symedia/process/:", result.result)
        self.assertIn("https://docs.example.com/symedia/guide/", result.result)
        self.assertIn("https://docs.example.com/symedia/api/", result.result)
        self.assertIn("Do not keep guessing deeper URLs", result.result)
        self.assertNotIn("https://docs.example.com/symedia/missing-too", result.result)
        self.assertNotIn("evil.example.net", result.result)
        self.assertNotIn("javascript:", result.result)
        self.assertNotIn("mailto:", result.result)
        self.assertNotIn("127.0.0.1", result.result)

    def test_404_with_unavailable_parents_keeps_original_error_and_stops_guessing(self):
        responses = {
            "https://docs.example.com/symedia/process/missing": _fake_http_error_response(404),
            "https://docs.example.com/symedia/process/": _fake_http_error_response(404),
            "https://docs.example.com/symedia/": _fake_http_error_response(404),
        }

        with patch("socket.getaddrinfo", return_value=_gai("93.184.216.34")), \
                patch("requests.get", side_effect=lambda url, **kwargs: responses[url]):
            result = self.tool.execute({"url": "https://docs.example.com/symedia/process/missing"})

        self.assertEqual(result.status, "error")
        self.assertIn("Error: HTTP 404 for URL: https://docs.example.com/symedia/process/missing", result.result)
        self.assertIn("No reachable same-site parent page was found", result.result)
        self.assertIn("Do not keep guessing deeper URLs", result.result)

    def test_same_site_candidate_probe_attempts_are_bounded_and_deduplicated(self):
        parent_html = b"""
        <html><body>
          <a href="/bad-1">Bad 1</a>
          <a href="/bad-1">Bad 1 duplicate</a>
          <a href="/bad-2">Bad 2</a>
          <a href="/bad-3">Bad 3</a>
          <a href="/bad-4">Bad 4</a>
          <a href="/bad-5">Bad 5</a>
          <a href="/bad-6">Bad 6</a>
          <a href="/good">Good but too late</a>
        </body></html>
        """
        responses = {
            "https://docs.example.com/symedia/process/missing": _fake_http_error_response(404),
            "https://docs.example.com/symedia/process/": _fake_ok_response(parent_html),
            "https://docs.example.com/symedia/": _fake_http_error_response(404),
            "https://docs.example.com/bad-1": _fake_http_error_response(404),
            "https://docs.example.com/bad-2": _fake_http_error_response(404),
            "https://docs.example.com/bad-3": _fake_http_error_response(404),
            "https://docs.example.com/bad-4": _fake_http_error_response(404),
            "https://docs.example.com/bad-5": _fake_http_error_response(404),
            "https://docs.example.com/bad-6": _fake_http_error_response(404),
            "https://docs.example.com/good": _fake_ok_response(),
        }
        requested_urls = []

        def fake_get(url, **kwargs):
            requested_urls.append(url)
            return responses[url]

        with patch("socket.getaddrinfo", return_value=_gai("93.184.216.34")), \
                patch("requests.get", side_effect=fake_get):
            result = self.tool.execute({"url": "https://docs.example.com/symedia/process/missing"})

        self.assertEqual(result.status, "error")
        self.assertEqual(requested_urls.count("https://docs.example.com/bad-1"), 1)
        self.assertIn("https://docs.example.com/bad-5", requested_urls)
        self.assertNotIn("https://docs.example.com/bad-6", requested_urls)
        self.assertNotIn("https://docs.example.com/good", requested_urls)
        self.assertNotIn("https://docs.example.com/good", result.result)


if __name__ == "__main__":
    unittest.main()
