"""Shared title vocabulary for the real storm/rain ambience pillar
(growth pass, 2026-07-21).

Sister module to utils/lofi_branding.py, same shape (a scene -> hook/emoji
table, branded_title(), playlist bucketing) but a deliberately different
vocabulary: this pillar's whole point is to stop competing on "anime
lofi" search terms an oversaturated ocean of near-identical channels
already owns, and instead target the real, much larger, much less
lofi-specific search intent behind "rain sounds for sleep" / "thunderstorm
ambience" -- terms an insomniac, a parent settling a baby, or someone with
tinnitus/anxiety actually types, not "cute anime girl studying". No anime
references anywhere in this vocabulary, on purpose (see
tests/test_storm_branding.py's brand-safety test).

Still published as "Amber Hours" (the brand suffix), not a separate
sub-brand name: the channel already has some (if early) subscriber/search
history worth compounding, and viewers who like one format have a reason
to explore the other under the same recognizable name.
"""

from __future__ import annotations

BRAND_SUFFIX = "Amber Hours"
DEFAULT_EMOJI = "\U0001f327️"  # rain cloud

# scene -> (hook phrase, emoji). Every hook is phrased the way someone
# actually searches for this, not a mood label -- see the module
# docstring. Anything not listed falls back to f"{scene} Rain Sounds" with
# the default rain-cloud emoji, so a new scene added later still gets an
# on-brand title without this table needing to change in lockstep.
HOOK_BY_SCENE: dict[str, tuple[str, str]] = {
    "deep sleep": ("Heavy Rain & Distant Thunder for Deep Sleep", "\U0001f634"),
    "power nap": ("Rain Sounds for a Quick Power Nap", "\U0001f4a4"),
    "insomnia": ("Distant Thunder & Rain for Insomnia Relief", "\U0001f329️"),
    "focus": ("Rain Sounds for Studying & Deep Focus", "\U0001f4d6"),
    "white noise": ("Rain White Noise -- Block Out Distractions", "\U0001f50a"),
    "reading": ("Rain on Window -- Cozy Reading Ambience", "\U0001f4da"),
    "anxiety relief": ("Calming Rain Sounds for Anxiety Relief", DEFAULT_EMOJI),
    "meditation": ("Rain Sounds for Meditation & Mindfulness", "\U0001f9d8"),
    "baby sleep": ("Gentle Rain Sounds to Help Baby Sleep", "\U0001f37c"),
    "tinnitus": ("Rain Sounds to Mask Tinnitus & Ringing Ears", DEFAULT_EMOJI),
    "night drive": ("Rain on the Car Window -- Night Drive Ambience", "\U0001f697"),
    "cabin": ("Rain on a Cabin Roof -- Cozy Storm Ambience", "\U0001f3d5️"),
}


def branded_title(scene: str, *, suffix: str = "") -> str:
    """Build "{hook} [suffix] — Amber Hours {emoji}" for a storm scene.

    `suffix` is free text inserted before the brand dash (e.g. a duration
    like "(3 Hours)"), same convention as utils.lofi_branding.branded_title.
    """
    hook, emoji = HOOK_BY_SCENE.get(scene.lower(), (f"{scene} Rain Sounds", DEFAULT_EMOJI))
    parts = [hook] + ([suffix] if suffix else [])
    return f"{' '.join(parts)} -- {BRAND_SUFFIX} {emoji}"


# Keyword -> playlist bucket, same "checked in order, most specific first"
# design as utils.lofi_branding.playlist_bucket_for_title -- groups the
# many individual hooks into a handful of playlists a viewer would
# actually browse.
_DEFAULT_PLAYLIST_BUCKET = "Rain & Storm Ambience"
_PLAYLIST_BUCKET_SIGNALS: tuple[tuple[str, str], ...] = (
    ("thunder", "Thunderstorm Sounds"),
    ("baby", "Rain for Baby Sleep"),
    ("nap", "Rain for Naps & Quick Sleep"),
    ("sleep", "Rain for Deep Sleep"),
    ("stud", "Rain for Studying & Focus"),
    ("focus", "Rain for Studying & Focus"),
    ("read", "Rain for Studying & Focus"),
    ("anxiety", "Rain for Calm & Anxiety Relief"),
    ("meditat", "Rain for Calm & Anxiety Relief"),
    ("tinnitus", "Rain White Noise"),
    ("white noise", "Rain White Noise"),
)


def playlist_bucket_for_title(title: str) -> str:
    """Which storm playlist a published video's (already branded) title
    belongs in -- see _PLAYLIST_BUCKET_SIGNALS."""
    text = (title or "").lower()
    for signal, bucket in _PLAYLIST_BUCKET_SIGNALS:
        if signal in text:
            return bucket
    return _DEFAULT_PLAYLIST_BUCKET
