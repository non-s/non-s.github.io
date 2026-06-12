"""Human-feel heuristics for Wild Brief narration."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

_PERSONAL_RE = re.compile(
    r"\b(i|i'm|i've|my|me|honestly|here's|watch|look|listen|notice|favorite|favourite)\b",
    re.IGNORECASE,
)
_CONCRETE_RE = re.compile(
    r"\b(face|faces|eyes|beak|tail|skin|bone|bones|feet|claw|teeth|reef|snow|flower|bottle|name|sound)\b",
    re.IGNORECASE,
)
_GENERIC_RE = re.compile(
    r"\b(fascinating|remarkable|incredible|amazing|nature's wonders|animal kingdom|"
    r"plays a vital role|unique adaptations|did you know|fun fact)\b",
    re.IGNORECASE,
)
_SPEECHY_RE = re.compile(r"\b(don't|can't|isn't|they're|here's|that's|you're|it's|watch)\b", re.IGNORECASE)


@dataclass(frozen=True)
class HumanVoiceScore:
    score: int
    strengths: tuple[str, ...]
    issues: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


def score_text(text: str) -> HumanVoiceScore:
    """Score whether narration feels edited by a human host."""
    text = text or ""
    score = 50
    strengths: list[str] = []
    issues: list[str] = []

    if _PERSONAL_RE.search(text):
        score += 18
        strengths.append("host_presence")
    else:
        score -= 14
        issues.append("no_host_presence")

    concrete_hits = len(set(m.group(0).lower() for m in _CONCRETE_RE.finditer(text)))
    if concrete_hits >= 2:
        score += 14
        strengths.append("concrete_detail")
    else:
        score -= 10
        issues.append("needs_concrete_detail")

    if _SPEECHY_RE.search(text):
        score += 8
        strengths.append("spoken_language")
    else:
        score -= 6
        issues.append("too_written")

    generic_hits = len(_GENERIC_RE.findall(text))
    if generic_hits:
        score -= min(24, generic_hits * 8)
        issues.append("generic_phrasing")

    sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
    long_sentences = [s for s in sentences if len(s.split()) > 22]
    if long_sentences:
        score -= min(18, len(long_sentences) * 6)
        issues.append("sentences_too_long")
    else:
        score += 6
        strengths.append("short_sentences")

    return HumanVoiceScore(
        score=max(0, min(100, score)),
        strengths=tuple(strengths),
        issues=tuple(dict.fromkeys(issues)),
    )
