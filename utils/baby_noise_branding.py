"""Shared title vocabulary for the white/pink/brown-noise ambience pillar
(acting-founder growth pass, 2026-07-22).

Same shape as utils/storm_branding.py (scene -> hook/emoji table,
branded_title(), playlist bucketing), same brand ("Amber Hours") --
unlike "Pata Jazz", this pillar's promise ("real ambient sound to help
you sleep/focus/calm down") is identical to the rain pillar's, just a
different scene/audience within it: parents needing white/brown noise
for a baby, and the study-focus/tinnitus-masking audiences a plain noise
tone serves more precisely than rain texture does. See
utils/noise_audio.py's module docstring for the full reasoning on why
this is a new pillar rather than more rain-pillar scenes.

Content language is Brazilian Portuguese (pt-BR), matching the channel's
existing pivot -- hooks are real pt-BR search phrases ("ruído branco
bebê", "ruído marrom para dormir", ...), not machine-transliterated
English white-noise-app copy.
"""

from __future__ import annotations

BRAND_SUFFIX = "Amber Hours"
DEFAULT_EMOJI = "\U0001f50a"  # speaker/volume

# scene -> (hook phrase, emoji). Scenes here are keyed by noise color +
# audience, not a visual mood the way the rain pillar's scenes are, since
# the actual audio-color choice is the point of the search intent. Anything
# not listed falls back to f"Ruído Branco -- {scene}" with the default
# speaker emoji.
HOOK_BY_SCENE: dict[str, tuple[str, str]] = {
    "white noise": ("Ruído Branco Puro para o Bebê Dormir a Noite Toda", "\U0001f37c"),
    "pink noise": ("Ruído Rosa Suave para Dormir Profundamente", "\U0001f319"),
    "brown noise": ("Ruído Marrom Grave para Acalmar e Dormir", "\U0001f43b"),
    "baby sleep": ("Som Constante para Ajudar o Bebê a Dormir a Noite Toda", "\U0001f37c"),
    "focus": ("Ruído Branco para Estudar e Focar sem Distrações", "\U0001f4d6"),
    "tinnitus": ("Ruído Branco para Mascarar o Zumbido no Ouvido", "\U0001f50a"),
}


def branded_title(scene: str, *, suffix: str = "") -> str:
    """Build "{hook} [suffix] -- Amber Hours {emoji}" for a noise scene."""
    hook, emoji = HOOK_BY_SCENE.get(scene.lower(), (f"Ruído Branco -- {scene}", DEFAULT_EMOJI))
    parts = [hook] + ([suffix] if suffix else [])
    return f"{' '.join(parts)} -- {BRAND_SUFFIX} {emoji}"


# Keyword -> playlist bucket, checked IN ORDER against the (already-
# branded) title text -- same design as utils/storm_branding.py's
# identical function.
_DEFAULT_PLAYLIST_BUCKET = "Ruído para Dormir e Focar"
_PLAYLIST_BUCKET_SIGNALS: tuple[tuple[str, str], ...] = (
    ("bebê", "Ruído para o Bebê Dormir"),
    ("marrom", "Ruído Marrom"),
    ("rosa", "Ruído Rosa"),
    ("branco", "Ruído Branco"),
    ("estud", "Ruído Branco para Estudar e Focar"),
    ("focar", "Ruído Branco para Estudar e Focar"),
    ("zumbido", "Ruído Branco para o Zumbido"),
)


def playlist_bucket_for_title(title: str) -> str:
    """Which noise-pillar playlist a published video's (already branded)
    title belongs in -- see _PLAYLIST_BUCKET_SIGNALS."""
    text = (title or "").lower()
    for signal, bucket in _PLAYLIST_BUCKET_SIGNALS:
        if signal in text:
            return bucket
    return _DEFAULT_PLAYLIST_BUCKET
