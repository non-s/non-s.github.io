#!/usr/bin/env python3
"""Plan recovery rules for paused or fragile categories."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT = ROOT / "_data" / "category_recovery.json"


def _safe(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def main() -> int:
    ops = _safe(ROOT / "_data" / "ops_guardian.json")
    latest = _safe(ROOT / "_data" / "analytics" / "latest.json")
    retention = latest.get("category_avg_view_pct") or {}
    plans = []
    for item in ops.get("paused_topics") or []:
        category = str(item.get("category") or "")
        plans.append({
            "category": category,
            "state": "paused_recovery",
            "reason": item.get("reason", ""),
            "retention": item.get("retention", retention.get(category, 0)),
            "allowed_formats": ["myth_buster", "body_superpower", "animal_memory"],
            "blocked_patterns": ["generic cute behavior", "slow setup", "question-only hook"],
            "rules": [
                "Only publish this category with an outcome-first hook.",
                "Use a visibly different source clip from recent weak videos.",
                "Keep script under 95 words until retention recovers.",
                "Require retention_surgery verdict ready or tighten; never rewrite.",
            ],
        })
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(plans),
        "plans": plans,
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"category recovery: {payload['count']} plan(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
