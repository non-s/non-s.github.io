#!/usr/bin/env python3
"""Write the Wild Brief scale blueprint."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.scale_blueprint import build_scale_blueprint

OUT = ROOT / "_data" / "scale_blueprint.json"


def _safe(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def main() -> int:
    payload = build_scale_blueprint(
        latest=_safe(ROOT / "_data" / "analytics" / "latest.json"),
        channel_success=_safe(ROOT / "_data" / "channel_success.json"),
        objective=_safe(ROOT / "_data" / "channel_objective.json"),
        queue_audit=_safe(ROOT / "_data" / "queue_audit.json"),
        next_shorts=_safe(ROOT / "_data" / "next_shorts.json"),
        early_performance=_safe(ROOT / "_data" / "early_performance.json"),
    )
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    summary = payload.get("dashboard_summary") or {}
    print(
        "scale blueprint: "
        f"{summary.get('phase', payload.get('phase'))} "
        f"top={summary.get('top_bottleneck', 'none')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
