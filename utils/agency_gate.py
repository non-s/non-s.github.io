"""Publish gate for agency-level production controls."""
from __future__ import annotations

import json
from pathlib import Path

from utils.retention_surgeon import diagnose
from utils.story_intelligence import classify_format

REWRITE_QUEUE = Path("_data/retention_rewrite_queue.json")
CATEGORY_RECOVERY = Path("_data/category_recovery.json")


def _safe_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def load_rewrite_ids(path: Path | None = None) -> set[str]:
    payload = _safe_json(path or REWRITE_QUEUE)
    return {
        str(item.get("id") or "")
        for item in (payload.get("items") or [])
        if str(item.get("id") or "")
    }


def load_recovery_plans(path: Path | None = None) -> dict[str, dict]:
    payload = _safe_json(path or CATEGORY_RECOVERY)
    out = {}
    for item in payload.get("plans") or []:
        category = str(item.get("category") or "").lower()
        if category:
            out[category] = item
    return out


def recovery_allows(story: dict, plan: dict) -> bool:
    surgery = diagnose(story)
    if surgery.get("verdict") == "rewrite":
        return False
    allowed_formats = set(str(item) for item in (plan.get("allowed_formats") or []))
    story_format = str(story.get("story_format") or classify_format(
        f"{story.get('title', '')} {story.get('hook', '')} {story.get('script', '')}"
    ))
    if allowed_formats and story_format not in allowed_formats:
        return False
    words = len(str(story.get("script") or "").split())
    if words > 95:
        return False
    hook_style = (story.get("experiments") or {}).get("hook_style")
    return hook_style in {"outcome_first", ""} or bool(story.get("remake_of"))


def evaluate_story(story: dict,
                   rewrite_ids: set[str] | None = None,
                   recovery_plans: dict[str, dict] | None = None) -> dict:
    rewrite_ids = rewrite_ids if rewrite_ids is not None else load_rewrite_ids()
    recovery_plans = recovery_plans if recovery_plans is not None else load_recovery_plans()
    story_id = str(story.get("id") or story.get("_queue_id") or "")
    reasons: list[str] = []
    if story_id in rewrite_ids:
        reasons.append("retention_rewrite_required")
    category = str(story.get("category") or "").lower()
    if category in recovery_plans and not recovery_allows(story, recovery_plans[category]):
        reasons.append("category_recovery_rules_not_met")
    approved = not reasons
    return {
        "approved": approved,
        "reasons": reasons,
        "state": "approved" if approved else "held",
    }


def filter_candidates(candidates: list[dict],
                      rewrite_ids: set[str] | None = None,
                      recovery_plans: dict[str, dict] | None = None) -> tuple[list[dict], list[dict]]:
    rewrite_ids = rewrite_ids if rewrite_ids is not None else load_rewrite_ids()
    recovery_plans = recovery_plans if recovery_plans is not None else load_recovery_plans()
    approved = []
    held = []
    for story in candidates:
        verdict = evaluate_story(story, rewrite_ids, recovery_plans)
        item = dict(story)
        item["agency_gate"] = verdict
        if verdict["approved"]:
            approved.append(item)
        else:
            held.append(item)
    return approved, held
