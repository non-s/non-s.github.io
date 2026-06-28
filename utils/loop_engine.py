"""Replay-loop planning for Wild Brief Shorts."""

from __future__ import annotations

import re
from difflib import SequenceMatcher

STOPWORDS = {
    "the",
    "and",
    "for",
    "that",
    "this",
    "with",
    "from",
    "into",
    "your",
    "you",
    "are",
    "was",
    "were",
    "but",
    "not",
    "why",
    "how",
    "what",
}

SUBJECT_CALLBACKS = {
    "animal",
    "animals",
    "nature",
    "forest",
    "forests",
    "tree",
    "trees",
    "fungi",
    "mushroom",
    "mushrooms",
    "geology",
    "weather",
    "earth",
    "systems",
    "wildlife",
}


def _clean(value: object) -> str:
    return " ".join(str(value or "").split())


def _words(value: object) -> list[str]:
    return re.findall(r"[a-z0-9][a-z0-9'-]*", _clean(value).lower())


def _sentences(value: object) -> list[str]:
    text = _clean(value)
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [part.strip() for part in parts if part.strip()]


def strongest_shared_token(opening: str, ending: str) -> str:
    opening_words = [word for word in _words(opening) if word not in STOPWORDS]
    ending_words = [word for word in _words(ending) if word not in STOPWORDS]
    for word in opening_words:
        if word in ending_words:
            return word
    return opening_words[0] if opening_words else (ending_words[0] if ending_words else "cue")


def _callback_tokens(callback: str) -> set[str]:
    return {word for word in _words(callback) if word not in STOPWORDS}


def _normalize_callback(value: object) -> str:
    words = [word for word in _words(value) if word not in STOPWORDS and word not in {"again", "first", "start"}]
    if not words:
        return ""
    return " ".join(words[:3])


def strongest_visible_callback(package: dict, opening: str) -> str:
    """Prefer the concrete first-frame cue over a generic subject callback."""
    opening_words = set(_words(opening))
    candidates = [
        package.get("callback_keyword"),
        package.get("visual_cue"),
        package.get("cue"),
        package.get("first_frame_text"),
        package.get("thumbnail_text"),
        package.get("cover_text"),
    ]
    normalized = [_normalize_callback(candidate) for candidate in candidates]
    normalized = [candidate for candidate in normalized if candidate and candidate != "cue"]
    for candidate in normalized:
        if _callback_tokens(candidate) & opening_words:
            return candidate
    return normalized[0] if normalized else ""


def estimate_loop_strength(opening: str, final_line: str) -> float:
    shared = len((set(_words(opening)) - STOPWORDS) & (set(_words(final_line)) - STOPWORDS))
    similarity = SequenceMatcher(None, _clean(opening).lower(), _clean(final_line).lower()).ratio()
    score = min(1.0, shared * 0.18 + similarity * 0.55)
    if "?" in final_line:
        score += 0.12
    return round(max(0.0, min(1.0, score)), 3)


def _callback_phrase(callback: str) -> str:
    callback = _clean(callback or "cue").lower()
    if callback in SUBJECT_CALLBACKS:
        return "first clue"
    return callback or "first clue"


def _sense_verb(phrase: str) -> str:
    lower = str(phrase or "").lower().strip()
    if lower.endswith("s") and lower not in {"first clue", "this"}:
        return "make"
    return "makes"


def rewrite_to_reopen_question(ending: str, callback: str, max_words: int = 13) -> str:
    callback = _callback_phrase(callback)
    line = f"Now the {callback} at the start {_sense_verb(callback)} sense."
    if ending and "?" in ending:
        line = ending
    line = re.sub(r"\?+\.+$", "?", line.strip())
    line = re.sub(r"\.+\?+$", "?", line)
    words = line.split()
    if len(words) > max_words:
        line = " ".join(words[:max_words]).rstrip(".,;:") + "."
    return line


class LoopGenerator:
    """Build lightweight render hints for replay-friendly endings."""

    def plan(self, script: dict, package: dict, context: dict | None = None) -> dict:
        context = context or {}
        package = package or {}
        script_text = _clean(script.get("script") or script.get("text") or package.get("script"))
        sentences = _sentences(script_text)
        opening = _clean(package.get("hook") or script.get("hook") or (sentences[0] if sentences else ""))
        opening_context = _clean(
            " ".join(str(package.get(key) or "") for key in ("first_frame_text", "thumbnail_text", "cover_text"))
            + " "
            + opening
        )
        ending = _clean(package.get("ending") or (sentences[-1] if sentences else opening))
        callback = strongest_shared_token(opening, ending)
        visible_callback = strongest_visible_callback(package, opening_context)
        ending_tokens = set(_words(ending)) - STOPWORDS
        callback_tokens = _callback_tokens(callback)
        visible_tokens = _callback_tokens(visible_callback)
        if visible_callback and (
            (callback_tokens and callback_tokens < visible_tokens and visible_tokens & ending_tokens)
            or callback in SUBJECT_CALLBACKS
            or not (callback_tokens & ending_tokens)
            or estimate_loop_strength(opening_context, ending) < 0.42
        ):
            callback = visible_callback
            callback_tokens = _callback_tokens(callback)
        weak_question = "?" in ending and callback_tokens and not callback_tokens <= ending_tokens
        force_reopen = weak_question or estimate_loop_strength(opening_context, ending) < 0.35
        final_line = rewrite_to_reopen_question(
            "" if force_reopen else ending,
            callback,
            int(context.get("max_final_words") or 13),
        )
        loop_score = estimate_loop_strength(opening_context, final_line)
        opening_tokens = set(_words(opening_context)) - STOPWORDS
        final_tokens = set(_words(final_line)) - STOPWORDS
        if callback_tokens and callback_tokens & opening_tokens and callback_tokens & final_tokens:
            original_callback_bonus = 0.12 if callback_tokens & ending_tokens else 0.0
            loop_score = round(min(1.0, loop_score + 0.18 + original_callback_bonus), 3)
        elif callback in set(_words(opening)) and callback in set(_words(ending)):
            loop_score = round(min(1.0, loop_score + 0.15), 3)
        return {
            "callback_keyword": callback,
            "opening_line": opening,
            "ending_line": ending,
            "final_line": final_line,
            "rewrite_applied": bool(force_reopen),
            "audio_crossfade_ms": 120,
            "subtitle_tail_mode": "carry-forward",
            "loop_score": loop_score,
            "render_hints": {
                "carry_keyword": callback,
                "subtle_audio_tail": True,
                "avoid_hard_stop": True,
            },
        }

    def build_outro_to_intro_bridge(self, plan: dict) -> dict:
        plan = plan or {}
        callback = _clean(plan.get("callback_keyword") or "cue")
        return {
            "callback_keyword": callback,
            "subtitle_tail": _clean(plan.get("final_line") or f"Watch the {callback} again."),
            "audio_crossfade_ms": int(plan.get("audio_crossfade_ms") or 120),
        }

    def apply_render_hints(self, meta: dict, plan: dict) -> dict:
        out = dict(meta or {})
        out["loop_plan"] = dict(plan or {})
        out["loop_score"] = float((plan or {}).get("loop_score") or 0)
        out.setdefault("render_hints", {})
        out["render_hints"].update((plan or {}).get("render_hints") or {})
        return out
