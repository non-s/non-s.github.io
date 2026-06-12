"""Shared publishing priority helpers.

These helpers rank candidates after quality gates have already decided a
story is publishable. The autonomy plan is the operational owner of the
next slot; queue and publish scores only break ties.
"""

from __future__ import annotations


def numeric(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def queue_score(story: dict) -> float:
    return numeric((story.get("queue_prune") or {}).get("score"), 0.0)


def autonomy_priority(story: dict, fallback: float = 0.0) -> float:
    priority = numeric((story.get("autonomy") or {}).get("priority"), 0.0)
    return priority if priority > 0 else numeric(fallback, 0.0)


def publish_priority_key(story: dict, publish_score: dict | None = None) -> tuple[float, float, float]:
    q_score = queue_score(story)
    p_score = numeric((publish_score or story.get("publish_score") or {}).get("score"), 0.0)
    return (autonomy_priority(story, q_score or p_score), q_score, p_score)
