#!/usr/bin/env python3
"""Write narrator performance from latest analytics."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.narrator_optimizer import narrator_report

LATEST = ROOT / "_data" / "analytics" / "latest.json"
OUT = ROOT / "_data" / "narrator_report.json"


def _safe_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def main() -> int:
    latest = _safe_json(LATEST)
    payload = narrator_report(latest.get("top_performers") or [])
    payload["generated_at"] = datetime.now(timezone.utc).isoformat()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"narrator report: {len(payload.get('voices') or [])} voice group(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
