"""Runtime environment helpers for isolated Skill Hub dependencies."""

import json
import os
from pathlib import Path
from typing import Mapping, Optional


def build_skill_runtime_env(
    workspace: str,
    base_env: Optional[Mapping[str, str]] = None,
):
    """Expose installed skill dependency directories to child processes."""
    env = dict(base_env or os.environ)
    workspace = os.path.abspath(workspace)
    envs_root = os.path.realpath(os.path.join(workspace, ".skill-envs"))
    names = _installed_skill_names(os.path.join(workspace, "skills.lock.json"))
    path_entries = []
    python_entries = []
    node_entries = []

    for name in names:
        skill_env = os.path.realpath(os.path.join(envs_root, name))
        if skill_env != envs_root and not skill_env.startswith(envs_root + os.sep):
            continue
        candidates = (
            os.path.join(skill_env, "bin"),
            os.path.join(skill_env, "python", "bin"),
            os.path.join(skill_env, "npm", "node_modules", ".bin"),
        )
        path_entries.extend(path for path in candidates if os.path.isdir(path))
        python_dir = os.path.join(skill_env, "python")
        node_dir = os.path.join(skill_env, "npm", "node_modules")
        if os.path.isdir(python_dir):
            python_entries.append(python_dir)
        if os.path.isdir(node_dir):
            node_entries.append(node_dir)

    _prepend_env_path(env, "PATH", path_entries)
    _prepend_env_path(env, "PYTHONPATH", python_entries)
    _prepend_env_path(env, "NODE_PATH", node_entries)
    if names:
        env["LIGHTAGENT_SKILL_ENVS"] = envs_root
    return env


def _installed_skill_names(lock_path):
    try:
        value = json.loads(Path(lock_path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return []
    skills = value.get("skills") if isinstance(value, dict) else None
    if not isinstance(skills, dict):
        return []
    return sorted(name for name in skills if _valid_skill_name(name))


def _valid_skill_name(name):
    value = str(name or "")
    return bool(value) and value not in (".", "..") and all(
        character.isalnum() or character in "-_." for character in value
    )


def _prepend_env_path(env, key, entries):
    existing = [item for item in str(env.get(key) or "").split(os.pathsep) if item]
    values = list(dict.fromkeys([*entries, *existing]))
    if values:
        env[key] = os.pathsep.join(values)
