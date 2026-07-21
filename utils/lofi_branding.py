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
    # Was "lofi girl" (chat, growth pass 2026-07-21): that key's own lowercased
    # text became a video tag and leaked into descriptions ("lofi girl lofi
    # beats...") on every video with this mood, and its hook text was
    # byte-identical to "study desk"'s -- the two moods collided on title the
    # first time both got picked, tripping upload_youtube.py's dedup path and
    # publishing "... | Lofi girl" (a giant competitor's brand name) as a
    # visible tag suffix. Renamed to its own visual motif (the potted plant
    # already drawn on the windowsill in every Shorts/live scene) with a
    # distinct hook so it can no longer collide with "study desk", and no
    # longer rides a competitor's name for search traffic.
    "windowsill desk": ("Windowsill Study Anime Lofi", "\U0001fab4"),
    "rain window": ("Rainy Night Anime Lofi", "\U0001f327️"),
    "night city": ("Midnight City Anime Lofi", "\U0001f303"),
    "study desk": ("Late Night Study Anime Lofi", "\U0001f56f️"),
    "cozy room": ("Cozy Fireplace Anime Lofi", DEFAULT_EMOJI),
    "cafe jazz": ("Late Night Cafe Anime Lofi", DEFAULT_EMOJI),
    "bedroom plants": ("Cozy Bedroom Anime Lofi", DEFAULT_EMOJI),
    "cat sleeping": ("Sleepy Cat Anime Lofi", "\U0001f43e"),
    "library reading": ("Late Night Library Lofi", "\U0001f4da"),
    "snow window": ("Snowy Night Anime Lofi", "\U0001f328️"),
    "autumn rain": ("Autumn Rain Anime Lofi", "\U0001f327️"),
    "foggy morning": ("Foggy Morning Anime Lofi", DEFAULT_EMOJI),
    "rooftop night": ("Rooftop Rain Anime Lofi", "\U0001f327️"),
    "train window": ("Late Night Train Anime Lofi", "\U0001f327️"),
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


# Most of this channel's moods are the same nocturnal/rainy energy by
# design (see the module docstring), so only the two scenes that read as
# visually busier than the rest -- a moving city skyline, a jazz cafe --
# get pulled out of the default "calm" bucket. Keyed off _mood_label()'s
# output (lowercased), same as HOOK_BY_MOOD.
_LIVELY_MOODS = {"night city", "cafe jazz"}

# scripts/sync_jamendo_music.py's sidecar "speed" field (Jamendo's own
# verylow/low/medium/high tempo classification) bucketed to match
# mood_energy()'s two buckets. "medium" is the single most common value by
# far (~74% of the catalog checked live), so it's treated as compatible
# with either mood -- restricting it to "lively" only would starve the
# "calm" bucket (the one nearly every video in this niche wants) down to
# the ~10% of tracks tagged low/verylow.
CALM_BGM_SPEEDS = {"verylow", "low", "medium"}
LIVELY_BGM_SPEEDS = {"medium", "high"}


def mood_energy(mood: str) -> str:
    """ "calm" or "lively", per _LIVELY_MOODS -- see bgm_speeds_for_mood()."""
    return "lively" if mood.lower() in _LIVELY_MOODS else "calm"


def bgm_speeds_for_mood(mood: str) -> set[str]:
    """Which scripts/sync_jamendo_music.py sidecar "speed" values pair well
    with this b-roll mood, for generate_lofi_short.py's single clip + single
    track pairing (generate_lofi_mix.py and live_stream_dynamic.py loop the
    whole bgm library regardless of mood, so this doesn't apply there)."""
    return LIVELY_BGM_SPEEDS if mood_energy(mood) == "lively" else CALM_BGM_SPEEDS
