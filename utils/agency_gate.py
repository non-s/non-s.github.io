"""Publish gate for agency-level production controls."""

from __future__ import annotations

import json
import re
from pathlib import Path

from utils.fact_ledger import duplicate_angle_ids
from utils.retention_surgeon import diagnose
from utils.story_intelligence import classify_format
from utils.claim_risk import evaluate_claim_risk
from utils.editorial_guard import editorial_verdict
from utils.rights_audit import audit_rights
from utils.rights_guard import evaluate_rights_guard

REWRITE_QUEUE = Path("_data/retention_rewrite_queue.json")
CATEGORY_RECOVERY = Path("_data/category_recovery.json")
QUEUE_FILE = Path("_data/stories_queue.json")
CHANNEL_SUCCESS = Path("_data/channel_success.json")


def _safe_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def load_rewrite_ids(path: Path | None = None) -> set[str]:
    payload = _safe_json(path or REWRITE_QUEUE)
    return {str(item.get("id") or "") for item in (payload.get("items") or []) if str(item.get("id") or "")}


def load_recovery_plans(path: Path | None = None) -> dict[str, dict]:
    payload = _safe_json(path or CATEGORY_RECOVERY)
    out = {}
    for item in payload.get("plans") or []:
        category = str(item.get("category") or "").lower()
        if category:
            out[category] = item
    return out


def load_duplicate_ids(queue_path: Path | None = None) -> set[str]:
    payload = _safe_json(queue_path or QUEUE_FILE)
    stories = payload.get("stories") or []
    if not isinstance(stories, list):
        return set()
    return duplicate_angle_ids([story for story in stories if isinstance(story, dict)])


def load_success_plan(path: Path | None = None) -> dict:
    return _safe_json(path or CHANNEL_SUCCESS)


def _story_text(story: dict) -> str:
    return " ".join(
        str(story.get(key) or "") for key in ("seo_title", "title", "hook", "script", "thumbnail_text")
    ).lower()


def _has_phrase(text: str, phrase: str) -> bool:
    if not phrase:
        return False
    pattern = r"\b" + re.escape(phrase.lower()) + r"\b"
    return bool(re.search(pattern, text))


def success_allows(story: dict, success_plan: dict) -> tuple[bool, list[str]]:
    """Apply growth-focused channel rules on top of mechanical health gates."""
    if not success_plan:
        return True, []
    reasons: list[str] = []
    text = _story_text(story)
    category = str(story.get("category") or "").lower()
    retention = success_plan.get("retention") or {}
    recovery_categories = {
        str(item.get("category") or "").lower() for item in (retention.get("recovery_categories") or [])
    }
    if category in recovery_categories:
        story_format = str(story.get("story_format") or classify_format(text))
        hook_style = str((story.get("experiments") or {}).get("hook_style") or "")
        if story_format not in {"body_superpower", "animal_memory", "myth_buster"}:
            reasons.append("success_recovery_format_required")
        if hook_style not in {"outcome_first", "curiosity_gap"} and not story.get("remake_of"):
            reasons.append("success_recovery_hook_required")
    for item in retention.get("phrase_pressure") or []:
        phrase = str(item.get("phrase") or "")
        if _has_phrase(text, phrase):
            reasons.append("overused_phrase_pressure")
            break
    script = str(story.get("script") or "")
    if len(script.split()) > 115:
        reasons.append("success_script_too_long")
    if text.count("?") >= 2:
        reasons.append("success_question_overload")
    return not reasons, reasons


def recovery_allows(story: dict, plan: dict) -> bool:
    surgery = diagnose(story)
    if surgery.get("verdict") == "rewrite":
        return False
    allowed_formats = set(str(item) for item in (plan.get("allowed_formats") or []))
    story_format = str(
        story.get("story_format")
        or classify_format(f"{story.get('title', '')} {story.get('hook', '')} {story.get('script', '')}")
    )
    if allowed_formats and story_format not in allowed_formats:
        return False
    words = len(str(story.get("script") or "").split())
    if words > 95:
        return False
    hook_style = (story.get("experiments") or {}).get("hook_style")
    return hook_style in {"outcome_first", ""} or bool(story.get("remake_of"))


