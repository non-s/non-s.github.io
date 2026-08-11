"""Human-centred, non-manipulative attention review for Pata Jazz assets."""

from __future__ import annotations

from utils.seo_keywords import has_unsupported_outcome_claim

_MANIPULATIVE_PATTERNS = ("you won't believe", "shocking", "must watch", "urgent", "secret trick")


def assess_viewer_experience(
    *, title: str, description: str, story_card: dict[str, str], visual: dict
) -> dict[str, object]:
    """Return review signals that favor clarity, trust, agency and wellbeing.

    This is a quality prompt, not a psychological diagnosis or a score for
    maximizing compulsive viewing.
    """
    flags: list[str] = []
    recommendations: list[str] = []
    thumbnail = visual.get("thumbnail", {}) if isinstance(visual, dict) else {}
    lowered = f"{title} {description}".lower()
    clarity = 1.0
    if thumbnail:
        brightness = float(thumbnail.get("brightness", 128))
        contrast = float(thumbnail.get("contrast", 40))
        if not 35 <= brightness <= 225:
            clarity -= 0.2
            flags.append("review thumbnail brightness for feed clarity")
        if contrast < 18:
            clarity -= 0.2
            flags.append("review thumbnail contrast for immediate readability")
    if any(pattern in lowered for pattern in _MANIPULATIVE_PATTERNS):
        clarity -= 0.4
        flags.append("reject manipulative or misleading framing")
    if has_unsupported_outcome_claim(lowered):
        clarity = 0.0
        flags.append("reject unsupported wellbeing claim")
    participation = 1.0 if story_card.get("community_prompt") else 0.0
    if not participation:
        recommendations.append("add one optional, specific community question")
    if not story_card.get("visual_direction"):
        recommendations.append("define a visual direction before production")
    return {
        "principles": ["clarity", "honest curiosity", "viewer agency", "emotional safety"],
        "clarity_score": round(max(clarity, 0.0), 2),
        "participation_ready": bool(participation),
        "flags": flags,
        "recommendations": recommendations,
        "publication_rule": "review flags; never optimize for compulsive viewing",
    }
