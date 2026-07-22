# encoding:utf-8
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class BrowserServiceDependencyTest(unittest.TestCase):
    def test_launch_browser_reports_missing_playwright_dependency(self):
        from agent.tools.browser import browser_service
        from agent.tools.browser.browser_service import BrowserService

        service = BrowserService({"persistent": False, "headless": True})

        with patch.object(browser_service, "_HAS_PLAYWRIGHT", False):
            with self.assertRaisesRegex(RuntimeError, "pip install playwright"):
                service._launch_browser()


if __name__ == "__main__":
    unittest.main()
