#!/usr/bin/env python3
"""
Seed the LightAgent knowledge base with project documentation on first run.

Converts README.md and docs/zh/ files (.mdx / .md) into structured knowledge
under the ``project-docs/`` category inside the agent workspace knowledge dir.

Usage::

    python scripts/seed_project_knowledge.py --workspace ~/lightagent --app-root /app
    python scripts/seed_project_knowledge.py --workspace ~/lightagent --app-root . --force

Idempotent: a sentinel file (``.project-docs-seeded``) is created after the
first successful run. Pass ``--force`` to re-import regardless.
"""

import argparse
import os
import re
import sys
import yaml
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# .mdx → .md conversion
# ---------------------------------------------------------------------------

# JSX self-closing tags that carry no useful text content for the knowledge
# base — strip them entirely.
STRIP_SELF_CLOSING = re.compile(
    r"<("
    r"CardGroup[^>]*/>|"
    r"Card[^>]*/>|"
    r"Tab[^>]*/>|"
    r"Tabs[^>]*/>|"
    r"Frame[^>]*/>|"
    r"Accordion[^>]*/>|"
    r"AccordionGroup[^>]*/>|"
    r"Tabs[^>]*/>|"
    r"Tab[^>]*/>"
    r")[^>]*/>",
    re.IGNORECASE,
)

# Opening tags of wrapper components whose *children* we want to keep.
_OPEN_TAG_RE = re.compile(
    r"<(CardGroup|Card|Tabs|Tab|Frame|Accordion|AccordionGroup|div)\b[^>]*>",
    re.IGNORECASE,
)
_CLOSE_TAG_RE = re.compile(
    r"</(CardGroup|Card|Tabs|Tab|Frame|Accordion|AccordionGroup|div)\s*>",
    re.IGNORECASE,
)


