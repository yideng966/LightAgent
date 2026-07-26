#!/usr/bin/env python3
"""Generate a review-gap report for the original skill marketplace."""

import argparse
import hashlib
import json
from pathlib import Path

import requests

from agent.skills.legacy_compat import load_legacy_compat_manifest


API = "https://skills.cowagent.ai/api"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="legacy-skill-review-report.json")
    parser.add_argument("--download-hashes", action="store_true")
    args = parser.parse_args()
    catalog = fetch_catalog(requests)
    reviewed = load_legacy_compat_manifest().get("skills", {})
    rows = []
    for item in catalog:
        name = str(item.get("name") or "")
        version = str(item.get("version") or "")
        entry = (reviewed.get(name) or {}).get(version) or (reviewed.get(name) or {}).get("*")
        row = {"name": name, "version": version, "reviewed": bool(entry), "artifact_sha256": None}
        if args.download_hashes:
            package = requests.post(f"{API}/skills/{name}/download", json={"mirror": True}, timeout=30)
            package.raise_for_status()
            row["artifact_sha256"] = hashlib.sha256(package.content).hexdigest()
        rows.append(row)
    Path(args.output).write_text(json.dumps({"skills": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已生成 {len(rows)} 个技能的审核缺口报告: {args.output}")


def fetch_catalog(session):
    catalog = []
    page = 1
    while True:
        response = session.get(
            f"{API}/skills", params={"page": page, "limit": 100}, timeout=(5, 20)
        )
        response.raise_for_status()
        value = response.json()
        skills = list(value.get("skills") or [])
        catalog.extend(skills)
        total = int(value.get("total") or len(catalog))
        if not skills or len(catalog) >= total:
            return catalog
        page += 1


if __name__ == "__main__":
    main()
