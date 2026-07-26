"""Signed static registry client for the official LightAgent Skill Hub."""

import base64
import json
import os
import tempfile
import threading
from dataclasses import dataclass
from typing import Dict, List, Optional
from urllib.parse import quote

import requests

from cli.utils import SKILL_HUB_API, get_workspace_dir, load_config_json
from agent.skills.legacy_compat import merge_legacy_requirements


DEFAULT_REGISTRY_URL = "https://xiaoguiwucan.github.io/LightAgent-SkillHub/registry.json"
REGISTRY_PUBLIC_KEYS = {
    "lightagent-skillhub-2026-01": "ddZUto18e4bp5pRMgrHD8xJoCfFGxiXznA8G8ksyaMQ=",
}

_CACHE_WRITE_LOCK = threading.Lock()


def _legacy_requirements(item):
    return merge_legacy_requirements(item)[0]


class RegistryError(RuntimeError):
    pass


class RegistrySecurityError(RegistryError):
    pass


def _canonical_json(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _registry_url():
    config = load_config_json()
    return str(
        os.environ.get("LIGHTAGENT_SKILL_REGISTRY_URL")
        or config.get("skill_registry_url")
        or DEFAULT_REGISTRY_URL
    ).strip()


@dataclass(frozen=True)
class RegistrySnapshot:
    data: Dict
    source: str
    cached: bool = False


class SkillRegistryClient:
    """Loads and verifies the official registry, with last-known-good cache."""

    def __init__(self, url: Optional[str] = None, cache_dir: Optional[str] = None, session=None):
        self.url = url or _registry_url()
        self.cache_dir = cache_dir or os.path.join(get_workspace_dir(), ".skillhub")
        self.cache_path = os.path.join(self.cache_dir, "registry.last-good.json")
        self.session = session or requests

    def load(self, allow_cache=True) -> RegistrySnapshot:
        try:
            response = self.session.get(self.url, timeout=(5, 15))
            response.raise_for_status()
            document = response.json()
            self._verify(document)
            self._write_cache(document)
            return RegistrySnapshot(document, self.url, cached=False)
        except RegistrySecurityError:
            raise
        except Exception as exc:
            if allow_cache:
                cached = self._read_cache()
                if cached is not None:
                    return RegistrySnapshot(cached, self.cache_path, cached=True)
            raise RegistryError(f"无法读取技能注册表: {exc}") from exc

    def list_skills(
        self, query="", include_unavailable=False, snapshot: Optional[RegistrySnapshot] = None
    ) -> List[Dict]:
        skills = (snapshot or self.load()).data.get("skills", [])
        if not include_unavailable:
            skills = [item for item in skills if item.get("status", "active") in ("active", "deprecated")]
        query = str(query or "").strip().lower()
        if query:
            skills = [
                item for item in skills
                if query in " ".join(
                    [str(item.get("name", "")), str(item.get("description", "")),
                     str(item.get("author", "")), *[str(tag) for tag in item.get("tags", [])]]
                ).lower()
            ]
        return skills

    def get_skill(self, name: str) -> Dict:
        for item in self.load().data.get("skills", []):
            if item.get("name") == name:
                status = item.get("status", "active")
                if status in ("yanked", "revoked"):
                    raise RegistrySecurityError(f"技能 {name} 的 {item.get('version')} 版本已被 {status}")
                return item
        raise RegistryError(f"官方技能中心不存在技能 {name}")

    def _verify(self, document):
        if not isinstance(document, dict) or document.get("registry_version") not in (1, 2):
            raise RegistrySecurityError("不支持的技能注册表格式")
        signature = document.get("signature")
        if not isinstance(signature, dict) or signature.get("algorithm") != "ed25519":
            raise RegistrySecurityError("技能注册表缺少 Ed25519 签名")
        key_id = signature.get("key_id")
        encoded_key = REGISTRY_PUBLIC_KEYS.get(key_id)
        if not encoded_key or not signature.get("value"):
            raise RegistrySecurityError("技能注册表使用了未知签名密钥")
        payload = dict(document)
        payload.pop("signature", None)
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

            key = Ed25519PublicKey.from_public_bytes(base64.b64decode(encoded_key))
            key.verify(base64.b64decode(signature["value"]), _canonical_json(payload))
        except ImportError as exc:
            raise RegistrySecurityError("缺少 cryptography，无法验证技能注册表签名") from exc
        except Exception as exc:
            raise RegistrySecurityError("技能注册表签名无效") from exc

    def _write_cache(self, document):
        with _CACHE_WRITE_LOCK:
            os.makedirs(self.cache_dir, exist_ok=True)
            fd, temp_path = tempfile.mkstemp(
                prefix="registry.", suffix=".tmp", dir=self.cache_dir
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(document, handle, ensure_ascii=False, indent=2)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp_path, self.cache_path)
            finally:
                try:
                    os.unlink(temp_path)
                except FileNotFoundError:
                    pass

    def _read_cache(self):
        try:
            with open(self.cache_path, "r", encoding="utf-8") as handle:
                document = json.load(handle)
            self._verify(document)
            return document
        except FileNotFoundError:
            return None
        except RegistrySecurityError:
            raise
        except Exception:
            return None


class LegacySkillRegistryClient:
    """Catalog client for the original CowAgent skill marketplace.

    This source is intentionally kept distinct from the signed official
    registry. Its entries are normalized for the shared UI, but are never
    presented as signed artifacts.
    """

    SOURCE = "cowagent-skillhub"

    def __init__(self, api_url: Optional[str] = None, cache_dir: Optional[str] = None, session=None):
        self.api_url = (api_url or SKILL_HUB_API).rstrip("/")
        self.cache_dir = cache_dir or os.path.join(get_workspace_dir(), ".skillhub")
        self.cache_path = os.path.join(self.cache_dir, "cowagent-catalog.last-good.json")
        self.session = session or requests

    def list_skills(self, query="", allow_cache=True) -> List[Dict]:
        try:
            first = self._fetch_page(1)
            skills = list(first.get("skills") or [])
            total = int(first.get("total") or len(skills))
            limit = max(1, int(first.get("limit") or 50))
            for page in range(2, (total + limit - 1) // limit + 1):
                skills.extend(self._fetch_page(page).get("skills") or [])
            normalized = [self._normalize(item) for item in skills]
            self._write_cache(normalized)
        except Exception as exc:
            normalized = self._read_cache() if allow_cache else None
            if normalized is None:
                raise RegistryError(f"无法读取原技能广场: {exc}") from exc
        for item in normalized:
            item.setdefault(
                "detail_url",
                f"https://skills.cowagent.ai/{quote(str(item.get('name') or ''), safe='')}",
            )
            item["requirements"], compat = merge_legacy_requirements(item)
            item["compat_manifest_version"] = compat.get("manifest_version") if compat else None
            item["reviewed_artifact_sha256"] = compat.get("artifact_sha256") if compat else None
            item["integrity_status"] = "reviewed_hash" if item["reviewed_artifact_sha256"] else "first_install_lock"
        query = str(query or "").strip().lower()
        if query:
            normalized = [
                item for item in normalized
                if query in " ".join([
                    str(item.get("name", "")), str(item.get("display_name", "")),
                    str(item.get("description", "")), str(item.get("author", "")),
                    *[str(tag) for tag in item.get("tags", [])],
                ]).lower()
            ]
        return normalized

    def get_skill(self, name: str) -> Dict:
        for item in self.list_skills():
            if item.get("name") == name:
                return item
        raise RegistryError(f"原技能广场不存在技能 {name}")

    def _fetch_page(self, page):
        response = self.session.get(
            f"{self.api_url}/skills",
            params={"page": page, "limit": 50},
            timeout=(5, 15),
        )
        response.raise_for_status()
        value = response.json()
        if not isinstance(value, dict) or not isinstance(value.get("skills"), list):
            raise RegistryError("原技能广场返回了无效目录")
        return value

    def _normalize(self, item):
        status = "active" if item.get("status") == "published" else str(item.get("status") or "active")
        normalized = {
            **item,
            "description": item.get("description") or item.get("summary") or "",
            "publisher": item.get("author") or item.get("source_provider") or "community",
            "status": status,
            "registry_source": self.SOURCE,
            "registry_label": "原技能广场",
            "registry_url": self.api_url,
            "detail_url": f"https://skills.cowagent.ai/{quote(str(item.get('name') or ''), safe='')}",
            "min_lightagent_version": None,
            "max_lightagent_version": None,
            "requirements": {},
            "lightagent": {
                "network_domains": [], "file_paths": [], "tools": [],
                "docker_notes": "请根据技能声明预先准备所需命令和环境变量。",
            },
        }
        normalized["requirements"], compat = merge_legacy_requirements(normalized)
        normalized["compat_manifest_version"] = compat.get("manifest_version") if compat else None
        normalized["reviewed_artifact_sha256"] = compat.get("artifact_sha256") if compat else None
        normalized["integrity_status"] = "reviewed_hash" if normalized["reviewed_artifact_sha256"] else "first_install_lock"
        return normalized

    def _write_cache(self, skills):
        with _CACHE_WRITE_LOCK:
            os.makedirs(self.cache_dir, exist_ok=True)
            fd, temp_path = tempfile.mkstemp(prefix="cowagent-catalog.", suffix=".tmp", dir=self.cache_dir)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(skills, handle, ensure_ascii=False, indent=2)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp_path, self.cache_path)
            finally:
                try:
                    os.unlink(temp_path)
                except FileNotFoundError:
                    pass

    def _read_cache(self):
        try:
            with open(self.cache_path, "r", encoding="utf-8") as handle:
                value = json.load(handle)
            return value if isinstance(value, list) else None
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return None
