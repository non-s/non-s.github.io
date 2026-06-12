"""Local monetization-readiness checks for Wild Brief Shorts."""

from __future__ import annotations

import re

_AI_TELLS = re.compile(r"\b(delves?|pivotal|unprecedented|paradigm|realm|journey)\b", re.I)


def audit(meta: dict) -> dict:
    reasons: list[str] = []
    strengths: list[str] = []
    score = 70

    if meta.get("has_broll"):
        score += 8
        strengths.append("transformative_visual_edit")
    else:
        score -= 16
        reasons.append("no motion b-roll")

    if meta.get("has_captions"):
        score += 8
        strengths.append("captioned_original_presentation")
    else:
        score -= 12
        reasons.append("no captions")

    grade = int(meta.get("script_quality_grade", 0) or 0)
    if grade >= 8:
        score += 8
        strengths.append("original_script_quality")
    elif grade < 6:
        score -= 20
        reasons.append("script quality too low")

    humanity = meta.get("humanity") or {}
    if int(humanity.get("score", 0) or 0) >= 72:
        score += 8
        strengths.append("human_host_signal")
    else:
        score -= 10
        reasons.append("weak human host signal")

    if meta.get("source_url") or meta.get("source_license"):
        score += 5
        strengths.append("source_traceable")
    else:
        score -= 8
        reasons.append("source is not traceable")

    text = " ".join(str(meta.get(key) or "") for key in ("title", "description", "hook"))
    if _AI_TELLS.search(text):
        score -= 10
        reasons.append("AI-tell language in public metadata")

    score = max(0, min(100, score))
    approved = score >= 72 and not any(
        reason
        in {
            "no motion b-roll",
            "script quality too low",
            "weak human host signal",
        }
        for reason in reasons
    )
    return {
        "approved": approved,
        "score": score,
        "state": "monetization_ready" if approved else "needs_review",
        "reasons": reasons,
        "strengths": strengths,
    }
