import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WechatGroupMemoryUiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.chat_html = (ROOT / "channel/web/chat.html").read_text(encoding="utf-8")
        cls.console_js = (ROOT / "channel/web/static/js/console.js").read_text(encoding="utf-8")
        cls.console_css = (ROOT / "channel/web/static/css/console.css").read_text(encoding="utf-8")

    def test_memory_view_is_the_only_group_memory_management_entry(self):
        self.assertIn('id="memory-scope-global"', self.chat_html)
        self.assertIn('id="memory-scope-group"', self.chat_html)
        self.assertIn('id="group-memory-content"', self.chat_html)
        self.assertIn('id="group-memory-dialog"', self.chat_html)
        self.assertIn("const groupMemoryState =", self.console_js)
        self.assertIn("function switchMemoryScope(", self.console_js)
        self.assertIn("function renderGroupMemoryView(", self.console_js)

        self.assertNotIn("groups_nav_memory", self.console_js)
        self.assertNotIn("groupsMemoryState", self.console_js)
        self.assertNotIn("buildGroupsMemoryPanel", self.console_js)
        self.assertNotIn("groupsActiveSection === 'memory'", self.console_js)
        self.assertNotIn("buildGroupsSectionButton('memory'", self.console_js)

    def test_group_memory_view_preserves_management_capabilities(self):
        expected_functions = [
            "loadGroupMemoryRooms",
            "loadGroupMemoryItems",
            "submitGroupMemoryDialog",
            "disableGroupMemory",
            "loadGroupMemoryRuntime",
            "runGroupMemoryIncremental",
            "previewGroupMemoryHistory",
            "runGroupMemoryHistory",
            "runGroupMemoryRecall",
        ]
        for name in expected_functions:
            self.assertIn(f"function {name}(", self.console_js)

        expected_endpoints = [
            "/api/wechat-group/memories/groups",
            "/api/wechat-group/memories/group",
            "/api/wechat-group/memories/disable",
            "/api/wechat-group/memories/config",
            "/api/wechat-group/memories/learn/status",
            "/api/wechat-group/memories/learn/runs",
            "/api/wechat-group/memories/learn/history/preview",
            "/api/wechat-group/memories/learn/history",
            "/api/wechat-group/memories/recall",
        ]
        for endpoint in expected_endpoints:
            self.assertIn(endpoint, self.console_js)

        self.assertIn("pageSize: 20", self.console_js)
        self.assertIn("offset: String((groupMemoryState.page - 1) * groupMemoryState.pageSize)", self.console_js)
        self.assertIn("min_score: String(groupMemoryState.recallMinScore)", self.console_js)
        self.assertIn("sequence !== groupMemoryState.requestSequence", self.console_js)

    def test_profiles_keep_autonomous_learning_after_memory_entry_removal(self):
        self.assertIn("groups_nav_profiles", self.console_js)
        self.assertIn("function buildGroupsProfilesPanel(", self.console_js)
        self.assertIn('id="groups-profiles-room-filter"', self.console_js)
        self.assertIn('id="groups-profiles-list"', self.console_js)
        self.assertIn('id="groups-profiles-detail"', self.console_js)
        self.assertIn("function loadGroupsProfileEvolutionData(", self.console_js)
        self.assertIn("function saveGroupsProfileEvolutionConfig(", self.console_js)
        self.assertIn("function runGroupsProfileEvolution(", self.console_js)
        self.assertIn("function rollbackGroupsProfileEvolutionRun(", self.console_js)
        self.assertIn("/api/wechat-group/memories/profiles/config", self.console_js)
        self.assertIn("/api/wechat-group/memories/profile-evolution/status", self.console_js)
        self.assertIn("/api/wechat-group/memories/profile-evolution/runs", self.console_js)
        self.assertIn("/api/wechat-group/memories/profile-evolution/run", self.console_js)
        self.assertIn("/api/wechat-group/memories/profile-evolution/rollback", self.console_js)
        self.assertIn("evolutionRequestId", self.console_js)
        self.assertIn("resetGroupsProfileEvolutionRoomState", self.console_js)

    def test_humanization_keeps_full_context_preview(self):
        start = self.console_js.index("function buildGroupsContextPreviewPanel")
        end = self.console_js.index("function ensureGroupsContextPreviewLoaded", start)
        body = self.console_js[start:end]

        self.assertIn("groups-context-preview-room", body)
        self.assertIn("groups-context-preview-sender", body)
        self.assertIn("groups-context-preview-content", body)
        self.assertIn("/api/wechat-group/memories/preview", self.console_js)
        self.assertIn("<wechat-group-memory>".strip(""), self.console_js)
        self.assertIn("群记忆与画像上下文", self.console_js)

    def test_group_memory_tabs_and_dialog_are_keyboard_accessible(self):
        self.assertIn("function handleMemoryScopeKey(", self.console_js)
        self.assertIn("function handleGroupMemoryTabKey(", self.console_js)
        self.assertIn("group-memory-tab-${id}", self.console_js)
        self.assertIn("aria-selected=", self.console_js)
        self.assertIn("tabindex=", self.console_js)
        self.assertIn("'group-memory-tab-' + groupMemoryState.activeTab", self.console_js)
        self.assertIn("document.getElementById(focusedTabId)?.focus()", self.console_js)
        self.assertIn("function handleGroupMemoryDialogKey(", self.console_js)
        self.assertIn("event.key === 'Escape'", self.console_js)
        self.assertIn("groupMemoryState.dialogReturnFocus?.focus?.()", self.console_js)
        self.assertIn("prefers-reduced-motion: reduce", self.console_css)
        self.assertIn(".memory-scope-tab:focus-visible", self.console_css)
        self.assertIn(".group-memory-tab:focus-visible", self.console_css)

    def test_profile_room_names_keep_saved_name_fallback(self):
        start = self.console_js.index("function getGroupsMemoryRooms(extra)")
        end = self.console_js.index("function resetGroupsProfileEvolutionRoomState", start)
        body = self.console_js[start:end]

        self.assertIn("selected_room_names", body)
        self.assertIn("selectedNames[idx]", body)

    def test_console_cache_busting_remains_chat_handler_owned(self):
        self.assertIn('src="assets/js/console.js"', self.chat_html)
        self.assertNotIn("assets/js/console.js?v=", self.chat_html)


if __name__ == "__main__":
    unittest.main()
