"""Background update status checks for Skill Hub managed skills."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from typing import Dict, Optional

from common.log import logger

from agent.skills.lifecycle import SkillLifecycleManager, _version_tuple
from agent.skills.registry import SkillRegistryClient


def _list_change(previous, current):
    before = list(previous or [])
    after = list(current or [])
    return {
        "added": [item for item in after if item not in before],
        "removed": [item for item in before if item not in after],
        "changed": before != after,
    }


def _update_changes(local, remote):
    old_requirements = local.get("requirements") or {}
    new_requirements = remote.get("requirements") or {}
    requirements = {
        kind: _list_change(old_requirements.get(kind), new_requirements.get(kind))
        for kind in ("env", "bins", "python", "npm", "downloads", "capabilities")
    }
    old_lightagent = local.get("lightagent") or {}
    new_lightagent = remote.get("lightagent") or {}
    permissions = {
        kind: _list_change(old_lightagent.get(kind), new_lightagent.get(kind))
        for kind in ("network_domains", "file_paths", "tools")
    }
    return {
        "release_notes": remote.get("release_notes") or "",
        "release_notes_available": bool(remote.get("release_notes")),
        "breaking_changes": list(remote.get("breaking_changes") or []),
        "requirements": requirements,
        "permissions": permissions,
        "requirements_changed": any(item["changed"] for item in requirements.values()),
        "permissions_changed": any(item["changed"] for item in permissions.values()),
    }


DEFAULT_CHECK_INTERVAL_SECONDS = 6 * 60 * 60


class SkillUpdateChecker:
    def __init__(
        self,
        workspace: str,
        skills_dir: Optional[str] = None,
        registry: Optional[SkillRegistryClient] = None,
        interval_seconds: int = DEFAULT_CHECK_INTERVAL_SECONDS,
    ):
        self.workspace = os.path.abspath(workspace)
        self.skills_dir = os.path.abspath(
            skills_dir or os.path.join(self.workspace, "skills")
        )
        self.registry = registry or SkillRegistryClient(
            cache_dir=os.path.join(self.workspace, ".skillhub")
        )
        self.interval_seconds = max(1, int(interval_seconds))
        self.status_path = os.path.join(
            self.workspace, ".skillhub", "update-status.json"
        )
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread = None

    def start(self):
        with self._lock:
            if self._thread and self._thread.is_alive():
                return self._thread
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run,
                daemon=True,
                name="skill-update-checker",
            )
            self._thread.start()
            return self._thread

    def stop(self):
        self._stop_event.set()

    def _run(self):
        while not self._stop_event.is_set():
            try:
                self.check()
            except Exception as exc:
                logger.warning("[SkillHub] Background update check failed: %s", exc)
            if self._stop_event.wait(self.interval_seconds):
                break

    def check(self, name: Optional[str] = None, snapshot=None) -> Dict:
        with self._lock:
            previous = self.read_status()
            attempted_at = _now()
            try:
                snapshot = snapshot or self.registry.load()
                manager = SkillLifecycleManager(
                    workspace=self.workspace,
                    skills_dir=self.skills_dir,
                    registry=self.registry,
                )
                installed = manager.installed()
                remote = {
                    str(item.get("name")): item
                    for item in snapshot.data.get("skills", [])
                }
                revocations = {
                    (str(item.get("name")), str(item.get("version"))): item
                    for item in snapshot.data.get("revocations", [])
                }
                statuses = {}
                for skill_name, local in installed.items():
                    if name and skill_name != name:
                        continue
                    item = remote.get(skill_name)
                    if local.get("source") == "cowagent-skillhub":
                        try:
                            item = manager.legacy_registry.get_skill(skill_name)
                        except Exception:
                            item = None
                    if not item:
                        statuses[skill_name] = {
                            "name": skill_name,
                            "installed_version": local.get("version"),
                            "available_version": None,
                            "update_available": False,
                            "update_status": "not_in_registry",
                            "reason": None,
                        }
                        continue
                    revoked = revocations.get(
                        (skill_name, str(local.get("version")))
                    )
                    item_status = (
                        revoked.get("status")
                        if revoked
                        else item.get("status", "active")
                    )
                    update_available = _version_tuple(
                        item.get("version")
                    ) > _version_tuple(local.get("version"))
                    statuses[skill_name] = {
                        "name": skill_name,
                        "installed_version": local.get("version"),
                        "available_version": item.get("version"),
                        "update_available": update_available,
                        "update_status": (
                            str(item_status)
                            if item_status in ("yanked", "revoked")
                            else ("update_available" if update_available else "latest")
                        ),
                        "reason": revoked.get("reason") if revoked else None,
                        "source": local.get("source"),
                        "integrity_status": item.get("integrity_status") or local.get("integrity_status"),
                        "execution_mode": (
                            "runner" if (item.get("lightagent") or {}).get("entrypoints")
                            else local.get("execution_mode", "compatibility")
                        ),
                        "changes": _update_changes(local, item),
                    }
                if name:
                    merged = dict(previous.get("skills") or {})
                    merged.update(statuses)
                    statuses = merged
                value = {
                    "schema_version": 2,
                    "checked_at": attempted_at,
                    "last_attempted_at": attempted_at,
                    "source": snapshot.source,
                    "cached": bool(snapshot.cached),
                    "error": None,
                    "skills": statuses,
                }
                value["update_count"] = sum(
                    1
                    for item in statuses.values()
                    if item.get("update_available")
                    or item.get("update_status") in ("yanked", "revoked")
                )
                self._write_status(value)
                return value
            except Exception as exc:
                value = dict(previous)
                value.setdefault("schema_version", 2)
                value.setdefault("skills", {})
                value.setdefault("update_count", 0)
                value["last_attempted_at"] = attempted_at
                value["error"] = str(exc)
                self._write_status(value)
                return value

    def read_status(self) -> Dict:
        try:
            with open(self.status_path, "r", encoding="utf-8") as handle:
                value = json.load(handle)
            if isinstance(value, dict):
                return value
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass
        return {
            "schema_version": 2,
            "checked_at": None,
            "last_attempted_at": None,
            "source": None,
            "cached": False,
            "error": None,
            "skills": {},
            "update_count": 0,
        }

    def _write_status(self, value: Dict):
        directory = os.path.dirname(self.status_path)
        os.makedirs(directory, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(
            prefix="update-status.", suffix=".tmp", dir=directory
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(value, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self.status_path)
        finally:
            try:
                os.unlink(temp_path)
            except FileNotFoundError:
                pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


_CHECKERS: Dict[str, SkillUpdateChecker] = {}
_CHECKERS_LOCK = threading.Lock()


def get_skill_update_checker(
    workspace: str,
    skills_dir: Optional[str] = None,
) -> SkillUpdateChecker:
    key = os.path.abspath(workspace)
    with _CHECKERS_LOCK:
        checker = _CHECKERS.get(key)
        if checker is None:
            checker = SkillUpdateChecker(key, skills_dir=skills_dir)
            _CHECKERS[key] = checker
        return checker


def start_skill_update_checker(
    workspace: str,
    skills_dir: Optional[str] = None,
) -> SkillUpdateChecker:
    checker = get_skill_update_checker(workspace, skills_dir=skills_dir)
    checker.start()
    return checker
