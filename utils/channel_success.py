"""Channel success operating layer.

The rest of the project makes videos and measures them. This module turns
those signals into a concrete playbook for retention, subscribers, comments,
series, first-day reactions and brand consistency.
"""
from __future__ import annotations

from datetime import datetime, timezone


RETENTION_FLOOR = 62.0
RETENTION_STRETCH = 70.0
SUBS_PER_1000_TARGET = 1.5


def _float(value: object, default: float = 0.0) -> float:
    try:
        return float(value or default)
    except Exception:
        return default


def _int(value: object, default: int = 0) -> int:
    try:
        return int(value or default)
    except Exception:
        return default


def _rank_map(mapping: dict, limit: int = 5) -> list[dict]:
    ranked = [
        {"value": str(key), "score": round(_float(value), 3)}
        for key, value in (mapping or {}).items()
    ]
    ranked.sort(key=lambda item: item["score"], reverse=True)
    return ranked[:limit]


def retention_command_center(latest: dict, fact_ledger: dict) -> dict:
    avg = _float(latest.get("avg_view_pct", latest.get("avg_view_percentage", 0)))
    categories = latest.get("category_avg_view_pct") or {}
    below_floor = latest.get("below_62_pct") or latest.get("below_60_pct") or []
    recovery = []
    watch = []
    scale = []
    for category, raw_pct in sorted(categories.items(), key=lambda item: _float(item[1]), reverse=True):
        pct = round(_float(raw_pct), 3)
        row = {"category": str(category), "retention": pct}
        if pct >= RETENTION_FLOOR:
            scale.append(row)
        elif pct < 45:
            recovery.append(row)
        else:
            watch.append(row)

    repeated_phrases = fact_ledger.get("repeated_phrases") or {}
    phrase_pressure = [
        {"phrase": str(phrase), "uses": _int(count)}
        for phrase, count in list(repeated_phrases.items())[:8]
        if _int(count) >= 3
    ]
    commands = []
    if avg < RETENTION_FLOOR:
        commands.append("Rewrite the first 2 seconds around the visible animal cue before publishing.")
        commands.append("Keep one animal, one surprise, one payoff; remove second facts from weak scripts.")
    if recovery:
        commands.append("Put recovery categories through stricter hooks before they can publish.")
    if scale:
        commands.append("Scale the categories already above 62% retention before adding new experiments.")
    if phrase_pressure:
        commands.append("Rotate repeated title/script phrases so the channel does not feel templated.")

    return {
        "target_floor": RETENTION_FLOOR,
        "target_stretch": RETENTION_STRETCH,
        "average_retention": round(avg, 3),
        "gap_to_floor": round(max(0.0, RETENTION_FLOOR - avg), 3),
        "state": "scale" if avg >= RETENTION_FLOOR else "needs_retention_work",
        "below_floor_count": len(below_floor),
        "scale_categories": scale,
        "watch_categories": watch,
        "recovery_categories": recovery,
        "phrase_pressure": phrase_pressure,
        "commands": commands[:6],
    }


def subscriber_engine(latest: dict) -> dict:
    views = _int(latest.get("total_views", latest.get("total_views_14d", 0)))
    subs = _int(latest.get("subscribers_gained", 0))
    rate = round(subs * 1000 / views, 3) if views else 0.0
    commands = []
    if rate < SUBS_PER_1000_TARGET:
        commands.extend([
            "Use a soft channel promise CTA only after the payoff, never before it.",
            "Connect the CTA to the viewer identity: follow for one animal signal a day.",
            "Apply the CTA only to strong candidates so weak videos do not waste the close.",
        ])
    return {
        "views": views,
        "subscribers_gained": subs,
        "subs_per_1000_views": rate,
        "target_subs_per_1000": SUBS_PER_1000_TARGET,
        "gap_to_target": round(max(0.0, SUBS_PER_1000_TARGET - rate), 3),
        "state": "strong" if rate >= SUBS_PER_1000_TARGET else "needs_conversion_work",
        "commands": commands,
    }


def audience_loop(comments: dict) -> dict:
    sampled = _int(comments.get("comments_sampled", 0))
    requested = [str(item) for item in (comments.get("requested_animals") or [])[:8]]
    prompts = [str(item) for item in (comments.get("content_prompts") or [])[:8]]
    fallback_prompts = [
        "Which animal should we decode next?",
        "Did this behavior surprise you?",
        "Should this become a part 2?",
        "What animal signal have you seen in real life?",
    ]
    if sampled <= 0:
        return {
            "state": "blind_spot",
            "comments_sampled": 0,
            "requested_animals": [],
            "prompts": fallback_prompts,
            "commands": [
                "Pin one viewer question on every strong Short.",
                "Use comments as the next subject source once replies begin arriving.",
                "Keep questions specific so viewers answer with animal names or behaviors.",
            ],
        }
    commands = ["Turn repeated viewer questions into the next queue refresh."]
    if requested:
        commands.append("Prioritize requested animals that also match winning categories.")
    return {
        "state": "active",
        "comments_sampled": sampled,
        "requested_animals": requested,
        "prompts": prompts or fallback_prompts,
        "commands": commands,
    }


