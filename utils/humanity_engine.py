"""Human editorial signal for Wild Brief Shorts.

This module is deliberately local and deterministic. It does not rewrite
scripts or call a paid model; it scores the material we already have so
the automation can prefer stories that feel watched, felt, and edited by
a real host.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from utils.human_voice import score_text

_TENSION_RE = re.compile(
    r"\b(but|then|because|why|so|until|before|after|escape|hide|hunt|"
    r"remember|recognize|protect|freeze|change|vanish|survive)\b",
    re.IGNORECASE,
)
_PAYOFF_RE = re.compile(
    r"\b(that's why|so when|which means|the reason|because|this is why|"
    r"it helps|it lets|it makes|useful for|so they can)\b",
    re.IGNORECASE,
)
_COMMENT_RE = re.compile(
    r"\?\s*$|\b(comments|which animal|would you|have you|ever seen)\b",
    re.IGNORECASE,
)
_BODY_DETAIL_RE = re.compile(
    r"\b(eye|eyes|face|faces|beak|tail|skin|fur|feather|feathers|wing|"
    r"wings|paw|paws|hoof|hooves|claw|claws|teeth|bone|bones|ear|ears|"
    r"nose|whiskers|neck|feet|legs|muscle|muscles|texture|colour|color)\b",
    re.IGNORECASE,
)
_GENERIC_TITLE_RE = re.compile(
    r"\b(amazing|incredible|you won't believe|mind[- ]?blowing|crazy|"
    r"animal fact|did you know)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class HumanityScore:
    score: int
    label: str
    strengths: tuple[str, ...]
    issues: tuple[str, ...]
    rewrite_brief: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


def _word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9']+", text or ""))


def _label(score: int) -> str:
    if score >= 86:
        return "signature"
    if score >= 72:
        return "human"
    if score >= 58:
        return "serviceable"
    return "robotic"


def score_story(story: dict) -> HumanityScore:
    """Score the story as a short human-hosted editorial beat."""
    title = str(story.get("title") or story.get("seo_title") or "")
    hook = str(story.get("hook") or "")
    script = str(story.get("script") or "")
    thumbnail = str(story.get("thumbnail_text") or "")
    voice = score_text(script)

    score = 38 + round(voice.score * 0.35)
    strengths: list[str] = []
    issues: list[str] = []
    rewrite: list[str] = []

    if voice.score >= 76:
        score += 10
        strengths.append("host_voice")
    elif voice.score < 60:
        score -= 8
        issues.append("host_voice_too_flat")
        rewrite.append("Add one tiny host reaction that sounds observed, not hyped.")

    if _TENSION_RE.search(f"{hook} {script}"):
        score += 10
        strengths.append("story_tension")
    else:
        score -= 8
        issues.append("no_story_tension")
        rewrite.append("Create a before/after or problem/payoff beat in one sentence.")

    if _PAYOFF_RE.search(script):
        score += 9
        strengths.append("clear_payoff")
    else:
        score -= 9
        issues.append("missing_payoff")
        rewrite.append("Explain why the fact matters to the animal before the ending.")

    if len(set(m.group(0).lower() for m in _BODY_DETAIL_RE.finditer(script))) >= 2:
        score += 9
        strengths.append("felt_detail")
    else:
        score -= 7
        issues.append("needs_felt_detail")
        rewrite.append("Name two visible body details the viewer can notice on screen.")

    if _COMMENT_RE.search(script):
        score += 5
        strengths.append("soft_comment_prompt")
    else:
        score -= 4
        issues.append("no_soft_comment_prompt")

    hook_words = _word_count(hook)
    if 4 <= hook_words <= 12 and not hook.lower().startswith(("today", "did you know")):
        score += 7
        strengths.append("clean_hook")
    else:
        score -= 8
        issues.append("hook_needs_human_cut")
        rewrite.append("Cut the hook to one direct surprise under twelve words.")

    words = _word_count(script)
    if 42 <= words <= 58:
        score += 7
        strengths.append("shorts_length")
    elif words < 36:
        score -= 9
        issues.append("too_thin")
        rewrite.append("Add one concrete fact before the comment question.")
    else:
        score -= 5
        issues.append("too_long")

    thumb_words = _word_count(thumbnail)
    if 2 <= thumb_words <= 4:
        score += 4
        strengths.append("thumbnail_reads_fast")
    else:
        score -= 4
        issues.append("thumbnail_not_instant")

    if _GENERIC_TITLE_RE.search(title):
        score -= 8
        issues.append("generic_title_shape")
        rewrite.append("Make the title name the animal plus the exact surprise.")

    score = max(0, min(100, score))
    return HumanityScore(
        score=score,
        label=_label(score),
        strengths=tuple(dict.fromkeys(strengths)),
        issues=tuple(dict.fromkeys(issues)),
        rewrite_brief=tuple(dict.fromkeys(rewrite[:4])),
    )
