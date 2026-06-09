"""Generate sequel/remake prompts from proven Shorts."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from utils.remake_factory import build_remake_story

ANALYTICS_FILE = Path("_data/analytics/latest.json")
SEQUENCES_FILE = Path("_data/sequence_plan.json")


def _safe_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def build_sequence_plan(analytics: dict | None = None, *, limit: int = 5) -> dict:
    analytics = analytics or _safe_json(ANALYTICS_FILE)
    winners = []
    for item in analytics.get("top_performers") or []:
        retention = float(item.get("view_pct") or item.get("average_view_percentage") or 0)
        growth = float(item.get("growth_score") or 0)
        views = int(item.get("views") or 0)
        if (retention >= 60 and growth >= 180) or views >= 1200:
            winners.append(item)
    variants = []
    for winner in winners[:limit]:
        base = {
            "source_video_id": winner.get("video_id", ""),
            "source_title": winner.get("title", ""),
            "category": winner.get("category", ""),
            "views": winner.get("views", 0),
            "retention": winner.get("view_pct") or winner.get("average_view_percentage") or 0,
            "growth_score": winner.get("growth_score", 0),
        }
        for kind in ("same_format_new_animal", "same_animal_new_behavior", "same_topic_stronger_hook"):
            story = build_remake_story({**base, "action": kind})
            story["sequence_variant"] = kind
            variants.append(story)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_winners": len(winners),
        "variants": variants,
        "commands": [
            "Use one sequence variant per winner before exploring a cold topic.",
            "Do not publish all variants back-to-back; mix with proven farm/birds inventory.",
        ],
    }


def write_sequence_plan(path: Path = SEQUENCES_FILE) -> dict:
    plan = build_sequence_plan()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    return plan
