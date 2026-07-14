"""Level-based operating loop for the Wild Brief automation.

The scale blueprint says where the channel must grow. This module turns the
current automation state into a concrete game loop: current level, boss,
upgrade, gates, and the next free-resource moves.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

PUBLISH_READY_TARGET = 6
PENDING_TARGET = 20


LEVELS = [
    {
        "number": 1,
        "name": "Launch safety",
        "mission": "Keep the publisher safe, recoverable, and able to upload without manual drama.",
        "unlock": "At least one real upload is recorded and automation health is usable.",
        "revenue_job": "Protect the channel asset before chasing volume.",
    },
    {
        "number": 2,
        "name": "Publish supply engine",
        "mission": "Maintain enough final-eligible Shorts that every publish window has a strong option.",
        "unlock": "Six operationally publish-ready Shorts, at least one dry-run eligible Short, and twenty pending stories.",
        "revenue_job": "Turn production from lucky shots into repeatable inventory.",
    },
    {
        "number": 3,
        "name": "Retention packaging",
        "mission": "Make the opening frame and first sentence clear enough that strangers keep watching.",
        "unlock": "Stayed-to-watch rate at 40% or higher and average view percentage at 62% or higher.",
        "revenue_job": "Convert reach into watch time and proof that the format works.",
    },
    {
        "number": 4,
        "name": "Repeat audience loop",
        "mission": "Turn one-off viewers into people who recognize the channel and come back.",
        "unlock": "Recurring viewer rate reaches 2% and audience comments keep producing usable prompts.",
        "revenue_job": "Build an audience identity instead of isolated viral posts.",
    },
    {
        "number": 5,
        "name": "Free distribution mesh",
        "mission": "Give every winner a free web, search, and cross-post path without paid tools.",
        "unlock": "Search traffic reaches 5% and the free cross-post pack has at least three ready assets.",
        "revenue_job": "Make each successful Short travel farther than the Shorts feed.",
    },
    {
        "number": 6,
        "name": "Monetization runway",
        "mission": "Prove sponsor-safe consistency, subscriber conversion, and a clean operating record.",
        "unlock": "One thousand subscribers and at least 1.5 subscribers gained per thousand views.",
        "revenue_job": "Prepare the channel for platform revenue, sponsorship, and product experiments.",
    },
    {
        "number": 7,
        "name": "Compound scale",
        "mission": "Run the machine with enough quality, cadence, and audience memory to compound.",
        "unlock": "One million views per 28 days, excellent health, and ten publish-ready Shorts in reserve.",
        "revenue_job": "Scale the proven system instead of adding random effort.",
    },
]


BLOCKER_LABELS = {
    "queue_prune:rewrite": "rewrite the held candidate until queue prune clears",
    "packaging:missing_visible_cue": "make the opening visual cue explicit",
    "agency_gate:success_recovery_format_required": "match the recovery format rule",
    "agency_gate:success_recovery_hook_required": "rewrite the recovery hook",
    "youtube_brain:script_length_risk": "tighten the script before render",
    "youtube_brain:subject_not_immediately_clear": "front-load the subject in the opening",
    "publish_score:rewrite": "repair the publish score package",
    "editor_in_chief:cooldown_subject": "pick a fresh subject inside the same lane",
    "agency_gate:category_recovery_rules_not_met": "follow the category recovery rule",
    "publish_blocklist:monetization audit needs review": "clear the monetization review note before publishing",
    "objective_gate:bootstrap_observe_before_scaling": "collect more observed signal before scaling this pattern",
    "objective_gate:observe_before_scaling": "observe this pattern before scaling it",
    "objective_gate:payoff_too_late_for_current_swipe_baseline": "move the payoff earlier",
}


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return default


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _ratio(value: float, target: float) -> float:
    if target <= 0:
        return 0.0
    return max(0.0, min(1.0, value / target))


def _dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _uploaded_count(upload_intents: list[dict]) -> int:
    return sum(
        1
        for row in upload_intents
        if isinstance(row, dict)
        and str(row.get("status") or "").lower() == "uploaded"
        and str(row.get("video_id") or "").strip()
    )


def _blockers(health: dict, dry_run: dict, queue_audit: dict, scale_blueprint: dict) -> list[dict]:
    counts: Counter[str] = Counter()
    queue = _dict(health.get("queue"))
    counts.update({str(key): _int(value) for key, value in _dict(queue.get("held_reasons")).items()})
    counts.update({str(key): _int(value) for key, value in _dict(dry_run.get("objective_reasons")).items()})
    for payload in (dry_run, queue_audit):
        prune = _dict(payload.get("prune_summary"))
        counts.update({str(key): _int(value) for key, value in _dict(prune.get("reasons")).items()})
    for item in _list(scale_blueprint.get("bottlenecks")):
        if isinstance(item, dict):
            counts[f"scale:{item.get('id', 'unknown')}"] += 1
    rows = []
    for key, count in counts.most_common(12):
        rows.append(
            {
                "id": key,
                "count": count,
                "operator_translation": BLOCKER_LABELS.get(key, str(key).replace("_", " ")),
            }
        )
    return rows


def _metrics(
    health: dict,
    dry_run: dict,
    next_shorts: dict,
    queue_audit: dict,
    scale_blueprint: dict,
    comments: dict,
    crosspost_pack: dict,
    upload_intents: list[dict],
) -> dict:
    queue = _dict(health.get("queue"))
    baseline = _dict(scale_blueprint.get("baseline"))
    next_items = _list(next_shorts.get("items"))
    editorial_mix = _dict(next_shorts.get("editorial_mix"))
    editorial_candidates = _list(editorial_mix.get("items"))
    queue_states = _dict(queue_audit.get("states"))
    health_comments = _dict(health.get("comments"))
    health_analytics = _dict(health.get("analytics"))
    subs_gained = _num(baseline.get("subs_per_1000_views"))
    return {
        "health_score": _int(health.get("score")),
        "health_state": str(health.get("state") or "unknown"),
        "pending": _int(queue.get("pending"), _int(queue_audit.get("pending"))),
        "operational_publish_ready": _int(queue.get("publish_ready")),
        "apparent_publish_ready": _int(queue_states.get("publish_ready")),
        "eligible_count": _int(dry_run.get("eligible_count")),
        "scale_ready_count": _int(dry_run.get("scale_ready_count")),
        "next_shorts_count": len(next_items),
        "editorial_candidate_count": len(editorial_candidates),
        "published_count": _uploaded_count(upload_intents),
        "views_28d": _int(baseline.get("views"), _int(health_analytics.get("total_views"))),
        "total_subscribers": _int(baseline.get("total_subscribers")),
        "subs_per_1000_views": round(subs_gained, 3),
        "stayed_to_watch_rate": round(_num(baseline.get("stayed_to_watch_rate")), 4),
        "avg_view_percentage": round(
            _num(baseline.get("avg_view_percentage"), _num(health_analytics.get("avg_view_pct"))),
            3,
        ),
        "recurring_viewer_rate": round(_num(baseline.get("recurring_viewer_rate")), 4),
        "youtube_search_view_rate": round(_num(baseline.get("youtube_search_view_rate")), 4),
        "crosspost_assets": len(_list(crosspost_pack.get("items"))),
        "comments_sampled": _int(comments.get("comments_sampled"), _int(health_comments.get("comments_sampled"))),
    }


def _level_checks(metrics: dict, *, ready_target: int, pending_target: int) -> dict[int, dict]:
    return {
        1: {
            "passed": metrics["published_count"] >= 1 and metrics["health_score"] >= 50,
            "progress": (_ratio(metrics["published_count"], 1) + _ratio(metrics["health_score"], 50)) / 2,
            "evidence": {
                "published_count": metrics["published_count"],
                "health_score": metrics["health_score"],
            },
        },
        2: {
            "passed": (
                metrics["operational_publish_ready"] >= ready_target
                and metrics["eligible_count"] >= 1
                and metrics["pending"] >= pending_target
            ),
            "progress": min(
                1.0,
                (
                    _ratio(metrics["operational_publish_ready"], ready_target)
                    + _ratio(metrics["eligible_count"], 1)
                    + _ratio(metrics["pending"], pending_target)
                )
                / 3,
            ),
            "evidence": {
                "operational_publish_ready": metrics["operational_publish_ready"],
                "eligible_count": metrics["eligible_count"],
                "pending": metrics["pending"],
                "target_publish_ready": ready_target,
                "target_pending": pending_target,
            },
        },
        3: {
            "passed": metrics["stayed_to_watch_rate"] >= 0.4 and metrics["avg_view_percentage"] >= 62,
            "progress": (_ratio(metrics["stayed_to_watch_rate"], 0.4) + _ratio(metrics["avg_view_percentage"], 62)) / 2,
            "evidence": {
                "stayed_to_watch_rate": metrics["stayed_to_watch_rate"],
                "avg_view_percentage": metrics["avg_view_percentage"],
            },
        },
        4: {
            "passed": metrics["recurring_viewer_rate"] >= 0.02 and metrics["comments_sampled"] >= 20,
            "progress": (_ratio(metrics["recurring_viewer_rate"], 0.02) + _ratio(metrics["comments_sampled"], 20)) / 2,
            "evidence": {
                "recurring_viewer_rate": metrics["recurring_viewer_rate"],
                "comments_sampled": metrics["comments_sampled"],
            },
        },
        5: {
            "passed": metrics["youtube_search_view_rate"] >= 0.05 and metrics["crosspost_assets"] >= 3,
            "progress": (_ratio(metrics["youtube_search_view_rate"], 0.05) + _ratio(metrics["crosspost_assets"], 3))
            / 2,
            "evidence": {
                "youtube_search_view_rate": metrics["youtube_search_view_rate"],
                "crosspost_assets": metrics["crosspost_assets"],
            },
        },
        6: {
            "passed": metrics["total_subscribers"] >= 1000 and metrics["subs_per_1000_views"] >= 1.5,
            "progress": (_ratio(metrics["total_subscribers"], 1000) + _ratio(metrics["subs_per_1000_views"], 1.5)) / 2,
            "evidence": {
                "total_subscribers": metrics["total_subscribers"],
                "subs_per_1000_views": metrics["subs_per_1000_views"],
            },
        },
        7: {
            "passed": (
                metrics["views_28d"] >= 1_000_000
                and metrics["health_state"] == "excellent"
                and metrics["operational_publish_ready"] >= 10
            ),
            "progress": min(
                1.0,
                (
                    _ratio(metrics["views_28d"], 1_000_000)
                    + (1 if metrics["health_state"] == "excellent" else 0)
                    + _ratio(metrics["operational_publish_ready"], 10)
                )
                / 3,
            ),
            "evidence": {
                "views_28d": metrics["views_28d"],
                "health_state": metrics["health_state"],
                "operational_publish_ready": metrics["operational_publish_ready"],
            },
        },
    }


def _current_level(level_checks: dict[int, dict]) -> dict:
    for level in LEVELS:
        check = level_checks[level["number"]]
        if not check["passed"]:
            return {**level, "status": "boss_fight", "progress_pct": round(check["progress"] * 100, 1)}
    final = LEVELS[-1]
    return {**final, "status": "cleared", "progress_pct": 100.0}


def _boss(current: dict, metrics: dict, blockers: list[dict], *, ready_target: int, pending_target: int) -> dict:
    number = current["number"]
    if number == 1:
        return {
            "id": "launch_proof_missing",
            "label": "Launch proof is incomplete",
            "severity": "high",
            "evidence": {
                "published_count": metrics["published_count"],
                "health_score": metrics["health_score"],
            },
        }
    if number == 2:
        if metrics["eligible_count"] < 1:
            boss_id = "final_publish_supply_empty"
            label = "No candidate clears the final publish gate"
        elif metrics["operational_publish_ready"] < ready_target:
            boss_id = "publish_ready_reserve_low"
            label = "Publish-ready reserve is below target"
        else:
            boss_id = "pending_queue_low"
            label = "Pending queue is below target"
        return {
            "id": boss_id,
            "label": label,
            "severity": "critical",
            "evidence": {
                "eligible_count": metrics["eligible_count"],
                "operational_publish_ready": metrics["operational_publish_ready"],
                "apparent_publish_ready": metrics["apparent_publish_ready"],
                "pending": metrics["pending"],
                "target_publish_ready": ready_target,
                "target_pending": pending_target,
                "top_blockers": blockers[:5],
            },
        }
    if number == 3:
        return {
            "id": "opening_retention_gap",
            "label": "Opening retention is below scale floor",
            "severity": "critical",
            "evidence": {
                "stayed_to_watch_rate": metrics["stayed_to_watch_rate"],
                "avg_view_percentage": metrics["avg_view_percentage"],
                "top_blockers": blockers[:5],
            },
        }
    if number == 4:
        return {
            "id": "repeat_audience_gap",
            "label": "Viewers are not returning often enough",
            "severity": "high",
            "evidence": {
                "recurring_viewer_rate": metrics["recurring_viewer_rate"],
                "comments_sampled": metrics["comments_sampled"],
            },
        }
    if number == 5:
        return {
            "id": "distribution_mesh_gap",
            "label": "Winners do not have enough free off-feed paths",
            "severity": "medium",
            "evidence": {
                "youtube_search_view_rate": metrics["youtube_search_view_rate"],
                "crosspost_assets": metrics["crosspost_assets"],
            },
        }
    if number == 6:
        return {
            "id": "monetization_runway_gap",
            "label": "Subscriber and conversion proof are not strong enough yet",
            "severity": "high",
            "evidence": {
                "total_subscribers": metrics["total_subscribers"],
                "subs_per_1000_views": metrics["subs_per_1000_views"],
            },
        }
    return {
        "id": "compound_scale_gap",
        "label": "Scale metrics are below the final game target",
        "severity": "high",
        "evidence": {
            "views_28d": metrics["views_28d"],
            "health_state": metrics["health_state"],
            "operational_publish_ready": metrics["operational_publish_ready"],
        },
    }


def _next_upgrade(current: dict, boss: dict, metrics: dict, blockers: list[dict]) -> dict:
    number = current["number"]
    if number == 2:
        return {
            "id": "repair_final_publish_supply",
            "title": "Turn held strong candidates into final-eligible reserve",
            "why": "The automation can publish safely, but the final gate has zero eligible candidates.",
            "success_gate": "eligible_count >= 1, operational_publish_ready >= 6, pending >= 20",
            "free_only": True,
            "primary_files": [
                "_data/automation_health.json",
                "_data/dry_run_publish.json",
                "_data/queue_audit.json",
            ],
        }
    if number == 3:
        return {
            "id": "raise_opening_retention",
            "title": "Make every opening instantly legible",
            "why": "The channel needs stronger first-second clarity before volume compounds.",
            "success_gate": "stayed_to_watch_rate >= 0.40 and avg_view_percentage >= 62",
            "free_only": True,
            "primary_files": ["_data/scale_blueprint.json", "_data/opening_audit_report.json"],
        }
    if number == 4:
        return {
            "id": "build_returning_viewer_loop",
            "title": "Convert comments and sequels into audience memory",
            "why": "Reach becomes a business only after viewers know why to come back.",
            "success_gate": "recurring_viewer_rate >= 0.02 and comments_sampled >= 20",
            "free_only": True,
            "primary_files": ["_data/session_graph.json", "_data/comment_to_short_candidates.json"],
        }
    if number == 5:
        return {
            "id": "expand_free_distribution",
            "title": "Give winners search and cross-post paths",
            "why": "Free distribution reduces dependence on one feed algorithm.",
            "success_gate": "youtube_search_view_rate >= 0.05 and crosspost_assets >= 3",
            "free_only": True,
            "primary_files": ["_data/crosspost_pack.json", "_data/seo_metadata_lint.json"],
        }
    if number == 6:
        return {
            "id": "prove_monetization_runway",
            "title": "Grow subscriber conversion and brand-safe proof",
            "why": "Revenue needs repeatable trust, not just a spike.",
            "success_gate": "total_subscribers >= 1000 and subs_per_1000_views >= 1.5",
            "free_only": True,
            "primary_files": ["_data/channel_success.json", "_data/security_manifest.json"],
        }
    if number == 7:
        return {
            "id": "compound_scale_machine",
            "title": "Scale only the proven machine",
            "why": "The last level is about compounding quality, not adding random output.",
            "success_gate": "views_28d >= 1000000, health_state == excellent, operational_publish_ready >= 10",
            "free_only": True,
            "primary_files": ["_data/scale_blueprint.json", "_data/automation_health.json"],
        }
    return {
        "id": "prove_safe_launch",
        "title": "Get the safe launch proof on record",
        "why": "The business starts with reliable publishing.",
        "success_gate": "published_count >= 1 and health_score >= 60",
        "free_only": True,
        "primary_files": ["_data/upload_intents.jsonl", "_data/automation_health.json"],
    }


def _actions(current: dict, boss: dict, metrics: dict, blockers: list[dict], scale_blueprint: dict) -> list[dict]:
    number = current["number"]
    if number == 2:
        top = blockers[:4]
        rows = [
            {
                "priority": "P0",
                "action": "Repair one held high-score story until dry-run eligible_count reaches one.",
                "target": "eligible_count >= 1",
                "why": boss["label"],
            },
            {
                "priority": "P0",
                "action": "Batch-fix the top blocker reasons before fetching a larger queue.",
                "target": ", ".join(item["id"] for item in top[:3]) if top else "held_reasons",
                "why": "Current supply has strong ideas but fails late gates.",
            },
            {
                "priority": "P1",
                "action": "Build the reserve to six operational publish-ready Shorts.",
                "target": f"{metrics['operational_publish_ready']}/{PUBLISH_READY_TARGET}",
                "why": "One upload slot should never depend on one fragile candidate.",
            },
            {
                "priority": "P1",
                "action": "Refresh free discovery only after the current repair batch is clean.",
                "target": f"pending {metrics['pending']}/{PENDING_TARGET}",
                "why": "Bigger inventory helps only when the gate can accept winners.",
            },
        ]
        return rows
    if number == 3:
        commands = _list(scale_blueprint.get("production_commands"))
        return [
            {
                "priority": "P0" if idx == 0 else "P1",
                "action": str(command),
                "target": "retention packaging",
                "why": "The scale blueprint marks this as the active bottleneck.",
            }
            for idx, command in enumerate(commands[:4])
        ] or [
            {
                "priority": "P0",
                "action": "Rewrite every candidate opening around subject, visual cue, and payoff.",
                "target": "stayed_to_watch_rate >= 0.40",
                "why": "Opening clarity is below scale floor.",
            }
        ]
    if number == 4:
        return [
            {
                "priority": "P0",
                "action": "Turn every strong upload into a sequel prompt and pinned audience question.",
                "target": "recurring_viewer_rate >= 0.02",
                "why": "The next level is repeat viewing.",
            },
            {
                "priority": "P1",
                "action": "Promote real viewer questions into the next queue batch.",
                "target": "comments_sampled >= 20",
                "why": "Audience-led ideas make the channel feel alive.",
            },
        ]
    if number == 5:
        return [
            {
                "priority": "P0",
                "action": "Package winners for search metadata and free cross-post captions.",
                "target": "crosspost_assets >= 3",
                "why": "Every winner should have more than one distribution path.",
            },
            {
                "priority": "P1",
                "action": "Turn winner titles into query-shaped descriptions after upload.",
                "target": "youtube_search_view_rate >= 0.05",
                "why": "Search creates a longer tail without ad spend.",
            },
        ]
    if number == 6:
        return [
            {
                "priority": "P0",
                "action": "Keep a clean sponsorship-safe proof trail for every published Short.",
                "target": "brand-safe operating record",
                "why": "Revenue partners buy consistency and trust.",
            },
            {
                "priority": "P1",
                "action": "Place the channel promise after the payoff in every strong Short.",
                "target": "subs_per_1000_views >= 1.5",
                "why": "Subscriber conversion is the runway.",
            },
        ]
    return [
        {
            "priority": "P0",
            "action": "Keep compounding only lanes that clear supply, retention, and return-viewer gates.",
            "target": "compound scale",
            "why": "The final level rewards consistency over novelty.",
        }
    ]


def _level_rows(level_checks: dict[int, dict], current_number: int) -> list[dict]:
    rows = []
    for level in LEVELS:
        number = level["number"]
        check = level_checks[number]
        if check["passed"]:
            status = "cleared"
        elif number == current_number:
            status = "current"
        else:
            status = "locked"
        rows.append(
            {
                **level,
                "status": status,
                "progress_pct": round(check["progress"] * 100, 1),
                "evidence": check["evidence"],
            }
        )
    return rows


def build_level_system(
    *,
    health: dict,
    dry_run: dict,
    next_shorts: dict,
    queue_audit: dict,
    scale_blueprint: dict,
    comments: dict | None = None,
    crosspost_pack: dict | None = None,
    upload_intents: list[dict] | None = None,
    ready_target: int = PUBLISH_READY_TARGET,
    pending_target: int = PENDING_TARGET,
) -> dict:
    comments = comments or {}
    crosspost_pack = crosspost_pack or {}
    upload_intents = upload_intents or []
    metrics = _metrics(
        health=health,
        dry_run=dry_run,
        next_shorts=next_shorts,
        queue_audit=queue_audit,
        scale_blueprint=scale_blueprint,
        comments=comments,
        crosspost_pack=crosspost_pack,
        upload_intents=upload_intents,
    )
    blockers = _blockers(health, dry_run, queue_audit, scale_blueprint)
    checks = _level_checks(metrics, ready_target=ready_target, pending_target=pending_target)
    current = _current_level(checks)
    boss = _boss(current, metrics, blockers, ready_target=ready_target, pending_target=pending_target)
    next_upgrade = _next_upgrade(current, boss, metrics, blockers)
    actions = _actions(current, boss, metrics, blockers, scale_blueprint)
    levels = _level_rows(checks, current["number"])
    cleared = sum(1 for row in levels if row["status"] == "cleared")
    overall_progress = min(100.0, round((cleared + current["progress_pct"] / 100) * 100 / len(LEVELS), 1))
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "free_resources_only",
        "status": "complete" if current.get("status") == "cleared" else "in_progress",
        "overall_progress_pct": overall_progress,
        "current_level": current,
        "boss": boss,
        "next_upgrade": next_upgrade,
        "action_plan": actions,
        "metrics": metrics,
        "top_blockers": blockers,
        "levels": levels,
        "game_loop": {
            "now": actions[0]["action"] if actions else next_upgrade["title"],
            "next": (
                LEVELS[min(current["number"], len(LEVELS) - 1)]["name"]
                if current["number"] < len(LEVELS)
                else "Maintain compound scale"
            ),
            "after_next": (
                LEVELS[min(current["number"] + 1, len(LEVELS) - 1)]["name"]
                if current["number"] + 1 < len(LEVELS)
                else "Defend the final level"
            ),
        },
        "free_resource_policy": {
            "paid_tools_required": False,
            "allowed_resources": [
                "GitHub Actions",
                "GitHub Pages",
                "YouTube Analytics exports",
                "public comments",
                "Pexels free media",
                "local deterministic scripts",
            ],
            "rule": "Spend money only after a free signal proves the next bottleneck is worth scaling.",
        },
        "business_path": [
            {
                "stage": "attention_asset",
                "job": "Publish safely and learn what strangers keep watching.",
            },
            {
                "stage": "audience_identity",
                "job": "Turn winners into recognizable lanes, sequels, and comments.",
            },
            {
                "stage": "sponsor_safe_proof",
                "job": "Keep rights, metadata, and performance evidence clean enough for partners.",
            },
            {
                "stage": "revenue_experiments",
                "job": "Test platform revenue, sponsorship, licensing, and product ideas only after repeat demand appears.",
            },
        ],
        "data_contract": {
            "requires": [
                "_data/automation_health.json",
                "_data/dry_run_publish.json",
                "_data/next_shorts.json",
                "_data/queue_audit.json",
                "_data/scale_blueprint.json",
            ],
            "writes": "_data/level_system.json",
        },
    }