def _extract_frontmatter(text: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body) from a .mdx / .md string.

    Frontmatter is the YAML block between the first two ``---`` lines.
    """
    if not text.startswith("---"):
        return {}, text
    end = text.find("---", 3)
    if end == -1:
        return {}, text
    fm_text = text[3:end].strip()
    body = text[end + 3 :].lstrip("\n")
    try:
        fm = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError:
        fm = {}
    return fm, body


_CARD_RE = re.compile(
    r"<Card\b([^>]*)>(.*?)</Card\s*>", re.IGNORECASE | re.DOTALL
)
_CARD_ATTR_RE = re.compile(r"""title\s*=\s*["']([^"']*)["']""", re.IGNORECASE)

_TAB_RE = re.compile(
    r"<Tab\b([^>]*)>(.*?)</Tab\s*>", re.IGNORECASE | re.DOTALL
)
_TAB_ATTR_RE = re.compile(r"""title\s*=\s*["']([^"']*)["']""", re.IGNORECASE)


def _clean_jsx(text: str) -> str:
    """Strip Mintlify JSX components, keeping inner markdown / text content.

    Special handling:
    - ``<Card title="X">desc</Card>`` → ``- **X**: desc``
    - ``<Tab title="X">content</Tab>`` → ``### X\\n\\ncontent``
    - ``<CardGroup>`` / ``<Tabs>`` → stripped (children processed)
    - ``<Frame>`` / ``<Accordion*>`` / ``<div>`` → stripped, children kept
    """

    # 1. Remove self-closing variants first.
    text = STRIP_SELF_CLOSING.sub("", text)

    # 2. Convert <Card> components to bullet list items.
    def _card_sub(m: re.Match) -> str:
        attrs = m.group(1)
        body = m.group(2).strip()
        title_match = _CARD_ATTR_RE.search(attrs)
        title = title_match.group(1) if title_match else ""
        if title:
            return f"- **{title}**{'：' + body if body else ''}"
        return body

    text = _CARD_RE.sub(_card_sub, text)

    # 3. Convert <Tab> components to sub-headings.
    def _tab_sub(m: re.Match) -> str:
        attrs = m.group(1)
        body = m.group(2).strip()
        title_match = _TAB_ATTR_RE.search(attrs)
        title = title_match.group(1) if title_match else ""
        if title:
            return f"### {title}\n\n{body}"
        return body

    text = _TAB_RE.sub(_tab_sub, text)

    # 4. Strip remaining paired wrapper tags — keep children.
    changed = True
    while changed:
        changed = False
        for tag in ("CardGroup", "Tabs", "Frame", "Accordion", "AccordionGroup",
                     "Note", "div"):
            pattern = re.compile(
                rf"<{tag}\b[^>]*>(.*?)</{tag}\s*>", re.IGNORECASE | re.DOTALL
            )
            new_text = pattern.sub(r"\1", text)
            if new_text != text:
                text = new_text
                changed = True
    return text


def _clean_mdx_links(text: str) -> str:
    """Replace absolute Mintlify doc paths (``/zh/...``) with relative links."""
    # /zh/guide/quick-start → guide/quick-start.md
    text = re.sub(
        r"\]\(/zh/([^)]+)\)",
        r"](../\1.md)",
        text,
    )
    return text


def convert_mdx_to_md(source_text: str) -> str:
    """Convert a .mdx document to clean markdown suitable for the knowledge base.

    1. Strip YAML frontmatter; use ``title`` as H1 if present.
    2. Remove JSX wrapper components; keep children.
    3. Clean internal doc links.
    """
    fm, body = _extract_frontmatter(source_text)
    lines: list[str] = []

    # Title
    title = fm.get("title", "").strip()
    if title:
        lines.append(f"# {title}")
        lines.append("")

    # Body — strip JSX wrappers
    body = _clean_jsx(body)
    body = _clean_mdx_links(body)

    # Collapse excessive blank lines (more than 2 consecutive)
    body = re.sub(r"\n{3,}", "\n\n", body)
    lines.append(body.strip())
    return "\n".join(lines).strip() + "\n"


def convert_md(source_text: str) -> str:
    """Process a regular .md file (may or may not have frontmatter).

    Strips frontmatter if present, using ``title`` as H1.
    """
    fm, body = _extract_frontmatter(source_text)
    lines: list[str] = []
    title = fm.get("title", "").strip()
    if title and not body.lstrip().startswith("# "):
        # Only add a title heading if the body doesn't already start with one.
        existing_h1 = False
        for line in body.splitlines():
            stripped = line.strip()
            if stripped:
                existing_h1 = stripped.startswith("# ")
                break
        if not existing_h1:
            lines.append(f"# {title}")
            lines.append("")
    body = _clean_mdx_links(body)
    body = re.sub(r"\n{3,}", "\n\n", body)
    lines.append(body.strip())
    return "\n".join(lines).strip() + "\n"


# ---------------------------------------------------------------------------
# File-system helpers
# ---------------------------------------------------------------------------

SENTINEL_NAME = ".project-docs-seeded"
PROJECT_DOCS_DIR = "project-docs"

# Directories under docs/zh/ that we import as knowledge sub-categories.
# Key: source dir name → same (we keep original names).
DOC_CATEGORIES = [
    "intro",
    "guide",
    "models",
    "channels",
    "tools",
    "skills",
    "memory",
    "cli",
    "knowledge",
]

# Files at docs/zh/ root to import directly under project-docs/.
DOC_ROOT_FILES = ["README.md"]


def _read_file(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def seed(workspace: str, app_root: str, force: bool = False) -> bool:
    """Seed project documentation into the knowledge base.

    Returns True when files were actually written (first run or --force).
    """
    knowledge_dir = Path(workspace) / "knowledge"
    sentinel = knowledge_dir / SENTINEL_NAME
    dest_root = knowledge_dir / PROJECT_DOCS_DIR
    app_path = Path(app_root)

    if sentinel.exists() and not force:
        print(f"[seed_knowledge] Already seeded (sentinel exists at {sentinel}).  Use --force to re-import.")
        return False

    # Ensure the knowledge directory exists
    knowledge_dir.mkdir(parents=True, exist_ok=True)

    docs_zh = app_path / "docs" / "zh"
    readme_path = app_path / "README.md"

    if not docs_zh.is_dir():
        print(f"[seed_knowledge] ERROR: docs/zh not found at {docs_zh}")
        return False

    errors: list[str] = []
    written = 0

    # ---- 1. Root README.md → project-docs/overview.md ----
    if readme_path.is_file():
        try:
            raw = _read_file(readme_path)
            # Root README has no frontmatter — keep as-is.
            content = raw.strip() + "\n"
            _write_file(dest_root / "overview.md", content)
            written += 1
            print("[seed_knowledge]  Wrote project-docs/overview.md (from README.md)")
        except Exception as exc:
            errors.append(f"README.md: {exc}")
    else:
        print("[seed_knowledge]  WARNING: README.md not found — skipping overview.md")

    # ---- 2. docs/zh/ root .md files ----
    for filename in DOC_ROOT_FILES:
        src = docs_zh / filename
        if not src.is_file():
            continue
        try:
            raw = _read_file(src)
            content = convert_md(raw)
            _write_file(dest_root / filename, content)
            written += 1
            print(f"[seed_knowledge]  Wrote project-docs/{filename}")
        except Exception as exc:
            errors.append(f"docs/zh/{filename}: {exc}")

    # ---- 3. docs/zh/ sub-directories → project-docs/<category>/ ----
    for category in DOC_CATEGORIES:
        cat_src = docs_zh / category
        if not cat_src.is_dir():
            print(f"[seed_knowledge]  SKIP: docs/zh/{category}/ not found")
            continue

        for src_file in sorted(cat_src.iterdir()):
            if src_file.name.startswith("."):
                continue

            suffix = src_file.suffix.lower()
            if suffix not in (".mdx", ".md"):
                continue

            dest_name = src_file.stem + ".md"
            dest_path = dest_root / category / dest_name

            try:
                raw = _read_file(src_file)
                if suffix == ".mdx":
                    content = convert_mdx_to_md(raw)
                else:
                    content = convert_md(raw)
                _write_file(dest_path, content)
                written += 1
                print(f"[seed_knowledge]  Wrote project-docs/{category}/{dest_name}")
            except Exception as exc:
                errors.append(f"docs/zh/{category}/{src_file.name}: {exc}")

    # ---- 4. Rebuild knowledge index ----
    try:
        # Import here to avoid forcing full dependency resolution when the
        # script is imported for inspection / testing.
        sys.path.insert(0, str(app_path))
        from agent.knowledge.service import KnowledgeService
        svc = KnowledgeService(workspace)
        svc.rebuild_index_md()
        print("[seed_knowledge]  Rebuilt knowledge/index.md")
    except Exception as exc:
        errors.append(f"rebuild_index_md: {exc}")
        print(f"[seed_knowledge]  WARNING: Could not rebuild knowledge index: {exc}")

    # ---- 5. Sentinel ----
    if not errors:
        _write_file(sentinel, f"Seeded from {app_root}/README.md and {app_root}/docs/zh/\n")
        print(f"[seed_knowledge] Done: {written} file(s) written, sentinel at {sentinel}")
    else:
        print(f"[seed_knowledge] Done with {len(errors)} error(s):")
        for e in errors:
            print(f"  - {e}")
        # Still write sentinel so we don't retry on every startup; user can
        # --force after fixing the underlying issue.
        _write_file(sentinel, f"Seeded with errors:\n" + "\n".join(f"- {e}" for e in errors))

    return written > 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Seed LightAgent knowledge base with project documentation."
    )
    parser.add_argument(
        "--workspace",
        default=os.path.expanduser("~/lightagent"),
        help="Agent workspace root (default: ~/lightagent)",
    )
    parser.add_argument(
        "--app-root",
        default="/app",
        help="LightAgent application root containing README.md and docs/ (default: /app)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-import even if already seeded",
    )
    args = parser.parse_args()

    workspace = os.path.expanduser(args.workspace)
    app_root = os.path.expanduser(args.app_root)

    if not os.path.isdir(app_root):
        print(f"ERROR: --app-root is not a directory: {app_root}", file=sys.stderr)
        sys.exit(1)

    ok = seed(workspace, app_root, force=args.force)
    sys.exit(0 if ok or not ok else 0)  # Never fail the entrypoint


if __name__ == "__main__":
    main()
