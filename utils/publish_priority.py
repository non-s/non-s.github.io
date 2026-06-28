"""Shared publishing priority helpers.

These helpers rank candidates after quality gates have already decided a
story is publishable. The autonomy plan is the operational owner of the
next slot; queue and publish scores only break ties.
"""

from __future__ import annotations

SELECTION_RULE = "autonomy_priority with retention lift, then queue_score and publish_score"


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


def _nested_numeric(payload: dict | None, path: tuple[str, ...], default: float | None = None) -> float | None:
    cur: object = payload or {}
    for key in path:
        cur = cur.get(key) if isinstance(cur, dict) else None
    if cur in (None, ""):
        return default
    return numeric(cur, default if default is not None else 0.0)


def _first_numeric(*values: float | None, default: float) -> float:
    for value in values:
        if value is not None:
            return value
    return default


def _payoff_score(seconds: float | None) -> float:
    if seconds is None or seconds <= 0:
        return 70.0
    if seconds <= 8.5:
        return 100.0
    if seconds <= 10.5:
        return 92.0
    if seconds <= 12.0:
        return 68.0
    if seconds <= 18.0:
        return 44.0
    return 18.0


def _swipe_score(story: dict, publish_score: dict | None = None) -> float:
    band = (
        str(
            _nested_value(publish_score, ("objective_gate", "swipe_risk_band"))
            or _nested_value(story, ("packaging", "swipe_risk", "band"))
            or ""
        )
        .strip()
        .lower()
    )
    if band == "high":
        return 20.0
    if band == "medium":
        return 55.0
    return 100.0


def _nested_value(payload: dict | None, path: tuple[str, ...]):
    cur: object = payload or {}
    for key in path:
        cur = cur.get(key) if isinstance(cur, dict) else None
    return cur


def _loop_score(story: dict, publish_score: dict | None = None) -> float:
    value = _first_numeric(
        _nested_numeric(story, ("loop_plan", "loop_score")),
        _nested_numeric(story, ("packaging", "loop_plan", "loop_score")),
        _nested_numeric(story, ("packaging", "loop_score")),
        _nested_numeric(story, ("loop_score",)),
        _nested_numeric(story, ("loop", "score")),
        default=0.5,
    )
    if value <= 1.0:
        return value * 100.0
    return min(100.0, value)


def retention_priority_score(story: dict, publish_score: dict | None = None) -> float:
    """Score the packaging traits that matter most while Level 3 is active."""
    publish_score = publish_score or story.get("publish_score") or {}
    opening = _first_numeric(
        _nested_numeric(publish_score, ("opening_retention", "score")),
        _nested_numeric(story, ("opening_retention", "score")),
        _nested_numeric(story, ("frame_zero_packaging", "retention_opening", "score")),
        _nested_numeric(story, ("packaging", "opening_retention", "score")),
        _nested_numeric(story, ("packaging", "frame_zero", "retention_opening", "score")),
        _nested_numeric(story, ("youtube_brain", "opening_retention", "score")),
        default=70.0,
    )
    replay = _first_numeric(
        _nested_numeric(publish_score, ("retention", "signals", "replay_score")),
        _nested_numeric(publish_score, ("retention", "score")),
        default=65.0,
    )
    payoff = _first_numeric(
        _nested_numeric(publish_score, ("objective_gate", "payoff_time_s")),
        _nested_numeric(story, ("packaging", "preflight_inputs", "payoff_time_s")),
        default=0.0,
    )
    score = (
        opening * 0.38
        + replay * 0.22
        + _loop_score(story, publish_score) * 0.20
        + _payoff_score(payoff) * 0.15
        + _swipe_score(story, publish_score) * 0.05
    )
    return round(max(0.0, min(100.0, score)), 2)


def retention_lift(story: dict, publish_score: dict | None = None) -> float:
    """Bounded primary-rank nudge so retention can break close autonomy calls."""
    score = retention_priority_score(story, publish_score)
    return round(max(-8.0, min(6.0, (score - 75.0) / 4.0)), 3)


def publish_priority_key(story: dict, publish_score: dict | None = None) -> tuple[float, float, float, float]:
    q_score = queue_score(story)
    p_score = numeric((publish_score or story.get("publish_score") or {}).get("score"), 0.0)
    r_score = retention_priority_score(story, publish_score)
    return (
        autonomy_priority(story, q_score or p_score) + retention_lift(story, publish_score),
        r_score,
        q_score,
        p_score,
    )
