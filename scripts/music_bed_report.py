#!/usr/bin/env python3
"""Report safe music-bed canary readiness."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build_report(root: Path = ROOT) -> dict:
    manifest = root / "_data" / "audio_library_manifest.json"
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except Exception:
        data = {"tracks": []}
    tracks = data.get("tracks") if isinstance(data, dict) else []
    safe = [row for row in tracks or [] if isinstance(row, dict) and row.get("safe_for_short") is not False]
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "safe_tracks": len(safe),
        "canary_percent": 5,
        "rollout_state": "ready" if safe else "disabled_no_safe_tracks",
    }
    out = root / "_data" / "music_bed_report.json"
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
