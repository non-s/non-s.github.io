#!/usr/bin/env python3
"""Build learned format memory from uploaded Wild Brief markers."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.growth_engine import MEMORY_PATH, build_format_memory

VIDEOS_DIR = ROOT / "_videos"


def _load_markers() -> list[dict]:
    markers: list[dict] = []
    for path in sorted(VIDEOS_DIR.glob("*.done")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict):
            markers.append(data)
    return markers


def main() -> int:
    payload = build_format_memory(_load_markers())
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    MEMORY_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"format-memory: wrote {MEMORY_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
