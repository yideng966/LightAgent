"""Stable system capability probes used by Skill Hub manifests."""

import importlib.util
import json
import shutil
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def capability_manifest():
    value = json.loads(Path(__file__).with_name("capabilities.json").read_text(encoding="utf-8"))
    if value.get("manifest_version") != 1:
        raise ValueError("技能能力清单格式无效")
    return value


def capability_status(names):
    manifest = capability_manifest()
    definitions = manifest.get("capabilities", {})
    result = []
    for raw_name in names or []:
        name = str(raw_name)
        definition = definitions.get(name)
        if not definition:
            result.append({"name": name, "available": False, "reason": "unknown_capability"})
            continue
        missing = []
        for probe in definition.get("probes", []):
            kind = probe.get("type")
            value = str(probe.get("value") or "")
            if kind == "bin" and not shutil.which(value):
                missing.append(value)
            elif kind == "python_module" and importlib.util.find_spec(value) is None:
                missing.append(value)
        result.append({
            "name": name,
            "label": definition.get("label_zh", name),
            "available": not missing,
            "missing": missing,
            "build_pack": definition.get("build_pack"),
            "full_image": manifest.get("full_image"),
        })
    return result


def require_capabilities(skill):
    names = (skill.get("requirements") or {}).get("capabilities", [])
    statuses = capability_status(names)
    missing = [item for item in statuses if not item.get("available")]
    if missing:
        details = ", ".join(
            f"{item['name']} ({'/'.join(item.get('missing') or [item.get('reason', 'unavailable')])})"
            for item in missing
        )
        image = capability_manifest().get("full_image")
        raise RuntimeError(
            f"技能 {skill.get('name')} 缺少系统能力: {details}。"
            f"请使用官方能力镜像 {image} 或通过 SKILL_CAPABILITY_PACKS 构建。"
        )
    return statuses
