"""AI-based natural-language coherence gate for Shorts titles.

``utils/seo_optimizer.py`` and ``utils/editorial_guard.py`` only catch
known-bad structural/regex patterns (weak search front, stacked animal
words, a fixed list of robotic phrasings). A generated title can still be
grammatically broken in ways no fixed pattern predicts -- e.g. "Cows use
herd memory before they remember" scores 100/100 on the structural SEO
check and slips past every regex, but no native English speaker would
call it a real sentence.

This asks one small free-tier AI call to judge naturalness of the FINAL
candidate title only (never all ~10 packaging variants), so the added
quota/latency cost stays one call per published Short.
"""

from __future__ import annotations

import os

from utils.ai_helper import ai_text

_YES = {"yes", "y", "true"}
_NO = {"no", "n", "false"}


def evaluate_title_coherence(title: str) -> dict:
    """Return a verdict dict: checked, natural, reason, state.

    ``state`` mirrors the other publish gates in generate_shorts.py:
    "approved" (ship it), "held" (block publish, TITLE_COHERENCE_MODE=block),
    "warn" (log only), "skipped" (AI unavailable or empty title -- fail open,
    never halt the pipeline over an outage in a free-tier provider).
    """
    title = (title or "").strip()
    if not title:
        return {"checked": False, "natural": None, "reason": "empty_title", "state": "skipped"}

    prompt = (
        "You are a strict English copy editor. Read this YouTube Shorts "
        "title and decide if a native English speaker would consider it "
        "grammatically correct AND immediately meaningful (not vague, not "
        "a garbled template).\n\n"
        f'Title: "{title}"\n\n'
        "Reply with exactly one line: YES or NO, followed by a dash and a "
        "reason under 12 words. Example: 'NO - subject and verb do not agree'."
    )
    response = ai_text(prompt, task="title_coherence", timeout=15).strip()
    if not response:
        return {"checked": False, "natural": None, "reason": "ai_unavailable", "state": "skipped"}

    head = response.splitlines()[0].strip()
    verdict, _, tail = head.partition("-")
    verdict = verdict.strip().lower()
    reason = tail.strip()

    if verdict in _YES:
        return {"checked": True, "natural": True, "reason": reason, "state": "approved"}
    if verdict in _NO:
        mode = os.environ.get("TITLE_COHERENCE_MODE", "block").strip().lower()
        state = "held" if mode == "block" else "warn"
        return {
            "checked": True,
            "natural": False,
            "reason": reason or "flagged_incoherent",
            "state": state,
        }
    # Unparseable reply (provider drifted off-format) -- fail open rather
    # than block a good title on a formatting fluke.
    return {
        "checked": True,
        "natural": None,
        "reason": f"unparseable_response:{head[:60]}",
        "state": "warn",
    }
