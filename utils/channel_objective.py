"""Channel objective targets from YouTube Studio operator snapshots."""

from __future__ import annotations

import json
from pathlib import Path

OBJECTIVE_PATH = Path("_data/channel_objective.json")

DEFAULT_TARGETS = {
    "stayed_to_watch_floor": 0.4,
    "stayed_to_watch_stretch": 0.45,
    "swipe_away_ceiling": 0.6,
    "new_viewer_subscribe_rate_floor": 0.005,
    "new_viewer_subscribe_rate_stretch": 0.008,
    "recurring_viewer_rate_floor": 0.02,
    "recurring_viewer_rate_stretch": 0.05,
    "subs_per_1000_views_floor": 1.5,
    "max_publish_ready_template_cluster": 2,
    "max_publish_ready_mechanism_cluster": 2,
    "decision_confidence_floor": 0.18,
    "decision_confidence_scale_floor": 0.35,
    "payoff_time_floor_seconds": 10.5,
}


def _num(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def load_channel_objective(path: Path = OBJECTIVE_PATH) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data["targets"] = {**DEFAULT_TARGETS, **(data.get("targets") or {})}
            return data
    except Exception:
        pass
    return {"targets": dict(DEFAULT_TARGETS), "baseline": {}}


def reach_goal_status(objective: dict, reach_summary: dict | None = None) -> dict:
    targets = {**DEFAULT_TARGETS, **(objective.get("targets") or {})}
    baseline = objective.get("baseline") or {}
    summary = reach_summary or {}
    row_count = int(summary.get("rows") or 0)
    if row_count:
        stayed = _num(summary.get("stayed_to_watch_rate"), _num(baseline.get("stayed_to_watch_rate")))
        swiped = _num(summary.get("swipe_away_rate"), _num(baseline.get("swipe_away_rate"), max(0.0, 1.0 - stayed)))
    else:
        stayed = _num(baseline.get("stayed_to_watch_rate"))
        swiped = _num(baseline.get("swipe_away_rate"), max(0.0, 1.0 - stayed))
    floor = _num(targets.get("stayed_to_watch_floor"), 0.4)
    return {
        "source": "studio_reach_import" if row_count else "operator_baseline",
        "rows": row_count,
        "stayed_to_watch_rate": round(stayed, 4),
        "stayed_to_watch_floor": floor,
        "gap_to_floor": round(max(0.0, floor - stayed), 4),
        "swipe_away_rate": round(swiped, 4),
        "swipe_away_ceiling": _num(targets.get("swipe_away_ceiling"), 0.6),
        "state": "healthy" if stayed >= floor else "needs_first_second_work",
        "commands": (
            [
                "Rewrite frame zero and the first spoken line around animal + real curiosity + visible anchor + payoff.",
                "Reject packages with slow payoff, vague first-frame text, or medium/high swipe risk.",
                "Use Studio Reach exports to replace this baseline with per-video stayed-to-watch data.",
            ]
            if stayed < floor
            else [
                "Keep measuring stayed-to-watch by video before scaling a title pattern.",
            ]
        ),
    }


def audience_goal_status(objective: dict) -> dict:
    targets = {**DEFAULT_TARGETS, **(objective.get("targets") or {})}
    baseline = objective.get("baseline") or {}
    monthly = _num(baseline.get("monthly_audience"))
    subs = _num(baseline.get("subscribers_gained"))
    new_rate = _num(baseline.get("new_viewer_rate"))
    recurring = _num(baseline.get("recurring_viewer_rate"), _num(baseline.get("recurring_viewer_rate_upper_bound")))
    new_viewers = monthly * new_rate
    subscribe_rate = subs / max(new_viewers, 1.0)
    sub_floor = _num(targets.get("new_viewer_subscribe_rate_floor"), 0.005)
    recurring_floor = _num(targets.get("recurring_viewer_rate_floor"), 0.02)
    commands: list[str] = []
    if subscribe_rate < sub_floor:
        commands.append("Put the same channel promise after strong payoffs: Follow for one animal signal a day.")
    if recurring < recurring_floor:
        commands.append("Publish recognizable lanes and sequels so new viewers know what returns tomorrow.")
    commands.append(
        "Treat a video as a full winner only when it drives retention plus subscribers, comments, or return signals."
    )
    return {
        "source": "operator_baseline",
        "monthly_audience": int(monthly),
        "new_viewer_rate": round(new_rate, 4),
        "casual_viewer_rate": round(_num(baseline.get("casual_viewer_rate")), 4),
        "recurring_viewer_rate": round(recurring, 4),
        "recurring_viewer_rate_floor": recurring_floor,
        "new_viewer_subscribe_rate": round(subscribe_rate, 4),
        "new_viewer_subscribe_rate_floor": sub_floor,
        "state": "needs_recurrence_work" if recurring < recurring_floor else "recurrence_building",
        "commands": commands,
    }


def title_template_cluster(title: str) -> str:
    lower = " ".join(str(title or "").lower().split())
    if "read the moment from one" in lower:
        return "read_the_moment"
    if "react differently when" in lower:
        return "react_differently"
    if lower.startswith("this ") and " changes what " in lower:
        return "this_changes_what"
    if "hiding in plain sight" in lower:
        return "hiding_plain_sight"
    if " rely on " in lower and " to survive" in lower:
        return "rely_to_survive"
    return ""


def cognitive_mechanism_cluster(story: dict) -> str:
    text = " ".join(
        str(story.get(key) or "")
        for key in ("seo_title", "title", "hook", "script", "thumbnail_text", "category", "story_format")
    )
    lower = " ".join(text.lower().split())
    if "fake injuries" in lower or "fake injury" in lower or "limp pulls" in lower:
        return "decoy_injury"
    if "keep the hunt quiet" in lower or "quiet moment" in lower or "silent cue" in lower:
        return "stealth_hunt"
    if "bigger group" in lower or "group before they swim" in lower or "clutch" in lower:
        return "group_choice"
    if "recognize faces" in lower or "recognizes faces" in lower:
        return "face_recognition"
    if "face memory" in lower or "remember familiar faces" in lower:
        return "face_recognition"
    if "steady eyes" in lower or "view steady" in lower:
        return "visual_stabilization"
    if "wing scales" in lower:
        return "wing_scales"
    if "taste feet" in lower or "taste flowers" in lower:
        return "taste_sensors"
    if "tongue smell" in lower or "smell the air" in lower:
        return "tongue_smell"
    if "electric sense" in lower or "electric fields" in lower:
        return "electric_sense"
    if "scent map" in lower or "scent post" in lower:
        return "scent_map"
    if "magnetic map" in lower:
        return "magnetic_navigation"
    if "dance map" in lower:
        return "dance_navigation"
    if "recognize signals through" in lower or "recognize familiar signals" in lower:
        return "signal_recognition"
    if "body posture" in lower or "body cue" in lower:
        return "body_posture_signal"
    if "feeding cue" in lower or "bottle feeding" in lower:
        return "feeding_signal"
    if "react differently when" in lower:
        return "reaction_to_visible_cue"
    if "read the moment from one" in lower:
        return "cue_timing_read"
    if lower.startswith("this ") and " changes what " in lower:
        return "cue_changes_next_move"
    if " rely on " in lower and " to survive" in lower:
        return "survival_cue"
    for cue, cluster in (
        ("ear", "ear_signal"),
        ("tail", "tail_signal"),
        ("head", "head_signal"),
        ("wing", "wing_signal"),
        ("fin", "fin_signal"),
        ("flipper", "flipper_signal"),
        ("beak", "beak_signal"),
        ("call", "call_signal"),
    ):
        if cue in lower and any(word in lower for word in ("signal", "cue", "movement", "shift", "position")):
            return cluster
    return ""


def objective_gate_for_story(
    story: dict, publish: dict, packaging: dict | None = None, objective: dict | None = None
) -> dict:
    objective = objective or load_channel_objective()
    targets = {**DEFAULT_TARGETS, **(objective.get("targets") or {})}
    packaging = packaging or story.get("packaging") or {}
    confidence = _num((publish.get("decision_confidence") or {}).get("confidence_score"))
    swipe = packaging.get("swipe_risk") or {}
    preflight = packaging.get("preflight_inputs") or {}
    payoff_time = _num(preflight.get("payoff_time_s"))
    viewer_request = (
        str(story.get("studio_state") or "") == "comment_idea"
        or str(story.get("source") or "").strip().lower() == "youtube comment idea"
        or "viewer_question" in ((story.get("comment_score") or {}).get("reasons") or [])
    )
    reasons: list[str] = []
    penalty = 0.0
    if confidence and confidence < _num(targets.get("decision_confidence_floor")):
        if viewer_request:
            reasons.append("viewer_request_observe_before_scaling")
            penalty += 0
        else:
            reasons.append("low_decision_confidence")
            penalty += 10
    elif confidence and confidence < _num(targets.get("decision_confidence_scale_floor")):
        reasons.append("observe_before_scaling")
        penalty += 0
    if (swipe.get("band") or "") in {"medium", "high"}:
        reasons.append("swipe_risk_not_low")
        penalty += 8 if swipe.get("band") == "medium" else 18
    if payoff_time and payoff_time > _num(targets.get("payoff_time_floor_seconds")):
        reasons.append("payoff_too_late_for_current_swipe_baseline")
        penalty += 6
    cluster = title_template_cluster(str(story.get("seo_title") or story.get("title") or ""))
    mechanism = cognitive_mechanism_cluster(story)
    blocking = any(
        reason in reasons
        for reason in (
            "swipe_risk_not_low",
            "payoff_too_late_for_current_swipe_baseline",
        )
    )
    return {
        "penalty": penalty,
        "reasons": reasons,
        "confidence_score": round(confidence, 3),
        "scale_ready": not reasons,
        "publish_blocking": blocking,
        "swipe_risk_band": str(swipe.get("band") or ""),
        "payoff_time_s": round(payoff_time, 2),
        "template_cluster": cluster,
        "mechanism_cluster": mechanism,
    }
