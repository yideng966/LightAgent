"""Signed static registry client for the official LightAgent Skill Hub."""

import base64
import json
import os
from dataclasses import dataclass
from typing import Dict, List, Optional

import requests

from cli.utils import get_workspace_dir, load_config_json


DEFAULT_REGISTRY_URL = "https://yideng966.github.io/LightAgent-SkillHub/registry.json"
REGISTRY_PUBLIC_KEYS = {
    "lightagent-skillhub-2026-01": "ddZUto18e4bp5pRMgrHD8xJoCfFGxiXznA8G8ksyaMQ=",
}


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

    def list_skills(self, query="", include_unavailable=False) -> List[Dict]:
        skills = self.load().data.get("skills", [])
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
        if not isinstance(document, dict) or document.get("registry_version") != 1:
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
        os.makedirs(self.cache_dir, exist_ok=True)
        temp_path = self.cache_path + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as handle:
            json.dump(document, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, self.cache_path)

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
