"""Reviewed compatibility metadata for the unsigned original marketplace."""

import json
import re
from functools import lru_cache
from pathlib import Path


_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
_KINDS = ("env", "bins", "python", "npm", "downloads", "capabilities")


@lru_cache(maxsize=1)
def load_legacy_compat_manifest():
    path = Path(__file__).with_name("legacy_compat.json")
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("manifest_version") != 1 or not isinstance(value.get("skills"), dict):
        raise ValueError("原技能广场兼容清单格式无效")
    for name, versions in value["skills"].items():
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,62}[a-z0-9]", str(name)):
            raise ValueError(f"原技能广场兼容清单包含无效技能名: {name}")
        if not isinstance(versions, dict):
            raise ValueError(f"{name} 的兼容版本清单无效")
        for version, entry in versions.items():
            if version != "*" and not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?", str(version)):
                raise ValueError(f"{name} 的兼容版本号无效: {version}")
            _validate_entry(name, version, entry)
    return value


def _validate_entry(name, version, entry):
    if not isinstance(entry, dict):
        raise ValueError(f"{name} {version} 的兼容条目无效")
    digest = str(entry.get("artifact_sha256") or "").lower()
    if digest and not _SHA256_RE.fullmatch(digest):
        raise ValueError(f"{name} {version} 的审核哈希无效")
    requirements = entry.get("requirements") or {}
    if not isinstance(requirements, dict) or any(key not in _KINDS for key in requirements):
        raise ValueError(f"{name} {version} 的依赖字段无效")
    for kind, values in requirements.items():
        if not isinstance(values, list):
            raise ValueError(f"{name} {version} 的 {kind} 依赖必须是列表")
        if kind == "downloads":
            for download in values:
                if not isinstance(download, dict) or not str(download.get("url") or "").startswith("https://"):
                    raise ValueError(f"{name} {version} 包含无效下载依赖")
                if not _SHA256_RE.fullmatch(str(download.get("sha256") or "").lower()):
                    raise ValueError(f"{name} {version} 的下载依赖缺少有效 SHA-256")
        elif not all(isinstance(item, str) and item.strip() for item in values):
            raise ValueError(f"{name} {version} 的 {kind} 依赖无效")


def legacy_compat_entry(name, version):
    manifest = load_legacy_compat_manifest()
    versions = manifest["skills"].get(str(name), {})
    entry = versions.get(str(version)) or versions.get("*")
    if not isinstance(entry, dict):
        return None
    digest = str(entry.get("artifact_sha256") or "").lower()
    if digest and not _SHA256_RE.fullmatch(digest):
        raise ValueError(f"{name} {version} 的审核哈希无效")
    result = dict(entry)
    result["manifest_version"] = manifest["manifest_version"]
    return result


def merge_legacy_requirements(item):
    current = item.get("requirements") if isinstance(item.get("requirements"), dict) else {}
    merged = {
        "env": list(item.get("requires_env") or current.get("env") or []),
        "bins": list(item.get("requires_bins") or current.get("bins") or []),
        "python": list(current.get("python") or []),
        "npm": list(current.get("npm") or []),
        "downloads": list(current.get("downloads") or []),
        "capabilities": list(current.get("capabilities") or []),
    }
    compat = legacy_compat_entry(item.get("name"), item.get("version"))
    if compat:
        for kind, values in (compat.get("requirements") or {}).items():
            if kind in _KINDS:
                merged[kind] = list(dict.fromkeys([*merged.get(kind, []), *list(values or [])]))
    return merged, compat
