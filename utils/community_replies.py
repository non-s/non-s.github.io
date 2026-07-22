"""Templated, on-brand replies to channel comments (chat, growth pass 2026-07-21).

scripts/reply_to_comments.py posts one of these to every fresh top-level
comment across the channel. A 100%-automated, zero-community-signal
channel is exactly the kind of thing both YouTube's own ranking and a
human viewer read as "nobody's actually here" -- this is the cheapest,
lowest-risk way to close that gap without hand-writing a reply to every
comment. These lines are generic enough to fit any top-level comment (no
sentiment/NLP -- this pipeline has no AI text provider key requirement to
preserve, see README's "no AI text provider key required" line) while
staying in the channel's own voice: the "nook", the mood vocabulary
utils/lofi_branding.py already established.
"""

from __future__ import annotations

import zlib

REPLY_TEMPLATES: tuple[str, ...] = (
    "Thanks for stopping by the Amber Hours nook \U0001f319 -- hope it's helping you focus or unwind.",
    "Glad you're here for the rainy-night vibes ☔ -- let us know what mood you'd like to see next.",
    "Appreciate you listening \U0001f56f️ -- more Amber Hours loops dropping every couple hours.",
    "Thank you! \U0001fab4 What are you up to while this plays -- studying, working, just relaxing?",
    "Means a lot that you took the time to comment \U0001f303 -- welcome to the nook.",
    "Thanks for the love! \U0001f327️ More cozy loops on the way.",
    "Hey, thanks for watching! \U0001f319 Which mood should the next loop be -- rain, snow, or midnight city?",
    "Appreciate you \U0001fab4 -- glad the Amber Hours vibe is doing its job.",
)

# Comments containing a link are far more often self-promo/spam/scam than a
# genuine reply-worthy comment -- auto-replying to those would publicly
# associate the channel with whatever the link points to. Flagged for
# manual review instead of replied to (see scripts/reply_to_comments.py).
_LINK_SIGNALS = ("http://", "https://", "www.")


def looks_like_spam(text: str) -> bool:
    lowered = (text or "").lower()
    return any(signal in lowered for signal in _LINK_SIGNALS)


def pick_reply(comment_id: str) -> str:
    """Deterministic per-comment pick -- stable across retries/reruns, so
    the same comment never gets re-rolled into a different reply if a run
    retries, and crc32's spread keeps back-to-back comments from drawing
    the same line every time (same technique as
    utils/thumbnail_branding.py's _stable_seed)."""
    index = zlib.crc32(str(comment_id or "").encode("utf-8")) % len(REPLY_TEMPLATES)
    return REPLY_TEMPLATES[index]
