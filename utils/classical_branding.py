"""Shared title vocabulary for the "Amber Hours Classical" pillar (chat,
2026-07-22).

Fourth content pillar, and the only one in this repo published in
English rather than Brazilian Portuguese -- the channel owner was
explicit about this. Real classical/orchestral/piano recordings, licensed
CC BY from Jamendo (by far the best-yielding genre checked live that
night, ~18.5-19% commercially-safe vs. 1.5-9% for every other genre
tried), looping under one fixed, hand-picked real Pixabay clip (an
anime-style "studying at a rainy window" scene, `_assets/video/
pinned_classical_ambience.mp4`) -- one real track per video, not a mixed
bed, per the owner's explicit spec.

Kept under the "Amber Hours" umbrella (unlike "Pata Jazz", which needed
a fully separate identity because playful cute-animal content clashes
with the calm/sleep-and-focus promise the main brand already makes).
Classical/piano study ambience doesn't clash with that promise -- it's
the same "real ambient sound for sleep, focus or calm" identity, just in
English and built from real licensed recordings instead of synthesized
audio, so it stays "Amber Hours Classical" rather than inventing a new
name from scratch.
"""

from __future__ import annotations

BRAND_SUFFIX = "Amber Hours Classical"
DEFAULT_EMOJI = "\U0001f3b9"  # musical keyboard

# mood -> (hook phrase, emoji). Real English search-intent phrases for
# this niche (classical/piano study & sleep music), not mood labels.
# Anything not listed falls back to f"Classical Piano -- {mood}" with the
# default keyboard emoji, so a new mood added later still gets an
# on-brand title without this table needing to change in lockstep.
HOOK_BY_MOOD: dict[str, tuple[str, str]] = {
    "deep focus": ("Classical Piano for Deep Focus and Studying", "\U0001f4d6"),
    "sleep": ("Calm Classical Music for Sleep", "\U0001f634"),
    "relaxation": ("Relaxing Classical Piano and Orchestral Music", DEFAULT_EMOJI),
    "reading": ("Classical Music for Reading -- Rainy Window Ambience", "\U0001f4da"),
    "anxiety relief": ("Soothing Classical Music to Calm Anxiety", "\U0001f33f"),
    "rainy day": ("Classical Piano on a Rainy Day", "\U0001f327️"),
    "study session": ("Classical Study Music -- Piano and Strings", "\U0001f4dd"),
    "night ambience": ("Classical Music for a Quiet Night", "\U0001f319"),
}


def branded_title(mood: str, *, suffix: str = "") -> str:
    """Build "{hook} [suffix] -- Amber Hours Classical {emoji}" for a mood.

    `suffix` is free text inserted before the brand dash (e.g. a track
    name or duration).
    """
    hook, emoji = HOOK_BY_MOOD.get(mood.lower(), (f"Classical Piano -- {mood}", DEFAULT_EMOJI))
    parts = [hook] + ([suffix] if suffix else [])
    return f"{' '.join(parts)} -- {BRAND_SUFFIX} {emoji}"


# Keyword -> playlist bucket, checked IN ORDER against the (already-
# branded) title text -- same design as utils/storm_branding.py's
# identical pattern.
_DEFAULT_PLAYLIST_BUCKET = "Classical Ambience"
_PLAYLIST_BUCKET_SIGNALS: tuple[tuple[str, str], ...] = (
    ("focus", "Classical Music for Focus"),
    ("stud", "Classical Music for Focus"),
    ("sleep", "Classical Music for Sleep"),
    ("anxiety", "Classical Music to Calm Anxiety"),
    ("rain", "Rainy-Day Classical Piano"),
    ("night", "Classical Music for Night"),
    ("read", "Classical Music for Reading"),
)


def playlist_bucket_for_title(title: str) -> str:
    """Which classical playlist a published video's (already branded)
    title belongs in -- see _PLAYLIST_BUCKET_SIGNALS."""
    text = (title or "").lower()
    for signal, bucket in _PLAYLIST_BUCKET_SIGNALS:
        if signal in text:
            return bucket
    return _DEFAULT_PLAYLIST_BUCKET
