#!/usr/bin/env python3
"""
Seed the LightAgent knowledge base with project documentation on every startup.

Imports README.md into the ``project-docs/`` category inside the agent workspace
knowledge directory.

Usage::

    python scripts/seed_project_knowledge.py --workspace ~/lightagent --app-root /app
"""

import argparse
import os
import shutil
import sys
from pathlib import Path


PROJECT_DOCS_DIR = "project-docs"


def _read_file(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def seed(workspace: str, app_root: str) -> bool:
    """Import README.md into the knowledge base.

    Always overwrites ``project-docs/overview.md`` with the latest content.
    """
    knowledge_dir = Path(workspace) / "knowledge"
    dest_root = knowledge_dir / PROJECT_DOCS_DIR
    app_path = Path(app_root)
    readme_path = app_path / "README.md"

    knowledge_dir.mkdir(parents=True, exist_ok=True)

    if not readme_path.is_file():
        print("[seed_knowledge] WARNING: README.md not found")
        return False

    # Clean and recreate target directory
    if dest_root.is_dir():
        shutil.rmtree(dest_root)

    errors: list[str] = []

    # ---- README.md → project-docs/overview.md ----
    try:
        raw = _read_file(readme_path)
        _write_file(dest_root / "overview.md", raw.strip() + "\n")
        print("[seed_knowledge]  Wrote project-docs/overview.md (from README.md)")
    except Exception as exc:
        errors.append(f"README.md: {exc}")

    # ---- Rebuild knowledge index ----
    try:
        sys.path.insert(0, str(app_path))
        from agent.knowledge.service import KnowledgeService
        svc = KnowledgeService(workspace)
        svc.rebuild_index_md()
        print("[seed_knowledge]  Rebuilt knowledge/index.md")
    except Exception as exc:
        errors.append(f"rebuild_index_md: {exc}")
        print(f"[seed_knowledge]  WARNING: Could not rebuild knowledge index: {exc}")

    if not errors:
        print("[seed_knowledge] Done: 1 file written")
    else:
        print(f"[seed_knowledge] Done with {len(errors)} error(s):")
        for e in errors:
            print(f"  - {e}")

    return len(errors) == 0


def main():
    parser = argparse.ArgumentParser(
        description="Seed LightAgent knowledge base with README.md."
    )
    parser.add_argument(
        "--workspace",
        default=os.path.expanduser("~/lightagent"),
        help="Agent workspace root (default: ~/lightagent)",
    )
    parser.add_argument(
        "--app-root",
        default="/app",
        help="LightAgent application root containing README.md (default: /app)",
    )
    args = parser.parse_args()

    workspace = os.path.expanduser(args.workspace)
    app_root = os.path.expanduser(args.app_root)

    if not os.path.isdir(app_root):
        print(f"ERROR: --app-root is not a directory: {app_root}", file=sys.stderr)
        sys.exit(1)

    seed(workspace, app_root)


if __name__ == "__main__":
    main()
