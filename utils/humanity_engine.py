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
_ANIMAL_RE = re.compile(
    r"\b(bear|bears|bird|birds|cat|cats|chicken|chickens|cow|cows|deer|"
    r"dog|dogs|dolphin|dolphins|duck|ducklings|eagle|elephant|elephants|"
    r"fish|fox|goat|goats|horse|horses|leopard|lion|octopus|owl|owls|"
    r"parrot|parrots|penguin|penguins|shark|sheep|tiger|turtle|whale|wolf)\b",
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


def _sentence(text: str) -> str:
    text = re.sub(r"\s+", " ", (text or "")).strip(" .")
    return text[:1].upper() + text[1:] if text else ""


def _animal_name(story: dict) -> str:
    haystack = " ".join(str(story.get(k) or "") for k in (
        "title", "seo_title", "hook", "script", "description", "category",
    ))
    match = _ANIMAL_RE.search(haystack)
    return match.group(0).lower() if match else "this animal"


def _best_hook(story: dict) -> str:
    hook = _sentence(str(story.get("hook") or ""))
    if 4 <= _word_count(hook) <= 12 and not hook.lower().startswith(("today", "did you know")):
        return hook.rstrip(".!?") + "."
    title = _sentence(str(story.get("title") or story.get("seo_title") or ""))
    if 4 <= _word_count(title) <= 12:
        return title.rstrip(".!?") + "."
    animal = _animal_name(story)
    return f"{animal.capitalize()} have one detail most people miss."


def _details(story: dict) -> tuple[str, str]:
    text = " ".join(str(story.get(k) or "") for k in ("script", "description", "title", "hook"))
    found = list(dict.fromkeys(m.group(0).lower() for m in _BODY_DETAIL_RE.finditer(text)))
    defaults = ["eyes", "body"]
    while len(found) < 2:
        found.append(defaults[len(found)])
    return found[0], found[1]


def _thumbnail_from_hook(hook: str, animal: str) -> str:
    words = [
        w.upper() for w in re.findall(r"[A-Za-z0-9]+", hook)
        if w.lower() not in {"this", "that", "your", "their", "they", "can", "the", "and", "why"}
    ]
    if len(words) >= 2:
        return " ".join(words[:3])
    return f"{animal.upper()} SECRET"[:30]


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
    if (story.get("studio_polish") or {}).get("applied"):
        score = min(score, 84)
    return HumanityScore(
        score=score,
        label=_label(score),
        strengths=tuple(dict.fromkeys(strengths)),
        issues=tuple(dict.fromkeys(issues)),
        rewrite_brief=tuple(dict.fromkeys(rewrite[:4])),
    )


def polish_story(story: dict, *, min_gain: int = 12) -> dict:
    """Return a locally polished story when it clearly improves humanity."""
    original = dict(story)
    before = score_story(original)
    if before.score >= 72:
        return original

    animal = _animal_name(original)
    hook = _best_hook(original)
    detail_one, detail_two = _details(original)
    script = (
        f"{hook} I love this detail: watch the {detail_one} and the {detail_two}. "
        f"Because those tiny cues explain what the {animal} is doing before the big move. "
        f"That's why this clip feels small at first, but gets stranger when you notice it. "
        f"Which animal should we decode next?"
    )
    polished = dict(original)
    polished["hook"] = hook
    polished["script"] = script
    if not str(polished.get("thumbnail_text") or "").strip() or before.score < 58:
        polished["thumbnail_text"] = _thumbnail_from_hook(hook, animal)
    after = score_story(polished)
    if after.score >= 58 and after.score >= before.score + min_gain:
        polished["studio_polish"] = {
            "applied": True,
            "before_score": before.score,
            "after_score": after.score,
            "before_label": before.label,
            "after_label": after.label,
            "original_hook": original.get("hook", ""),
            "original_script": original.get("script", ""),
        }
        return polished
    original["studio_polish"] = {
        "applied": False,
        "before_score": before.score,
        "after_score": after.score,
        "before_label": before.label,
        "after_label": after.label,
    }
    return original
