"""Growth studio intelligence for Wild Brief.

This module keeps the next-level growth logic local and free: it turns
existing queue entries and analytics snapshots into editorial choices
for narrative format, narrator profile, remake candidates and weekly
operator guidance.
"""
from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import asdict, dataclass

from utils.experiments import assign_for_production, read_winners
from utils.story_intelligence import classify_format


@dataclass(frozen=True)
class NarrativeTemplate:
    id: str
    label: str
    prompt_rule: str
    best_for: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


NARRATIVE_TEMPLATES: tuple[NarrativeTemplate, ...] = (
    NarrativeTemplate(
        id="outcome_then_because",
        label="Outcome, then because",
        prompt_rule=(
            "Open with the animal plus the surprising outcome, then resolve it "
            "with one clear because/that-is-why payoff."
        ),
        best_for=("animal_intelligence", "animal_memory", "survival_mechanism"),
    ),
    NarrativeTemplate(
        id="myth_flip",
        label="Myth flip",
        prompt_rule=(
            "Start from what viewers probably assume, then flip it with the "
            "real animal reason in plain language."
        ),
        best_for=("myth_bust", "surprising_behavior", "pet_behavior"),
    ),
    NarrativeTemplate(
        id="watch_closely",
        label="Watch closely",
        prompt_rule=(
            "Point viewers at one visible body detail in the first seconds, "
            "then explain why that detail matters."
        ),
        best_for=("visual_detail", "survival_mechanism", "camouflage"),
    ),
    NarrativeTemplate(
        id="tiny_question",
        label="Tiny question",
        prompt_rule=(
            "Ask a small concrete why/how question, answer it quickly, and end "
            "with a viewer-friendly follow-up question."
        ),
        best_for=("animal_intelligence", "pet_behavior", "animal_memory"),
    ),
    NarrativeTemplate(
        id="cute_but_survival",
        label="Cute, but survival",
        prompt_rule=(
            "If the clip looks cute, reveal the survival function behind the "
            "behavior without overdramatizing it."
        ),
        best_for=("pet_behavior", "survival_mechanism", "farm_behavior"),
    ),
)


_CATEGORY_TEMPLATE = {
    "cats": "myth_flip",
    "dogs": "tiny_question",
    "farm": "cute_but_survival",
    "ocean": "outcome_then_because",
    "birds": "watch_closely",
    "reptiles": "watch_closely",
    "insects": "watch_closely",
    "primates": "outcome_then_because",
}

_NARRATOR_BY_VARIANT = {
    "aria": {
        "variant": "aria",
        "role": "crisp documentary host",
        "direction": "calm, precise, curious, with one human reaction",
    },
    "jenny": {
        "variant": "jenny",
        "role": "warm animal explainer",
        "direction": "friendly, close, a little more emotional on cute clips",
    },
    "guy": {
        "variant": "guy",
        "role": "measured field-note narrator",
        "direction": "steady, observational, useful for predators and survival facts",
    },
}


def _hash_bucket(key: str, modulo: int = 100) -> int:
    digest = hashlib.sha1(key.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % modulo


def _template_by_id(template_id: str) -> NarrativeTemplate:
    for template in NARRATIVE_TEMPLATES:
        if template.id == template_id:
            return template
    return NARRATIVE_TEMPLATES[0]


def _strategy_or_latest(strategy: dict | None) -> dict:
    if strategy is not None:
        return strategy
    try:
        from utils.growth_strategy import load_strategy
        return load_strategy()
    except Exception:
        return {}


def choose_narrative_template(story: dict, strategy: dict | None = None) -> dict:
    strategy = _strategy_or_latest(strategy)
    text = f"{story.get('title', '')} {story.get('hook', '')} {story.get('script', '')}"
    story_format = str(story.get("story_format") or classify_format(text))
    hot_formats = [str(item) for item in (strategy.get("hot_formats") or [])]
    for template in NARRATIVE_TEMPLATES:
        if story_format in template.best_for and story_format in hot_formats:
            return template.to_dict()
    category = str(story.get("category") or "").lower()
    if category in _CATEGORY_TEMPLATE:
        return _template_by_id(_CATEGORY_TEMPLATE[category]).to_dict()
    matching = [t for t in NARRATIVE_TEMPLATES if story_format in t.best_for]
    if matching:
        return matching[0].to_dict()
    key = str(story.get("id") or story.get("title") or "wildbrief")
    return NARRATIVE_TEMPLATES[_hash_bucket(key, len(NARRATIVE_TEMPLATES))].to_dict()


def choose_narrator_profile(story: dict, strategy: dict | None = None) -> dict:
    strategy = _strategy_or_latest(strategy)
    winners = read_winners()
    variant = winners.get("narrator_voice")
    if not variant:
        variant = (story.get("experiments") or {}).get("narrator_voice")
    if not variant:
        category = str(story.get("category") or "").lower()
        if category in {"cats", "dogs", "farm"}:
            variant = "jenny"
        elif category in {"reptiles", "wildlife", "arctic", "nocturnal"}:
            variant = "guy"
        else:
            variant = assign_for_production(
                "narrator_voice",
                str(story.get("id") or story.get("title") or category or "wildbrief"),
                exploration_percent=20,
            )
    profile = dict(_NARRATOR_BY_VARIANT.get(str(variant), _NARRATOR_BY_VARIANT["aria"]))
    profile["reason"] = "winner_or_category_fit"
    return profile


def production_mode_for_story(story: dict, strategy: dict | None = None) -> str:
    strategy = _strategy_or_latest(strategy)
    key = str(story.get("id") or story.get("title") or "wildbrief")
    bucket = _hash_bucket("mode:" + key)
    hot_categories = {str(item).lower() for item in (strategy.get("hot_categories") or [])}
    hot_formats = {str(item) for item in (strategy.get("hot_formats") or [])}
    story_format = str(story.get("story_format") or classify_format(
        f"{story.get('title', '')} {story.get('hook', '')} {story.get('script', '')}"
    ))
    category = str(story.get("category") or "").lower()
    if category in hot_categories or story_format in hot_formats:
        return "exploit" if bucket < 78 else "explore"
    if bucket < 10:
        return "moonshot"
    if bucket < 35:
        return "explore"
    return "steady"


def studio_brief_for_story(story: dict, strategy: dict | None = None) -> dict:
    strategy = _strategy_or_latest(strategy)
    template = choose_narrative_template(story, strategy)
    narrator = choose_narrator_profile(story, strategy)
    mode = production_mode_for_story(story, strategy)
    return {
        "production_mode": mode,
        "narrative_template": template,
        "narrator": narrator,
        "prompt_overlay": (
            f"Narrative template: {template['label']}. {template['prompt_rule']} "
            f"Narrator direction: {narrator['direction']}."
        ),
    }


def _avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 3) if values else 0.0


