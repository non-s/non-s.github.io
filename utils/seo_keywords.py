"""
utils/seo_keywords.py — Keywords e padrões de títulos otimizados para YouTube.

Em ingles: o nicho pet+jazz e dominado por volume de busca em ingles
("relaxing music for cats/dogs", "pet anxiety music") - o conteudo em si
(visual + instrumental) nao depende de idioma, entao ingles maximiza alcance.
"""

from __future__ import annotations

import json
import logging
import random
import textwrap
from pathlib import Path
from typing import Literal

from utils.channel_config import active_channel
from utils.paths import data_dir

log = logging.getLogger(__name__)


def _title_pattern_performance_file() -> Path:
    """Caminho de title_pattern_performance.json no diretorio do canal ativo."""
    return data_dir() / "title_pattern_performance.json"

# YouTube aceita ate 15 hashtags, mas descricoes com muitas leem como spam;
# 8 cobre marca + animal + musica + formato sem exagerar.
_MAX_HASHTAGS = 8

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
    "emocao": ["#Relaxation", "#Peaceful", "#Calm", "#WellBeing", "#Zen", "#Cute"],
    "formato": ["#Shorts", "#YouTubeShorts", "#RelaxingVideo", "#ASMR"],
    "nicho": ["#CatLover", "#DogLover", "#PetLover", "#JazzLover", "#MusicForPets"],
}


