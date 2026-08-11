"""
utils/channel_config.py — configuração do canal Pata Jazz.

Mantém a abstração ChannelConfig para facilitar futuras mudanças, mas hoje
o projeto opera com um único canal: Pata Jazz.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChannelConfig:
    """Configuração autocontida do canal.

    Define marca, tags, playlists, keywords, prompts de IA e mapeamentos
    de cena/mood. Tudo que antes era hardcoded "Pata Jazz" em outros módulos
    vive aqui agora.
    """

    name: str  # "Pata Jazz"
    slug: str  # "pata_jazz"
    brand_prefix: str  # "Pata Jazz |"
    hashtag_brand: list[str]  # ["#PataJazz", "#CatJazz", ...]
    base_tags: list[str]  # ["Pata Jazz", "cat", "dog", "jazz", ...]
    playlists_by_mood: dict[str, str]  # {"relax": "Pata Jazz | Relaxar e Dormir"}
    playlists_by_kind: dict[str, str]  # {"short": "Pata Jazz | Shorts"}
    seo_keywords: dict[str, list[str]]  # HIGH_PERFORMANCE_KEYWORDS
    title_patterns: dict[str, list[str]]
    emojis: dict[str, str]  # {"brand": "...", ...}
    scene_categories: dict[str, list[str]]
    hourly_mood: dict[int, str]
    default_description: str


PATA_JAZZ: ChannelConfig = ChannelConfig(
    name="Pata Jazz",
    slug="pata_jazz",
    brand_prefix="Pata Jazz |",
    hashtag_brand=["#PataJazz", "#CatJazz", "#DogJazz", "#PetJazz"],
    base_tags=["Pata Jazz", "cat", "dog", "jazz", "cute", "relaxing"],
    playlists_by_mood={
        "relax": "Pata Jazz | Quiet & Cozy",
        # Legacy mood keys are kept for pipeline compatibility. Public labels
        # must describe a scene, never an outcome for an animal.
        "sleep": "Pata Jazz | Night & Cozy",
        "anxiety": "Pata Jazz | Gentle Moments",
        "fofura": "Pata Jazz | Cute & Cozy",
        "diversao": "Pata Jazz | Happy Pets",
        "home_alone": "Pata Jazz | Home Alone",
        "thunder": "Pata Jazz | Thunder & Fireworks",
        "cat_playlist": "Pata Jazz | For Cats",
        "dog_playlist": "Pata Jazz | For Dogs",
    },
    playlists_by_kind={
        "short": "Pata Jazz | Shorts",
        "long": "Pata Jazz | Long-Form",
    },
    seo_keywords={
        "cuteness": [
            "cute", "adorable", "charming", "sweet",
            "precious", "lovable", "gentle", "tender",
        ],
        "relaxation": [
            "relaxing", "calm", "calming", "soothing", "peaceful",
            "gentle", "cozy", "tranquil", "mellow", "zen",
        ],
        "gentle": [
            "gentle", "quiet", "cozy", "soft", "unhurried", "at home",
        ],
        "sleep": [
            "night jazz", "bedtime", "naptime", "dreamy", "night music", "sleepy",
        ],
        "fun": [
            "funny", "playful", "silly", "energetic",
            "curious", "spontaneous", "lively", "cheerful",
        ],
        "music": [
            "jazz", "smooth jazz", "relaxing jazz", "ambient music",
            "jazz instrumental", "coffee shop jazz", "lounge jazz", "soft jazz",
            "lofi jazz", "jazz for pets", "music for pets",
        ],
    },
    title_patterns={
        "short": [
            "{keyword_primary} 🐾 {emoji}",
            "{keyword_long_tail} | a cozy {animal} moment {emoji}",
            "{keyword_animal} | gentle {animal} + jazz {emoji}",
            "{keyword_primary} in {seconds} seconds {emoji}",
            "{trigger} {emoji}",
            "A gentle {keyword_style} moment with your {animal} {emoji}",
            "A little {keyword_style} for your {animal} {emoji}",
            "{scenario}? A quiet {animal} + jazz moment {emoji}",
            # A5: padrões que promovem playlists temáticas explicitamente.
            "{scenario}? Calm music for {animal}s — full playlist {emoji}",
            "The {keyword_style} playlist for cozy pet moments {emoji}",
            "A cozy playlist with a {animal} | {keyword_long_tail} {emoji}",
        ],
    },
    emojis={"brand": "🐾🎷", "sleep": "💤", "calm": "😴", "love": "💛"},
    scene_categories={
        "fofura": ["cat", "kitten", "puppy", "dog", "sleepy cat"],
        "diversao": ["playful dog", "cat playing", "puppy playing", "dog relaxing"],
        "relax": ["sleepy cat", "sleepy dog", "cat relaxing", "dog relaxing"],
        "anxiety": ["dog relaxing", "cat relaxing", "sleepy puppy", "sleepy cat"],
        "sleep": ["sleepy cat", "sleepy dog", "cat napping", "dog napping"],
    },
    hourly_mood={
        h: (
            "sleep" if 0 <= h < 6 else
            "relax" if 6 <= h < 9 else
            "diversao" if 9 <= h < 12 else
            "fofura" if 12 <= h < 15 else
            "relax" if 15 <= h < 19 else
            "sleep" if 19 <= h < 24 else "relax"
        )
        for h in range(24)
    },
    default_description=(
        "Soft jazz and gentle pet moments for quieter homes. Pata Jazz pairs "
        "calm instrumental music with real cats and dogs — a cozy pause for "
        "pet parents, study sessions, and winding down."
    ),
)


CHANNELS: dict[str, ChannelConfig] = {
    "pata_jazz": PATA_JAZZ,
}

active_channel: ChannelConfig = PATA_JAZZ


def set_channel(name: str) -> None:
    """Troca o canal ativo pelo nome (chave de CHANNELS).

    Levanta KeyError se o canal não estiver registrado.
    """
    global active_channel
    if name not in CHANNELS:
        raise KeyError(f"Canal não registrado: {name!r}. Disponíveis: {sorted(CHANNELS)}")
    active_channel = CHANNELS[name]


def set_channel_from_env() -> None:
    """Lê YOUTUBE_CHANNEL env var e ativa o canal correspondente.

    Não faz nada se a env var não estiver definida (mantém Pata Jazz default).
    """
    import os

    channel = os.environ.get("YOUTUBE_CHANNEL", "").strip().lower()
    if channel:
        set_channel(channel)
