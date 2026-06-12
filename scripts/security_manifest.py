#!/usr/bin/env python3
"""Generate a tiny local SBOM/license manifest without network calls."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _requirements(root: Path) -> list[str]:
    path = root / "requirements.txt"
    if not path.exists():
        return []
    names = []
    for line in path.read_text(encoding="utf-8").splitlines():
        clean = line.split("#", 1)[0].strip()
        if not clean:
            continue
        names.append(re.split(r"[<>=!~;,\[]", clean, maxsplit=1)[0].strip())
    return sorted(set(name for name in names if name))


def _license_from_metadata(dist_meta: metadata.PackageMetadata) -> str:
    license_text = dist_meta.get("License-Expression") or dist_meta.get("License") or ""
    if license_text:
        return license_text
    for classifier in dist_meta.get_all("Classifier") or []:
        prefix = "License :: OSI Approved :: "
        if classifier.startswith(prefix):
            return classifier.removeprefix(prefix)
    return ""


def build_manifest(root: Path = ROOT) -> dict:
    packages = []
    for name in _requirements(root):
        try:
            version = metadata.version(name)
            dist_meta = metadata.metadata(name)
            license_text = _license_from_metadata(dist_meta)
        except Exception:
            version = ""
            license_text = ""
        packages.append({"name": name, "version": version, "license": license_text})
    if not packages:
        for dist in sorted(metadata.distributions(), key=lambda d: (d.metadata.get("Name") or "").lower()):
            name = dist.metadata.get("Name") or ""
            if not name:
                continue
            packages.append({"name": name, "version": dist.version, "license": _license_from_metadata(dist.metadata)})
            if len(packages) >= 25:
                break
    report = {
        "bomFormat": "CycloneDX-lite",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "components": packages,
        "component_count": len(packages),
    }
    out = root / "_data" / "security_manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = build_manifest(Path(args.root).resolve())
    print(
        json.dumps({"component_count": report["component_count"]}, sort_keys=True)
        if args.json
        else "security_manifest: ok"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
