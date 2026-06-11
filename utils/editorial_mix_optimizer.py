"""Editorial mix balancing across trend, evergreen, sequel and recovery lanes."""

from __future__ import annotations

from collections import Counter

LANE_TARGETS = {
    "trend": 0.25,
    "evergreen": 0.35,
    "sequel": 0.25,
    "recovery": 0.15,
}


def classify_lane(story: dict) -> str:
    if story.get("freshness_score", 0) and float(story.get("freshness_score") or 0) >= 65:
        return "trend"
    title = " ".join(str(story.get(key) or "").lower() for key in ("title", "seo_title", "story_format", "series"))
    if "sequel" in title or story.get("sequence_variant"):
        return "sequel"
    if (story.get("category") or "").lower() in {"cats", "dogs", "farm"}:
        return "recovery"
    return "evergreen"


def mix_adjustment(story: dict, recent_lanes: list[str] | None = None) -> float:
    lane = classify_lane(story)
    recent_lanes = recent_lanes or []
    counts = Counter(recent_lanes)
    total = max(sum(counts.values()), 1)
    current_share = counts.get(lane, 0) / total
    target = LANE_TARGETS.get(lane, 0.25)
    if current_share > target + 0.15:
        return -8.0
    if current_share < max(target - 0.12, 0):
        return 5.0
    return 0.0


def build_mix_plan(stories: list[dict], recent_lanes: list[str] | None = None) -> dict:
    rows = []
    for story in stories:
        lane = classify_lane(story)
        rows.append(
            {
                "id": story.get("id", ""),
                "title": story.get("seo_title") or story.get("title") or "",
                "category": story.get("category", ""),
                "lane": lane,
                "adjustment": mix_adjustment(story, recent_lanes),
                "freshness_score": story.get("freshness_score", 0),
            }
        )
    counts = Counter(row["lane"] for row in rows)
    return {
        "targets": LANE_TARGETS,
        "counts": dict(counts),
        "items": rows,
        "recommendation": "balance_underrepresented_lanes_first",
    }
