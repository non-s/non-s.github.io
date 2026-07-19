"""Shared title vocabulary for the lofi Shorts + horizontal mix pipelines.

Both generate_lofi_short.py and generate_lofi_mix.py need the exact same
hook wording per b-roll mood so a viewer sees one consistent "Amber Hours"
identity across formats. Titles used to be generic ("Chill Beats to Unwind")
-- the same vocabulary every large lofi channel already owns, which a small
channel can't win on. This leads with a specific mood hook instead and
tags the channel name as a suffix (see the 2026-07-18 rebrand of the already
published titles for the reasoning), so search relevance sits on the words
that are actually distinctive.
"""

from __future__ import annotations

BRAND_SUFFIX = "Amber Hours"
DEFAULT_EMOJI = "\U0001f319"  # moon

# mood (as produced by _mood_label(), lowercased) -> (hook phrase, emoji).
# Keyed off scripts/sync_lofi_broll.py's LOFI_QUERIES. Anything not listed
# falls back to f"{mood} Anime Lofi" with the default moon emoji below, so a
# new query added there still gets an on-brand title without this table
# needing to change in lockstep.
HOOK_BY_MOOD: dict[str, tuple[str, str]] = {
    "lofi girl": ("Late Night Study Anime Lofi", "\U0001f56f️"),
    "rain window": ("Rainy Night Anime Lofi", "\U0001f327️"),
    "night city": ("Midnight City Anime Lofi", "\U0001f303"),
    "study desk": ("Late Night Study Anime Lofi", "\U0001f56f️"),
    "cozy room": ("Cozy Fireplace Anime Lofi", DEFAULT_EMOJI),
    "cafe jazz": ("Late Night Cafe Anime Lofi", DEFAULT_EMOJI),
    "bedroom plants": ("Cozy Bedroom Anime Lofi", DEFAULT_EMOJI),
    "cat sleeping": ("Sleepy Cat Anime Lofi", "\U0001f43e"),
    "library reading": ("Late Night Library Lofi", "\U0001f4da"),
    "snow window": ("Snowy Night Anime Lofi", "\U0001f328️"),
}


def branded_title(mood: str, *, suffix: str = "") -> str:
    """Build "{hook} [suffix] — Amber Hours {emoji}" for a b-roll mood.

    `suffix` is free text inserted before the brand dash (e.g. "(1 Hour)"
    for the horizontal mix) so both pipelines can share this one table.
    """
    hook, emoji = HOOK_BY_MOOD.get(mood.lower(), (f"{mood} Anime Lofi", DEFAULT_EMOJI))
    parts = [hook] + ([suffix] if suffix else [])
    return f"{' '.join(parts)} — {BRAND_SUFFIX} {emoji}"


# Keyword -> playlist bucket, checked IN ORDER against the (already-branded)
# title text -- order matters, most specific first: "night"/"midnight" shows
# up in almost every hook this channel uses ("Late Night Study", "Purring
# Through the Night", ...) since the whole identity is nocturnal, so it has
# to be the last, catch-most-of-the-rest signal or it swallows hooks that
# belong in a more specific bucket. "purr" catches "Purring Through the
# Night", which doesn't contain the literal word "cat". Groups the many
# individual hooks (Sleepy Cat/Cat Nap/Purring Through the Night, ...) into
# a handful of playlists a viewer would actually browse, instead of one
# near-empty playlist per hook. Keyword-based (not a mood-key lookup) so it
# still groups a title correctly even for a mood HOOK_BY_MOOD has no entry
# for.
_DEFAULT_PLAYLIST_BUCKET = "Cozy Anime Lofi"
_PLAYLIST_BUCKET_SIGNALS: tuple[tuple[str, str], ...] = (
    ("rain", "Rainy Night Lofi"),
    ("snow", "Snowy Night Lofi"),
    ("cat", "Cozy Cat Lofi"),
    ("purr", "Cozy Cat Lofi"),
    ("stud", "Late Night Study Lofi"),
    ("librar", "Late Night Study Lofi"),
    ("cafe", _DEFAULT_PLAYLIST_BUCKET),
    ("fireplace", _DEFAULT_PLAYLIST_BUCKET),
    ("bedroom", _DEFAULT_PLAYLIST_BUCKET),
    ("night", "Midnight City Lofi"),
)


def playlist_bucket_for_title(title: str) -> str:
    """Which mood playlist a published video's (already branded) title
    belongs in -- see _PLAYLIST_BUCKET_SIGNALS."""
    text = (title or "").lower()
    for signal, bucket in _PLAYLIST_BUCKET_SIGNALS:
        if signal in text:
            return bucket
    return _DEFAULT_PLAYLIST_BUCKET
