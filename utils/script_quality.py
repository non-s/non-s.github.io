"""
utils/script_quality.py — Pre-flight lint for Shorts scripts.

Why this exists
---------------
YouTube's July 2025 "Inauthentic Content" policy terminated 12M+
channels in 2025 for "mass-produced, repetitive, templated AI
output". Pure narration of wire copy with no editorial transformation
is the kill-shot pattern. Multiple post-mortems converge on the same
diagnosis: the channels didn't validate their own output — they shipped
whatever the LLM produced.

This module is the automated "human-in-the-loop" QA gate. It runs on
the AI-generated script + metadata before any upload and returns:

  * A list of `Issue` records (one per detected problem)
  * A `quality_grade` (0-10) — drops 1-2 points per issue
  * `should_block` — True if the script is so problematic we'd rather
    skip the Short than publish AI slop

Rules are heuristic and conservative. False positives are cheap
(skip a Short and ship the next-best); false negatives are expensive
(channel termination).

The 30-second human review the case studies recommend can layer on
top: the daily digest issue (utils/digest.py) shows every flagged
Short so the operator can spot patterns the lint missed.
"""

from __future__ import annotations

import dataclasses
import re

from utils.human_voice import score_text

# ── Banned phrases ────────────────────────────────────────────────
#
# AI-tell phrases the system prompt already forbids. We re-check the
# OUTPUT to catch the cases where the LLM ignored its instructions.
# Frequency of any single phrase in the published script is a strong
# AI-slop signal that YouTube's classifiers also key on.
_BANNED_PHRASES = [
    r"\bcrucial\b",
    r"\bvital\b",
    r"\bpivotal\b",
    r"\bdelve\b",
    r"\blandscape\b",
    r"\bgame[- ]?changer\b",
    r"\brevolutionary\b",
    r"\bgroundbreaking\b",
    r"\bunderscores the importance\b",
    r"\bsheds light on\b",
    r"\bhighlights the critical role\b",
    r"\bin this article\b",
    r"\bin this report\b",
    r"\bit is worth noting\b",
    r"\bit is important to\b",
    r"\bnavigate the complexities\b",
    r"\bcould reshape\b",
    r"\bparadigm shift\b",
    r"\bunprecedented\b",
    r"\bpaves the way\b",
    r"\bin the realm of\b",
    r"\bin today.s fast[- ]?paced\b",
    r"\ba testament to\b",
    r"\btapestry\b",
    r"\bembark on\b",
    r"\bushering in\b",
    r"\breshape the future\b",
    # Clickbait the SEO prompt also forbids.
    r"\byou won.t believe\b",
    r"\bshocking\b",
    r"\bjaw[- ]?dropping\b",
    r"\bmind[- ]?blowing\b",
]
_BANNED_RE = [re.compile(p, re.IGNORECASE) for p in _BANNED_PHRASES]

_GENERIC_RETENTION_SCAFFOLD_RE = re.compile(
    r"\b(?:before the payoff|one visible signal|payoff appears before the final move|"
    r"final move|hidden cue|replay the first second)\b",
    re.IGNORECASE,
)

# Weak opening words — the hook should NOT start with these per the
# fetch_animals.py prompt rules. We check the script's first sentence
# matches the hook AND lead with action.
_WEAK_HOOK_OPENERS = (
    "today",
    "in a recent",
    "according to",
    "it was announced",
    "a new report",
    "in this video",
    "welcome",
    "hi everyone",
    "hello",
    "this is",
)