def build_performance_matrix(observations: list[dict]) -> dict:
    axes = (
        "category", "story_format", "narrator_voice", "hook_style",
        "script_tone", "thumbnail_style", "series", "humanity_label",
    )
    buckets: dict[str, dict[str, list[dict]]] = {
        axis: defaultdict(list) for axis in axes
    }
    for item in observations:
        experiments = item.get("experiments") or {}
        values = {
            "category": item.get("category") or "unknown",
            "story_format": item.get("story_format") or "unknown",
            "narrator_voice": item.get("narrator_voice") or experiments.get("narrator_voice") or "unknown",
            "hook_style": experiments.get("hook_style") or "unknown",
            "script_tone": experiments.get("script_tone") or "unknown",
            "thumbnail_style": experiments.get("thumbnail_style") or "unknown",
            "series": item.get("series") or "Unassigned",
            "humanity_label": item.get("humanity_label") or "unknown",
        }
        for axis, value in values.items():
            buckets[axis][str(value)].append(item)

    matrix: dict[str, dict[str, dict]] = {}
    for axis, by_value in buckets.items():
        matrix[axis] = {}
        for value, rows in by_value.items():
            growth = [float(r.get("growth_score", 0) or 0) for r in rows]
            retention = [
                float(r.get("average_view_percentage", 0) or 0)
                for r in rows if float(r.get("average_view_percentage", 0) or 0) > 0
            ]
            subscribers = sum(int(r.get("subscribers_gained", 0) or 0) for r in rows)
            matrix[axis][value] = {
                "n": len(rows),
                "mean_growth": _avg(growth),
                "mean_retention": _avg(retention),
                "subscribers_gained": subscribers,
            }
    return matrix


def winners_and_losers(matrix: dict) -> dict:
    out = {"winners": {}, "losers": {}}
    for axis, by_value in matrix.items():
        ranked = sorted(
            by_value.items(),
            key=lambda kv: (kv[1].get("mean_growth", 0), kv[1].get("mean_retention", 0), kv[1].get("n", 0)),
            reverse=True,
        )
        if ranked:
            out["winners"][axis] = {"value": ranked[0][0], **ranked[0][1]}
        eligible_losers = [item for item in ranked if item[1].get("n", 0) > 0]
        if len(eligible_losers) >= 2:
            value, stats = eligible_losers[-1]
            out["losers"][axis] = {"value": value, **stats}
    return out


def remake_candidates(top_performers: list[dict]) -> list[dict]:
    candidates: list[dict] = []
    for item in top_performers:
        views = int(item.get("views", 0) or 0)
        retention = float(item.get("view_pct", item.get("average_view_percentage", 0)) or 0)
        growth = float(item.get("growth_score", 0) or 0)
        if retention >= 60 and views >= 250:
            action = "make sequel with a new animal in the same story shape"
        elif retention >= 55 and views < 250:
            action = "remake with sharper title and first-second visual text"
        elif 0 < retention < 55 and views >= 250:
            action = "reuse topic only after changing the hook format"
        else:
            continue
        candidates.append({
            "video_id": item.get("video_id", ""),
            "title": item.get("title", ""),
            "views": views,
            "retention": retention,
            "growth_score": growth,
            "action": action,
        })
        if len(candidates) >= 8:
            break
    return candidates


def production_mix(observations: list[dict]) -> dict:
    tracked = len(observations)
    if tracked < 12:
        return {"exploit": 50, "explore": 35, "moonshot": 15, "reason": "early_channel_learning"}
    return {"exploit": 70, "explore": 20, "moonshot": 10, "reason": "measured_growth_loop"}


def weekly_brief(snapshot: dict, observations: list[dict], matrix: dict,
                 remakes: list[dict]) -> dict:
    wl = winners_and_losers(matrix)
    winners = wl.get("winners", {})
    return {
        "headline": "Scale what retains, remake what nearly worked, keep experiments small.",
        "views": snapshot.get("total_views", 0),
        "avg_retention": snapshot.get("avg_view_pct", snapshot.get("avg_view_percentage", 0)),
        "subscribers_gained": snapshot.get("subscribers_gained", 0),
        "best_category": (winners.get("category") or {}).get("value", ""),
        "best_format": (winners.get("story_format") or {}).get("value", ""),
        "best_narrator": (winners.get("narrator_voice") or {}).get("value", ""),
        "remake_count": len(remakes),
        "production_mix": production_mix(observations),
        "next_actions": [
            "Publish mostly proven categories and formats until new data says otherwise.",
            "Use one visible detail in the first second before explaining the fact.",
            "Turn high-retention videos into sequels with a new animal or angle.",
            "Keep narrator testing measured so the channel still feels like one host.",
        ],
    }
