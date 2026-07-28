import tempfile
import unittest
from pathlib import Path

from scripts.validate_release_notes import validate_release_notes


ROOT = Path(__file__).resolve().parents[1]


VALID_NOTES = """> LightAgent - 多渠道 Agent Harness

本版本提供一项可验证的用户改进。

## 优化改进

- 改进一项用户可感知的行为。

---

## 安装

```bash
docker pull yideng966/lightagent:v9.8.7
```

## 文档

- [项目文档](https://github.com/yideng966/LightAgent)
"""


class ReleaseNotesValidatorTest(unittest.TestCase):
    def _validate(self, content: str, *, filename: str = "v9.8.7.md", tag: str = "v9.8.7"):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / filename
            path.write_text(content, encoding="utf-8")
            return validate_release_notes(path, tag)

    def test_accepts_valid_release_notes(self):
        self.assertEqual([], self._validate(VALID_NOTES))

    def test_rejects_stale_filename_and_placeholder(self):
        errors = self._validate(
            VALID_NOTES.replace("一项可验证的用户改进", "TODO：待补充"),
            filename="v9.8.6.md",
        )

        self.assertTrue(any("文件名必须与标签一致" in error for error in errors))
        self.assertTrue(any("占位内容" in error for error in errors))

    def test_rejects_missing_change_section(self):
        content = VALID_NOTES.replace("## 优化改进\n\n- 改进一项用户可感知的行为。\n\n", "")

        errors = self._validate(content)

        self.assertTrue(any("至少保留一个变更分类" in error for error in errors))

    def test_current_release_notes_pass(self):
        path = ROOT / "docs" / "releases" / "v2.1.11.md"
        self.assertEqual([], validate_release_notes(path, "v2.1.11"))

    def test_release_workflow_uses_versioned_notes(self):
        workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        self.assertIn("publish-github-release:", workflow)
        self.assertIn('NOTES_FILE="docs/releases/${TAG}.md"', workflow)
        self.assertIn("scripts/validate_release_notes.py", workflow)
        self.assertIn('gh release create "$TAG"', workflow)


if __name__ == "__main__":
    unittest.main()