# Verbs/numbers that signal an outcome-first hook (preferred shape).
_OUTCOME_INDICATORS_RE = re.compile(
    r"\b(just|now|today|after|already)\s+\w+ed\b"
    r"|\b\d+\s*(percent|%|times|seconds|minutes|hours|days|miles|kilometers)\b"
    r"|\b(?:change|changes|changed|remember|remembers|recognize|recognizes|"
    r"use|uses|used|survive|survives|escape|escapes|heal|heals|call|calls|"
    r"plan|plans|love|loves|hide|hides|hunt|hunts|crush|crushes|breathe|"
    r"breathes|save|saves|protect|protects|track|tracks|see|sees|hear|hears|"
    r"keep|keeps|act|acts|bleed|bleeds|swim|swims|touch|touches|build|builds|"
    r"disappear|disappears|climb|climbs|bray|brays|chew|chews|have|has|"
    r"stop|stops|sleep|sleeps|groom|grooms|lie|lies|chase|chases|pant|pants|"
    r"fool|fools|hold|holds|cool|cools|turn|turns|born|wear|wears|wag|wags|"
    r"aim|aims|carry|carries|cover|covers|covered|fly|flies|leave|leaves|"
    r"lay|lays|"
    r"taste|tastes|smell|smells|sense|senses|compare|compares|imprint|imprints|"
    r"steer|steers|stabilize|stabilizes|trap|traps|measure|measures|lock|locks|"
    r"sample|samples|detect|detects|feel|feels|"
    r"aren't|isn't|don't|can't)\b",
    re.IGNORECASE,
)


@dataclasses.dataclass
class Issue:
    """One quality problem detected on a script."""

    code: str  # short identifier ("ai_tell", "weak_hook", ...)
    severity: str  # "warn" | "block"
    message: str
    span: str = ""  # the matching text fragment (if any)


def check_banned_phrases(text: str) -> list[Issue]:
    """Flag AI-tell phrases in the script."""
    if not text:
        return []
    out: list[Issue] = []
    seen: set[str] = set()
    for pat in _BANNED_RE:
        m = pat.search(text)
        if m:
            phrase = m.group(0).lower()
            if phrase in seen:
                continue
            seen.add(phrase)
            out.append(
                Issue(
                    code="ai_tell",
                    severity="warn",
                    message=f"AI-tell phrase '{phrase}' in script — system prompt forbids it",
                    span=m.group(0),
                )
            )
    return out


def check_generic_retention_scaffold(text: str) -> list[Issue]:
    """Block template language that describes retention mechanics to the viewer."""
    if not text:
        return []
    match = _GENERIC_RETENTION_SCAFFOLD_RE.search(text)
    if not match:
        return []
    return [
        Issue(
            code="generic_retention_scaffold",
            severity="block",
            message="Script contains internal retention-template language instead of a concrete fact",
            span=match.group(0),
        )
    ]


def check_hook_opens_strong(hook: str, script: str = "") -> list[Issue]:
    """The first sentence has to lead with an action verb / consequence.

    Returns at most one Issue: weak_hook OR missing_outcome.
    """
    if not hook:
        return [Issue(code="missing_hook", severity="block", message="Story has no `hook` field on the queue")]
    lower = hook.strip().lower()
    for bad in _WEAK_HOOK_OPENERS:
        if lower.startswith(bad):
            return [
                Issue(
                    code="weak_hook",
                    severity="warn",
                    message=f"Hook opens with weak word '{bad}'. Lead with verb + consequence.",
                    span=hook[:80],
                )
            ]
    # Hook should mention some action / number — outcome-first shape.
    if not _OUTCOME_INDICATORS_RE.search(hook):
        return [
            Issue(
                code="vague_hook",
                severity="warn",
                message="Hook lacks an outcome verb or number — may bury the lede",
                span=hook[:80],
            )
        ]
    return []


def check_script_starts_with_hook(hook: str, script: str) -> list[Issue]:
    """fetch_animals.py's prompt requires script[0] == hook. Drift = bug."""
    if not hook or not script:
        return []
    h = hook.strip().lower().rstrip(".!?")
    s = script.strip().lower()
    # Tolerate small variations: leading punctuation, the script may
    # have stripped/added a period.
    if not s.startswith(h):
        return [
            Issue(
                code="script_hook_mismatch",
                severity="warn",
                message="Script doesn't open with the hook verbatim — TTS will sound off",
                span=script[:80],
            )
        ]
    return []


