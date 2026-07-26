"""
utils/seo_keywords.py — Keywords e padrões de títulos otimizados para YouTube.

Em ingles: o nicho pet+jazz e dominado por volume de busca em ingles
("relaxing music for cats/dogs", "pet anxiety music") - o conteudo em si
(visual + instrumental) nao depende de idioma, entao ingles maximiza alcance.
"""

from __future__ import annotations

import random
import textwrap
from typing import Literal

# Keywords de alta performance para o nicho pet + jazz
HIGH_PERFORMANCE_KEYWORDS = {
    "cuteness": [
        "cute", "adorable", "charming", "sweet",
        "precious", "lovable", "gentle", "tender"
    ],
    "relaxation": [
        "relaxing", "calm", "calming", "soothing", "peaceful",
        "gentle", "cozy", "tranquil", "mellow", "zen"
    ],
    "fun": [
        "funny", "playful", "silly", "energetic",
        "curious", "spontaneous", "lively", "cheerful"
    ],
    "music": [
        "jazz", "smooth jazz", "relaxing jazz", "ambient music",
        "jazz instrumental", "coffee shop jazz", "lounge jazz", "soft jazz"
    ]
}

# Padrões de títulos que performam bem (testados A/B)
TITLE_PATTERNS: dict[str, list[str]] = {
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
    ]
}

# Emoções e benefícios que geram engajamento
EMOCAO_BENEFICIOS = {
    "happy": ["joy", "happiness", "smiles", "well-being"],
    "calm": ["peace", "tranquility", "serenity", "relaxation"],
    "comfort": ["coziness", "comfort", "warmth", "love"],
    "nostalgia": ["nostalgia", "memories", "fond memories"],
    "focus": ["concentration", "focus", "productivity", "clarity"],
}

# CTAs (Call-to-Action) para descrições
CTAS = [
    "🐾 Subscribe for more cuteness every day!",
    "🎷 Hit the bell so you never miss a video!",
    "💬 Comment which pet you want to see tomorrow!",
    "👍 Leave a like if this brought some peace to your day!",
    "🔗 Share with someone who needs a zen moment!",
    "📱 Follow @PataJazz for exclusive content!",
]

# Hashtags estratégicas por categoria
HASHTAGS_POR_CATEGORIA = {
    "brand": ["#PataJazz", "#CatJazz", "#DogJazz", "#PetJazz"],
    "animal": ["#Cats", "#Dogs", "#Kittens", "#Puppies", "#Pets", "#Animals"],
    "musica": ["#Jazz", "#RelaxingMusic", "#SmoothJazz", "#JazzInstrumental", "#AmbientMusic"],
    "emocao": ["#Cute", "#Relaxation", "#Peaceful", "#Calm", "#WellBeing", "#Zen"],
    "formato": ["#Shorts", "#YouTubeShorts", "#RelaxingVideo", "#ASMR"],
    "nicho": ["#CatLover", "#DogLover", "#PetLover", "#JazzLover", "#MusicForPets"],
}


def pick_title_pattern(kind: Literal["short", "horizontal", "live"]) -> str:
    """Seleciona um padrão de título otimizado para o formato."""
    patterns = TITLE_PATTERNS.get(kind, TITLE_PATTERNS["short"])
    return random.choice(patterns)


def generate_title(
    animal: str,
    acao: str,
    estilo_musical: str,
    kind: Literal["short", "horizontal", "live"],
    emoji: str,
    duracao: int | None = None,
) -> str:
    """Gera título otimizado usando padrões de alta performance."""
    pattern = pick_title_pattern(kind)

    # Seleciona adjetivos relevantes
    adjetivos_cuteness = random.sample(HIGH_PERFORMANCE_KEYWORDS["cuteness"], 2)
    adjetivos_relax = random.sample(HIGH_PERFORMANCE_KEYWORDS["relaxation"], 1)
    adjetivo = random.choice(adjetivos_cuteness + adjetivos_relax)

    # Seleciona emoção/benefício
    emocao = random.choice(list(EMOCAO_BENEFICIOS.keys()))
    beneficio = random.choice(EMOCAO_BENEFICIOS[emocao])

    # Tenta preencher o padrão, caindo para versão simplificada se falhar
    try:
        title = pattern.format(
            emoji=emoji,
            animal=animal,
            acao=acao,
            estilo_musical=estilo_musical,
            adjetivo=adjetivo,
            duracao=duracao or 4,
            emocao=beneficio,
        )
    except KeyError:
        # Fallback para pattern mais simples
        title = f"{adjetivo.title()} {animal} + {estilo_musical} {emoji}"

    # Limpeza final
    title = " ".join(title.split())  # Remove espaços duplos
    title = title.strip()

    # Garante que está dentro do limite (100 chars para YouTube).
    # Usa textwrap.shorten para cortar em boundary de palavra quando possivel.
    if len(title) > 100:
        title = textwrap.shorten(title, width=100, placeholder="...")
        # textwrap.shorten corta no meio; se ficar muito curto, fallback simples.
        if not title or len(title) > 100:
            title = title[:97] + "..."

    return title


