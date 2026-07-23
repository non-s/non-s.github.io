"""
utils/seo_keywords.py — Keywords e padrões de títulos otimizados para YouTube.
"""

from __future__ import annotations

import random
from typing import Literal

# Keywords de alta performance para o nicho pet + jazz
HIGH_PERFORMANCE_KEYWORDS = {
    "fofura": [
        "fofo", "fofinho", "adorável", "charmoso", "doce",
        "tíerno", "encantador", "gracioso", "meigo", "amoroso"
    ],
    "relaxamento": [
        "relaxante", "calmo", "tranquilo", "sereno", "pacífico",
        "meditativo", "suave", "aconchegante", "reconfortante", "zen"
    ],
    "diversao": [
        "engraçado", "hilário", "divertido", "brincalhão", "travesso",
        "curioso", "espontâneo", "animado", "vibrante", "energético"
    ],
    "musica": [
        "jazz", "smooth jazz", "jazz relaxante", "música ambiente",
        "jazz instrumental", "café jazz", "lounge jazz", "soft jazz"
    ]
}

# Padrões de títulos que performam bem (testados A/B)
TITLE_PATTERNS: dict[str, list[str]] = {
    "short": [
        "{emoji} {adjetivo} {animal} + {estilo_musical}",
        "Quando {animal} {acao} com {estilo_musical} 🎵",
        "{adjetivo} {animal} curtindo {estilo_musical} {emoji}",
        "POV: {animal} {acao} no seu {estilo_musical} diário",
        "O {adjetivo} {animal} que você precisa hoje {emoji}",
    ],
    "horizontal": [
        "{adjetivo} {animal} + {estilo_musical} por {duracao} minutos",
        "Relaxe com {animal} {adjetivo} e {estilo_musical}",
        "{estilo_musical} + {animal} {adjetivo} para relaxar",
        "Ambiente {adjetivo} de {animal} com {estilo_musical}",
        "Sessão {adjetivo}: {animal} + {estilo_musical} {emoji}",
    ],
    "live": [
        "🔴 AO VIVO: {animal} {adjetivo} + {estilo_musical} 24/7",
        "Rádio {estilo_musical} com {animal} {adjetivo} - AO VIVO",
        "LIVE: Relaxe com {animal} e {estilo_musical} o dia todo",
        "🔴 AO VIVO: {estilo_musical} Non-Stop + {animal} {adjetivo}",
    ]
}

# Emoções e benefícios que geram engajamento
EMOCAO_BENEFICIOS = {
    "feliz": ["alegria", "felicidade", "sorriso", "bem-estar"],
    "calmo": ["paz", "tranquilidade", "serenidade", "relaxamento"],
    "conforto": ["aconchego", "conforto", "carinho", "amor"],
    "nostalgia": ["saudade", "memória", "nostalgia", "recordação"],
    "foco": ["concentração", "foco", "produtividade", "clareza"],
}

# CTAs (Call-to-Action) para descrições
CTAS = [
    "🐾 Inscreva-se para mais fofura diária!",
    "🎷 Ative o sininho para não perder nenhum vídeo!",
    "💬 Comente qual bichinho você quer ver amanhã!",
    "👍 Deixe seu like se isso trouxe paz ao seu dia!",
    "🔗 Compartilhe com quem precisa de um momento zen!",
    "📱 Siga @PataJazz para conteúdo exclusivo!",
]

