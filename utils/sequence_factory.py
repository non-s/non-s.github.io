"""Generate sequel/remake prompts from proven Shorts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from utils.editorial_guard import editorial_issues
from utils.remake_factory import build_remake_story

ANALYTICS_FILE = Path("_data/analytics/latest.json")
SEQUENCES_FILE = Path("_data/sequence_plan.json")
SESSION_SEQUELS_FILE = Path("_data/sequel_candidates.json")


def _safe_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _recommendable_title(title: str) -> bool:
    title = str(title or "").strip()
    if not title:
        return False
    return not editorial_issues({"title": title, "seo_title": title}, include_script=False)


def build_sequence_plan(
    analytics: dict | None = None, *, limit: int = 5, include_session_handoff: bool | None = None
) -> dict:
    include_session_handoff = analytics is None if include_session_handoff is None else include_session_handoff
    analytics = analytics or _safe_json(ANALYTICS_FILE)
    winners = []
    for item in analytics.get("top_performers") or []:
        if not _recommendable_title(str(item.get("title") or "")):
            continue
        retention = float(item.get("view_pct") or item.get("average_view_percentage") or 0)
        growth = float(item.get("growth_score") or 0)
        views = int(item.get("views") or 0)
        if (retention >= 62 and growth >= 180) or views >= 1200:
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
    session_sequels = (_safe_json(SESSION_SEQUELS_FILE).get("items") or []) if include_session_handoff else []
    for item in session_sequels[:limit]:
        if not isinstance(item, dict):
            continue
        story = build_remake_story(
            {
                "source_video_id": item.get("video_id") or item.get("source_video_id", ""),
                "source_title": item.get("title", ""),
                "category": item.get("category", ""),
                "action": item.get("prompt") or "session_graph_sequel",
            }
        )
        story["sequence_variant"] = "session_graph_sequel"
        handoff = dict(item)
        original_title = str(item.get("title") or "")
        clean_title = str((story.get("remake_of") or {}).get("title") or story.get("title") or "")
        if original_title and clean_title and not _recommendable_title(original_title):
            handoff["title"] = clean_title
            prompt = str(handoff.get("prompt") or "")
            handoff["prompt"] = prompt.replace(original_title, clean_title)
        story["session_handoff"] = handoff
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