def generate_description(
    hook: str,
    kind: Literal["short", "horizontal", "live"],
    hashtags: list[str],
    include_cta: bool = True,
) -> str:
    """Gera descrição otimizada com SEO e CTAs."""
    # Introdução com keywords
    intro_templates = [
        f"{hook} 🐾 Welcome to Pata Jazz, where cats and dogs meet the perfect jazz!",
        f"{hook} 🎷 Relax, enjoy, and fall in love with this unique blend of cuteness and music!",
        f"{hook} 💫 Your daily moment of peace with adorable pets and soft jazz!",
    ]
    intro = random.choice(intro_templates)

    # Corpo da descrição (varia por formato)
    if kind == "short":
        corpo = (
            "\n\n✨ This Short was made to bring a moment of joy to your day! "
            "Cute cats and dogs + relaxing jazz = guaranteed happiness! 🐱🐶"
        )
    elif kind == "horizontal":
        corpo = (
            "\n\n✨ Enjoy this relaxing video with adorable pets and a carefully picked jazz soundtrack. "
            "Perfect for:\n"
            "  • Unwinding after a tiring day\n"
            "  • Focusing while you study or work\n"
            "  • Falling asleep peacefully\n"
            "  • Just enjoying the cuteness!"
        )
    else:  # live
        corpo = (
            "\n\n🔴 LIVE 24/7 STREAM!\n"
            "Leave this live running while you work, study or relax. "
            "There's always a cute pet and quality jazz waiting for you! 🎵"
        )

    # CTA (opcional)
    cta = ""
    if include_cta:
        cta_text = random.choice(CTAS)
        cta = "\n\n" + cta_text

    # Hashtags
    hashtags_str = " ".join(hashtags[:15])  # YouTube limita a 15

    return f"{intro}{corpo}{cta}\n\n{hashtags_str}"


def generate_hashtags(
    animal: str,
    categoria: str = "cuteness",
    kind: Literal["short", "horizontal", "live"] = "short",
) -> list[str]:
    """Gera conjunto estratégico de hashtags em camadas."""
    hashtags = []

    # Camada 1: Brand (sempre presente)
    hashtags.extend(HASHTAGS_POR_CATEGORIA["brand"][:2])

    # Camada 2: Animal específico
    if "cat" in animal.lower() or "gato" in animal.lower():
        hashtags.extend(["#Cats", "#Kittens", "#CatLover"])
    elif "dog" in animal.lower() or "cachorro" in animal.lower():
        hashtags.extend(["#Dogs", "#Puppies", "#DogLover"])
    else:
        hashtags.extend(HASHTAGS_POR_CATEGORIA["animal"][:2])

    # Camada 3: Música
    hashtags.extend(HASHTAGS_POR_CATEGORIA["musica"][:3])

    # Camada 4: Emoção/Categoria
    if categoria in ("cuteness", "fofura"):
        hashtags.extend(["#Cute", "#CutePets", "#AdorableAnimal"])
    elif categoria in ("relaxation", "relaxamento"):
        hashtags.extend(HASHTAGS_POR_CATEGORIA["emocao"][:3])
    elif categoria in ("fun", "diversao"):
        hashtags.extend(["#Fun", "#FunnyPets", "#FunnyAnimals"])

    # Camada 5: Formato
    if kind == "short":
        hashtags.extend(["#Shorts", "#YouTubeShorts"])
    elif kind == "live":
        hashtags.extend(["#Live", "#LiveStream", "#247"])

    # Remove duplicatas e limita a 15
    hashtags = list(dict.fromkeys(hashtags))[:15]

    return hashtags


def optimize_for_search(title: str, description: str) -> tuple[str, str]:
    """Otimiza título e descrição para busca do YouTube."""
    # Palavras-chave primárias para o nicho
    primary_keywords = [
        "cat jazz", "dog jazz", "relaxing pet music",
        "music for pets", "cute kitten", "cute puppy",
        "calming music for dogs", "relaxing music for cats",
    ]

    # Verifica se pelo menos uma keyword primária está presente
    title_lower = title.lower()
    has_keyword = any(kw in title_lower for kw in primary_keywords)

    if not has_keyword:
        # Adiciona keyword ao final do título se couber
        keyword = random.choice(primary_keywords)
        if len(title) + len(keyword) + 2 <= 90:
            title = f"{title}, {keyword}"

    # Adiciona keywords semanticamente relacionadas à descrição
    related_terms = [
        "relaxation", "meditation", "studying", "working",
        "focus", "inner peace", "well-being",
    ]

    if not any(term in description.lower() for term in related_terms):
        term = random.choice(related_terms)
        description += f"\n\nGreat for moments of {term}."

    return title, description
