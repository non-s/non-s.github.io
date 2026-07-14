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

from utils.visual_qa_backfill import infer_marker_visual_qa
from utils.visual_learning import build_visual_learning, visual_profile_key


def build_report() -> dict:
    total = checked = approved = rejected = 0
    ctr_checked = ctr_strong = ctr_weak = 0
    reasons: Counter[str] = Counter()
    weak = []
    observations = []
    for path in sorted(VIDEOS.glob("*.done")) if VIDEOS.exists() else []:
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        total += 1
        qa = item.get("visual_qa") or {}
        local = item.get("local_visual_qa") or {}
        inferred = infer_marker_visual_qa(item)
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
        ctr = item.get("visual_ctr") or {}
        observations.append(
            {
                "visual_profile": visual_profile_key(item),
                "visual_ctr_score": ctr.get("score") if ctr.get("checked") else None,
                "growth_score": item.get("growth_score", 0),
                "average_view_percentage": item.get("view_pct", item.get("average_view_percentage", 0)),
                "views": item.get("views", 0),
            }
        )
        if ctr.get("checked"):
            ctr_checked += 1
            ctr_score = int(ctr.get("score", 0) or 0)
            if ctr_score >= 72:
                ctr_strong += 1
            elif ctr_score < 58:
                ctr_weak += 1
                reasons[str(ctr.get("reason") or "weak_ctr_frame")] += 1
        if quality and quality < 6:
            weak.append(
                {
                    "video_id": item.get("video_id", ""),
                    "title": item.get("title", ""),
                    "quality": quality,
                    "reason": qa.get("reason") or local.get("reason", ""),
                }
            )
        elif inferred.get("needs_backfill"):
            reason = str(inferred.get("reason") or "legacy_unchecked")
            reasons[reason] += 1
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_markers": total,
        "checked": checked,
        "coverage_pct": round(checked * 100 / total, 2) if total else 0,
        "inferred_legacy_checked": max(0, total - checked),
        "inferred_coverage_pct": 100.0 if total else 0,
        "approved": approved,
        "rejected": rejected,
        "ctr_checked": ctr_checked,
        "ctr_strong": ctr_strong,
        "ctr_weak": ctr_weak,
        "visual_learning": build_visual_learning(observations),
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
