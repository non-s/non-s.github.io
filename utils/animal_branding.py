"""Shared title vocabulary for the cute-animal jazz Shorts pillar (chat,
2026-07-22).

Brand name: "Pata Jazz" ("paw jazz") -- deliberately NOT "Amber Hours".
That name already means "real rain/thunder ambience for sleep" to anyone
who has seen the channel; reusing it on playful, upbeat cute-animal
content would confuse both audiences (a sleep-sound viewer expects calm,
a pet-content viewer expects fun) and dilute what "Amber Hours" already
stands for. Same channel/account for now, but its own on-screen identity,
same principle the rain pillar itself used to justify NOT reusing the
even-earlier "Wild Brief" nature-facts name (see docs/adr history).

Content language is Brazilian Portuguese (pt-BR), matching the channel's
existing language pivot -- hooks below are real pt-BR search phrases
("gatinho fofo", "cachorro fofo", ...), not machine-transliterated
English pet-content tags.
"""

from __future__ import annotations

BRAND_SUFFIX = "Pata Jazz"
DEFAULT_EMOJI = "\U0001f43e"  # paw prints

# scene -> (hook phrase, emoji). Every hook is phrased the way someone
# actually searches for cute-animal Shorts in pt-BR. Anything not listed
# falls back to f"Fofura Total -- {scene}" with the default paw emoji.
HOOK_BY_SCENE: dict[str, tuple[str, str]] = {
    "cat": ("Gatinho Fofo Fazendo Manha", "\U0001f431"),
    "kitten": ("Filhote de Gato Mais Fofo do Dia", "\U0001f408"),
    "puppy": ("Filhote de Cachorro Fofo Demais", "\U0001f436"),
    "dog": ("Cachorro Fofo Brincando", "\U0001f415"),
    "bunny": ("Coelhinho Fofo -- Impossível Não Sorrir", "\U0001f430"),
    "hamster": ("Hamster Fofinho Fazendo a Festa", "\U0001f439"),
    "funny": ("Bicho de Estimação Aprontando", "\U0001f602"),
    "adorable": ("Fofura Nível Máximo", DEFAULT_EMOJI),
}


def branded_title(scene: str, *, suffix: str = "") -> str:
    """Build "{hook} [suffix] -- Pata Jazz {emoji}" for an animal scene."""
    hook, emoji = HOOK_BY_SCENE.get(scene.lower(), (f"Fofura Total -- {scene}", DEFAULT_EMOJI))
    parts = [hook] + ([suffix] if suffix else [])
    return f"{' '.join(parts)} -- {BRAND_SUFFIX} {emoji}"


# Keyword -> playlist bucket, checked IN ORDER against the (already-
# branded) title text -- same design as utils/storm_branding.py's
# identical function.
_DEFAULT_PLAYLIST_BUCKET = "Fofura Total"
_PLAYLIST_BUCKET_SIGNALS: tuple[tuple[str, str], ...] = (
    ("gat", "Gatinhos Fofos"),
    ("cachorr", "Cachorros Fofos"),
    ("coelh", "Coelhinhos Fofos"),
    ("hamster", "Hamsters Fofinhos"),
    ("aprontando", "Pets Aprontando"),
)


def playlist_bucket_for_title(title: str) -> str:
    """Which animal playlist a published Short's (already branded) title
    belongs in -- see _PLAYLIST_BUCKET_SIGNALS."""
    text = (title or "").lower()
    for signal, bucket in _PLAYLIST_BUCKET_SIGNALS:
        if signal in text:
            return bucket
    return _DEFAULT_PLAYLIST_BUCKET
