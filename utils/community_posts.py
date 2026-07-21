"""Community-tab post drafts (chat, growth pass 2026-07-21).

The YouTube Data API has no public endpoint for the Community tab -- it's
a Studio-only surface (see SECURITY.md: "When Studio-only features are
needed, generate operator-assist artifacts instead of automating them").
So unlike scripts/reply_to_comments.py, nothing here posts anything: this
drafts one ready-to-paste suggestion per week, rotating through a small
pool so scripts/draft_community_post.py always has something fresh to
propose. A human still has to paste it into YouTube Studio.
"""

from __future__ import annotations

import zlib

from utils.lofi_branding import HOOK_BY_MOOD


def _sample_moods(n: int = 3) -> list[str]:
    """A few evenly-spread mood names from the real, current vocabulary
    (utils.lofi_branding.HOOK_BY_MOOD) -- pulled live rather than hardcoded,
    so renaming or adding a mood there never leaves a stale option here."""
    moods = sorted(HOOK_BY_MOOD.keys())
    if not moods:
        return []
    step = max(1, len(moods) // n)
    return [mood.title() for mood in moods[::step][:n]]


def _poll_options_text() -> str:
    return " / ".join(_sample_moods())


POST_TEMPLATES: tuple[str, ...] = (
    "\U0001f319 What should the next Amber Hours loop be? {options} -- drop your pick below.",
    "Cozy check-in: what are you doing while an Amber Hours loop plays right now? Studying, "
    "working, or just winding down? \U0001fab4",
    "New loops drop every couple hours around here \U0001f327️ -- which time of night is "
    "your favorite to listen to: rainy, snowy, or midnight city?",
    "Thanks for hanging out in the Amber Hours nook this week \U0001f319 -- more rainy-night lofi on the way.",
    "Quick poll: {options} -- which mood matches your vibe tonight?",
    "Behind the loop: every Amber Hours scene is hand-drawn, not stock footage or AI art "
    "\U0001fab4 -- glad you're here for it.",
)


def draft_for_week(week_key: str) -> dict:
    """`week_key` is any stable per-week string (e.g. ISO "2026-W30") -- the
    same key always drafts the same post, so re-running within the same
    week doesn't roll a different suggestion out from under an operator
    who already saw last night's draft."""
    index = zlib.crc32(week_key.encode("utf-8")) % len(POST_TEMPLATES)
    template = POST_TEMPLATES[index]
    text = template.format(options=_poll_options_text()) if "{options}" in template else template
    return {"week": week_key, "text": text}
