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
        ending = _clean(package.get("ending") or (sentences[-1] if sentences else opening))
        callback = strongest_shared_token(opening, ending)
        final_line = rewrite_to_reopen_question(ending, callback, int(context.get("max_final_words") or 13))
        loop_score = estimate_loop_strength(opening, final_line)
        if callback in set(_words(opening)) and callback in set(_words(ending)):
            loop_score = round(min(1.0, loop_score + 0.15), 3)
        return {
            "callback_keyword": callback,
            "opening_line": opening,
            "ending_line": ending,
            "final_line": final_line,
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
