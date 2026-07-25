"""Transactional lifecycle operations for Hub-installed skills."""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import requests

from agent.skills.frontmatter import parse_frontmatter
from agent.skills.registry import RegistryError, RegistrySecurityError, SkillRegistryClient
from cli import __version__
from cli.utils import SKILL_HUB_API, get_builtin_skills_dir, get_skills_dir, get_workspace_dir


PROTECTED_SKILL_NAMES = {"image-generation", "knowledge-wiki", "skill-creator"}
_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$")
_MAX_PACKAGE_BYTES = 50 * 1024 * 1024
_MAX_EXTRACTED_BYTES = 200 * 1024 * 1024
_MAX_ARCHIVE_FILES = 2000
_MAX_DEPENDENCY_DOWNLOAD_BYTES = 100 * 1024 * 1024
_PROCESS_LOCKS = {}
_PROCESS_LOCKS_GUARD = threading.Lock()


class SkillLifecycleError(RuntimeError):
    pass


def _version_tuple(value):
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)", str(value or ""))
    return tuple(int(part) for part in match.groups()) if match else (0, 0, 0)


def _tree_hash(root):
    digest = hashlib.sha256()
    root = Path(root)
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _dependency_fingerprint(skill):
    value = {
        "requirements": skill.get("requirements", {}),
        "network_domains": skill.get("lightagent", {}).get("network_domains", []),
        "file_paths": skill.get("lightagent", {}).get("file_paths", []),
        "tools": skill.get("lightagent", {}).get("tools", []),
    }
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class SkillLifecycleManager:
    def __init__(self, skills_dir=None, workspace=None, registry=None, session=None):
        self.skills_dir = os.path.abspath(skills_dir or get_skills_dir())
        self.workspace = os.path.abspath(workspace or get_workspace_dir())
        self.registry = registry or SkillRegistryClient()
        self.session = session or requests
        self.lock_path = os.path.join(self.workspace, "skills.lock.json")
        self.versions_dir = os.path.join(self.workspace, ".skill-versions")
        self.envs_dir = os.path.join(self.workspace, ".skill-envs")
        self.data_dir = os.path.join(self.workspace, "skill-data")
        self.config_dir = os.path.join(self.workspace, "skill-config")
        self.operation_locks_dir = os.path.join(self.workspace, ".skill-locks")

    def search(self, query=""):
        return self.registry.list_skills(query=query)

    def installed(self):
        return self._load_lock().get("skills", {})

    def install(self, name, expected_version=None):
        skill = self.registry.get_skill(name)
        self._validate_entry(skill, expected_version=expected_version)
        fingerprint = _dependency_fingerprint(skill)
        with self._skill_lock(name):
            return self._install_locked(skill, fingerprint)

    def outdated(self):
        remote = {item["name"]: item for item in self.registry.list_skills(include_unavailable=True)}
        revocations = []
        try:
            revocations = self.registry.load().data.get("revocations", [])
        except AttributeError:
            pass
        revoked_versions = {
            (item.get("name"), str(item.get("version"))): item
            for item in revocations
        }
        result = []
        for name, local in self.installed().items():
            item = remote.get(name)
            if not item:
                continue
            revoked = revoked_versions.get((name, str(local.get("version"))))
            status = revoked.get("status") if revoked else item.get("status", "active")
            if status in ("yanked", "revoked") or _version_tuple(item.get("version")) > _version_tuple(local.get("version")):
                result.append({
                    "name": name,
                    "installed_version": local.get("version"),
                    "available_version": item.get("version"),
                    "status": status,
                    "reason": revoked.get("reason") if revoked else None,
                })
        return result

    def update(self, name):
        if name not in self.installed():
            raise SkillLifecycleError(f"技能 {name} 尚未通过官方技能中心安装")
        return self.install(name)

    def rollback(self, name):
        with self._skill_lock(name):
            lock = self._load_lock()
            current = lock.get("skills", {}).get(name)
            if not current or not current.get("previous"):
                raise SkillLifecycleError(f"技能 {name} 没有可回滚版本")
            previous = current["previous"]
            backup = previous.get("path")
            target = os.path.join(self.skills_dir, name)
            if not backup or not os.path.isdir(backup):
                raise SkillLifecycleError(f"技能 {name} 的回滚文件不存在")
            swap = tempfile.mkdtemp(prefix=f".{name}-rollback-", dir=self.skills_dir)
            os.rmdir(swap)
            if os.path.exists(target):
                os.replace(target, swap)
            env_target = os.path.join(self.envs_dir, name)
            env_swap = None
            previous_env = previous.get("env_path")
            if previous_env and os.path.isdir(previous_env):
                env_swap = tempfile.mkdtemp(prefix=f".{name}-env-rollback-", dir=self.envs_dir)
                os.rmdir(env_swap)
                if os.path.exists(env_target):
                    os.replace(env_target, env_swap)
            try:
                os.replace(backup, target)
                if previous_env and os.path.isdir(previous_env):
                    os.replace(previous_env, env_target)
            except Exception:
                if os.path.exists(swap):
                    os.replace(swap, target)
                if env_swap and os.path.exists(env_swap):
                    os.replace(env_swap, env_target)
                raise
            current_backup = os.path.join(self.versions_dir, name, f"{current.get('version', 'unknown')}-{int(time.time())}")
            os.makedirs(os.path.dirname(current_backup), exist_ok=True)
            if os.path.exists(swap):
                os.replace(swap, current_backup)
            current_env_backup = None
            if env_swap and os.path.exists(env_swap):
                current_env_backup = current_backup + "-env"
                os.replace(env_swap, current_env_backup)
            restored = dict(previous.get("lock", {}))
            restored["previous"] = {
                "path": current_backup,
                "env_path": current_env_backup,
                "lock": {key: value for key, value in current.items() if key != "previous"},
            }
            lock["skills"][name] = restored
            self._save_lock(lock)
            self._refresh()
            return restored

    def uninstall(self, name, purge_data=False):
        with self._skill_lock(name):
            lock = self._load_lock()
            if name not in lock.get("skills", {}):
                raise SkillLifecycleError(f"技能 {name} 尚未通过官方技能中心安装")
            shutil.rmtree(os.path.join(self.skills_dir, name), ignore_errors=True)
            shutil.rmtree(os.path.join(self.envs_dir, name), ignore_errors=True)
            shutil.rmtree(os.path.join(self.versions_dir, name), ignore_errors=True)
            if purge_data:
                shutil.rmtree(os.path.join(self.data_dir, name), ignore_errors=True)
                shutil.rmtree(os.path.join(self.config_dir, name), ignore_errors=True)
            lock["skills"].pop(name, None)
            self._save_lock(lock)
            self._remove_skills_config(name)
            self._refresh()

    def verify(self, name=None):
        findings = []
        for skill_name, entry in self.installed().items():
            if name and skill_name != name:
                continue
            path = os.path.join(self.skills_dir, skill_name)
            ok = os.path.isdir(path) and _tree_hash(path) == entry.get("tree_sha256")
            findings.append({"name": skill_name, "version": entry.get("version"), "ok": ok, "status": entry.get("status", "active")})
        if name and not findings:
            raise SkillLifecycleError(f"技能 {name} 不在锁文件中")
        return findings

    def _install_locked(self, skill, fingerprint):
        name = skill["name"]
        target = os.path.join(self.skills_dir, name)
        if os.path.exists(target) and name not in self.installed():
            raise SkillLifecycleError(
                f"本地已存在同名技能 {name}；为避免覆盖非 Hub 技能，请先手动处理名称冲突"
            )
        package = self._download_package(skill)
        if len(package) > _MAX_PACKAGE_BYTES:
            raise RegistrySecurityError(f"技能 {name} 下载包超过 50 MiB 限制")
        actual = hashlib.sha256(package).hexdigest()
        if actual != str(skill.get("sha256", "")).lower():
            raise RegistrySecurityError(f"技能 {name} 下载包 SHA-256 不匹配")
        os.makedirs(self.skills_dir, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=f".{name}-stage-", dir=self.skills_dir) as stage:
            extract = os.path.join(stage, "extract")
            os.makedirs(extract)
            self._safe_extract(package, extract)
            source = self._find_skill_root(extract, name)
            metadata = parse_frontmatter(Path(source, "SKILL.md").read_text(encoding="utf-8"))
            if metadata.get("name") != name or str(metadata.get("version")) != str(skill.get("version")):
                raise RegistrySecurityError("技能包元数据与注册表不一致")
            staged_skill = os.path.join(stage, "ready")
            shutil.copytree(source, staged_skill)
            staged_env = os.path.join(stage, "environment")
            self._install_dependencies(skill, staged_env)
            env_target = os.path.join(self.envs_dir, name)
            previous = None
            previous_path = None
            previous_env_path = None
            if os.path.exists(target):
                previous_path = os.path.join(self.versions_dir, name, f"{self.installed().get(name, {}).get('version', 'unknown')}-{int(time.time())}")
                os.makedirs(os.path.dirname(previous_path), exist_ok=True)
                os.replace(target, previous_path)
                if os.path.exists(env_target):
                    previous_env_path = previous_path + "-env"
                    os.replace(env_target, previous_env_path)
                old_lock = self.installed().get(name)
                if old_lock:
                    previous = {
                        "path": previous_path,
                        "env_path": previous_env_path,
                        "lock": {key: value for key, value in old_lock.items() if key != "previous"},
                    }
            try:
                os.replace(staged_skill, target)
                os.makedirs(self.envs_dir, exist_ok=True)
                os.replace(staged_env, env_target)
            except Exception:
                shutil.rmtree(target, ignore_errors=True)
                shutil.rmtree(env_target, ignore_errors=True)
                if previous and os.path.exists(previous["path"]):
                    os.replace(previous["path"], target)
                if previous_env_path and os.path.exists(previous_env_path):
                    os.replace(previous_env_path, env_target)
                raise
        os.makedirs(os.path.join(self.data_dir, name), exist_ok=True)
        os.makedirs(os.path.join(self.config_dir, name), exist_ok=True)
        record = {
            "name": name,
            "version": skill["version"],
            "source": "lightagent-skillhub",
            "registry_url": getattr(self.registry, "url", None),
            "source_url": skill.get("repository"),
            "source_commit": skill.get("source_commit"),
            "artifact_sha256": actual,
            "tree_sha256": _tree_hash(os.path.join(self.skills_dir, name)),
            "dependency_fingerprint": fingerprint,
            "requirements": skill.get("requirements", {}),
            "installed_at": datetime.now(timezone.utc).isoformat(),
            "status": skill.get("status", "active"),
            "previous": previous,
        }
        lock = self._load_lock()
        original_lock = json.loads(json.dumps(lock))
        lock.setdefault("skills", {})[name] = record
        try:
            self._save_lock(lock)
            self._register_skills_config(skill)
            self._refresh()
        except Exception:
            shutil.rmtree(os.path.join(self.skills_dir, name), ignore_errors=True)
            shutil.rmtree(os.path.join(self.envs_dir, name), ignore_errors=True)
            if previous_path and os.path.exists(previous_path):
                os.replace(previous_path, os.path.join(self.skills_dir, name))
            if previous_env_path and os.path.exists(previous_env_path):
                os.replace(previous_env_path, os.path.join(self.envs_dir, name))
            self._save_lock(original_lock)
            raise
        return record

    def _download_package(self, skill):
        try:
            response = self.session.get(
                skill["download_url"], timeout=(5, 30), allow_redirects=True
            )
            response.raise_for_status()
            return response.content
        except Exception as primary_error:
            try:
                return self._download_verified_legacy_mirror(skill)
            except Exception as fallback_error:
                raise SkillLifecycleError(
                    f"官方技能包下载失败（{primary_error}），"
                    f"后备源也无法通过验证（{fallback_error}）"
                ) from primary_error

    def _download_verified_legacy_mirror(self, skill):
        name = skill["name"]
        info_response = self.session.post(
            f"{SKILL_HUB_API}/skills/{name}/download",
            json={},
            timeout=15,
        )
        info_response.raise_for_status()
        if "application/json" not in info_response.headers.get("Content-Type", ""):
            raise RegistrySecurityError("后备源未返回可验证的来源信息")
        info = info_response.json()
        source_identity = str(info.get("source_url") or info.get("repository") or "")
        if self._normalize_source_identity(source_identity) != self._normalize_source_identity(
            skill.get("repository")
        ):
            raise RegistrySecurityError("后备源的源码身份与签名索引不一致")
        if not info.get("has_mirror"):
            raise RegistrySecurityError("后备源没有可验证镜像")
        mirror = self.session.post(
            f"{SKILL_HUB_API}/skills/{name}/download",
            json={"mirror": True},
            timeout=30,
        )
        mirror.raise_for_status()
        if "application/zip" not in mirror.headers.get("Content-Type", ""):
            raise RegistrySecurityError("后备源镜像不是 ZIP 技能包")
        return mirror.content

    @staticmethod
    def _normalize_source_identity(value):
        return str(value or "").strip().lower().rstrip("/").removesuffix(".git")

    def _validate_entry(self, skill, expected_version=None):
        name = str(skill.get("name", ""))
        if not _NAME_RE.match(name):
            raise RegistrySecurityError("注册表包含非法技能名称")
        if name in PROTECTED_SKILL_NAMES or os.path.isdir(os.path.join(get_builtin_skills_dir(), name)):
            raise RegistrySecurityError(f"技能 {name} 是 LightAgent 内置保留名称")
        if skill.get("status", "active") in ("yanked", "revoked"):
            raise RegistrySecurityError(f"技能 {name} 当前不可安装")
        if expected_version and str(skill.get("version")) != str(expected_version):
            raise SkillLifecycleError(f"注册表版本已变化，期望 {expected_version}，当前 {skill.get('version')}")
        current = _version_tuple(__version__)
        if current < _version_tuple(skill.get("min_lightagent_version")):
            raise SkillLifecycleError(f"技能 {name} 需要 LightAgent >= {skill.get('min_lightagent_version')}")
        maximum = skill.get("max_lightagent_version")
        if maximum and current > _version_tuple(maximum):
            raise SkillLifecycleError(f"技能 {name} 仅支持 LightAgent <= {maximum}")
        if not str(skill.get("download_url", "")).startswith("https://"):
            raise RegistrySecurityError("技能下载地址必须使用 HTTPS")
        if not re.match(r"^[a-fA-F0-9]{64}$", str(skill.get("sha256", ""))):
            raise RegistrySecurityError("技能缺少有效 SHA-256")

    def _install_dependencies(self, skill, env_dir):
        requirements = skill.get("requirements", {})
        os.makedirs(env_dir, exist_ok=True)
        python_packages = [str(item) for item in requirements.get("python", [])]
        if any(item.startswith("-") or "://" in item for item in python_packages):
            raise RegistrySecurityError("Python 依赖只能使用包名与版本约束")
        if python_packages:
            subprocess.run([sys.executable, "-m", "pip", "install", "--target", os.path.join(env_dir, "python"), *python_packages], check=True, timeout=300)
        npm_packages = [str(item) for item in requirements.get("npm", [])]
        if any(item.startswith("-") or "://" in item for item in npm_packages):
            raise RegistrySecurityError("npm 依赖只能使用包名与版本约束")
        if npm_packages:
            subprocess.run(["npm", "install", "--prefix", os.path.join(env_dir, "npm"), *npm_packages], check=True, timeout=300)
        for item in requirements.get("downloads", []):
            response = self.session.get(item["url"], timeout=(5, 30), allow_redirects=True)
            response.raise_for_status()
            if len(response.content) > _MAX_DEPENDENCY_DOWNLOAD_BYTES:
                raise RegistrySecurityError("技能依赖下载超过 100 MiB 限制")
            if hashlib.sha256(response.content).hexdigest() != item["sha256"].lower():
                raise RegistrySecurityError("技能依赖下载 SHA-256 不匹配")
            downloads = os.path.join(env_dir, "downloads")
            os.makedirs(downloads, exist_ok=True)
            filename = os.path.basename(item["url"].split("?", 1)[0]) or item["sha256"]
            with open(os.path.join(downloads, filename), "wb") as handle:
                handle.write(response.content)

    @staticmethod
    def _safe_extract(package, destination):
        with zipfile.ZipFile(__import__("io").BytesIO(package)) as archive:
            root = os.path.realpath(destination)
            members = archive.infolist()
            files = [member for member in members if not member.is_dir()]
            if len(files) > _MAX_ARCHIVE_FILES:
                raise RegistrySecurityError("技能包文件数超过限制")
            if sum(member.file_size for member in files) > _MAX_EXTRACTED_BYTES:
                raise RegistrySecurityError("技能包解压后超过 200 MiB 限制")
            for member in members:
                if member.flag_bits & 0x1:
                    raise RegistrySecurityError("技能包不允许加密文件")
                target = os.path.realpath(os.path.join(root, member.filename))
                if target != root and not target.startswith(root + os.sep):
                    raise RegistrySecurityError("技能包包含路径穿越")
                if member.is_dir():
                    continue
                mode = member.external_attr >> 16
                if mode and (mode & 0o170000) == 0o120000:
                    raise RegistrySecurityError("技能包不允许符号链接")
            archive.extractall(root)

    @staticmethod
    def _find_skill_root(extract, name):
        matches = [path.parent for path in Path(extract).rglob("SKILL.md")]
        named = [path for path in matches if path.name == name]
        if len(named) == 1:
            return str(named[0])
        if len(matches) == 1:
            return str(matches[0])
        raise RegistrySecurityError("技能包必须且只能包含一个目标技能")

    def _load_lock(self):
        try:
            with open(self.lock_path, "r", encoding="utf-8") as handle:
                value = json.load(handle)
            return value if isinstance(value, dict) else {"lock_version": 1, "skills": {}}
        except (FileNotFoundError, json.JSONDecodeError):
            return {"lock_version": 1, "skills": {}}

    def _save_lock(self, value):
        os.makedirs(os.path.dirname(self.lock_path), exist_ok=True)
        temp = self.lock_path + ".tmp"
        with open(temp, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, self.lock_path)

    @contextmanager
    def _skill_lock(self, name):
        with _PROCESS_LOCKS_GUARD:
            process_lock = _PROCESS_LOCKS.setdefault(name, threading.Lock())
        if not process_lock.acquire(timeout=30):
            raise SkillLifecycleError(f"技能 {name} 正在被其他请求修改")
        os.makedirs(self.operation_locks_dir, exist_ok=True)
        path = os.path.join(self.operation_locks_dir, name + ".lock")
        fd = None
        try:
            deadline = time.time() + 30
            while fd is None:
                try:
                    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                    os.write(fd, str(os.getpid()).encode("ascii"))
                except FileExistsError:
                    try:
                        if time.time() - os.path.getmtime(path) > 300:
                            os.unlink(path)
                            continue
                    except FileNotFoundError:
                        continue
                    if time.time() >= deadline:
                        raise SkillLifecycleError(f"技能 {name} 正在被其他进程修改")
                    time.sleep(0.1)
            yield
        finally:
            if fd is not None:
                os.close(fd)
                try:
                    os.unlink(path)
                except FileNotFoundError:
                    pass
            process_lock.release()

    def _register_skills_config(self, skill):
        path = os.path.join(self.skills_dir, "skills_config.json")
        try:
            with open(path, "r", encoding="utf-8") as handle:
                config = json.load(handle)
        except Exception:
            config = {}
        config[skill["name"]] = {
            "name": skill["name"], "description": skill.get("description", ""),
            "source": "lightagent-skillhub", "source_identity": skill.get("repository", ""),
            "version": skill.get("version"), "enabled": True, "category": "skill",
        }
        with open(path + ".tmp", "w", encoding="utf-8") as handle:
            json.dump(config, handle, ensure_ascii=False, indent=2)
        os.replace(path + ".tmp", path)

    def _remove_skills_config(self, name):
        path = os.path.join(self.skills_dir, "skills_config.json")
        try:
            with open(path, "r", encoding="utf-8") as handle:
                config = json.load(handle)
        except Exception:
            return
        config.pop(name, None)
        with open(path + ".tmp", "w", encoding="utf-8") as handle:
            json.dump(config, handle, ensure_ascii=False, indent=2)
        os.replace(path + ".tmp", path)

    @staticmethod
    def _refresh():
        try:
            from cli.commands.skill import _sync_wechat_group_skill_catalog
            _sync_wechat_group_skill_catalog()
        except Exception:
            pass
        try:
            from bridge.bridge import Bridge
            agent_bridge = Bridge().get_agent_bridge()
            agents = [agent_bridge.default_agent] + list(agent_bridge.agents.values())
            for agent in agents:
                if agent and getattr(agent, "skill_manager", None):
                    agent.skill_manager.refresh_skills()
        except Exception:
            pass
