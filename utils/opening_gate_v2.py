"""Second-generation opening quality gate for the first 1.5 seconds."""

from __future__ import annotations

import os
import re
from typing import Any, Iterable, Mapping

from utils.first_frame_audit import (
    check_contrast_heuristic,
    check_cover_text_budget,
    check_text_safe_zone,
    score_motion_first_1s,
)
from utils.opening_retention import score_retention_opening

CURIOSITY_TERMS = {
    "because",
    "before",
    "hidden",
    "impossible",
    "secret",
    "seconds",
    "survives",
    "trick",
    "why",
}


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _words(text: object) -> list[str]:
    return re.findall(r"[A-Za-z0-9']+", str(text or ""))


def _mode(value: str | None = None, env: Mapping[str, str] | None = None) -> str:
    raw = (value if value is not None else (env or os.environ).get("OPENING_GATE_MODE", "warn")).strip().lower()
    return raw if raw in {"off", "warn", "block"} else "warn"


def _word_start(word: dict) -> float:
    return _num(word.get("start", word.get("start_s", word.get("time", 99))), 99)


def _first_word_timing(transcript_words: Iterable[dict] | None, hook: str) -> dict:
    starts = sorted(_word_start(word) for word in transcript_words or [] if isinstance(word, dict))
    first = starts[0] if starts else None
    if first is None:
        score = 78.0 if hook else 58.0
        reason = "timing_inferred_from_hook"
    elif first <= 0.7:
        score = 100.0
        reason = "first_word_inside_0_7s"
    elif first <= 1.5:
        score = 84.0
        reason = "first_word_inside_1_5s"
    else:
        score = max(20, 74 - (first - 1.5) * 28)
        reason = "first_word_late"
    return {"score": round(score, 2), "first_word_start_s": first, "reason": reason}


def _curiosity_score(metadata: dict) -> dict:
    hook = str(metadata.get("hook") or metadata.get("title") or metadata.get("thumbnail_text") or "")
    words = _words(hook)
    lower = {word.lower() for word in words}
    specificity = min(22, len([w for w in words if len(w) >= 5]) * 4)
    trigger_bonus = 18 if lower & CURIOSITY_TERMS or "?" in hook else 0
    title_bonus = 8 if metadata.get("category") and str(metadata.get("category")).lower() in hook.lower() else 0
    penalty = 18 if len(words) > 14 else (8 if len(words) < 4 else 0)
    score = 58 + specificity + trigger_bonus + title_bonus - penalty
    return {
        "score": round(max(0.0, min(100.0, score)), 2),
        "word_count": len(words),
        "reason": "curiosity_specificity",
    }


def evaluate_opening_gate(
    metadata: dict | None = None,
    *,
    frames: list[dict] | None = None,
    transcript_words: list[dict] | None = None,
    text_boxes: list[dict] | None = None,
    mode: str | None = None,
    min_score: float | None = None,
    env: Mapping[str, str] | None = None,
) -> dict:
    """Return a warn/block verdict for 0.7s and 1.5s opening quality."""
    metadata = metadata or {}
    source_env = env if env is not None else os.environ
    gate_mode = _mode(mode, env)
    threshold = _num(min_score if min_score is not None else source_env.get("OPENING_GATE_MIN_SCORE", "78"), 78)
    if gate_mode == "off":
        return {"enabled": False, "mode": "off", "approved": True, "score": 100, "reasons": ["opening_gate_off"]}

    cover_text = str(metadata.get("thumbnail_text") or metadata.get("cover_text") or metadata.get("title") or "")
    motion = score_motion_first_1s(metadata, frames)
    contrast = check_contrast_heuristic(metadata)
    cover = check_cover_text_budget(cover_text)
    safe_zone = check_text_safe_zone(text_boxes or metadata.get("opening_text_boxes") or [])
    legibility = {
        "score": round(cover["score"] * 0.58 + safe_zone["score"] * 0.42, 2),
        "cover_text": cover,
        "safe_zone": safe_zone,
        "reason": "cover_text_and_safe_zone",
    }
    curiosity = _curiosity_score(metadata)
    retention_opening = score_retention_opening(metadata)
    timing = _first_word_timing(transcript_words, str(metadata.get("hook") or ""))

    score_0_7 = round(
        motion["score"] * 0.35 + contrast["score"] * 0.2 + legibility["score"] * 0.25 + timing["score"] * 0.2, 2
    )
    score_1_5 = round(
        motion["score"] * 0.18
        + contrast["score"] * 0.14
        + legibility["score"] * 0.17
        + curiosity["score"] * 0.18
        + timing["score"] * 0.13
        + retention_opening["score"] * 0.20,
        2,
    )
    score = round(score_0_7 * 0.46 + score_1_5 * 0.54, 2)
    subscores = {
        "motion": motion,
        "contrast": contrast,
        "legibility": legibility,
        "curiosity": curiosity,
        "retention_opening": retention_opening,
        "first_word_timing": timing,
        "score_first_0_7s": score_0_7,
        "score_first_1_5s": score_1_5,
    }
    reasons: list[str] = []
    if score < threshold:
        reasons.append("opening_gate_score_below_threshold")
    if motion["score"] < 55:
        reasons.append("weak_motion_first_second")
    if contrast["score"] < 55:
        reasons.append("low_opening_contrast")
    if legibility["score"] < 65:
        reasons.append("opening_text_legibility_risk")
    if curiosity["score"] < 62:
        reasons.append("opening_curiosity_gap_weak")
    if retention_opening["score"] < 68:
        reasons.append("opening_retention_promise_weak")
    if timing["score"] < 65:
        reasons.append("first_word_after_1_5s")
    approved = not (gate_mode == "block" and reasons)
    return {
        "enabled": True,
        "mode": gate_mode,
        "approved": approved,
        "state": "pass" if not reasons else ("block" if gate_mode == "block" else "warn"),
        "score": score,
        "threshold": threshold,
        "subscores": subscores,
        "reasons": reasons,
    }
