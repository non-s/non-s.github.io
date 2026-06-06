#!/usr/bin/env python3
"""Summarise visual QA coverage from uploaded marker metadata."""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

VIDEOS = ROOT / "_videos"
OUT = ROOT / "_data" / "visual_quality_report.json"


def build_report() -> dict:
    total = checked = approved = rejected = 0
    reasons: Counter[str] = Counter()
    weak = []
    for path in sorted(VIDEOS.glob("*.done")) if VIDEOS.exists() else []:
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        total += 1
        qa = item.get("visual_qa") or {}
        local = item.get("local_visual_qa") or {}
        if qa.get("checked") or local.get("checked"):
            checked += 1
        is_approved = not (
            (qa.get("checked") and not qa.get("approved", True))
            or (local.get("checked") and not local.get("approved", True))
        )
        if qa.get("checked") or local.get("checked"):
            if is_approved:
                approved += 1
            else:
                rejected += 1
                reason = str(qa.get("reason") or local.get("reason") or "visual_rejected")
                reasons[reason] += 1
        quality = int(qa.get("thumbnail_quality", local.get("score", 0)) or 0)
        if quality and quality < 6:
            weak.append({
                "video_id": item.get("video_id", ""),
                "title": item.get("title", ""),
                "quality": quality,
                "reason": qa.get("reason") or local.get("reason", ""),
            })
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_markers": total,
        "checked": checked,
        "coverage_pct": round(checked * 100 / total, 2) if total else 0,
        "approved": approved,
        "rejected": rejected,
        "top_reasons": dict(reasons.most_common(8)),
        "weak_visuals": weak[:20],
    }


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = build_report()
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"visual qa report: {payload['checked']}/{payload['total_markers']} checked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
