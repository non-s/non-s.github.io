"""World-class package rulebook for Wild Brief Shorts.

This module is intentionally additive. It does not replace the existing
editorial gate in ``utils.editorial``; it gives the pipeline one compact
scorecard for first-second packaging, replay potential and freshness.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from utils.first_frame_audit import audit_opening_frames
from utils.opening_retention import score_retention_opening

SPECIFIC_TERMS = {
    "before",
    "after",
    "seconds",
    "skin",
    "eyes",
    "body",
    "tail",
    "teeth",
    "wing",
    "wings",
    "color",
    "heat",
    "sound",
    "memory",
    "signal",
    "track",
    "attack",
    "escape",
    "fake",
    "changes",
    "hides",
    "warns",
    "learns",
}

GENERIC_HOOKS = {
    "amazing",
    "incredible",
    "unbelievable",
    "crazy",
    "shocking",
    "mind-blowing",
    "you wont believe",
    "you won't believe",
}

CATEGORY_FORMAT = {
    "ocean": "mechanism_reveal",
    "plants": "hidden_network",
    "fungi": "hidden_network",
    "geology": "earth_engine",
    "weather": "natural_phenomenon",
    "cats": "behavior_reveal",
    "dogs": "behavior_reveal",
    "farm": "behavior_reveal",
}


def _clean_text(value: object) -> str:
    return " ".join(str(value or "").replace("_", " ").split())


def _words(value: object) -> list[str]:
    return re.findall(r"[a-z0-9][a-z0-9'-]*", _clean_text(value).lower())


def _word_count(value: object) -> int:
    return len(_words(value))


def _to_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _similarity(left: str, right: str) -> float:
    left_clean = _clean_text(left).lower()
    right_clean = _clean_text(right).lower()
    if not left_clean or not right_clean:
        return 0.0
    return SequenceMatcher(None, left_clean, right_clean).ratio()


def _specificity(text: str) -> float:
    words = _words(text)
    if not words:
        return 0.0
    score = 0.0
    if any(any(char.isdigit() for char in word) for word in words):
        score += 0.24
    if set(words) & SPECIFIC_TERMS:
        score += 0.34
    if len(words) <= 11:
        score += 0.18
    if words and words[0] not in {"this", "that", "it", "they", "something"}:
        score += 0.14
    if any(term in " ".join(words) for term in GENERIC_HOOKS):
        score -= 0.25
    return max(0.0, min(1.0, score))


def _script_concreteness(story: dict, package: dict) -> float:
    text = " ".join(
        [
            _clean_text(story.get("script")),
            _clean_text(story.get("hook")),
            _clean_text(package.get("first_2s_narration")),
        ]
    )
    words = _words(text)
    if not words:
        return 0.0
    concrete_hits = sum(1 for word in words if word in SPECIFIC_TERMS or any(char.isdigit() for char in word))
    density = concrete_hits / max(len(words), 1)
    if re.search(r"\b(because|so|that is why|which means|right before)\b", text.lower()):
        density += 0.18
    return max(0.0, min(1.0, density * 4.0))


def _recent_overlap(hook: str, context: dict) -> float:
    recent = list(context.get("recent_hooks") or []) + list(context.get("recent_titles") or [])
    if not recent:
        return 0.0
    return max((_similarity(hook, str(item)) for item in recent), default=0.0)


def _subject_is_fresh(story: dict, context: dict) -> bool:
    subject = _clean_text(
        story.get("subject") or story.get("topic_hashtag") or story.get("category") or story.get("title")
    ).lower()
    if not subject:
        return True
    recent_subjects = {_clean_text(item).lower() for item in (context.get("recent_subjects") or [])}
    if subject in recent_subjects:
        return False
    ledger = context.get("published_ledger") or []
    for item in ledger:
        if not isinstance(item, dict):
            continue
        past = _clean_text(item.get("subject") or item.get("topic") or item.get("category")).lower()
        if past and _similarity(subject, past) > 0.82:
            return False
    return True


@dataclass
class EditorialRulebook:
    """Evaluate package quality before expensive render/upload work."""

    approval_score: float = 72.0

    def evaluate(self, story: dict, package: dict, context: dict | None = None) -> dict:
        context = context or {}
        package = package or {}
        violations: list[str] = []
        notes: list[str] = []
        score = 50.0

        hook = _clean_text(package.get("hook") or story.get("hook") or story.get("title"))
        first_frame_words = int(
            _to_float(package.get("first_frame_text_words"), _word_count(package.get("first_frame_text")))
        )
        hook_words = int(_to_float(package.get("hook_words"), _word_count(hook)))
        visual_motion = _to_float(package.get("visual_motion_score"), 0.55)
        contrast = _to_float(package.get("contrast_score"), 0.7)
        novelty = _to_float(package.get("novelty_score"), 0.55)
        caption_cps = _to_float(package.get("caption_chars_per_second"), 14.0)
        payoff_time = _to_float(package.get("payoff_time_s"), 14.0)
        loop_score = _to_float(package.get("loop_score"), 0.45)
        cta_count = int(_to_float(package.get("cta_count"), 1.0))

        if first_frame_words <= 4:
            score += 8
        elif first_frame_words <= 5:
            score += 3
            notes.append("first-frame text is at the hard cap")
        else:
            score -= 12
            violations.append("first-frame text exceeds five words")

        if visual_motion >= 0.7:
            score += 10
        elif visual_motion < 0.45:
            score -= 14
            violations.append("opening visual motion is too weak")

        hook_specificity = _to_float(package.get("hook_specificity"), _specificity(hook))
        if hook_specificity >= 0.68:
            score += 12
        elif hook_specificity < 0.45:
            score -= 12
            violations.append("hook is not specific enough")

        if hook_words <= 9:
            score += 7
        elif hook_words > 11:
            score -= 8
            violations.append("hook is too long for the swipe window")

        concreteness = _script_concreteness(story, package)
        if concreteness >= 0.5:
            score += 8
        else:
            score -= 8
            violations.append("script does not expose enough concrete visual detail")

        if payoff_time <= 12:
            score += 7
        elif payoff_time > 18:
            score -= 8
            violations.append("payoff arrives too late")

        if loop_score >= 0.65:
            score += 8
        elif loop_score < 0.3:
            score -= 6
            notes.append("loop callback is weak")

        if cta_count <= 1:
            score += 4
        else:
            score -= 10
            violations.append("CTA burden is too high")

        if caption_cps > 18:
            score -= 7
            violations.append("caption density is too high for mobile viewing")
        if contrast < 0.6:
            score -= 7
            violations.append("opening text contrast is too low")
        if novelty < 0.35:
            score -= 6
            notes.append("topic novelty is low")

        opening_audit = package.get("opening_audit") or story.get("opening_audit") or {}
        if not opening_audit:
            opening_audit = audit_opening_frames(
                {
                    "thumbnail_text": package.get("first_frame_text") or story.get("thumbnail_text"),
                    "title": story.get("title"),
                    "has_broll": visual_motion >= 0.45,
                    "opening_contrast": contrast * 100,
                }
            )
        opening_score = _to_float(opening_audit.get("score"), 75)
        if opening_score >= 82:
            score += 4
        elif opening_score < 60:
            score -= 10
            violations.append("opening audit score is too low")
        elif opening_score < 72:
            score -= 4
            notes.append("opening audit is below target")

        opening_retention = package.get("opening_retention") or story.get("opening_retention") or {}
        if not opening_retention:
            opening_retention = score_retention_opening(
                {
                    **story,
                    "first_frame_text": package.get("first_frame_text") or story.get("thumbnail_text"),
                    "first_2s_narration": package.get("first_2s_narration") or "",
                }
            )
        opening_retention_score = _to_float(opening_retention.get("score"), 72)
        if opening_retention_score >= 82:
            score += 5
        elif opening_retention_score < 64:
            score -= 12
            violations.append("opening promise is not concrete enough")
        elif opening_retention_score < 74:
            score -= 5
            notes.append("opening promise needs a clearer visual bridge")

        overlap = _recent_overlap(hook, context)
        if overlap > 0.52:
            score -= 12
            violations.append("hook overlaps too closely with recent uploads")
        elif overlap > 0.4:
            notes.append("hook may be too close to a recent angle")

        if not _subject_is_fresh(story, context):
            score -= 12
            violations.append("topic is inside the freshness cooldown")

        score = max(0.0, min(100.0, score))
        category = _clean_text(story.get("category")).lower()
        recommended_format = _clean_text(story.get("story_format")) or CATEGORY_FORMAT.get(category, "mechanism_reveal")
        recommended_duration = 24 if payoff_time > 15 or concreteness >= 0.65 else 18
        hard_blocks = [item for item in violations if item not in {"loop callback is weak"}]
        return {
            "approved": score >= self.approval_score and not hard_blocks,
            "score": round(score, 2),
            "violations": violations,
            "notes": notes,
            "recommended_format": recommended_format,
            "recommended_duration_s": recommended_duration,
        }


def evaluate_story_package(story: dict, package: dict, context: dict | None = None) -> dict:
    """Convenience wrapper for callers that do not need a custom rulebook."""
    return EditorialRulebook().evaluate(story, package, context)
