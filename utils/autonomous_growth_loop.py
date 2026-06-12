"""Closed-loop autonomy for Wild Brief production.

The loop turns the channel's current analytics into queue-level decisions:
what to exploit, what to test, what to recover, and which pending Shorts
should be attempted first.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from utils.experiments import axis_names, variant_choices
from utils.packaging import package_story
from utils.publish_score import score_story
from utils.story_intelligence import classify_format

PLAN_FILE = Path("_data/autonomous_growth_plan.json")
QUEUE_FILE = Path("_data/stories_queue.json")
LATEST_FILE = Path("_data/analytics/latest.json")
EXPERIMENTS_FILE = Path("_data/analytics/experiments.json")
POST24_FILE = Path("_data/post24_review.json")
SEQUENCE_FILE = Path("_data/sequence_plan.json")
COMMENTS_FILE = Path("_data/analytics/comments.json")


def _safe_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _num(value, default: float = 0.0) -> float:
    try:
        return float(value or default)
    except Exception:
        return default


def _rank_map(mapping: dict, *, limit: int = 5) -> list[dict]:
    rows = [{"name": str(key), "score": round(_num(value), 3)} for key, value in (mapping or {}).items()]
    rows.sort(key=lambda item: item["score"], reverse=True)
    return rows[:limit]


def _normalise(value: float, best: float) -> float:
    if best <= 0:
        return 0.0
    return max(0.0, min(1.0, value / best))


def _tokens(text: str) -> set[str]:
    return {
        token.lower()
        for token in re.findall(r"[A-Za-z][A-Za-z'-]{3,}", text or "")
        if token.lower()
        not in {
            "animal",
            "animals",
            "secret",
            "secrets",
            "their",
            "there",
            "about",
            "while",
            "because",
            "brief",
            "shorts",
            "really",
        }
    }


def _experiment_gaps(experiments: dict) -> list[dict]:
    axis_stats = experiments.get("axis_stats") or {}
    winners = experiments.get("winners") or {}
    gaps = []
    for axis in axis_names():
        stats = axis_stats.get(axis) or {}
        missing = [variant for variant in variant_choices(axis) if int((stats.get(variant) or {}).get("n", 0) or 0) < 8]
        gaps.append(
            {
                "axis": axis,
                "winner": winners.get(axis, ""),
                "needs_samples": missing,
                "state": "winner_locked" if winners.get(axis) else "collecting_signal",
            }
        )
    return gaps


def build_plan(
    *,
    latest: dict | None = None,
    experiments: dict | None = None,
    post24: dict | None = None,
    queue: dict | None = None,
    sequence_plan: dict | None = None,
    comments: dict | None = None,
) -> dict:
    latest = latest or _safe_json(LATEST_FILE)
    experiments = experiments or _safe_json(EXPERIMENTS_FILE)
    post24 = post24 or _safe_json(POST24_FILE)
    queue = queue or _safe_json(QUEUE_FILE)
    sequence_plan = sequence_plan or _safe_json(SEQUENCE_FILE)
    comments = comments or _safe_json(COMMENTS_FILE)

    category_rank = _rank_map(latest.get("category_avg_growth_score") or {})
    format_rank = _rank_map(latest.get("format_avg_growth_score") or {})
    best_category = category_rank[0]["score"] if category_rank else 0.0
    best_format = format_rank[0]["score"] if format_rank else 0.0
    hot_categories = [item["name"] for item in category_rank[:3]]
    slow_categories = [
        item["name"] for item in category_rank[-2:] if best_category and item["score"] < best_category * 0.45
    ]
    hot_formats = [item["name"] for item in format_rank[:3]]
    avg_retention = _num(latest.get("avg_view_pct") or latest.get("avg_view_percentage"))
    subs_per_1000 = (
        int(latest.get("subscribers_gained", 0) or 0) * 1000 / max(1, int(latest.get("total_views", 0) or 0))
    )
    post_counts = post24.get("counts") or {}
    sequence_variants = sequence_plan.get("variants") or []
    visual_learning = (
        latest.get("visual_learning") or (latest.get("production_recommendations") or {}).get("visual_learning") or {}
    )
    visual_winner = str(visual_learning.get("winner") or "")
    requested_animals = [
        str(item).strip().lower() for item in (comments.get("requested_animals") or []) if str(item).strip()
    ][:8]
    top_titles = " ".join(str(item.get("title") or "") for item in latest.get("top_performers") or [])
    winning_terms = sorted(_tokens(top_titles))[:12]

    hypotheses = []
    if hot_categories:
        hypotheses.append(
            {
                "id": "H1_DOUBLE_DOWN_CATEGORY",
                "lane": "proven_category",
                "statement": f"Next Shorts in {', '.join(hot_categories[:2])} should outperform cold topics.",
                "success_metric": "growth_score",
                "target": category_rank[0]["score"],
            }
        )
    if hot_formats:
        hypotheses.append(
            {
                "id": "H2_SCALE_FORMAT",
                "lane": "proven_format",
                "statement": f"{hot_formats[0]} is the strongest current story shape.",
                "success_metric": "avg_view_pct_plus_views_per_hour",
                "target": format_rank[0]["score"],
            }
        )
    if int(post_counts.get("rewrite_hook", 0) or 0):
        hypotheses.append(
            {
                "id": "H3_REWRITE_HOOKS",
                "lane": "rewrite_hook",
                "statement": "High-view/low-retention Shorts need stronger first-sentence outcomes.",
                "success_metric": "view_pct",
                "target": 60,
            }
        )
    if subs_per_1000 < 1.5:
        hypotheses.append(
            {
                "id": "H4_SUBSCRIBER_CONVERSION",
                "lane": "conversion",
                "statement": "A clearer one-line follow CTA should improve subscribers per 1k views.",
                "success_metric": "subs_per_1000_views",
                "target": 1.5,
            }
        )
    if slow_categories:
        hypotheses.append(
            {
                "id": "H5_RECOVER_OR_PAUSE",
                "lane": "recovery",
                "statement": f"{', '.join(slow_categories)} should only run with stronger hooks or remakes.",
                "success_metric": "view_pct",
                "target": 55,
            }
        )
    if sequence_variants:
        hypotheses.append(
            {
                "id": "H6_SEQUENCE_WINNERS",
                "lane": "sequence",
                "statement": "Turn top performers into sourced sequence/remake candidates before cold discovery.",
                "success_metric": "growth_score",
                "target": 180,
            }
        )
    if requested_animals:
        hypotheses.append(
            {
                "id": "H7_AUDIENCE_REQUESTS",
                "lane": "audience_request",
                "statement": "Viewer-requested animals should earn more comments and subscribers when packaging is strong.",
                "success_metric": "comments_plus_subscribers",
                "target": 1.5,
            }
        )
    if visual_winner:
        hypotheses.append(
            {
                "id": "H8_VISUAL_PROFILE",
                "lane": "visual_ctr",
                "statement": f"Favor frame profile {visual_winner} for stronger click and retention signals.",
                "success_metric": "growth_score_plus_retention",
                "target": visual_winner,
            }
        )

    pending = [item for item in queue.get("stories") or [] if isinstance(item, dict) and not item.get("consumed")]
    queue_snapshot = _score_queue(
        pending,
        hot_categories=hot_categories,
        slow_categories=slow_categories,
        hot_formats=hot_formats,
        category_rank=category_rank,
        format_rank=format_rank,
        best_category=best_category,
        best_format=best_format,
        hypotheses=hypotheses,
    )
    mode = "exploit"
    if avg_retention and avg_retention < 55:
        mode = "repair_retention"
    elif not experiments.get("winners"):
        mode = "learn"
    autonomy_score = 55
    autonomy_score += 15 if latest.get("metric_scope") == "youtube_analytics_and_public_statistics" else 5
    autonomy_score += 10 if hot_categories else 0
    autonomy_score += 10 if experiments.get("winners") else 0
    autonomy_score += 10 if queue_snapshot["approved_candidates"] >= 10 else 0
    autonomy_score -= 10 if avg_retention and avg_retention < 52 else 0
    autonomy_score = max(0, min(100, autonomy_score))
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "state": "fully_autonomous" if autonomy_score >= 80 else "autonomous_learning",
        "autonomy_score": autonomy_score,
        "operating_mode": mode,
        "data_status": {
            "metric_scope": latest.get("metric_scope", "unknown"),
            "shorts_tracked": int(latest.get("shorts_tracked", 0) or 0),
            "avg_view_pct": avg_retention,
            "subs_per_1000_views": round(subs_per_1000, 3),
        },
        "category_priorities": category_rank,
        "format_priorities": format_rank,
        "winning_terms": winning_terms,
        "experiment_bank": {
            "winners": experiments.get("winners") or {},
            "gaps": _experiment_gaps(experiments),
            "hypotheses": hypotheses,
        },
        "sequence_bank": {
            "source_winners": int(sequence_plan.get("source_winners", 0) or 0),
            "variant_count": len(sequence_variants),
            "next_variants": [
                {
                    "id": item.get("id", ""),
                    "title": item.get("seo_title") or item.get("title") or "",
                    "variant": item.get("sequence_variant", ""),
                    "category": item.get("category", ""),
                }
                for item in sequence_variants[:8]
                if isinstance(item, dict)
            ],
        },
        "audience_requests": {
            "requested_animals": requested_animals,
            "comment_prompts": [str(item) for item in (comments.get("content_prompts") or [])[:5]],
        },
        "visual_policy": {
            "winner": visual_winner,
            "profiles": (visual_learning.get("profiles") or [])[:8],
            "rule": visual_learning.get("policy") or "Collect visual CTR samples before locking a frame profile.",
        },
        "production_policy": {
            "exploit_percent": 55 if mode == "exploit" else 40,
            "sequence_percent": 25,
            "experiment_percent": 15 if mode != "repair_retention" else 10,
            "recovery_percent": 5 if mode == "repair_retention" else 10,
            "selection_rule": "highest autonomy_priority among non-rejected publish_score candidates",
        },
        "queue": queue_snapshot,
        "decisions": _decisions(mode, hot_categories, hot_formats, slow_categories, experiments),
    }


def _score_queue(
    pending: list[dict],
    *,
    hot_categories: list[str],
    slow_categories: list[str],
    hot_formats: list[str],
    category_rank: list[dict],
    format_rank: list[dict],
    best_category: float,
    best_format: float,
    hypotheses: list[dict],
) -> dict:
    category_scores = {item["name"]: item["score"] for item in category_rank}
    format_scores = {item["name"]: item["score"] for item in format_rank}
    hypothesis_by_lane = {item["lane"]: item["id"] for item in hypotheses}
    rows = []
    lane_counts: Counter[str] = Counter()
    for story in pending:
        publish = score_story(story)
        category = str(story.get("category") or "wildlife")
        fmt = str(
            story.get("story_format")
            or classify_format(f"{story.get('title', '')} {story.get('hook', '')} {story.get('script', '')}")
        )
        if story.get("sequel_of") or story.get("remake_of"):
            lane = "sequence"
        elif category in slow_categories:
            lane = "recovery"
        elif category in hot_categories or fmt in hot_formats:
            lane = "proven_category"
        else:
            lane = "fresh_experiment"
        lane_counts[lane] += 1
        lane_bonus = {
            "sequence": 13,
            "proven_category": 10,
            "fresh_experiment": 3,
            "recovery": -6,
        }.get(lane, 0)
        priority = publish["score"] + lane_bonus
        priority += 12 * _normalise(category_scores.get(category, 0.0), best_category)
        priority += 8 * _normalise(format_scores.get(fmt, 0.0), best_format)
        priority = round(max(0, min(140, priority)), 2)
        rows.append(
            {
                "id": story.get("id", ""),
                "title": story.get("seo_title") or story.get("title") or "",
                "category": category,
                "story_format": fmt,
                "lane": lane,
                "hypothesis_id": hypothesis_by_lane.get(lane, hypothesis_by_lane.get("proven_category", "")),
                "publish_score": publish,
                "autonomy_priority": priority,
                "packaging_lab": _packaging_lab(story),
            }
        )
    rows.sort(key=lambda item: item["autonomy_priority"], reverse=True)
    return {
        "pending": len(pending),
        "approved_candidates": sum(1 for row in rows if row["publish_score"]["state"] != "reject"),
        "lane_counts": dict(sorted(lane_counts.items())),
        "top_candidates": rows[:30],
    }


def _decisions(
    mode: str, hot_categories: list[str], hot_formats: list[str], slow_categories: list[str], experiments: dict
) -> list[str]:
    decisions = []
    if hot_categories:
        decisions.append("Prioritize categories: " + ", ".join(hot_categories[:3]) + ".")
    if hot_formats:
        decisions.append("Use formats first: " + ", ".join(hot_formats[:3]) + ".")
    if slow_categories:
        decisions.append("Keep weak categories in recovery mode: " + ", ".join(slow_categories) + ".")
    if experiments.get("winners"):
        winners = experiments.get("winners") or {}
        decisions.append(
            "Bias production toward experiment winners: " + ", ".join(f"{k}={v}" for k, v in winners.items()) + "."
        )
    else:
        decisions.append("No statistically locked experiment winners yet; reserve traffic for structured learning.")
    decisions.append(f"Current operating mode: {mode}.")
    return decisions


def _packaging_lab(story: dict) -> dict:
    packaged = package_story(story)
    packaging = packaged.get("packaging") or {}
    titles = [str(item) for item in packaging.get("title_options") or [] if str(item).strip()]
    thumbs = [str(item) for item in packaging.get("thumbnail_options") or [] if str(item).strip()]
    hook = str(packaged.get("hook") or story.get("hook") or "").strip()
    hook_variants = [
        hook,
        str(packaged.get("seo_title") or packaged.get("title") or "").strip(),
        str(packaging.get("pinned_comment") or "").split("?")[0].strip(),
    ]
    clean_hooks = []
    seen = set()
    for item in hook_variants:
        clean = " ".join(item.split())[:110]
        key = clean.lower()
        if clean and key not in seen:
            clean_hooks.append(clean)
            seen.add(key)
    return {
        "title_variants": titles[:3],
        "thumbnail_variants": thumbs[:3],
        "hook_variants": clean_hooks[:3],
        "pinned_comment": packaging.get("pinned_comment", ""),
        "test_rule": "Try the first variant now; keep the other two as measured rewrite options if 24h retention misses target.",
    }


def apply_plan_to_queue(queue: dict, plan: dict, *, limit: int = 80) -> tuple[dict, int]:
    top = {str(item.get("id")): item for item in (plan.get("queue") or {}).get("top_candidates") or []}
    if not top:
        return queue, 0
    changed = 0
    stories = []
    for story in queue.get("stories") or []:
        if not isinstance(story, dict):
            stories.append(story)
            continue
        item = top.get(str(story.get("id")))
        if not item:
            stories.append(story)
            continue
        annotation = {
            "priority": item["autonomy_priority"],
            "lane": item["lane"],
            "hypothesis_id": item.get("hypothesis_id", ""),
            "publish_score": item["publish_score"]["score"],
            "state": item["publish_score"]["state"],
            "packaging_lab": item.get("packaging_lab") or {},
            "updated_at": plan.get("generated_at", ""),
        }
        if story.get("autonomy") != annotation:
            story = dict(story)
            story["autonomy"] = annotation
            changed += 1
        stories.append(story)
        if changed >= limit:
            stories.extend(queue.get("stories", [])[len(stories) :])
            break
    updated = dict(queue)
    updated["stories"] = stories
    updated["updated_at"] = datetime.now(timezone.utc).isoformat()
    return updated, changed


def _annotation_count(queue: dict) -> int:
    return sum(
        1
        for story in queue.get("stories") or []
        if isinstance(story, dict) and not story.get("consumed") and story.get("autonomy")
    )


def write_plan(path: Path = PLAN_FILE, *, update_queue: bool = True) -> dict:
    queue = _safe_json(QUEUE_FILE)
    plan = build_plan(queue=queue)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    if update_queue and queue:
        updated, changed = apply_plan_to_queue(queue, plan)
        if changed:
            QUEUE_FILE.write_text(json.dumps(updated, indent=2, ensure_ascii=False), encoding="utf-8")
        plan["queue_annotations_written"] = _annotation_count(updated)
        plan["queue_annotations_changed"] = changed
        path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    return plan
