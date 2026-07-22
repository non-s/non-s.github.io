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

import random

BRAND_SUFFIX = "Amber Hours"
DEFAULT_EMOJI = "\U0001f327️"  # rain cloud

# scene -> (tuple of hook phrases, emoji). Every hook is phrased the way
# someone actually searches for this in pt-BR, not a mood label -- see the
# module docstring. Multiple hooks per scene reduce title collisions when
# publishing many Shorts/ambience videos from the same small set of scenes.
# Anything not listed falls back to f"Som de Chuva -- {scene}" with the
# default rain-cloud emoji, so a new scene added later still gets an
# on-brand title without this table needing to change in lockstep.
HOOK_BY_SCENE: dict[str, tuple[tuple[str, ...], str]] = {
    "deep sleep": (
        (
            "Chuva Forte e Trovão ao Longe para Dormir Profundamente",
            "Trovão Suave e Chuva para Dormir a Noite Toda",
            "Som de Chuva e Trovão para Sono Profundo",
            "Chuva Noturna e Trovão Distante para Dormir",
        ),
        "\U0001f634",
    ),
    "power nap": (
        (
            "Som de Chuva para uma Soneca Rápida",
            "Chuva Calmante para Soneca de 20 Minutos",
            "Trovão ao Longe para uma Soneca Revigorante",
            "Som de Chuva Suave para Descansar Rápido",
        ),
        "\U0001f4a4",
    ),
    "insomnia": (
        (
            "Trovão ao Longe e Chuva para Aliviar a Insônia",
            "Chuva e Trovão para Quem Não Consegue Dormir",
            "Som de Chuva para Combater a Insônia",
            "Trovão Distante e Chuva para Noites de Insonia",
        ),
        "\U0001f329️",
    ),
    "focus": (
        (
            "Som de Chuva para Estudar e Focar",
            "Chuva e Trovão para Concentracao e Trabalho",
            "Som de Chuva para Focar sem Distrações",
            "Trovão ao Longe para Ambiente de Estudo",
        ),
        "\U0001f4d6",
    ),
    "white noise": (
        (
            "Ruído Branco de Chuva -- Bloqueie as Distrações",
            "Som de Chuva como Ruído Branco para Foco",
            "Chuva Constante -- Ruído Branco para Estudo",
            "Trovão Distante e Ruído Branco de Chuva",
        ),
        "\U0001f50a",
    ),
    "reading": (
        (
            "Chuva na Janela -- Ambiente Aconchegante para Leitura",
            "Som de Chuva na Janela para Ler Tranquilo",
            "Trovão ao Longe e Chuva para Leitura",
            "Chuva e Vento na Janela -- Leitura Aconchegante",
        ),
        "\U0001f4da",
    ),
    "anxiety relief": (
        (
            "Som de Chuva Calmante para Aliviar a Ansiedade",
            "Chuva Suave para Acalmar a Ansiedade",
            "Trovão ao Longe para Relaxar e Aliviar a Ansiedade",
            "Som de Chuva para Tranquilizar a Mente",
        ),
        DEFAULT_EMOJI,
    ),
    "meditation": (
        (
            "Som de Chuva para Meditação e Mindfulness",
            "Chuva e Trovão para Meditar em Paz",
            "Som de Chuva para Relaxamento e Meditação",
            "Trovão Distante para Meditação Profunda",
        ),
        "\U0001f9d8",
    ),
    "baby sleep": (
        (
            "Som de Chuva Suave para Ajudar o Bebê a Dormir",
            "Chuva Calmante para Dormir o Bebê",
            "Trovão ao Longe para Sono do Bebê",
            "Som de Chuva para Bebê Dormir Tranquilo",
        ),
        "\U0001f37c",
    ),
    "tinnitus": (
        (
            "Som de Chuva para Mascarar o Zumbido no Ouvido",
            "Chuva Constante para Aliviar Tinnitus",
            "Ruído Branco de Chuva para Zumbido no Ouvido",
            "Som de Chuva para Confortar Ouvidos Sensíveis",
        ),
        DEFAULT_EMOJI,
    ),
    "night drive": (
        (
            "Chuva no Vidro do Carro -- Ambiente de Viagem Noturna",
            "Som de Chuva no Carro à Noite",
            "Trovão ao Longe e Chuva no Vidro do Carro",
            "Chuva Noturna no Carro para Relaxar",
        ),
        "\U0001f697",
    ),
    "cabin": (
        (
            "Chuva no Telhado da Cabana -- Ambiente Aconchegante de Tempestade",
            "Trovão e Chuva no Telhado de Cabana",
            "Som de Chuva no Telhado para Dormir Aconchegado",
            "Chuva na Cabana -- Ambiente de Tempestade",
        ),
        "\U0001f3d5️",
    ),
}


def branded_title(scene: str, *, suffix: str = "") -> str:
    """Build "{hook} [suffix] -- Amber Hours {emoji}" for a storm scene.

    A random hook is chosen from the scene's title pool to reduce
    collisions when many videos target the same search intent.

    `suffix` is free text inserted before the brand dash (e.g. a duration
    like "(3 Horas)").
    """
    hooks, emoji = HOOK_BY_SCENE.get(scene.lower(), ((f"Som de Chuva -- {scene}",), DEFAULT_EMOJI))
    hook = random.choice(hooks)
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
