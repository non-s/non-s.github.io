#!/usr/bin/env python3
"""Report background music-bed readiness."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _enabled(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def build_report(root: Path = ROOT) -> dict:
    music_enabled = _enabled("MUSIC_BED_ENABLED", "0")
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rollout_state": "disabled",
        "source": "",
        "music_bed_enabled": music_enabled,
        "canary_percent": 0,
        "license_policy": "no-external-music-source",
        "manual_download_required": False,
    }
    out = root / "_data" / "music_bed_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = build_report(Path(args.root).resolve())
    print(json.dumps(report, sort_keys=True, ensure_ascii=False) if args.json else "music_bed_report: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