def _title_pattern_weights() -> dict[str, float]:
    """Le _data/title_pattern_performance.json (gerado por collect_analytics.py
    a partir de views reais por padrao de titulo). Ausente/corrompido = sem
    preferencia. Mesmo mecanismo de utils.content_strategy._scene_weights,
    so que indexado pelo texto do padrao (title_pattern) em vez da cena -
    title_pattern ja era gravado em video_tags.json desde que
    generate_title_with_pattern existe, mas nunca era lido de volta."""
    try:
        data = json.loads(_title_pattern_performance_file().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        log.debug("title_pattern_performance.json ausente/corrompido: %s", exc)
        return {}


def pick_title_pattern(kind: Literal["short", "horizontal", "live"]) -> str:
    """Seleciona um padrão de título otimizado para o formato.

    Quando ha dados reais de performance (title_pattern_performance.json),
    a escolha e ponderada por eles em vez de puramente uniforme - padroes
    que historicamente tiveram mais views por video ficam mais provaveis,
    sem nunca zerar a chance dos outros (ver _MIN_WEIGHT em
    collect_analytics.py).
    """
    patterns = active_channel.title_patterns.get(kind, active_channel.title_patterns["short"])
    weights_by_pattern = _title_pattern_weights()
    if not weights_by_pattern:
        return random.choice(patterns)
    weights = [weights_by_pattern.get(p, 1.0) for p in patterns]
    return random.choices(patterns, weights=weights, k=1)[0]


def generate_title_with_pattern(
    animal: str,
    acao: str,
    estilo_musical: str,
    kind: Literal["short", "horizontal", "live"],
    emoji: str,
    duracao: int | None = None,
    pattern: str | None = None,
) -> tuple[str, str]:
    """Gera título otimizado e retorna tambem o padrao usado (para tracking).

    Guardar qual padrao gerou qual titulo e o que falta pra algum dia
    correlacionar performance (views/likes) com o padrao - hoje generate_title()
    descartava essa informacao, entao nao havia como saber depois.

    ``pattern`` (quando fornecido por utils/slot_optimizer) obriga o uso do
    padrao passado; caso contrario, sorteia/pondera como antes.
    """
    if pattern:
        # Valida que o padrao pertence ao canal; se nao, ignora e sortea.
        all_patterns = active_channel.title_patterns.get(kind, active_channel.title_patterns["short"])
        if pattern in all_patterns:
            chosen = pattern
        else:
            log.debug("Padrao %r nao existe para kind=%s; sorteando.", pattern, kind)
            chosen = pick_title_pattern(kind)
    else:
        chosen = pick_title_pattern(kind)

    # Seleciona adjetivos relevantes
    kws = active_channel.seo_keywords
    adjetivos_cuteness = random.sample(kws["cuteness"], 2)
    adjetivos_relax = random.sample(kws["relaxation"], 1)
    adjetivo = random.choice(adjetivos_cuteness + adjetivos_relax)

    # Seleciona emoção/benefício
    emocao = random.choice(list(EMOCAO_BENEFICIOS.keys()))
    beneficio = random.choice(EMOCAO_BENEFICIOS[emocao])

    # Tenta preencher o padrão, caindo para versão simplificada se falhar
    try:
        title = chosen.format(
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

    return title, chosen


def generate_title(
    animal: str,
    acao: str,
    estilo_musical: str,
    kind: Literal["short", "horizontal", "live"],
    emoji: str,
    duracao: int | None = None,
) -> str:
    """Gera título otimizado usando padrões de alta performance."""
    title, _pattern = generate_title_with_pattern(
        animal=animal, acao=acao, estilo_musical=estilo_musical,
        kind=kind, emoji=emoji, duracao=duracao,
    )
    return title


def generate_description(
    hook: str,
    kind: Literal["short", "horizontal", "live"],
    hashtags: list[str],
    include_cta: bool = True,
) -> tuple[str, str]:
    """Gera descrição otimizada com SEO e CTAs.

    Retorna (description, cta_text) para que o caller possa gravar qual CTA
    foi usado (A/B testing de CTA vs. inscritos — ver collect_analytics).
    """
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
    cta_text = ""
    if include_cta:
        cta_text = random.choice(CTAS)
        cta = "\n\n" + cta_text

    # Hashtags
    hashtags_str = " ".join(hashtags[:_MAX_HASHTAGS])  # YouTube aceita ate 15, mas mais que ~8 comeca a ler como spam

    return f"{intro}{corpo}{cta}\n\n{hashtags_str}", cta_text


def generate_hashtags(
    animal: str,
    categoria: str = "cuteness",
    kind: Literal["short", "horizontal", "live"] = "short",
) -> list[str]:
    """Gera conjunto estratégico de hashtags em camadas.

    Orcamento fixo por camada (2+2+1+1+2=8=_MAX_HASHTAGS) para que as 5
    camadas (brand, animal, musica, categoria, formato) sempre apareçam -
    fatias maiores nas primeiras camadas comiam o orcamento inteiro antes
    das ultimas serem consideradas (formato nunca sobrevivia ao slice final).
    """
    hashtags = []

    # Camada 1: Brand (sempre presente)
    hashtags.extend(HASHTAGS_POR_CATEGORIA["brand"][:2])

    # Camada 2: Animal específico
    if "cat" in animal.lower() or "gato" in animal.lower():
        hashtags.extend(["#Cats", "#CatLover"])
    elif "dog" in animal.lower() or "cachorro" in animal.lower():
        hashtags.extend(["#Dogs", "#DogLover"])
    else:
        hashtags.extend(HASHTAGS_POR_CATEGORIA["animal"][:2])

    # Camada 3: Música
    hashtags.extend(HASHTAGS_POR_CATEGORIA["musica"][:1])

    # Camada 4: Emoção/Categoria
    if categoria in ("cuteness", "fofura"):
        hashtags.extend(["#Cute"])
    elif categoria in ("relaxation", "relaxamento"):
        hashtags.extend(HASHTAGS_POR_CATEGORIA["emocao"][:1])
    elif categoria in ("fun", "diversao"):
        hashtags.extend(["#Fun"])

    # Camada 5: Formato
    if kind == "short":
        hashtags.extend(["#Shorts", "#YouTubeShorts"])
    elif kind == "live":
        hashtags.extend(["#Live", "#LiveStream"])

    # Remove duplicatas e aplica o teto final (camadas ja somam _MAX_HASHTAGS)
    hashtags = list(dict.fromkeys(hashtags))[:_MAX_HASHTAGS]

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
