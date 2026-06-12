"""Million-view scale blueprint for Wild Brief.

This module turns YouTube Studio/channel metrics into an operating plan. It is
intentionally opinionated: when the channel gets Shorts Feed discovery but weak
recurrence, the system should optimize for first-second retention, recognizable
series, and subscriber conversion before chasing random topics.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone


def _num(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _int(value: object, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return default


def _rate(part: float, whole: float) -> float:
    return round(part / whole, 4) if whole else 0.0


def _targets(objective: dict) -> dict:
    return objective.get("targets") if isinstance(objective.get("targets"), dict) else {}


def studio_baseline(latest: dict, objective: dict, channel_success: dict | None = None) -> dict:
    """Return one normalized view of channel scale metrics."""
    channel_success = channel_success or {}
    base = objective.get("baseline") if isinstance(objective.get("baseline"), dict) else {}
    reach = channel_success.get("studio_reach") if isinstance(channel_success.get("studio_reach"), dict) else {}
    recurrence = (
        channel_success.get("audience_recurrence")
        if isinstance(channel_success.get("audience_recurrence"), dict)
        else {}
    )

    views = _int(base.get("views"), _int(latest.get("total_views")))
    engaged = _int(base.get("engaged_views"))
    stayed = _num(base.get("stayed_to_watch_rate"), _num(reach.get("stayed_to_watch_rate")))
    if not engaged and stayed and views:
        engaged = round(views * stayed)
    subscribers_gained = _int(base.get("subscribers_gained"), _int(latest.get("subscribers_gained")))
    monthly_audience = _int(base.get("monthly_audience"), views)
    new_viewer_rate = _num(base.get("new_viewer_rate"), _num(recurrence.get("new_viewer_rate")))
    recurring_rate = _num(
        base.get("recurring_viewer_rate"),
        _num(base.get("recurring_viewer_rate_upper_bound"), _num(recurrence.get("recurring_viewer_rate"))),
    )
    total_subscribers = _int(base.get("total_subscribers"))
    subs_per_1000 = round(subscribers_gained * 1000 / views, 3) if views else 0.0

    return {
        "period": objective.get("period") or {"label": "latest"},
        "views": views,
        "engaged_views": engaged,
        "engaged_view_rate": _rate(engaged, views),
        "watch_time_hours": round(_num(base.get("watch_time_hours")), 3),
        "monthly_audience": monthly_audience,
        "total_subscribers": total_subscribers,
        "subscribers_gained": subscribers_gained,
        "subs_per_1000_views": subs_per_1000,
        "stayed_to_watch_rate": round(stayed, 4),
        "swipe_away_rate": round(_num(base.get("swipe_away_rate"), max(0.0, 1.0 - stayed)), 4),
        "new_viewer_rate": round(new_viewer_rate, 4),
        "casual_viewer_rate": round(_num(base.get("casual_viewer_rate")), 4),
        "recurring_viewer_rate": round(recurring_rate, 4),
        "shorts_feed_view_rate": round(_num(base.get("shorts_feed_view_rate")), 4),
        "youtube_search_view_rate": round(_num(base.get("youtube_search_view_rate")), 4),
        "channel_pages_view_rate": round(_num(base.get("channel_pages_view_rate")), 4),
        "mobile_watch_time_rate": round(_num(base.get("mobile_watch_time_rate")), 4),
        "top_country_us_view_rate": round(_num(base.get("top_country_us_view_rate")), 4),
        "no_captions_view_rate": round(_num(base.get("no_captions_view_rate")), 4),
        "realtime_48h_views": _int(base.get("realtime_48h_views")),
        "avg_view_percentage": round(
            _num(latest.get("avg_view_pct"), _num(latest.get("avg_view_percentage"))),
            3,
        ),
        "shorts_tracked": _int(latest.get("shorts_tracked")),
    }


def growth_phase(baseline: dict, targets: dict) -> str:
    views = _int(baseline.get("views"))
    subs = _int(baseline.get("total_subscribers"))
    recurring = _num(baseline.get("recurring_viewer_rate"))
    recurring_floor = _num(targets.get("recurring_viewer_rate_floor"), 0.02)
    if views >= 25000 and recurring < recurring_floor:
        return "discovery_spike_to_loyalty"
    if views >= 100000 and subs < 1000:
        return "scale_attention_into_subscribers"
    if subs >= 1000 and recurring >= recurring_floor:
        return "compound_winners"
    return "baseline_building"


def bottlenecks(baseline: dict, targets: dict, channel_success: dict | None = None) -> list[dict]:
    channel_success = channel_success or {}
    items: list[dict] = []
    stayed = _num(baseline.get("stayed_to_watch_rate"))
    stayed_floor = _num(targets.get("stayed_to_watch_floor"), 0.4)
    if stayed < stayed_floor:
        items.append(
            {
                "id": "first_second",
                "severity": "critical",
                "metric": "stayed_to_watch_rate",
                "current": stayed,
                "target": stayed_floor,
                "gap": round(stayed_floor - stayed, 4),
                "action": "Reject any package whose first frame and first spoken line do not show animal, visible cue, and payoff.",
            }
        )
    recurring = _num(baseline.get("recurring_viewer_rate"))
    recurring_floor = _num(targets.get("recurring_viewer_rate_floor"), 0.02)
    if recurring < recurring_floor:
        items.append(
            {
                "id": "recurring_audience",
                "severity": "critical",
                "metric": "recurring_viewer_rate",
                "current": recurring,
                "target": recurring_floor,
                "gap": round(recurring_floor - recurring, 4),
                "action": "Turn every strong Short into a named lane, sequel prompt, and pinned next-episode question.",
            }
        )
    sub_rate = _num(baseline.get("subs_per_1000_views"))
    sub_floor = _num(targets.get("subs_per_1000_views_floor"), 1.5)
    if sub_rate < sub_floor:
        items.append(
            {
                "id": "subscriber_conversion",
                "severity": "high",
                "metric": "subs_per_1000_views",
                "current": sub_rate,
                "target": sub_floor,
                "gap": round(sub_floor - sub_rate, 3),
                "action": "Place the channel promise after the payoff: follow for one animal signal a day.",
            }
        )
    feed_rate = _num(baseline.get("shorts_feed_view_rate"))
    search_rate = _num(baseline.get("youtube_search_view_rate"))
    if feed_rate >= 0.9 and search_rate < 0.05:
        items.append(
            {
                "id": "feed_dependency",
                "severity": "medium",
                "metric": "shorts_feed_view_rate",
                "current": feed_rate,
                "target": 0.85,
                "gap": round(feed_rate - 0.85, 4),
                "action": "Add query-shaped titles and descriptions around animal behavior so winners can collect search/suggested traffic later.",
            }
        )
    audience_loop = (
        channel_success.get("audience_loop") if isinstance(channel_success.get("audience_loop"), dict) else {}
    )
    if audience_loop.get("state") == "blind_spot":
        items.append(
            {
                "id": "comment_loop",
                "severity": "medium",
                "metric": "comments_sampled",
                "current": 0,
                "target": 20,
                "gap": 20,
                "action": "Ask specific animal-signal questions in pinned comments until comments become a topic source.",
            }
        )
    return items


def classify_video_action(item: dict) -> dict:
    title = str(item.get("title") or item.get("seo_title") or "")
    views = _int(item.get("views"))
    retention = _num(item.get("view_pct"), _num(item.get("average_view_percentage")))
    subs = _int(item.get("subscribers_gained"), _int(item.get("subscribers")))
    velocity = _num(item.get("views_per_hour"))
    action = "observe"
    reason = "not enough signal yet"
    if views >= 700 and retention >= 78:
        action = "make_sequel_now"
        reason = "high retention with real reach"
    elif views >= 900 and retention < 50:
        action = "remake_opening"
        reason = "reach exists but the opening leaks viewers"
    elif views >= 700 and retention < 62:
        action = "repair_packaging"
        reason = "views are useful but retention is below scale floor"
    elif retention >= 62 and subs >= 2:
        action = "loyalty_seed"
        reason = "viewer quality signal is stronger than raw views"
    elif velocity >= 20 and retention >= 62:
        action = "watch_for_breakout"
        reason = "early velocity and retention are both viable"
    return {
        "video_id": str(item.get("video_id") or ""),
        "title": title,
        "views": views,
        "retention": round(retention, 3),
        "subscribers_gained": subs,
        "views_per_hour": round(velocity, 3),
        "action": action,
        "reason": reason,
    }


def video_action_plan(latest: dict, limit: int = 12) -> dict:
    rows = [classify_video_action(item) for item in latest.get("top_performers") or []]
    priority = {"make_sequel_now": 5, "remake_opening": 4, "loyalty_seed": 3, "repair_packaging": 2}
    rows.sort(key=lambda row: (priority.get(row["action"], 0), row["views"]), reverse=True)
    return {
        "actions": rows[:limit],
        "counts": dict(Counter(row["action"] for row in rows)),
    }


def series_lanes(latest: dict, next_shorts: dict, queue_audit: dict) -> list[dict]:
    category_retention = (
        latest.get("category_avg_view_pct") if isinstance(latest.get("category_avg_view_pct"), dict) else {}
    )
    category_growth = (
        latest.get("category_avg_growth_score") if isinstance(latest.get("category_avg_growth_score"), dict) else {}
    )
    next_items = [item for item in (next_shorts.get("items") or []) if isinstance(item, dict)]
    category_supply = Counter(str(item.get("category") or "unknown") for item in next_items)
    mechanism_supply = (
        queue_audit.get("mechanism_clusters") if isinstance(queue_audit.get("mechanism_clusters"), dict) else {}
    )
    lane_defs = [
        {
            "lane": "Farmyard Minds",
            "categories": ["farm"],
            "promise": "familiar animals doing smarter things than viewers expect",
        },
        {
            "lane": "Body Clues",
            "categories": ["wildlife", "primates"],
            "promise": "one visible body cue that explains the next move",
        },
        {
            "lane": "Ocean Signals",
            "categories": ["ocean"],
            "promise": "underwater behavior decoded through a visible signal",
        },
        {
            "lane": "Predator tells",
            "categories": ["wildlife"],
            "promise": "small cues before hunting, escape, or defense",
        },
        {
            "lane": "Pet Signals",
            "categories": ["cats", "dogs"],
            "promise": "home-animal behavior only when the hook beats retention gates",
        },
    ]
    lanes: list[dict] = []
    for lane in lane_defs:
        cats = lane["categories"]
        retention = max((_num(category_retention.get(cat)) for cat in cats), default=0.0)
        growth = max((_num(category_growth.get(cat)) for cat in cats), default=0.0)
        supply = sum(category_supply.get(cat, 0) for cat in cats)
        state = "scale" if retention >= 62 or growth >= 180 else "test"
        if retention and retention < 45:
            state = "repair"
        lanes.append(
            {
                **lane,
                "state": state,
                "retention": round(retention, 3),
                "growth_score": round(growth, 3),
                "publish_ready_supply": supply,
            }
        )
    lanes.sort(
        key=lambda lane: (
            lane["state"] == "scale",
            lane["growth_score"],
            lane["retention"],
            lane["publish_ready_supply"],
        ),
        reverse=True,
    )
    return lanes


def operating_rules(baseline: dict, targets: dict) -> list[dict]:
    return [
        {
            "id": "frame_zero",
            "rule": "The first frame must contain the animal plus a concrete visual cue in 2-4 words.",
            "why": f"Only {round(_num(baseline.get('stayed_to_watch_rate')) * 100, 1)}% currently continue after the opening.",
        },
        {
            "id": "single_payoff",
            "rule": "One Short gets one promise, one mechanism, one payoff. Remove second facts.",
            "why": "The channel is still training viewers to understand the format instantly.",
        },
        {
            "id": "series_memory",
            "rule": "Every publish-ready story must belong to a recurring lane or a measured experiment.",
            "why": f"Recurring viewers are below {round(_num(targets.get('recurring_viewer_rate_floor'), 0.02) * 100, 1)}%.",
        },
        {
            "id": "cta_after_payoff",
            "rule": "Subscriber CTA appears only after payoff and must promise the next animal signal.",
            "why": f"Current subscriber conversion is {baseline.get('subs_per_1000_views')} per 1,000 views.",
        },
        {
            "id": "search_tail",
            "rule": "Winners get query-shaped metadata for animal + behavior + why/how searches.",
            "why": f"YouTube Search is only {round(_num(baseline.get('youtube_search_view_rate')) * 100, 1)}% of discovery.",
        },
    ]


def milestone_path(baseline: dict) -> list[dict]:
    views = _int(baseline.get("views"))
    total_subscribers = _int(baseline.get("total_subscribers"))
    return [
        {
            "milestone": "100 subscribers",
            "target_subscribers": 100,
            "remaining_subscribers": max(0, 100 - total_subscribers),
            "job": "Prove the channel promise converts strangers into followers.",
        },
        {
            "milestone": "1,000 subscribers",
            "target_subscribers": 1000,
            "remaining_subscribers": max(0, 1000 - total_subscribers),
            "job": "Build recognizable lanes and sequel loops before scaling volume.",
        },
        {
            "milestone": "1,000,000 views per 28 days",
            "target_views_28d": 1_000_000,
            "remaining_views_28d": max(0, 1_000_000 - views),
            "job": "Scale only lanes that beat retention and conversion floors.",
        },
        {
            "milestone": "Silver creator award path",
            "target_subscribers": 100_000,
            "remaining_subscribers": max(0, 100_000 - total_subscribers),
            "job": "Compound format memory into a repeatable audience identity.",
        },
    ]


def production_commands(bottleneck_rows: list[dict], lanes: list[dict], video_plan: dict) -> list[str]:
    commands: list[str] = []
    ids = {row["id"] for row in bottleneck_rows}
    if "first_second" in ids:
        commands.append(
            "Before rendering, run every candidate through a frame-zero rewrite: animal + visible cue + payoff."
        )
    if "recurring_audience" in ids:
        commands.append("Attach a named series lane and next-episode pinned question to every strong candidate.")
    if "feed_dependency" in ids:
        commands.append("For each winner, add one searchable title/description variant around animal behavior intent.")
    scale_lanes = [lane["lane"] for lane in lanes if lane.get("state") == "scale"]
    if scale_lanes:
        commands.append("Use the next publish block to deepen: " + ", ".join(scale_lanes[:3]) + ".")
    sequel_count = (video_plan.get("counts") or {}).get("make_sequel_now", 0)
    remake_count = (video_plan.get("counts") or {}).get("remake_opening", 0)
    if sequel_count:
        commands.append(
            f"Create {sequel_count} sequel/remix prompts from high-retention winners before new broad discovery."
        )
    if remake_count:
        commands.append(f"Remake {remake_count} high-reach/low-retention openings instead of copying their old hooks.")
    return commands[:8]


def build_scale_blueprint(
    latest: dict,
    channel_success: dict,
    objective: dict,
    queue_audit: dict,
    next_shorts: dict,
    early_performance: dict | None = None,
) -> dict:
    baseline = studio_baseline(latest, objective, channel_success)
    targets = _targets(objective)
    phase = growth_phase(baseline, targets)
    bottleneck_rows = bottlenecks(baseline, targets, channel_success)
    video_plan = video_action_plan(latest)
    lanes = series_lanes(latest, next_shorts, queue_audit)
    commands = production_commands(bottleneck_rows, lanes, video_plan)
    early_performance = early_performance or {}
    top_velocity = (
        early_performance.get("top_velocity") if isinstance(early_performance.get("top_velocity"), list) else []
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "phase": phase,
        "north_star": "Turn Shorts Feed spikes into a repeat audience that recognizes Wild Brief and comes back for the next animal signal.",
        "baseline": baseline,
        "bottlenecks": bottleneck_rows,
        "operating_rules": operating_rules(baseline, targets),
        "series_lanes": lanes,
        "video_action_plan": video_plan,
        "production_commands": commands,
        "milestone_path": milestone_path(baseline),
        "next_48h_watch": [
            {
                "title": str(item.get("title") or "")[:120],
                "views": _int(item.get("views")),
                "views_per_hour": round(_num(item.get("views_per_hour")), 3),
                "breakout_probability": item.get("breakout_probability") or {},
            }
            for item in top_velocity[:5]
            if isinstance(item, dict)
        ],
        "dashboard_summary": {
            "phase": phase,
            "views": baseline["views"],
            "subs_per_1000_views": baseline["subs_per_1000_views"],
            "stayed_to_watch_rate": baseline["stayed_to_watch_rate"],
            "recurring_viewer_rate": baseline["recurring_viewer_rate"],
            "top_bottleneck": bottleneck_rows[0]["id"] if bottleneck_rows else "none",
            "top_command": commands[0] if commands else "Keep compounding proven lanes.",
        },
        "data_contract": {
            "requires": [
                "_data/analytics/latest.json",
                "_data/channel_objective.json",
                "_data/channel_success.json",
                "_data/queue_audit.json",
                "_data/next_shorts.json",
            ],
            "writes": "_data/scale_blueprint.json",
        },
    }
