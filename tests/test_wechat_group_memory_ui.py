import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WechatGroupMemoryUiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.chat_html = (ROOT / "channel/web/chat.html").read_text(encoding="utf-8")
        cls.console_js = (ROOT / "channel/web/static/js/console.js").read_text(encoding="utf-8")
        cls.console_css = (ROOT / "channel/web/static/css/console.css").read_text(encoding="utf-8")

    def _function_source(self, name, next_name=None):
        marker = f"function {name}("
        start = self.console_js.index(marker)
        if next_name:
            candidates = [
                self.console_js.find(f"\nfunction {next_name}(", start),
                self.console_js.find(f"\nasync function {next_name}(", start),
            ]
            end = min(index for index in candidates if index >= 0)
        else:
            end = self.console_js.find("\nfunction ", start + len(marker))
            self.assertNotEqual(-1, end, f"could not isolate JavaScript function: {name}")
        return self.console_js[start:end]

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

    def test_profile_autonomous_learning_uses_main_scroll_flow(self):
        body = self._function_source("buildGroupsProfilesPanel", "buildGroupsProfileEvolutionPanel")

        self.assertIn('return `<div class="w-full min-w-0 pb-1">', body)
        self.assertIn("xl:h-[clamp(360px,46vh,560px)]", body)
        self.assertIn("min-h-[320px] xl:min-h-0", body)
        self.assertNotIn('return `<div class="h-full w-full flex flex-col min-h-0">', body)
        self.assertNotIn("flex-1 min-h-0 grid", body)

        panel = self._function_source("buildGroupsProfileEvolutionPanel", "renderGroupsProfileEvolutionMetric")
        self.assertIn('id="groups-profile-evolution-panel"', panel)
        self.assertIn('id="groups-profile-evolution-content"', panel)
        self.assertIn('ontoggle="setGroupsProfileEvolutionExpanded(this)"', panel)
        self.assertIn("groupsProfilesState.evolutionExpanded", panel)

    def test_profile_autonomous_learning_preserves_draft_and_action_state(self):
        for field in (
            "evolutionExpanded",
            "evolutionDraft",
            "evolutionDirty",
            "evolutionAction",
        ):
            self.assertIn(field, self.console_js)

        self.assertIn("function setGroupsProfileEvolutionExpanded(", self.console_js)
        self.assertIn("function updateGroupsProfileEvolutionDraft(", self.console_js)
        self.assertIn('oninput="updateGroupsProfileEvolutionDraft()"', self.console_js)
        self.assertIn('onchange="updateGroupsProfileEvolutionDraft()"', self.console_js)
        self.assertIn("groupsProfilesState.evolutionDraft || {}", self.console_js)
        self.assertIn("groupsProfilesState.evolutionDirty", self.console_js)

        ensure = self._function_source("ensureGroupsProfilesLoaded", "buildGroupsProfilesPanel")
        self.assertIn("groupsProfilesState.evolutionExpanded", ensure)
        self.assertIn("loadGroupsProfileEvolutionData()", ensure)

    def test_profile_autonomous_learning_refreshes_once_and_updates_profiles(self):
        run = self._function_source("runGroupsProfileEvolution", "refreshGroupsProfilesAfterEvolution")
        rollback = self._function_source("rollbackGroupsProfileEvolutionRun", "formatGroupsProfileTimestamp")
        refresh = self._function_source("refreshGroupsProfilesAfterEvolution", "loadGroupsProfileEvolutionRun")

        self.assertEqual(1, run.count("loadGroupsProfileEvolutionData(true)"))
        self.assertEqual(1, rollback.count("loadGroupsProfileEvolutionData(true)"))
        self.assertNotIn("evolutionLoadedRoom = ''", run)
        self.assertNotIn("evolutionLoadedRoom = ''", rollback)
        self.assertIn("refreshGroupsProfilesAfterEvolution(roomId)", run)
        self.assertIn("refreshGroupsProfilesAfterEvolution(roomId)", rollback)
        self.assertIn("groupsProfilesState.loadedRoomFilter = null", refresh)
        self.assertIn("refreshGroupsProfilesData()", refresh)
        self.assertIn("runStatus === 'skipped'", run)

    def test_profile_requests_drop_stale_room_responses(self):
        body = self._function_source("refreshGroupsProfilesData", "startGroupsProfileCreate")

        self.assertIn("const requestId = ++groupsProfilesState.requestId", body)
        self.assertIn("requestId !== groupsProfilesState.requestId", body)
        self.assertIn("roomId !== groupsProfilesState.roomFilter", body)
        self.assertIn("query !== groupsProfilesState.query", body)

    def test_profile_rollback_is_only_offered_for_the_latest_eligible_run(self):
        body = self._function_source("getGroupsProfileEvolutionRollbackRunId", "renderGroupsProfileEvolutionRun")

        self.assertIn("status === 'running'", body)
        self.assertIn("status !== 'success'", body)
        self.assertIn("Number(run.profile_update_count || 0) > 0", body)

    def test_humanization_removes_full_context_preview(self):
        self.assertNotIn("groupsContextPreviewState", self.console_js)
        self.assertNotIn("buildGroupsContextPreviewPanel", self.console_js)
        self.assertNotIn("ensureGroupsContextPreviewLoaded", self.console_js)
        self.assertNotIn("groups-context-preview-room", self.console_js)
        self.assertNotIn("groups-context-preview-sender", self.console_js)
        self.assertNotIn("groups-context-preview-content", self.console_js)
        self.assertNotIn("/api/wechat-group/memories/preview", self.console_js)
        self.assertNotIn("groups_memory_preview_", self.console_js)
        self.assertNotIn("注入预览", self.console_js)
        self.assertNotIn("Injection preview", self.console_js)

    def test_groups_save_preserves_the_single_main_scroll_position(self):
        loader = self._function_source("loadGroupsView", "getWechatGroupChannel")
        saver = self._function_source(
            "saveWechatGroupSettings",
            "readGroupsAdminRequiredPermissions",
        )

        self.assertIn("options.preserveScroll", loader)
        self.assertIn("previousMain.scrollTop", loader)
        self.assertIn("currentMain.scrollTop = savedScrollTop", loader)
        self.assertIn("loadGroupsView({ preserveScroll: true })", saver)

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
