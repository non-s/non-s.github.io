#!/usr/bin/env python3
"""Build fan-growth reporting focused on subscribers per 1k views."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.subscriber_conversion import FAN_GROWTH_PATH, write_fan_growth


def _load_markers(videos_dir: Path = ROOT / "_videos") -> list[dict]:
    markers: list[dict] = []
    for path in sorted(videos_dir.glob("*.done")) if videos_dir.exists() else []:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                markers.append(data)
        except Exception:
            continue
    return markers


def _load_comments(path: Path = ROOT / "_data" / "analytics" / "comments.json") -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    raw = data.get("raw_comments") if isinstance(data, dict) else []
    return raw if isinstance(raw, list) else []


def main() -> int:
    payload = write_fan_growth(_load_markers(), _load_comments(), ROOT / FAN_GROWTH_PATH)
    print(
        "fan_growth: "
        f"{len(payload.get('videos_ranked_by_subs_per_1k') or [])} ranked video(s), "
        f"{len(payload.get('recurring_commenters') or [])} recurring commenter(s)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
