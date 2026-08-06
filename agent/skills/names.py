"""Shared protection for names reserved by bundled LightAgent skills."""

from pathlib import Path

from agent.skills.frontmatter import parse_frontmatter


RESERVED_BUILTIN_SKILL_NAMES = frozenset({
    "image-generation",
    "knowledge-wiki",
    "skill-creator",
})


class BuiltinSkillNameError(ValueError):
    """Raised when a workspace operation targets a bundled skill name."""


def get_builtin_skill_names(builtin_dir=None):
    root = (
        Path(builtin_dir)
        if builtin_dir is not None
        else Path(__file__).resolve().parents[2] / "skills"
    )
    names = set(RESERVED_BUILTIN_SKILL_NAMES)
    if root.is_dir():
        for path in root.iterdir():
            skill_file = path / "SKILL.md"
            if not path.is_dir() or not skill_file.is_file():
                continue
            names.add(path.name)
            try:
                declared_name = parse_frontmatter(
                    skill_file.read_text(encoding="utf-8")
                ).get("name")
            except (OSError, UnicodeError):
                continue
            if isinstance(declared_name, list):
                declared_name = declared_name[0] if declared_name else ""
            if declared_name:
                names.add(str(declared_name))
    return names


def ensure_not_builtin_skill_name(name, builtin_dir=None):
    value = str(name or "")
    if value in get_builtin_skill_names(builtin_dir):
        raise BuiltinSkillNameError(
            f"skill '{value}' is a protected LightAgent builtin name"
        )