# Hashtags estratégicas por categoria
HASHTAGS_POR_CATEGORIA = {
    "brand": ["#PataJazz", "#GatoJazz", "#CachorroJazz", "#PetJazz"],
    "animal": ["#Gatos", "#Cachorros", "#Gatinhos", "#Cachorrinhos", "#Pets", "#Animais"],
    "musica": ["#Jazz", "#MusicaRelaxante", "#SmoothJazz", "#JazzInstrumental", "#MusicaAmbiente"],
    "emocao": ["#Fofura", "#Relaxamento", "#Paz", "#Tranquilidade", "#BemEstar", "#Zen"],
    "formato": ["#Shorts", "#YouTubeShorts", "#VideoRelaxante", "#ASMR"],
    "nicho": ["#CatLover", "#DogLover", "#PetLover", "#JazzLover", "#MusicaEAnimais"],
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
    adjetivos_fofura = random.sample(HIGH_PERFORMANCE_KEYWORDS["fofura"], 2)
    adjetivos_relax = random.sample(HIGH_PERFORMANCE_KEYWORDS["relaxamento"], 1)
    adjetivo = random.choice(adjetivos_fofura + adjetivos_relax)
    
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
    
    # Garante que está dentro do limite (100 chars para YouTube)
    if len(title) > 100:
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
        f"{hook} 🐾 Bem-vindo ao Pata Jazz, onde gatinhos e cachorrinhos encontram o jazz perfeito!",
        f"{hook} 🎷 Relaxe, curta e se encante com essa combinação única de fofura e música!",
        f"{hook} 💫 Seu momento diário de paz com pets adoráveis e jazz suave!",
    ]
    intro = random.choice(intro_templates)
    
    # Corpo da descrição (varia por formato)
    if kind == "short":
        corpo = (
            "\n\n✨ Este Short foi criado para trazer um momento de alegria ao seu dia! "
            "Gatinhos e cachorrinhos fofos + jazz relaxante = felicidade garantida! 🐱🐶"
        )
    elif kind == "horizontal":
        corpo = (
            "\n\n✨ Aproveite este vídeo relaxante com pets adoráveis e uma trilha de jazz cuidadosamente selecionada. "
            "Perfeito para:\n"
            "  • Relaxar após um dia cansativo\n"
            "  • Focar nos estudos ou trabalho\n"
            "  • Dormir com tranquilidade\n"
            "  • Simplesmente curtir a fofura!"
        )
    else:  # live
        corpo = (
            "\n\n🔴 TRANSMISSÃO AO VIVO 24/7!\n"
            "Deixe esta live rodando enquanto trabalha, estuda ou relaxa. "
            "Sempre terá um bichinho fofo e jazz de qualidade para você! 🎵"
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
    categoria: str = "fofura",
    kind: Literal["short", "horizontal", "live"] = "short",
) -> list[str]:
    """Gera conjunto estratégico de hashtags em camadas."""
    hashtags = []
    
    # Camada 1: Brand (sempre presente)
    hashtags.extend(HASHTAGS_POR_CATEGORIA["brand"][:2])
    
    # Camada 2: Animal específico
    if "cat" in animal.lower() or "gato" in animal.lower():
        hashtags.extend(["#Gatos", "#Gatinhos", "#CatLover"])
    elif "dog" in animal.lower() or "cachorro" in animal.lower():
        hashtags.extend(["#Cachorros", "#Cachorrinhos", "#DogLover"])
    else:
        hashtags.extend(HASHTAGS_POR_CATEGORIA["animal"][:2])
    
    # Camada 3: Música
    hashtags.extend(HASHTAGS_POR_CATEGORIA["musica"][:3])
    
    # Camada 4: Emoção/Categoria
    if categoria == "fofura":
        hashtags.extend(["#Fofura", "#PetsFofos", "#AnimalFofo"])
    elif categoria == "relaxamento":
        hashtags.extend(HASHTAGS_POR_CATEGORIA["emocao"][:3])
    elif categoria == "diversao":
        hashtags.extend(["#Diversao", "#PetsEngracados", "#AnimaisEngracados"])
    
    # Camada 5: Formato
    if kind == "short":
        hashtags.extend(["#Shorts", "#YouTubeShorts"])
    elif kind == "live":
        hashtags.extend(["#Live", "#AoVivo", "#247"])
    
    # Remove duplicatas e limita a 15
    hashtags = list(dict.fromkeys(hashtags))[:15]
    
    return hashtags


def optimize_for_search(title: str, description: str) -> tuple[str, str]:
    """Otimiza título e descrição para busca do YouTube."""
    # Palavras-chave primárias para o nicho
    primary_keywords = [
        "gato jazz", "cachorro jazz", "pet relaxante", 
        "musica para pets", "gatinho fofo", "cachorrinho fofo"
    ]
    
    # Verifica se pelo menos uma keyword primária está presente
    title_lower = title.lower()
    has_keyword = any(kw in title_lower for kw in primary_keywords)
    
    if not has_keyword:
        # Adiciona keyword ao final do título se couber
        keyword = random.choice(primary_keywords)
        if len(title) + len(keyword) + 3 <= 100:
            title = f"{title} | {keyword}"
    
    # Adiciona keywords semanticamente relacionadas à descrição
    related_terms = [
        "relaxamento", "meditação", "estudo", "trabalho",
        "concentração", "paz interior", "bem-estar"
    ]
    
    if not any(term in description.lower() for term in related_terms):
        term = random.choice(related_terms)
        description += f"\n\nIdeal para momentos de {term}."
    
    return title, description
