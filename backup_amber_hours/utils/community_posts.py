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

from utils.storm_branding import HOOK_BY_SCENE


def _sample_scenes(n: int = 3) -> list[str]:
    """A few evenly-spread scene names from the real, current vocabulary
    (utils.storm_branding.HOOK_BY_SCENE) -- pulled live rather than
    hardcoded, so renaming or adding a scene there never leaves a stale
    option here."""
    scenes = sorted(HOOK_BY_SCENE.keys())
    if not scenes:
        return []
    step = max(1, len(scenes) // n)
    return [scene.title() for scene in scenes[::step][:n]]


def _poll_options_text() -> str:
    return " / ".join(_sample_scenes())


POST_TEMPLATES: tuple[str, ...] = (
    "\U0001f327️ What should the next Amber Hours rain scene be? {options} -- drop your pick below.",
    "Cozy check-in: what are you doing while the rain plays right now? Sleeping, studying, or just "
    "winding down? \U0001f4a4",
    "New rain & thunder loops drop every couple hours around here \U0001f329️ -- do you prefer it "
    "with distant thunder, or just steady rain?",
    "Thanks for hanging out in the Amber Hours rain room this week \U0001f327️ -- more storm ambience on the way.",
    "Quick poll: {options} -- which one matches what you need tonight?",
    "Behind the loop: the rain and thunder are procedurally synthesized, not a looped recording "
    "\U0001f4a7 -- no sample to run out of, ever.",
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
