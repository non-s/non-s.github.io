"""Curiosity-gap scoring for Wild Brief hook selection."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher

GENERIC_PHRASES = (
    "amazing",
    "incredible",
    "you won't believe",
    "you wont believe",
    "mind blowing",
    "crazy",
    "shocking",
)
SPECIFIC_DETAIL_WORDS = {
    "seconds",
    "skin",
    "eyes",
    "tail",
    "wing",
    "wings",
    "teeth",
    "heat",
    "sound",
    "signal",
    "body",
    "color",
    "colour",
    "before",
    "after",
    "attack",
    "escape",
    "fake",
    "warn",
    "remember",
    "learn",
    "change",
    "changes",
    "glow",
    "lava",
    "roots",
    "reef",
    "ice",
    "storm",
}
OUTCOME_WORDS = {
    "attacks",
    "escapes",
    "survives",
    "hides",
    "warns",
    "tricks",
    "hunts",
    "protects",
    "moves",
    "changes",
    "remembers",
    "learns",
}


@dataclass(frozen=True)
class HookCandidate:
    hook: str
    source: str = "generated"
    score: float = 0.0
    reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return asdict(self)


def _clean(value: object) -> str:
    return " ".join(str(value or "").split())


def _words(value: object) -> list[str]:
    return re.findall(r"[a-z0-9][a-z0-9'-]*", _clean(value).lower())


def _subject(story: dict) -> str:
    for key in ("subject", "animal", "topic_hashtag", "category"):
        value = _clean(story.get(key)).replace("#", "")
        if value:
            return value.lower()
    title_words = _words(story.get("title"))
    return title_words[0] if title_words else "nature"


def _similarity(left: str, right: str) -> float:
    left_clean = _clean(left).lower()
    right_clean = _clean(right).lower()
    if not left_clean or not right_clean:
        return 0.0
    return SequenceMatcher(None, left_clean, right_clean).ratio()


def _contains_specific_detail(text: str) -> bool:
    words = _words(text)
    return any(any(ch.isdigit() for ch in word) for word in words) or bool(set(words) & SPECIFIC_DETAIL_WORDS)


def _opens_with_subject_or_outcome(text: str, subject: str) -> bool:
    words = _words(text)
    if not words:
        return False
    subject_words = set(_words(subject))
    return bool(subject_words & set(words[:4])) or words[0] in OUTCOME_WORDS


def _implies_unresolved_payoff(text: str) -> bool:
    lower = _clean(text).lower()
    return bool(re.search(r"\b(why|before|right before|because|actually|what looks|until|when)\b", lower))


def _visually_verifiable(story: dict) -> bool:
    return bool(
        story.get("pexels_download_url")
        or story.get("commons_image_url")
        or story.get("source_url")
        or story.get("url")
    )


def _overlap_recent(text: str, recent_hooks: list[str]) -> float:
    return max((_similarity(text, hook) for hook in recent_hooks), default=0.0)


class CuriosityGapEngine:
    """Build and score hook options for the first 1-2 seconds."""

    def build_candidates(self, story: dict, context: dict | None = None) -> list[HookCandidate]:
        context = context or {}
        subject = _subject(story)
        seeds = [
            story.get("hook_seed"),
            story.get("hook"),
            story.get("seo_title"),
            story.get("title"),
        ]
        candidates: list[HookCandidate] = []
        for seed in seeds:
            text = _clean(seed)
            if text:
                candidates.append(HookCandidate(text, source="story"))
        action = _clean(story.get("action") or context.get("action") or "changes")
        cue = _clean(story.get("cue") or context.get("cue") or "body cue")
        outcome = _clean(story.get("outcome") or context.get("outcome") or "the payoff")
        templates = (
            f"This {subject} {action} right before {outcome}.",
            f"Watch the {cue} before this {subject} {action}.",
            f"Why does this {subject} {action} before {outcome}?",
            f"What looks like {cue} is actually the warning.",
        )
        for text in templates:
            candidates.append(HookCandidate(_clean(text), source="template"))
        deduped: dict[str, HookCandidate] = {}
        for candidate in candidates:
            key = candidate.hook.lower()
            deduped.setdefault(key, candidate)
        return list(deduped.values())

    def score_candidate(self, candidate: HookCandidate, story: dict, context: dict | None = None) -> float:
        context = context or {}
        text = _clean(candidate.hook)
        lower = text.lower()
        subject = _subject(story)
        score = 0.0
        if _opens_with_subject_or_outcome(text, subject):
            score += 18
        if _contains_specific_detail(text):
            score += 14
        if _implies_unresolved_payoff(text):
            score += 20
        if _visually_verifiable(story):
            score += 16
        max_hook_words = int(context.get("max_hook_words") or 10)
        if len(_words(text)) <= max_hook_words:
            score += 10
        recent_overlap = _overlap_recent(text, list(context.get("recent_hooks") or []))
        if recent_overlap > 0.45:
            score -= 16
        if any(phrase in lower for phrase in GENERIC_PHRASES):
            score -= 18
        if re.match(r"^(this|that|it)\b", lower) and not (_contains_specific_detail(text) or subject in lower):
            score -= 14
        return max(0.0, min(100.0, round(score, 2)))

    def choose_best(self, candidates: list[HookCandidate]) -> HookCandidate:
        if not candidates:
            return HookCandidate("This nature detail changes the story.", source="fallback", score=0.0)
        return max(candidates, key=lambda item: item.score)

    def choose_for_story(self, story: dict, context: dict | None = None) -> HookCandidate:
        scored = []
        for candidate in self.build_candidates(story, context):
            score = self.score_candidate(candidate, story, context)
            reasons = []
            if _contains_specific_detail(candidate.hook):
                reasons.append("specific_detail")
            if _implies_unresolved_payoff(candidate.hook):
                reasons.append("payoff_gap")
            scored.append(HookCandidate(candidate.hook, candidate.source, score, tuple(reasons)))
        return self.choose_best(scored)
