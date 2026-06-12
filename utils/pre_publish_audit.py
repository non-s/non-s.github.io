"""Final local go/no-go audit for generated Shorts."""

from __future__ import annotations

import os
import re

MIN_AUDIT_SCORE = int(os.environ.get("WILD_BRIEF_MIN_PREPUBLISH_SCORE", "72"))


def _score_dict(meta: dict, *path: str) -> dict:
    cur = meta
    for key in path:
        cur = cur.get(key) if isinstance(cur, dict) else {}
    return cur if isinstance(cur, dict) else {}


def _words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9']+", text or "")


def audit_package(meta: dict) -> dict:
    """Return a deterministic final publication verdict for one Short.

    This is the last local editor before upload. It deliberately uses
    only metadata the pipeline already has, so it works on GitHub Actions
    without extra services or spend.
    """
    reasons: list[str] = []
    strengths: list[str] = []
    score = 50

    editorial = _score_dict(meta, "editorial")
    if editorial.get("approved"):
        score += 16
        strengths.append("editorial_approved")
    else:
        score -= 30
        reasons.append("editorial review is not approved")
    try:
        editorial_score = int(editorial.get("score", 0) or 0)
    except Exception:
        editorial_score = 0
    if editorial_score >= 80:
        score += 8
        strengths.append("strong_editorial_score")
    elif editorial_score < 62:
        score -= 14
        reasons.append("editorial score is below publish threshold")

    humanity = _score_dict(meta, "humanity") or _score_dict(editorial, "humanity")
    try:
        humanity_score = int(humanity.get("score", 0) or 0)
    except Exception:
        humanity_score = 0
    if humanity_score >= 86:
        score += 10
        strengths.append("signature_humanity")
    elif humanity_score >= 72:
        score += 6
        strengths.append("human_host_signal")
    elif humanity_score < 58:
        score -= 18
        reasons.append("humanity score is too low")

    grade = int(meta.get("script_quality_grade", 0) or 0)
    if grade >= 8:
        score += 8
        strengths.append("clean_script")
    elif grade < 6:
        score -= 18
        reasons.append("script quality grade is too low")

    if meta.get("has_captions"):
        score += 7
        strengths.append("captions_present")
    else:
        score -= 8
        reasons.append("captions are missing")
    if meta.get("has_broll"):
        score += 7
        strengths.append("motion_broll_present")
    else:
        score -= 6
        reasons.append("motion b-roll is missing")
    if not meta.get("has_captions") and not meta.get("has_broll"):
        score -= 12
        reasons.append("retention basics are missing")

    visual = _score_dict(meta, "visual_qa")
    if visual.get("checked") and not visual.get("approved"):
        score -= 40
        reasons.append("visual QA rejected the frame")
    try:
        visual_quality = int(visual.get("thumbnail_quality", 0) or 0)
    except Exception:
        visual_quality = 0
    if visual_quality >= 7:
        score += 5
        strengths.append("strong_visual_preview")
    elif visual.get("checked") and visual_quality < 5:
        score -= 10
        reasons.append("visual preview score is weak")

    hook_words = _words(str(meta.get("hook") or ""))
    if 4 <= len(hook_words) <= 12:
        score += 5
        strengths.append("short_hook")
    else:
        score -= 6
        reasons.append("hook is not in the 4-12 word range")

    title = str(meta.get("title") or "")
    if 35 <= len(title) <= 75:
        score += 4
        strengths.append("searchable_title_length")
    elif len(title) > 95:
        score -= 8
        reasons.append("title is too close to the YouTube limit")

    if _score_dict(meta, "hook_audit").get("approved") is False:
        score -= 8
        reasons.append("hook audit flagged the opening")
    if _score_dict(meta, "title_audit").get("approved") is False:
        score -= 8
        reasons.append("title audit flagged the metadata")
    monetization = _score_dict(meta, "monetization_audit")
    if monetization and monetization.get("approved") is False:
        score -= 18
        reasons.append("monetization audit needs review")

    score = max(0, min(100, score))
    blocking = {
        "editorial review is not approved",
        "editorial score is below publish threshold",
        "humanity score is too low",
        "script quality grade is too low",
        "visual QA rejected the frame",
        "retention basics are missing",
        "monetization audit needs review",
    }
    approved = score >= MIN_AUDIT_SCORE and not any(reason in blocking for reason in reasons)
    state = "publish_ready" if approved else ("hold_review" if score >= 55 else "blocked")
    return {
        "approved": approved,
        "score": score,
        "threshold": MIN_AUDIT_SCORE,
        "state": state,
        "reasons": reasons,
        "strengths": strengths,
    }
