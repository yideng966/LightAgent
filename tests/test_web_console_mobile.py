import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WebConsoleMobileLayoutTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "channel/web/chat.html").read_text(encoding="utf-8")
        cls.css = (ROOT / "channel/web/static/css/console.css").read_text(encoding="utf-8")
        cls.js = (ROOT / "channel/web/static/js/console.js").read_text(encoding="utf-8")

    def test_console_shell_uses_dynamic_viewport_height(self):
        self.assertEqual(3, self.html.count("console-viewport"))
        self.assertRegex(
            self.css,
            re.compile(
                r"\.console-viewport\s*\{[^}]*height:\s*100vh;"
                r"[^}]*height:\s*100dvh;[^}]*min-height:\s*0;",
                re.DOTALL,
            ),
        )

    def test_mobile_navigation_button_is_accessible_and_touch_sized(self):
        match = re.search(r'<button id="menu-toggle"(?P<attrs>.*?)>', self.html, re.DOTALL)
        self.assertIsNotNone(match)
        attrs = match.group("attrs")
        self.assertIn('type="button"', attrs)
        self.assertIn('aria-controls="sidebar"', attrs)
        self.assertIn('aria-expanded="false"', attrs)
        self.assertIn("w-11", attrs)
        self.assertIn("h-11", attrs)
        self.assertIn("flex-shrink-0", attrs)

    def test_mobile_initialization_does_not_focus_chat_input(self):
        self.assertIn("if (!_isMobileView())", self.js)
        self.assertIn("chatInput.focus({ preventScroll: true });", self.js)

    def test_sidebar_toggle_updates_expanded_state(self):
        self.assertIn("menuToggle.setAttribute('aria-expanded', 'true');", self.js)
        self.assertIn("menuToggle.setAttribute('aria-expanded', 'false');", self.js)


if __name__ == "__main__":
    unittest.main()
