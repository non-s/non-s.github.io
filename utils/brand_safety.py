"""
utils/brand_safety.py — Drop stories that crater RPM or invite strikes.

YouTube's brand-safety throttle is the silent killer of news channels'
revenue. Stories about war casualties, school shootings, political
attack-ads, conspiracy theories, etc. get tagged as "limited
monetization" — they still publish, still get views, but the ad fill
rate collapses. Channel-wide RPM drops accordingly.

Worse: a steady diet of these signals "this channel is risky" to
YouTube's ad-side classifier, dragging down the RPM of OTHER (clean)
videos on the same channel for weeks.

This module is a cheap regex+keyword gate that rejects sensitive
stories BEFORE we burn AI tokens on them. The thresholds are
deliberately conservative — false positives (dropping a clean story
by mistake) are far cheaper than false negatives (one demonetised
upload poisons the channel's classifier).

The story can still bypass the filter when `breaking=True` AND the
relevance score is unusually high — sometimes a major event IS the
story you need to cover even though it's tagged "war".
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

log = logging.getLogger(__name__)


# Heavy demonetisation triggers — these almost always end in
# "limited or no ads". Tuned against YouTube's published
# advertiser-friendly content guidelines (May 2025 update).
_HARD_BLOCKLIST = [
    # Graphic violence / death
    r"\bshooting\b", r"\bmassacre\b", r"\bgenocide\b",
    r"\bbeheaded?\b", r"\bdecapitat",
    r"\bmurdered?\b", r"\bkilled\s+\d+",
    r"\b\d+\s+(dead|killed)\b",
    r"\bsuicide\b", r"\bself[- ]harm\b",
    r"\bschool[- ]shooting\b",
    r"\bmass[- ]shooting\b",
    r"\bcasualties\b",
    # Conflict / war framing — RPM crushed
    r"\bairstrike\b", r"\bmissile strike\b", r"\bdrone strike\b",
    r"\bgenocide\b", r"\bethnic cleansing\b",
    r"\bwar crimes?\b", r"\batrocities\b",
    # Politically polarising attack framings
    r"\bgrooming\b",
    r"\bpedophil",
    # Sensitive medical / public-health panic
    r"\bpandemic outbreak\b",
    # Drug abuse
    r"\bfentanyl\b", r"\boverdosed?\b",
    # Hate / discrimination
    r"\bracist attack\b", r"\bantisemitic attack\b",
    r"\b(transphobic|homophobic) attack\b",
]

# Softer signals — penalty in scoring, not an outright block. A story
# with one of these can still ship if its overall score is strong; a
# story with TWO+ should be skipped.
_SOFT_PENALTY = [
    r"\bIsrael(i)?\b", r"\bPalestin", r"\bGaza\b",       # conflict framing
    r"\bRussia\b", r"\bPutin\b",  r"\bUkraine\b",        # conflict framing
    r"\babortion\b",
    r"\bguns?\b",
    r"\bcryptocurrency scam\b",
    r"\btrump\b", r"\bbiden\b",                            # high partisan loading
    r"\belection fraud\b",
    r"\bvaccine\b",                                        # mostly medical, sometimes anti-vax
    r"\bdeath toll\b",
]

# Compile once — module-level so we don't pay the regex cost per call.
_HARD_RE = [re.compile(p, re.IGNORECASE) for p in _HARD_BLOCKLIST]
_SOFT_RE = [re.compile(p, re.IGNORECASE) for p in _SOFT_PENALTY]


@dataclass
class SafetyVerdict:
    """Return shape from `evaluate()`."""
    ok: bool                # False → caller should drop the story
    reason: str             # human-readable explanation when ok is False
    hard_hits: list[str]    # the hard-blocklist patterns that fired
    soft_hits: list[str]    # the soft-penalty patterns that fired
    penalty: int            # subtract from the story's AI score


def evaluate(title: str, description: str = "",
             breaking_override: bool = False,
             relevance: float = 0.0) -> SafetyVerdict:
    """Run the brand-safety gate on one story.

    `breaking_override` + high `relevance` (≥ 8.0) lets a single hard-hit
    pass — useful for genuine major-event coverage that we WOULD shoot
    even at lower RPM (the algorithmic upside outweighs the RPM hit).
    """
    text = f"{title or ''} {description or ''}"
    hard_hits = [p.pattern for p in _HARD_RE if p.search(text)]
    soft_hits = [p.pattern for p in _SOFT_RE if p.search(text)]

    # Hard hits: block unless this is breaking news of unambiguous import.
    if hard_hits:
        if breaking_override and relevance >= 8.0 and len(hard_hits) == 1:
            return SafetyVerdict(
                ok=True,
                reason=f"hard hit {hard_hits[0]!r} overridden by breaking + relevance {relevance:.1f}",
                hard_hits=hard_hits, soft_hits=soft_hits,
                penalty=2,
            )
        return SafetyVerdict(
            ok=False,
            reason=f"hard-blocklist hit: {hard_hits[:2]}",
            hard_hits=hard_hits, soft_hits=soft_hits,
            penalty=10,
        )

    # Two or more soft hits: block. A single soft hit: pass with a
    # 1-point AI-score penalty (so a story with similar quality but
    # no soft hits wins the slot).
    if len(soft_hits) >= 2:
        return SafetyVerdict(
            ok=False,
            reason=f"two soft signals ({soft_hits[:3]}) — channel-classifier risk",
            hard_hits=hard_hits, soft_hits=soft_hits,
            penalty=4,
        )
    if soft_hits:
        return SafetyVerdict(
            ok=True,
            reason="one soft signal — light penalty",
            hard_hits=hard_hits, soft_hits=soft_hits,
            penalty=1,
        )

    return SafetyVerdict(
        ok=True, reason="clean", hard_hits=[], soft_hits=[], penalty=0,
    )