def first_24h_engine(latest: dict) -> dict:
    winners = []
    rework = []
    watch = []
    for item in latest.get("top_performers") or []:
        title = str(item.get("title") or "")
        views = _int(item.get("views", 0))
        velocity = _float(item.get("views_per_hour", 0))
        growth = _float(item.get("growth_score", 0))
        retention_raw = item.get("view_pct", item.get("average_view_percentage"))
        retention = _float(retention_raw)
        retention_ready = retention > 0
        row = {
            "title": title,
            "video_id": str(item.get("video_id") or ""),
            "views": views,
            "views_per_hour": round(velocity, 3),
            "growth_score": round(growth, 3),
            "retention": round(retention, 3),
            "retention_ready": retention_ready,
        }
        if retention_ready and retention >= RETENTION_FLOOR and (growth >= 180 or velocity >= 35):
            winners.append(row)
        elif retention_ready and views >= 300 and retention < RETENTION_FLOOR:
            rework.append(row)
        else:
            watch.append(row)
    return {
        "state": "winner_found" if winners else "monitoring",
        "winner_rules": [
            "If retention is above 62% and growth beats 180, make a sequel before chasing a new topic.",
            "If views are high but retention is below 62%, remake the hook instead of copying the topic.",
            "If both views and retention are low, retire the angle for 14 days.",
        ],
        "winners": winners[:6],
        "rework": rework[:6],
        "watch": watch[:6],
    }


def identity_lock() -> dict:
    return {
        "brand_promise": "Wild Brief decodes one surprising animal signal in a fast, human, evidence-aware Short.",
        "voice_rules": [
            "Sound curious, not robotic.",
            "Open with the animal and the payoff inside the first sentence.",
            "Use concrete body cues viewers can see on screen.",
            "End with a calm promise, not a hard sell.",
        ],
        "forbidden_patterns": [
            "Generic openings like 'Did you know'.",
            "Two unrelated facts in one Short.",
            "Overusing words like secret, amazing or incredible.",
            "CTA before the viewer gets the payoff.",
        ],
        "hook_formula": "Animal + visible behavior + surprising reason.",
        "cta_formula": "Follow for one animal signal a day.",
    }


def series_system(latest: dict, ops: dict) -> dict:
    category_growth = latest.get("category_avg_growth_score") or {}
    series_engagement = latest.get("series_avg_engagement") or {}
    paused = {str(item.get("category") or "") for item in ops.get("paused_topics") or []}
    lanes = [
        {"series": "Farmyard Minds", "categories": ["farm"], "promise": "smart behavior in familiar animals"},
        {"series": "Sky Intelligence", "categories": ["birds"], "promise": "bird senses, memory and navigation"},
        {"series": "Animal Superpowers", "categories": ["wildlife"], "promise": "body features that look impossible"},
        {"series": "Ocean Signals", "categories": ["ocean"], "promise": "underwater behavior viewers can decode"},
        {"series": "Pet Signals", "categories": ["cats", "dogs"], "promise": "home-animal behavior with stricter retention gates"},
    ]
    for lane in lanes:
        growth = max((_float(category_growth.get(category)) for category in lane["categories"]), default=0.0)
        existing = _float(series_engagement.get(lane["series"]))
        lane["priority_score"] = round(max(growth, existing), 3)
        lane["state"] = "recovery" if any(category in paused for category in lane["categories"]) else "active"
    lanes.sort(key=lambda item: item["priority_score"], reverse=True)
    return {
        "state": "ready",
        "lanes": lanes,
        "commands": [
            "Name each new script internally by series so learning compounds.",
            "Publish in repeatable lanes, not random animals.",
            "Keep one experimental lane open so the channel can discover the next breakout.",
        ],
    }


def thirty_day_review(latest: dict) -> dict:
    tracked = _int(latest.get("shorts_tracked", len(latest.get("top_performers") or [])))
    views = _int(latest.get("total_views", latest.get("total_views_14d", 0)))
    avg = _float(latest.get("avg_view_pct", latest.get("avg_view_percentage", 0)))
    ready = tracked >= 60
    return {
        "state": "ready_for_full_review" if ready else "baseline_building",
        "shorts_tracked": tracked,
        "target_sample": 60,
        "tracked_views": views,
        "average_retention": round(avg, 3),
        "review_questions": [
            "Which category creates both views and retention?",
            "Which format converts subscribers?",
            "Which narrator and hook style should become default?",
            "Which topics must be paused for 14 days?",
        ],
    }


def build_success_plan(
    latest: dict,
    comments: dict,
    health: dict,
    autonomous: dict,
    fact_ledger: dict,
    ops: dict,
) -> dict:
    retention = retention_command_center(latest, fact_ledger)
    subscribers = subscriber_engine(latest)
    audience = audience_loop(comments)
    first_day = first_24h_engine(latest)
    series = series_system(latest, ops)
    review = thirty_day_review(latest)

    score = 100.0
    score -= min(25.0, retention["gap_to_floor"] * 2)
    score -= min(15.0, subscribers["gap_to_target"] * 10)
    score -= 10.0 if audience["state"] == "blind_spot" else 0.0
    score -= 10.0 if _int(fact_ledger.get("risk_score", 0)) >= 80 else 0.0
    quota = autonomous.get("quota_budget") or {}
    score -= 8.0 if quota.get("state") == "watch" else 0.0
    score -= 8.0 if _int(health.get("score", 0)) < 80 else 0.0
    score = round(max(0.0, min(100.0, score)), 1)

    next_actions = []
    next_actions.extend(retention.get("commands") or [])
    next_actions.extend(subscribers.get("commands") or [])
    next_actions.extend(audience.get("commands") or [])
    if first_day.get("winners"):
        next_actions.append("Create sequels for first-day winners before broad discovery.")
    next_actions.extend(series.get("commands") or [])

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "success_score": score,
        "state": "success_ready" if score >= 80 else "growth_building",
        "retention": retention,
        "subscriber_conversion": subscribers,
        "audience_loop": audience,
        "first_24h": first_day,
        "identity": identity_lock(),
        "series_system": series,
        "thirty_day_review": review,
        "next_actions": next_actions[:10],
        "operating_principle": "Scale only what earns retention, then use comments and sequels to compound attention.",
    }
