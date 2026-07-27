"""
utils/channel_config.py — abstracao de multi-canal.

Permite rodar multiplos canais (Pata Jazz, e futuros Pata Lofi, Pata
Classical...) no mesmo repo. Hoje so PATA_JAZZ existe; novos canais podem
ser adicionados ao registry CHANNELS sem mudar os modulos consumidores
(animal_branding, playlist_manager, seo_keywords, upload_youtube,
live_broadcast), que leem de `active_channel`.

Backward compat: `active_channel` nasce como PATA_JAZZ com os mesmos
valores que antes eram hardcoded em cada modulo. Scripts e testes
existentes continuam funcionando sem mudanca - so chame set_channel()
se quiser trocar explicitamente.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChannelConfig:
    """Configuracao autocontida de um canal.

    Cada canal define sua marca, tags, playlists, keywords, prompts de IA
    e mapeamentos de cena/mood. Tudo que antes era hardcoded "Pata Jazz"
    em utils.animal_branding, utils.playlist_manager, utils.seo_keywords,
    upload_youtube e live_broadcast vive aqui agora.
    """

    name: str  # "Pata Jazz"
    brand_prefix: str  # "Pata Jazz |"
    hashtag_brand: list[str]  # ["#PataJazz", "#CatJazz", ...]
    base_tags: list[str]  # ["Pata Jazz", "cat", "dog", "jazz", ...]
    playlists_by_mood: dict[str, str]  # {"relax": "Pata Jazz | Relaxar e Dormir"}
    playlists_by_kind: dict[str, str]  # {"short": "Pata Jazz | Shorts"}
    live_tags: list[str]  # ["relaxing music for dogs", ...]
    live_title_prompt: str  # prompt base para IA gerar titulo de live
    seo_keywords: dict[str, list[str]]  # HIGH_PERFORMANCE_KEYWORDS
    title_patterns: dict[str, list[str]]
    emojis: dict[str, str]  # {"brand": "...", ...}
    scene_categories: dict[str, list[str]]
    hourly_mood: dict[int, str]
    default_description: str


PATA_JAZZ: ChannelConfig = ChannelConfig(
    name="Pata Jazz",
    brand_prefix="Pata Jazz |",
    hashtag_brand=["#PataJazz", "#CatJazz", "#DogJazz", "#PetJazz"],
    base_tags=["Pata Jazz", "cat", "dog", "jazz", "cute", "relaxing"],
    playlists_by_mood={
        "relax": "Pata Jazz | Relaxar e Dormir",
        "fofura": "Pata Jazz | Fofura Diaria",
        "diversao": "Pata Jazz | Pets Felizes",
    },
    playlists_by_kind={
        "short": "Pata Jazz | Shorts",
        "horizontal": "Pata Jazz | Videos Completos",
    },
    live_tags=[
        "relaxing music for dogs",
        "calming music for cats",
        "jazz for pets",
        "dog anxiety music",
        "cat sleep music",
        "music for pets",
        "background music for cats and dogs",
        "study jazz music",
        "cats and dogs live stream",
        "24/7 live stream",
        "Pata Jazz",
    ],
    live_title_prompt=(
        "Create a short, warm YouTube live stream title (max 80 characters) for a "
        "24/7 looping live stream of cats and dogs with relaxing jazz music playing. "
        "Target searches like 'calming music for dogs' or 'relaxing music for cats'. "
        "Return ONLY the title text, no quotes."
    ),
    seo_keywords={
        "cuteness": [
            "cute", "adorable", "charming", "sweet",
            "precious", "lovable", "gentle", "tender",
        ],
        "relaxation": [
            "relaxing", "calm", "calming", "soothing", "peaceful",
            "gentle", "cozy", "tranquil", "mellow", "zen",
        ],
        "fun": [
            "funny", "playful", "silly", "energetic",
            "curious", "spontaneous", "lively", "cheerful",
        ],
        "music": [
            "jazz", "smooth jazz", "relaxing jazz", "ambient music",
            "jazz instrumental", "coffee shop jazz", "lounge jazz", "soft jazz",
        ],
    },
    title_patterns={
        "short": [
            "{emoji} {adjetivo} {animal} + {estilo_musical}",
            "When a {animal} {acao} to {estilo_musical} 🎵",
            "{adjetivo} {animal} enjoying {estilo_musical} {emoji}",
            "POV: a {animal} {acao} to your daily {estilo_musical}",
            "The {adjetivo} {animal} you needed today {emoji}",
        ],
        "horizontal": [
            "{adjetivo} {animal} + {estilo_musical} for {duracao} minutes",
            "Relax with a {adjetivo} {animal} and {estilo_musical}",
            "{estilo_musical} + {adjetivo} {animal} to relax",
            "A {adjetivo} {animal} ambience with {estilo_musical}",
            "{adjetivo} session: {animal} + {estilo_musical} {emoji}",
        ],
        "live": [
            "🔴 LIVE: {adjetivo} {animal} + {estilo_musical} 24/7",
            "{estilo_musical} Radio with a {adjetivo} {animal} - LIVE",
            "LIVE: Relax with a {animal} and {estilo_musical} all day",
            "🔴 LIVE: Non-Stop {estilo_musical} + {adjetivo} {animal}",
        ],
    },
    emojis={"brand": "🐾🎷"},
    scene_categories={
        "fofura": ["cat", "kitten", "puppy", "dog", "sleepy cat"],
        "diversao": ["playful dog", "cat playing", "puppy playing", "dog relaxing"],
        "relax": ["sleepy cat", "sleepy dog", "cat relaxing", "dog relaxing"],
    },
    hourly_mood={
        h: ("diversao" if 6 <= h < 12 else "fofura" if 12 <= h < 18 else "relax")
        for h in range(24)
    },
    default_description=(
        "A 24/7 live stream of cats and dogs with relaxing jazz music - great "
        "background sound for calming an anxious pet, studying, working or sleeping."
    ),
)


CHANNELS: dict[str, ChannelConfig] = {
    "pata_jazz": PATA_JAZZ,
}

active_channel: ChannelConfig = PATA_JAZZ


def set_channel(name: str) -> None:
    """Troca o canal ativo pelo nome (chave de CHANNELS).

    Levanta KeyError se o canal nao estiver registrado. Use
    set_channel("pata_jazz") para restaurar o default.
    """
    global active_channel
    if name not in CHANNELS:
        raise KeyError(f"Canal nao registrado: {name!r}. Disponiveis: {sorted(CHANNELS)}")
    active_channel = CHANNELS[name]
