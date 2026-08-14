"""Deterministic editorial planning for a balanced Liquid Wire catalogue."""

from __future__ import annotations

from datetime import date, timedelta

from utils.community_rituals import ritual_for_date

_SHORT_SERIES = (
    ("geometric-generative", "wireframe", "focus", "discovery and funnel entry"),
    ("organic-generative", "organic", "ambient", "discovery and funnel entry"),
    ("cosmic-generative", "nebula", "relax", "discovery and funnel entry"),
    ("ambient-generative", "fluid", "ambient", "discovery and funnel entry"),
)
_LONG_DAYS = frozenset({1, 6})  # Tuesday and Sunday, matching the production workflow.


def build_calendar(start: date, days: int = 30) -> list[dict[str, str]]:
    """Plan one Short per day plus two long-form retention sessions per week."""
    if days < 1:
        return []
    items: list[dict[str, str]] = []
    for offset in range(days):
        publish_date = start + timedelta(days=offset)
        ritual = ritual_for_date(publish_date)
        pillar, scene, mood, funnel_role = _SHORT_SERIES[offset % len(_SHORT_SERIES)]
        items.append(
            {
                "date": publish_date.isoformat(),
                "format": "short",
                "pillar": pillar,
                "scene": scene,
                "mood": mood,
                "objective": "discovery",
                "primary_metric": "stayed to watch",
                "funnel_role": funnel_role,
                "ritual": ritual["id"],
                "viewer_intent": ritual["viewer_intent"],
                "community_prompt": ritual["community_prompt"],
            }
        )
        if publish_date.weekday() in _LONG_DAYS:
            items.append(
                {
                    "date": publish_date.isoformat(),
                    "format": "long",
                    "pillar": pillar,
                    "scene": scene,
                    "mood": mood,
                    "objective": "retention and return viewing",
                    "primary_metric": "average view duration",
                    "funnel_role": "playlist continuation",
                    "ritual": ritual["id"],
                    "viewer_intent": ritual["viewer_intent"],
                    "community_prompt": ritual["community_prompt"],
                }
            )
    return items
