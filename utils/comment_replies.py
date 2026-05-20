"""
utils/comment_replies.py — DEPRECATED for TikTok deployment.

History
-------
On YouTube, comments-per-view is one of the top three documented Shorts
ranking signals, and posting channel-owner replies to viewer comments
multiplies that signal. The bot used to fetch top-level comments on
recently-published Shorts and post one channel-owner reply per comment,
chosen from a short panel of templated responses customised by the
comment's tone.

Why this is a no-op on TikTok
-----------------------------
TikTok's public Open API (May 2026) does NOT expose endpoints for:
  • listing comments on a video the authenticated user owns
  • posting comments / replies as the authenticated user

Comment moderation on TikTok is a manual-only workflow inside the
TikTok mobile app. The Content Posting API only covers video publish
+ status — not engagement.

The classification helpers below (`classify_comment`, `pick_reply`,
`REPLY_PANEL`) are retained so that if/when TikTok exposes a comment
endpoint — or an operator wires up a 3rd-party tool that does — the
sentiment logic doesn't have to be rewritten. `reply_to_recent` is a
no-op that logs the deprecation.
"""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path

log = logging.getLogger(__name__)

MAX_REPLIES_PER_VIDEO = int(os.environ.get("COMMENT_REPLIES_MAX_PER_VIDEO", "5"))
MAX_REPLIES_PER_RUN   = int(os.environ.get("COMMENT_REPLIES_MAX_PER_RUN",   "25"))
LOOKBACK_HOURS        = int(os.environ.get("COMMENT_REPLIES_LOOKBACK_H",    "72"))

# Sentiment-keyed reply panel. We pick one at random (hash-derived,
# deterministic per comment) so a viewer scrolling the comments doesn't
# see the same reply twice in a row. Retained for forward-compat if the
# TikTok Open API ever exposes comment management.
REPLY_PANEL: dict[str, tuple[str, ...]] = {
    "positive": (
        "Thanks for watching — one weird animal fact every day 🐾",
        "Glad it landed. Follow for tomorrow's brief 🦅",
        "🙌 appreciated. Drop the next animal you want covered.",
        "Thanks — sharing helps the channel a lot.",
    ),
    "curious": (
        "Good question — we'll dig into this more soon. Stay tuned 👀",
        "Worth a follow-up — adding to next week's list.",
        "Sharp observation. Comment again when the next angle drops.",
    ),
    "agreement": (
        "Exactly — and that's why this one's bigger than people realise.",
        "Same read on it. Watch what happens next.",
        "💯 — pin worthy take.",
    ),
    "geo": (
        "Always good to hear from viewers around the world 🌍",
        "Big shoutout to the international crowd — keep the perspectives coming.",
        "Different countries, same scroll 👋",
    ),
}

# Sentiment classification — string-match heuristics, no AI call.
# Order matters: more specific signals first.
_GEO_PATTERN = re.compile(
    r"\b(from\s+\w+|watching from|here in|in\s+(brazil|brasil|usa|america|"
    r"uk|england|india|germany|france|spain|japan|china|portugal|canada|"
    r"australia|africa|mexico))\b",
    re.IGNORECASE,
)
_POSITIVE_PATTERNS = re.compile(
    r"\b(great|love|good|awesome|nice|thanks?|thank you|amazing|excellent|"
    r"helpful|best channel|brilliant|finally|liked|👍|❤|❤️|🔥|💯|🙌|good job)\b",
    re.IGNORECASE,
)
_CURIOUS_PATTERNS = re.compile(
    r"\?|\b(why|how|what|when|where|wondering|curious|explain)\b",
    re.IGNORECASE,
)
_AGREEMENT_PATTERNS = re.compile(
    r"\b(true|exactly|right|agree|spot on|fact|preach|💯|yep|yes|"
    r"this is correct|nailed it)\b",
    re.IGNORECASE,
)
# Stuff we should NEVER reply to automatically.
_AVOID_PATTERNS = re.compile(
    r"\b(ai (slop|generated|garbage)|bot|fake|wrong|incorrect|"
    r"misinformation|propaganda|nazi|fascist|terror|"
    r"kill (yourself|urself)|kys|sub for sub|sub4sub|"
    r"check out my channel|first|second|early)\b",
    re.IGNORECASE,
)


def classify_comment(text: str) -> str | None:
    """Return one of REPLY_PANEL keys, or None if we shouldn't reply."""
    if not text:
        return None
    text = text.strip()
    if len(text) < 4 or len(text) > 800:
        return None
    if _AVOID_PATTERNS.search(text):
        return None
    if _GEO_PATTERN.search(text):
        return "geo"
    if _AGREEMENT_PATTERNS.search(text):
        return "agreement"
    if _CURIOUS_PATTERNS.search(text):
        return "curious"
    if _POSITIVE_PATTERNS.search(text):
        return "positive"
    return None  # neutral / unclassified → skip


def pick_reply(comment_id: str, sentiment: str) -> str | None:
    """Deterministic reply pick based on comment id + sentiment."""
    panel = REPLY_PANEL.get(sentiment) or ()
    if not panel:
        return None
    import hashlib
    h = hashlib.sha1(f"{sentiment}:{comment_id}".encode()).digest()
    return panel[int.from_bytes(h[:4], "big") % len(panel)]


REPLIES_LOG = Path(os.environ.get("COMMENT_REPLIES_LOG",
                                    "_data/comment_replies.jsonl"))


def reply_to_recent(*_args, **_kwargs) -> int:
    """No-op on TikTok — the public Open API does not expose comment
    listing or posting endpoints. Logs the deprecation once and returns 0.
    """
    log.info(
        "comment_replies: TikTok Open API does not expose comment "
        "management. Skipping. (Moderate manually inside the TikTok app.)"
    )
    return 0
