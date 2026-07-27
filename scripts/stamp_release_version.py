#!/usr/bin/env python3
"""将发布版本同步写入 LightAgent 的两个 Python 版本来源。"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


VERSION_PATTERN = re.compile(
    r"\d+\.\d+\.\d+(?:-(?:alpha|beta|rc|dev)(?:\.\d+)?)?\Z"
)
VERSION_LINE_PATTERN = re.compile(
    r'^(\s*version\s*=\s*")[^"\r\n]*("[^\r\n]*)(\r?\n)?$'
)


def stamp_release_version(root: Path, version: str) -> None:
    """校验版本，并同步更新 cli/VERSION 与 [project].version。"""

    if version != version.strip() or not VERSION_PATTERN.fullmatch(version):
        raise ValueError(f"无效的发布版本：{version!r}")

    root = root.resolve()
    cli_version_path = root / "cli" / "VERSION"
    pyproject_path = root / "pyproject.toml"
    if not cli_version_path.is_file():
        raise FileNotFoundError(f"缺少版本文件：{cli_version_path}")
    if not pyproject_path.is_file():
        raise FileNotFoundError(f"缺少项目元数据：{pyproject_path}")

    pyproject_text = pyproject_path.read_bytes().decode("utf-8")
    lines = pyproject_text.splitlines(keepends=True)
    in_project = False
    version_line_indexes = []

    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "[project]":
            in_project = True
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            in_project = False
            continue
        if in_project and VERSION_LINE_PATTERN.fullmatch(line):
            version_line_indexes.append(index)

    if len(version_line_indexes) != 1:
        raise ValueError(
            "pyproject.toml 的 [project] 必须包含且仅包含一个 version 字段"
        )

    index = version_line_indexes[0]
    match = VERSION_LINE_PATTERN.fullmatch(lines[index])
    assert match is not None
    lines[index] = f"{match.group(1)}{version}{match.group(2)}{match.group(3) or ''}"

    pyproject_path.write_bytes("".join(lines).encode("utf-8"))
    cli_version_path.write_bytes(f"{version}\n".encode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="不带 v 前缀的发布版本，例如 2.1.7 或 2.1.7-rc.1")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="LightAgent 仓库根目录",
    )
    args = parser.parse_args()

    stamp_release_version(args.root, args.version)
    print(f"Stamped LightAgent release version: {args.version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
