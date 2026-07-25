import shutil
import tempfile
import unittest
from pathlib import Path

from agent.skills.manager import SkillManager
from channel.wechat_group.wechat_group_report_templates import (
    get_builtin_text_template,
    render_text_report,
    split_report_text,
    validate_text_template,
)
from channel.wechat_group.wechat_group_report_store import normalize_report_settings
from channel.wechat_group.wechat_group_report_templates_registry import (
    DEFAULT_CYBER_INTELLIGENCE_SKILL,
    WechatGroupReportTemplateRegistry,
)


ROOT = Path(__file__).resolve().parents[1]


def _report():
    return {
        "room_name": "测试群",
        "report_type": "daily",
        "period_start": "2026-07-20T00:00:00+08:00",
        "period_end": "2026-07-21T00:00:00+08:00",
        "timezone": "Asia/Shanghai",
        "active_speaker_count": 1,
        "total_messages": 1,
        "top_speaker": {"display_name": "Alice", "message_count": 1},
        "topic_count": 1,
        "ranking": [{"rank": 1, "display_name": "Alice", "message_count": 1}],
        "topics": [{"title": "计划", "summary": "推进测试", "heat": 80}],
        "highlights": [{"speaker_display_name": "Alice", "quote": "完成了", "commentary": "推进明确"}],
        "links": [],
        "archive_message_count": 1,
        "unresolved_message_count": 0,
        "generated_at": "2026-07-21T09:00:00+08:00",
    }


class WechatGroupReportTemplatesTest(unittest.TestCase):
    def test_builtin_template_renders_all_required_blocks(self):
        for template_id in ("standard_text", "compact_text"):
            with self.subTest(template_id=template_id):
                rendered = render_text_report(_report(), get_builtin_text_template(template_id))

                self.assertIn("测试群", rendered)
                self.assertIn("Alice", rendered)
                self.assertIn("计划", rendered)
                self.assertIn("本周期未收集到链接", rendered)

    def test_builtin_template_rejects_unknown_id(self):
        with self.assertRaisesRegex(ValueError, "unknown builtin text template"):
            get_builtin_text_template("not-a-template")

        with self.assertRaisesRegex(ValueError, "unknown builtin text template"):
            normalize_report_settings({
                "output": {
                    "mode": "text",
                    "text_template_source": "builtin",
                    "builtin_text_template_id": "not-a-template",
                },
            })

    def test_template_rejects_attribute_access_and_missing_required_blocks(self):
        with self.assertRaisesRegex(ValueError, "unsupported text template field"):
            validate_text_template("{room_name.__class__}")
        with self.assertRaisesRegex(ValueError, "misses required fields"):
            validate_text_template("{room_name}")

    def test_rendering_hides_internal_identifiers_and_splits_without_loss(self):
        report = _report()
        report["room_name"] = "wgr_secret /home/agent/private"
        rendered = render_text_report(report, get_builtin_text_template())
        parts = split_report_text(rendered + "\n\n" + ("很长的文本。" * 500), max_chars=220)

        self.assertNotIn("wgr_secret", rendered)
        self.assertNotIn("/home/agent/private", rendered)
        self.assertGreater(len(parts), 1)
        self.assertEqual(rendered + "\n\n" + ("很长的文本。" * 500), "".join(parts))

    def test_default_skill_template_manifest_is_discoverable(self):
        template = WechatGroupReportTemplateRegistry().resolve_template(
            DEFAULT_CYBER_INTELLIGENCE_SKILL
        )

        self.assertTrue(template["valid"])
        self.assertEqual("cyber_intelligence", template["template_id"])
        self.assertEqual(941, template["width"])

    def test_default_skill_uses_bundled_template_when_workspace_has_stale_override(self):
        with tempfile.TemporaryDirectory() as tempdir:
            custom_dir = Path(tempdir) / "skills"
            stale_dir = custom_dir / DEFAULT_CYBER_INTELLIGENCE_SKILL
            shutil.copytree(ROOT / "skills" / DEFAULT_CYBER_INTELLIGENCE_SKILL, stale_dir)
            manifest_path = stale_dir / "assets" / "wechat-group-report-template.json"
            manifest_path.write_text(
                manifest_path.read_text(encoding="utf-8").replace('"version": "1.1.0"', '"version": "1.0.0"'),
                encoding="utf-8",
            )
            registry = WechatGroupReportTemplateRegistry(SkillManager(
                builtin_dir=str(ROOT / "skills"), custom_dir=str(custom_dir),
            ))

            template = registry.resolve_template(DEFAULT_CYBER_INTELLIGENCE_SKILL)

        self.assertEqual("1.1.0", template["version"])
        self.assertEqual(
            (ROOT / "skills" / DEFAULT_CYBER_INTELLIGENCE_SKILL).resolve(),
            Path(template["base_dir"]).resolve(),
        )


if __name__ == "__main__":
    unittest.main()
