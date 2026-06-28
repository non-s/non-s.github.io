"""Generate sequel/remake prompts from proven Shorts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from utils.editorial_guard import editorial_issues
from utils.remake_factory import build_remake_story

ANALYTICS_FILE = Path("_data/analytics/latest.json")
SEQUENCES_FILE = Path("_data/sequence_plan.json")
SESSION_SEQUELS_FILE = Path("_data/sequel_candidates.json")
FRESH_UPLOAD_ACTIONS_FILE = Path("_data/fresh_upload_actions.json")

FRESH_ACTION_VARIANTS = {
    "package_rescue": "fresh_upload_package_rescue",
    "hook_iteration": "fresh_upload_hook_rescue",
    "opening_iteration": "fresh_upload_opening_rewrite",
    "package_test": "fresh_upload_package_test",
    "amplify": "fresh_upload_momentum_sequel",
}


def _safe_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _recommendable_title(title: str) -> bool:
    title = str(title or "").strip()
    if not title:
        return False
    return not editorial_issues({"title": title, "seo_title": title}, include_script=False)


def _num(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _fresh_variant_kind(action: dict) -> str:
    lane = str(action.get("lane") or "")
    return FRESH_ACTION_VARIANTS.get(lane, "")


def _fresh_handoff(action: dict) -> dict:
    keys = (
        "id",
        "priority",
        "lane",
        "action_type",
        "video_id",
        "title",
        "category",
        "series",
        "url",
        "state",
        "checkpoint_label",
        "checkpoint_state",
        "age_hours",
        "current_views",
        "target_views",
        "opening_retention_score",
        "recommended_action",
        "why",
        "free_only",
        "manual_approval_required",
    )
    return {key: action.get(key) for key in keys if key in action}


def _fresh_upload_variants(fresh_upload_actions: dict, *, limit: int) -> list[dict]:
    variants = []
    seen_sources: set[str] = set()
    for action in fresh_upload_actions.get("items") or []:
        if len(variants) >= limit:
            break
        if not isinstance(action, dict):
            continue
        kind = _fresh_variant_kind(action)
        if not kind:
            continue
        if not bool(action.get("manual_approval_required")):
            continue
        title = str(action.get("title") or "")
        video_id = str(action.get("video_id") or "")
        if not video_id or video_id in seen_sources or not _recommendable_title(title):
            continue
        story = build_remake_story(
            {
                "source_video_id": video_id,
                "source_title": title,
                "category": action.get("category") or "",
                "views": int(_num(action.get("current_views"))),
                "retention": _num(action.get("opening_retention_score")),
                "growth_score": 0,
                "action": action.get("recommended_action") or action.get("action_type") or kind,
            }
        )
        story["sequence_variant"] = kind
        story["sequence_source"] = "fresh_upload_actions"
        story["fresh_upload_handoff"] = _fresh_handoff(action)
        variants.append(story)
        seen_sources.add(video_id)
    return variants


def build_sequence_plan(
    analytics: dict | None = None,
    *,
    limit: int = 5,
    include_session_handoff: bool | None = None,
    fresh_upload_actions: dict | None = None,
    include_fresh_upload_handoff: bool | None = None,
) -> dict:
    load_from_disk = analytics is None
    include_session_handoff = load_from_disk if include_session_handoff is None else include_session_handoff
    include_fresh_upload_handoff = (
        load_from_disk or fresh_upload_actions is not None
        if include_fresh_upload_handoff is None
        else include_fresh_upload_handoff
    )
    analytics = analytics or _safe_json(ANALYTICS_FILE)
    fresh_upload_actions = fresh_upload_actions or (
        _safe_json(FRESH_UPLOAD_ACTIONS_FILE) if include_fresh_upload_handoff else {}
    )
    winners = []
    for item in analytics.get("top_performers") or []:
        if not _recommendable_title(str(item.get("title") or "")):
            continue
        retention = _num(item.get("view_pct") or item.get("average_view_percentage"))
        growth = _num(item.get("growth_score"))
        views = int(_num(item.get("views")))
        if (retention >= 62 and growth >= 180) or views >= 1200:
            winners.append(item)
    variants = []
    for winner in winners[:limit]:
        base = {
            "source_video_id": winner.get("video_id", ""),
            "source_title": winner.get("title", ""),
            "category": winner.get("category", ""),
            "views": winner.get("views", 0),
            "retention": winner.get("view_pct") or winner.get("average_view_percentage") or 0,
            "growth_score": winner.get("growth_score", 0),
        }
        for kind in ("same_format_new_animal", "same_animal_new_behavior", "same_topic_stronger_hook"):
            story = build_remake_story({**base, "action": kind})
            story["sequence_variant"] = kind
            variants.append(story)
    session_sequels = (_safe_json(SESSION_SEQUELS_FILE).get("items") or []) if include_session_handoff else []
    for item in session_sequels[:limit]:
        if not isinstance(item, dict):
            continue
        story = build_remake_story(
            {
                "source_video_id": item.get("video_id") or item.get("source_video_id", ""),
                "source_title": item.get("title", ""),
                "category": item.get("category", ""),
                "action": item.get("prompt") or "session_graph_sequel",
            }
        )
        story["sequence_variant"] = "session_graph_sequel"
        handoff = dict(item)
        original_title = str(item.get("title") or "")
        clean_title = str((story.get("remake_of") or {}).get("title") or story.get("title") or "")
        if original_title and clean_title and not _recommendable_title(original_title):
            handoff["title"] = clean_title
            prompt = str(handoff.get("prompt") or "")
            handoff["prompt"] = prompt.replace(original_title, clean_title)
        story["session_handoff"] = handoff
        variants.append(story)
    fresh_variants = _fresh_upload_variants(fresh_upload_actions, limit=limit) if include_fresh_upload_handoff else []
    variants.extend(fresh_variants)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_winners": len(winners),
        "fresh_upload_handoffs": len(fresh_variants),
        "variants": variants,
        "commands": [
            "Use one sequence variant per winner before exploring a cold topic.",
            "Do not publish all variants back-to-back; mix with proven farm/birds inventory.",
            "Use fresh-upload handoffs only as review-ready next drafts, not as automatic reuploads.",
        ],
    }


def write_sequence_plan(path: Path = SEQUENCES_FILE) -> dict:
    plan = build_sequence_plan()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    return plan