def check_transformation_present(script: str, description: str) -> list[Issue]:
    """Transformative bar: script must add something beyond the source.

    Conservative heuristic: if 70 %+ of the script's words appear in
    the source description (the short Pexels label), the narration is
    barely doing more than reading the metadata. YouTube's Inauthentic
    Content policy specifically demonetises that — original commentary
    is what keeps Wild Brief on the right side of the rules.
    """
    if not script or not description:
        return []
    script_tokens = re.findall(r"[A-Za-z']{4,}", script.lower())
    src_tokens = set(re.findall(r"[A-Za-z']{4,}", description.lower()))
    if not script_tokens:
        return []
    overlap = sum(1 for t in script_tokens if t in src_tokens) / len(script_tokens)
    if overlap > 0.70:
        return [
            Issue(
                code="low_transformation",
                severity="warn",
                message=f"Script overlaps {overlap*100:.0f}% with source description — " "may read as wire copy",
            )
        ]
    return []


def check_length(script: str) -> list[Issue]:
    """Spoken at +3% rate, ~85-120 words = a 30-45 s Short. We BLOCK
    only when the script is genuinely too thin to fill a Short — below
    40 words is <15 s of body audio after intro/outro chunks consume
    their share, which underperforms. Animal Pexels clips sometimes
    yield terse AI scripts; the relaxed bar means we publish-rather-
    than-skip when the AI ran lean."""
    if not script:
        return [Issue(code="empty_script", severity="block", message="Script is empty — TTS would produce nothing")]
    words = re.findall(r"\S+", script)
    n = len(words)
    if n < 40:
        return [
            Issue(
                code="script_too_short",
                severity="block",
                message=f"Script has only {n} words — Shorts < 15s underperform",
            )
        ]
    if n > 160:
        return [
            Issue(code="script_too_long", severity="warn", message=f"Script has {n} words — likely exceeds 60s cap")
        ]
    return []


def check_title_diverges_from_source(seo_title: str, raw_title: str) -> list[Issue]:
    """The SEO title MUST be a rewrite, not a copy of the source title."""
    if not seo_title or not raw_title:
        return []
    a = re.sub(r"[^a-z0-9 ]", "", seo_title.lower()).strip()
    b = re.sub(r"[^a-z0-9 ]", "", raw_title.lower()).strip()
    if a == b:
        return [
            Issue(
                code="seo_title_unchanged",
                severity="warn",
                message="seo_title is identical to the raw source title — no curiosity gap",
                span=seo_title[:80],
            )
        ]
    return []


def check_human_voice(script: str) -> list[Issue]:
    """Flag narration that reads like anonymous generated copy."""
    result = score_text(script)
    if result.score >= 58:
        return []
    return [
        Issue(
            code="low_human_voice",
            severity="warn",
            message=f"Narration feels too generic/hands-off (human_voice={result.score})",
            span=", ".join(result.issues[:3]),
        )
    ]


def evaluate(story: dict) -> tuple[int, list[Issue]]:
    """Run every check. Returns (grade_0_10, issues)."""
    hook = story.get("hook", "")
    script = story.get("script", "")
    description = story.get("description", "")
    seo_title = story.get("seo_title") or story.get("title", "")
    raw_title = story.get("raw_title", "")

    issues: list[Issue] = []
    issues += check_banned_phrases(script)
    issues += check_generic_retention_scaffold(
        " ".join(str(story.get(k) or "") for k in ("seo_title", "hook", "script", "thumbnail_text"))
    )
    issues += check_hook_opens_strong(hook, script)
    issues += check_script_starts_with_hook(hook, script)
    issues += check_transformation_present(script, description)
    issues += check_length(script)
    issues += check_title_diverges_from_source(seo_title, raw_title)
    issues += check_human_voice(script)

    # Grade: start at 10, subtract per issue. Blocks weigh 4, warns 1.
    penalty = sum(4 if i.severity == "block" else 1 for i in issues)
    grade = max(0, 10 - penalty)
    return grade, issues


def should_block(issues: list[Issue], min_grade: int = 8) -> bool:
    """MrBeast Kill Switch: True if any issue is `block`-severity OR the grade < 8."""
    if any(i.severity == "block" for i in issues):
        return True
    
    penalty = sum(4 if i.severity == "block" else 1 for i in issues)
    grade = max(0, 10 - penalty)
    return grade < min_grade
