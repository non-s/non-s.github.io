"""First-second swipe-risk scoring for Shorts packages."""

from __future__ import annotations


def _num(payload: dict, key: str, default: float = 0.0) -> float:
    try:
        return float(payload.get(key, default))
    except Exception:
        return default


class SwipeRiskScore:
    """Estimate how likely the first seconds are to lose the viewer."""

    def score_opening(self, package: dict) -> dict:
        package = package or {}
        risk = 0.0
        reasons: list[str] = []
        fixes: list[str] = []

        if _num(package, "first_frame_text_words") > 5:
            risk += 15
            reasons.append("first_frame_too_wordy")
            fixes.append("Cut first-frame text to 2-4 words.")
        if _num(package, "hook_words") > 11:
            risk += 12
            reasons.append("hook_too_long")
            fixes.append("Make the first sentence 8-11 words.")
        if _num(package, "visual_motion_score", 0.5) < 0.45:
            risk += 20
            reasons.append("low_motion_opening")
            fixes.append("Open on the clearest moving subject cue.")
        if _num(package, "caption_chars_per_second", 14) > 18:
            risk += 12
            reasons.append("caption_density_high")
            fixes.append("Reduce caption density or split the sentence.")
        if _num(package, "contrast_score", 0.7) < 0.60:
            risk += 14
            reasons.append("opening_contrast_low")
            fixes.append("Increase text/background contrast.")
        if _num(package, "hook_specificity", 0.5) < 0.50:
            risk += 18
            reasons.append("hook_not_specific")
            fixes.append("Name one visible body cue, behavior, number or outcome.")
        if _num(package, "novelty_score", 0.5) < 0.35:
            risk += 9
            reasons.append("novelty_low")
            fixes.append("Use a fresher subject or a sharper angle.")
        score = max(0, min(100, int(round(risk))))
        band = "high" if score >= 60 else "medium" if score >= 35 else "low"
        return {
            "score": score,
            "band": band,
            "reasons": reasons,
            "fixes": fixes,
        }

    def explain(self, score_payload: dict) -> list[str]:
        payload = score_payload or {}
        fixes = list(payload.get("fixes") or [])
        if fixes:
            return fixes
        band = payload.get("band") or "low"
        if band == "low":
            return ["Opening is compact enough for the Shorts swipe window."]
        return ["Tighten the first frame, hook and visible motion before rendering."]
