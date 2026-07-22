# encoding:utf-8
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _read(relative_path):
    with open(os.path.join(ROOT, relative_path), "r", encoding="utf-8") as f:
        return f.read()


class TestKnowledgeSourceReliabilityRules(unittest.TestCase):
    def test_prompt_builder_requires_verified_navigation_sources(self):
        source = _read("agent/prompt/builder.py")

        self.assertIn("优先使用页面真实暴露的导航链接", source)
        self.assertIn("只把已经成功读取的 URL 写入 Source", source)
        self.assertIn("404/410、失败请求或猜测路径不得写成资料来源", source)
        self.assertIn("Prefer navigation links actually exposed on the page", source)
        self.assertIn("Only record URLs that were successfully fetched as Source", source)
        self.assertIn("404/410, failed requests, or guessed paths must not be written as sources", source)

    def test_workspace_prompt_repeats_verified_source_rules(self):
        source = _read("agent/prompt/workspace.py")

        self.assertIn("优先使用页面真实暴露的导航链接", source)
        self.assertIn("只把已经成功读取的 URL 写入 Source", source)
        self.assertIn("404/410、失败请求或猜测路径不得写成资料来源", source)
        self.assertIn("Prefer navigation links actually exposed on the page", source)
        self.assertIn("Only record URLs that were successfully fetched as Source", source)
        self.assertIn("404/410, failed requests, or guessed paths must not be written as sources", source)

    def test_knowledge_wiki_skill_rejects_guessed_or_failed_sources(self):
        source = _read("skills/knowledge-wiki/SKILL.md")

        self.assertIn("Prefer navigation links actually exposed on the page", source)
        self.assertIn("Only record URLs that were successfully fetched as Source", source)
        self.assertIn("404/410, failed requests, or guessed paths must not be written as sources", source)


if __name__ == "__main__":
    unittest.main()