def production_allows(story: dict) -> tuple[bool, list[str], dict]:
    """Apply non-negotiable source, fact and copy gates."""
    reasons: list[str] = []
    rights = audit_rights(story)
    rights_guard = evaluate_rights_guard(story)
    claim = evaluate_claim_risk(story)
    editorial = editorial_verdict(story)
    if not rights.get("approved"):
        reasons.extend(f"rights_{reason}" for reason in rights.get("reasons") or [])
    if rights.get("warnings"):
        reasons.extend(f"rights_{warning}" for warning in rights.get("warnings") or [])
    if rights_guard.get("state") != "approved":
        reasons.extend(f"rights_guard_{reason}" for reason in rights_guard.get("reasons") or [])
    elif "missing_source_license" in (rights_guard.get("reasons") or []):
        reasons.append("rights_missing_source_license")
    if claim.get("level") == "block":
        reasons.append("fact_guard_block")
    if not editorial.get("approved"):
        reasons.extend(f"editorial_{issue}" for issue in editorial.get("issues") or [])
    return (
        not reasons,
        sorted(set(reasons)),
        {
            "rights_audit": rights,
            "rights_guard": rights_guard,
            "claim_risk": claim,
            "editorial_guard": editorial,
        },
    )


def evaluate_story(
    story: dict,
    rewrite_ids: set[str] | None = None,
    recovery_plans: dict[str, dict] | None = None,
    duplicate_ids: set[str] | None = None,
    success_plan: dict | None = None,
) -> dict:
    rewrite_ids = rewrite_ids if rewrite_ids is not None else load_rewrite_ids()
    recovery_plans = recovery_plans if recovery_plans is not None else load_recovery_plans()
    duplicate_ids = duplicate_ids if duplicate_ids is not None else load_duplicate_ids()
    success_plan = success_plan if success_plan is not None else load_success_plan()
    story_id = str(story.get("id") or story.get("_queue_id") or "")
    reasons: list[str] = []
    if story_id in rewrite_ids:
        reasons.append("retention_rewrite_required")
    if story_id in duplicate_ids:
        reasons.append("duplicate_angle_rewrite_required")
    category = str(story.get("category") or "").lower()
    if category in recovery_plans and not recovery_allows(story, recovery_plans[category]):
        reasons.append("category_recovery_rules_not_met")
    success_ok, success_reasons = success_allows(story, success_plan)
    if not success_ok:
        reasons.extend(success_reasons)
    production_ok, production_reasons, checks = production_allows(story)
    if not production_ok:
        reasons.extend(production_reasons)
    approved = not reasons
    return {
        "approved": approved,
        "reasons": sorted(set(reasons)),
        "state": "approved" if approved else "held",
        "checks": checks,
    }


def filter_candidates(
    candidates: list[dict],
    rewrite_ids: set[str] | None = None,
    recovery_plans: dict[str, dict] | None = None,
    duplicate_ids: set[str] | None = None,
    success_plan: dict | None = None,
) -> tuple[list[dict], list[dict]]:
    rewrite_ids = rewrite_ids if rewrite_ids is not None else load_rewrite_ids()
    recovery_plans = recovery_plans if recovery_plans is not None else load_recovery_plans()
    duplicate_ids = duplicate_ids if duplicate_ids is not None else load_duplicate_ids()
    success_plan = success_plan if success_plan is not None else load_success_plan()
    approved = []
    held = []
    for story in candidates:
        verdict = evaluate_story(story, rewrite_ids, recovery_plans, duplicate_ids, success_plan)
        item = dict(story)
        item["agency_gate"] = verdict
        if verdict["approved"]:
            approved.append(item)
        else:
            held.append(item)
    return approved, held
