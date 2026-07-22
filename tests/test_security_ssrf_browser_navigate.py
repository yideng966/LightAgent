# encoding:utf-8
"""
Regression tests for browser-navigate SSRF protection.

The browser tool navigates to a model-supplied URL via Playwright
``page.goto`` and then auto-snapshots the page back to the model. Without a
guard, a model (including one under prompt injection) can point it at the
cloud-metadata endpoint (169.254.169.254) and read the credentials back
through the snapshot.

Unlike the vision / web_fetch tools, the browser legitimately needs local
pages — a dev server on ``localhost`` / ``127.0.0.1`` / a LAN IP. So the guard
is deliberately narrow: it blocks only **link-local** addresses
(169.254.0.0/16, which includes the metadata endpoint, plus IPv6 fe80::/10) and
the IPv6 cloud-metadata address, while leaving loopback and RFC1918/LAN
reachable.

These tests ensure ``BrowserTool``:
  - blocks link-local / cloud-metadata targets *before* the navigation reaches
    the browser service,
  - still lets loopback, RFC1918/LAN and public URLs through to the (stubbed)
    service,
  - preserves the documented non-HTTP scheme behaviour (about:/data:), and
  - honours an explicit opt-out (allow_private_targets).

No real browser / Playwright / network is used: the BrowserService that the
tool would create is replaced with a stub, and DNS resolution is mocked.
"""
import os
import sys
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Stub 'requests' if not installed so sibling tool imports don't fail.
if "requests" not in sys.modules:
    _requests_stub = types.ModuleType("requests")
    _requests_stub.get = lambda *a, **k: None
    sys.modules["requests"] = _requests_stub


def _gai(ip_str):
    """Build a socket.getaddrinfo return value for a single IPv4 address."""
    return [(2, 1, 6, "", (ip_str, 0))]


class _StubService:
    """Stand-in for BrowserService that records navigation attempts."""

    def __init__(self):
        self.navigated = []

    def navigate(self, url, timeout=30000):
        self.navigated.append(url)
        return {"url": url, "title": "page", "status": 200}

    def snapshot(self, selector=None):
        return "Page: page  (http://page/)\nInteractive elements: 0\n---\ncontent"


class TestBrowserNavigateSSRF(unittest.TestCase):
    """Browser navigate blocks link-local/metadata but keeps local dev reachable."""

    def setUp(self):
        from agent.tools.browser.browser_tool import BrowserTool
        self.tool = BrowserTool()
        self.stub = _StubService()
        # Force the tool to use our stub instead of a real BrowserService.
        self.tool._service = self.stub
        patcher = patch.object(BrowserTool, "_get_service", return_value=self.stub)
        patcher.start()
        self.addCleanup(patcher.stop)

    # --- Link-local / cloud-metadata: rejected before any service call ---

    def test_cloud_metadata_literal_blocked(self):
        result = self.tool.execute(
            {"action": "navigate", "url": "http://169.254.169.254/latest/meta-data/"}
        )
        self.assertEqual(result.status, "error")
        self.assertIn("blocked for security", str(result.result))
        self.assertEqual(self.stub.navigated, [])

    def test_link_local_literal_blocked(self):
        result = self.tool.execute({"action": "navigate", "url": "http://169.254.1.1/x"})
        self.assertEqual(result.status, "error")
        self.assertIn("blocked for security", str(result.result))
        self.assertEqual(self.stub.navigated, [])

    def test_ipv6_metadata_literal_blocked(self):
        result = self.tool.execute(
            {"action": "navigate", "url": "http://[fd00:ec2::254]/latest/"}
        )
        self.assertEqual(result.status, "error")
        self.assertIn("blocked for security", str(result.result))
        self.assertEqual(self.stub.navigated, [])

    def test_metadata_hostname_blocked(self):
        # A hostname that resolves to the metadata endpoint is blocked too.
        with patch("socket.getaddrinfo", return_value=_gai("169.254.169.254")):
            result = self.tool.execute(
                {"action": "navigate", "url": "http://metadata.internal/latest/meta-data/"}
            )
        self.assertEqual(result.status, "error")
        self.assertIn("blocked for security", str(result.result))
        self.assertEqual(self.stub.navigated, [])

    # --- Local dev targets stay reachable (the maintainer's core workflow) ---

    def test_loopback_literal_allowed(self):
        result = self.tool.execute({"action": "navigate", "url": "http://127.0.0.1:3000/"})
        self.assertEqual(result.status, "success")
        self.assertEqual(self.stub.navigated, ["http://127.0.0.1:3000/"])

    def test_ipv6_loopback_literal_allowed(self):
        result = self.tool.execute({"action": "navigate", "url": "http://[::1]:5173/"})
        self.assertEqual(result.status, "success")
        self.assertEqual(self.stub.navigated, ["http://[::1]:5173/"])

    def test_localhost_bare_allowed(self):
        """A bare 'localhost' (no scheme) gets https:// prepended, then allowed."""
        with patch("socket.getaddrinfo", return_value=_gai("127.0.0.1")):
            result = self.tool.execute({"action": "navigate", "url": "localhost:3000"})
        self.assertEqual(result.status, "success")
        self.assertEqual(self.stub.navigated, ["https://localhost:3000"])

    def test_rfc1918_10_hostname_allowed(self):
        with patch("socket.getaddrinfo", return_value=_gai("10.1.2.3")):
            result = self.tool.execute({"action": "navigate", "url": "http://dev.lan/app"})
        self.assertEqual(result.status, "success")
        self.assertEqual(self.stub.navigated, ["http://dev.lan/app"])

    def test_rfc1918_192_168_hostname_allowed(self):
        with patch("socket.getaddrinfo", return_value=_gai("192.168.0.5")):
            result = self.tool.execute({"action": "navigate", "url": "http://router.lan/admin"})
        self.assertEqual(result.status, "success")
        self.assertEqual(self.stub.navigated, ["http://router.lan/admin"])

    # --- Public URL is allowed through to the (stubbed) service ---

    def test_public_url_allowed(self):
        with patch("socket.getaddrinfo", return_value=_gai("93.184.216.34")):
            result = self.tool.execute({"action": "navigate", "url": "http://example.com/page"})
        self.assertEqual(result.status, "success")
        self.assertEqual(self.stub.navigated, ["http://example.com/page"])

    # --- Documented non-HTTP scheme behaviour preserved (not an egress path) ---

    def test_about_blank_not_blocked(self):
        result = self.tool.execute({"action": "navigate", "url": "about:blank"})
        self.assertEqual(result.status, "success")
        self.assertEqual(self.stub.navigated, ["about:blank"])

    # --- Explicit opt-out lets an operator re-enable metadata/link-local ---

    def test_opt_out_allows_metadata(self):
        from agent.tools.browser.browser_tool import BrowserTool
        tool = BrowserTool({"allow_private_targets": True})
        stub = _StubService()
        tool._service = stub
        with patch.object(BrowserTool, "_get_service", return_value=stub):
            result = tool.execute(
                {"action": "navigate", "url": "http://169.254.169.254/latest/meta-data/"}
            )
        self.assertEqual(result.status, "success")
        self.assertEqual(stub.navigated, ["http://169.254.169.254/latest/meta-data/"])


if __name__ == "__main__":
    unittest.main()
