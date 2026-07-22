import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WechatGroupMemoryUiTest(unittest.TestCase):
    def test_groups_page_exposes_memory_management_section(self):
        console_js = (ROOT / "channel/web/static/js/console.js").read_text(encoding="utf-8")

        self.assertIn("groups_nav_memory", console_js)
        self.assertIn("groups_nav_profiles", console_js)
        self.assertIn("buildGroupsMemoryPanel", console_js)
        self.assertIn("buildGroupsProfilesPanel", console_js)
        self.assertIn("groups-profiles-room-filter", console_js)
        self.assertIn("groups-profiles-search", console_js)
        self.assertIn("groups-profiles-list", console_js)
        self.assertIn("groups-profiles-detail", console_js)
        self.assertIn("groups-profiles-create-member", console_js)
        self.assertIn("startGroupsProfileCreate", console_js)
        self.assertIn("selectGroupsProfile", console_js)
        self.assertIn("refreshGroupsProfilesData", console_js)
        self.assertIn("groups-memory-room-list", console_js)
        self.assertIn("groups-memory-group-content", console_js)
        self.assertIn("groups_memory_profiles_moved_hint", console_js)
        self.assertIn("goToGroupsProfilesSection", console_js)
        self.assertNotIn("${buildGroupsMemoryProfilesPanel(selectedRoomId)}", console_js)
        self.assertNotIn("groups-memory-profile-sender-id", console_js)
        self.assertNotIn("groups-memory-profile-aliases", console_js)
        self.assertNotIn("groups-memory-profile-member-query", console_js)
        self.assertNotIn("searchGroupsMemberProfiles", console_js)
        self.assertNotIn("selectGroupsMemberProfile", console_js)
        self.assertIn("groups-memory-preview-content", console_js)
        self.assertIn("groups-memory-search", console_js)
        self.assertIn("disableGroupsGroupMemory", console_js)
        self.assertIn("/api/wechat-group/memories/summary", console_js)
        self.assertIn("/api/wechat-group/memories/disable", console_js)
        self.assertIn("/api/wechat-group/memories/group", console_js)
        self.assertIn("/api/wechat-group/memories/profiles", console_js)
        self.assertIn("/api/wechat-group/memories/preview", console_js)
        self.assertIn("name_records", console_js)
        self.assertIn("last_seen_at", console_js)
        self.assertIn("buildGroupsMemoryLearningPanel", console_js)
        self.assertIn("runGroupsMemoryLearning", console_js)
        self.assertIn("/api/wechat-group/memories/learn/run", console_js)
        self.assertIn("/api/wechat-group/memories/learn/runs", console_js)
        self.assertIn("/api/wechat-group/memories/profile-evolution/config", console_js)
        self.assertIn("/api/wechat-group/memories/profile-evolution/status", console_js)
        self.assertIn("/api/wechat-group/memories/profile-evolution/runs", console_js)
        self.assertIn("/api/wechat-group/memories/profile-evolution/run", console_js)
        self.assertIn("/api/wechat-group/memories/profile-evolution/rollback", console_js)
        self.assertIn("groups-memory-profile-evolution-enabled", console_js)
        self.assertIn("groups-memory-profile-evolution-status", console_js)
        self.assertIn("groups-memory-profile-evolution-runs", console_js)
        self.assertIn("rollbackGroupsProfileEvolutionRun", console_js)
        self.assertIn("每个群独立维护群友画像", console_js)
        self.assertNotIn("全局画像", console_js)
        self.assertIn("<wechat-group-memory>", console_js)
        self.assertNotIn("/api/wechat-group/memories/distill/run", console_js)
        self.assertNotIn("/api/wechat-group/memories/distill/runs", console_js)
        self.assertNotIn("/api/wechat-group/memories/distill/candidates", console_js)
        self.assertNotIn("/api/wechat-group/memories/profiles/revisions", console_js)
        self.assertNotIn("approveGroupsMemoryCandidate", console_js)
        self.assertNotIn("rejectGroupsMemoryCandidate", console_js)
        self.assertNotIn("candidate review", console_js.lower())

    def test_room_profiles_list_counts_actual_name_records(self):
        console_js = (ROOT / "channel/web/static/js/console.js").read_text(encoding="utf-8")
        start = console_js.index("function buildGroupsProfilesList")
        end = console_js.index("function buildGroupsProfilesDetail", start)
        body = console_js[start:end]

        self.assertIn("const nameRecords = Array.isArray(profile.name_records) ? profile.name_records : [];", body)
        self.assertIn("String(nameRecords.length)", body)
        self.assertNotIn("String(roomSummaries.length)", body)

    def test_groups_page_cache_buster_changes_for_memory_ui(self):
        chat_html = (ROOT / "channel/web/chat.html").read_text(encoding="utf-8")

        self.assertIn("console.js?v=20260720-room-profiles", chat_html)

    def test_groups_memory_rooms_use_saved_room_names_as_fallback(self):
        console_js = (ROOT / "channel/web/static/js/console.js").read_text(encoding="utf-8")
        start = console_js.index("function getGroupsMemoryRooms(extra)")
        end = console_js.index("function ensureGroupsMemoryLoaded", start)
        body = console_js[start:end]

        self.assertIn("selected_room_names", body)
        self.assertIn("selectedNames[idx]", body)

    def test_learning_runs_format_started_at_as_full_datetime(self):
        console_js = (ROOT / "channel/web/static/js/console.js").read_text(encoding="utf-8")
        start = console_js.index("function buildGroupsMemoryLearningPanel")
        end = console_js.index("function buildGroupsMemoryNumberInput", start)
        body = console_js[start:end]

        self.assertIn("function formatGroupsMemoryRunTimestamp(value)", console_js)
        self.assertIn("formatGroupsMemoryRunTimestamp(run.started_at)", body)
        self.assertNotIn("String(run.started_at || '')", body)


if __name__ == "__main__":
    unittest.main()
