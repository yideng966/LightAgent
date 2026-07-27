#!/usr/bin/env python3
"""校验 LightAgent GitHub Release 说明的最小发布合同。"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Dict, List


CHANGE_SECTIONS = (
    "新增功能",
    "优化改进",
    "Bug 修复",
    "安全修复",
    "破坏性变更",
)
REQUIRED_SECTIONS = ("安装", "文档")
PLACEHOLDER_PATTERNS = (
    re.compile(r"\b(?:TODO|TBD)\b", re.IGNORECASE),
    re.compile(r"<[^>\n]+>"),
    re.compile(r"待补充|待填写|请填写|按需保留|占位"),
    re.compile(r"vX\.Y\.Z", re.IGNORECASE),
)


def _section_bodies(text: str) -> Dict[str, str]:
    matches = list(re.finditer(r"^##\s+(.+?)\s*$", text, re.MULTILINE))
    bodies: Dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        bodies[match.group(1)] = text[match.end() : end].strip()
    return bodies


def validate_release_notes(path: Path, tag: str) -> List[str]:
    """返回发行说明中的校验错误；空列表表示可发布。"""

    errors: List[str] = []
    if not re.fullmatch(r"v\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?", tag):
        errors.append(f"标签格式无效：{tag}")
    if path.name != f"{tag}.md":
        errors.append(f"文件名必须与标签一致：期望 {tag}.md，实际为 {path.name}")

    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        errors.append(f"无法按 UTF-8 读取发行说明：{exc}")
        return errors

    if not text.strip():
        errors.append("发行说明不能为空")
        return errors

    first_line = text.splitlines()[0].strip()
    if not first_line.startswith("> LightAgent - ") or len(first_line) <= len("> LightAgent - "):
        errors.append("首行必须使用“> LightAgent - <项目定位>”格式")

    first_heading = re.search(r"^##\s+", text, re.MULTILINE)
    preamble = text[: first_heading.start()] if first_heading else text
    summary_lines = [
        line.strip()
        for line in preamble.splitlines()[1:]
        if line.strip() and not line.lstrip().startswith((">", "<!--"))
    ]
    if not summary_lines:
        errors.append("项目定位后必须有一段面向用户的版本摘要")

    if re.search(r"^#\s+", text, re.MULTILINE):
        errors.append("正文不得重复一级标题，Release 标题由工作流生成")

    for pattern in PLACEHOLDER_PATTERNS:
        if pattern.search(text):
            errors.append(f"发行说明仍包含占位内容：{pattern.pattern}")

    sections = _section_bodies(text)
    change_sections = [name for name in CHANGE_SECTIONS if name in sections]
    if not change_sections:
        errors.append("至少保留一个变更分类：新增功能、优化改进、Bug 修复、安全修复或破坏性变更")
    for name in change_sections:
        if not re.search(r"^-\s+\S", sections[name], re.MULTILINE):
            errors.append(f"“{name}”分类至少需要一个列表项")

    for name in REQUIRED_SECTIONS:
        if not sections.get(name):
            errors.append(f"缺少非空的“{name}”章节")

    if tag not in sections.get("安装", ""):
        errors.append("安装章节必须包含当前完整版本标签，避免发布未固定版本的命令")
    if "](http" not in sections.get("文档", ""):
        errors.append("文档章节至少需要一个可访问的 Markdown 链接")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="发行说明 Markdown 文件")
    parser.add_argument("--tag", required=True, help="待发布的完整 Git 标签，例如 v2.1.6")
    args = parser.parse_args()

    errors = validate_release_notes(args.path, args.tag)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print(f"发行说明校验通过：{args.path} ({args.tag})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
