"""Shared title vocabulary for the real storm/rain ambience pillar
(growth pass, 2026-07-21).

Sister module to the earlier (now-removed) lofi pillar's branding module,
same shape (a scene -> hook/emoji table, branded_title(), playlist
bucketing) but a deliberately different vocabulary: this pillar's whole
point is to stop competing on "anime lofi" search terms an oversaturated
ocean of near-identical channels already owns, and instead target the
real, much larger, much less lofi-specific search intent behind "rain
sounds for sleep" / "thunderstorm ambience" -- terms an insomniac, a
parent settling a baby, or someone with tinnitus/anxiety actually types,
not "cute anime girl studying". No anime references anywhere in this
vocabulary, on purpose (see tests/test_storm_branding.py's brand-safety
test).

Content language is Brazilian Portuguese (pt-BR) as of the language
pivot (chat, 2026-07-21) -- the channel owner wants to try pt-BR as an
experiment. Hooks below are real pt-BR search phrases ("som de chuva
para dormir", "chuva e trovão", ...), not machine-transliterated English.
`BRAND_SUFFIX` ("Amber Hours") stays untranslated on purpose -- it's the
channel's wordmark/brand name, not content.

Still published as "Amber Hours" (the brand suffix), not a separate
sub-brand name: the channel already has some (if early) subscriber/search
history worth compounding, and viewers who like one format have a reason
to explore the other under the same recognizable name.
"""

from __future__ import annotations

BRAND_SUFFIX = "Amber Hours"
DEFAULT_EMOJI = "\U0001f327️"  # rain cloud

# scene -> (hook phrase, emoji). Every hook is phrased the way someone
# actually searches for this in pt-BR, not a mood label -- see the module
# docstring. Anything not listed falls back to f"Som de Chuva -- {scene}"
# with the default rain-cloud emoji, so a new scene added later still
# gets an on-brand title without this table needing to change in
# lockstep.
HOOK_BY_SCENE: dict[str, tuple[str, str]] = {
    "deep sleep": ("Chuva Forte e Trovão ao Longe para Dormir Profundamente", "\U0001f634"),
    "power nap": ("Som de Chuva para uma Soneca Rápida", "\U0001f4a4"),
    "insomnia": ("Trovão ao Longe e Chuva para Aliviar a Insônia", "\U0001f329️"),
    "focus": ("Som de Chuva para Estudar e Focar", "\U0001f4d6"),
    "white noise": ("Ruído Branco de Chuva -- Bloqueie as Distrações", "\U0001f50a"),
    "reading": ("Chuva na Janela -- Ambiente Aconchegante para Leitura", "\U0001f4da"),
    "anxiety relief": ("Som de Chuva Calmante para Aliviar a Ansiedade", DEFAULT_EMOJI),
    "meditation": ("Som de Chuva para Meditação e Mindfulness", "\U0001f9d8"),
    "baby sleep": ("Som de Chuva Suave para Ajudar o Bebê a Dormir", "\U0001f37c"),
    "tinnitus": ("Som de Chuva para Mascarar o Zumbido no Ouvido", DEFAULT_EMOJI),
    "night drive": ("Chuva no Vidro do Carro -- Ambiente de Viagem Noturna", "\U0001f697"),
    "cabin": ("Chuva no Telhado da Cabana -- Ambiente Aconchegante de Tempestade", "\U0001f3d5️"),
}


def branded_title(scene: str, *, suffix: str = "") -> str:
    """Build "{hook} [suffix] -- Amber Hours {emoji}" for a storm scene.

    `suffix` is free text inserted before the brand dash (e.g. a duration
    like "(3 Horas)").
    """
    hook, emoji = HOOK_BY_SCENE.get(scene.lower(), (f"Som de Chuva -- {scene}", DEFAULT_EMOJI))
    parts = [hook] + ([suffix] if suffix else [])
    return f"{' '.join(parts)} -- {BRAND_SUFFIX} {emoji}"


# Keyword -> playlist bucket, checked IN ORDER against the (already-
# branded) title text -- order matters, most specific first, same design
# as the earlier lofi pillar's playlist_bucket_for_title. Groups the many
# individual hooks into a handful of playlists a viewer would actually
# browse.
_DEFAULT_PLAYLIST_BUCKET = "Chuva e Tempestade"
_PLAYLIST_BUCKET_SIGNALS: tuple[tuple[str, str], ...] = (
    ("trovão", "Som de Trovão"),
    ("bebê", "Chuva para o Bebê Dormir"),
    ("soneca", "Chuva para Sonecas Rápidas"),
    ("dormir", "Chuva para Dormir Profundamente"),
    ("estud", "Chuva para Estudar e Focar"),
    ("focar", "Chuva para Estudar e Focar"),
    ("leitura", "Chuva para Estudar e Focar"),
    ("ansiedade", "Chuva para Acalmar e Aliviar a Ansiedade"),
    ("medita", "Chuva para Acalmar e Aliviar a Ansiedade"),
    ("zumbido", "Ruído Branco de Chuva"),
    ("ruído branco", "Ruído Branco de Chuva"),
)


def playlist_bucket_for_title(title: str) -> str:
    """Which storm playlist a published video's (already branded) title
    belongs in -- see _PLAYLIST_BUCKET_SIGNALS."""
    text = (title or "").lower()
    for signal, bucket in _PLAYLIST_BUCKET_SIGNALS:
        if signal in text:
            return bucket
    return _DEFAULT_PLAYLIST_BUCKET
