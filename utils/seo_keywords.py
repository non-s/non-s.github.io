"""
utils/seo_keywords.py — SEO agressivo para o Pata Jazz.

Títulos, descrições e hashtags são otimizados para palavras-chave de alto
volume real no nicho "pet relaxation music". O objetivo é dominar buscas como
"music for cats to sleep", "calming music for anxious dogs" e "jazz for pets".

Regras editoriais (Operação Zeus):
- 100% em inglês (volume de busca global é muito maior).
- Títulos devem espelhar o que as pessoas digitam no YouTube.
- Usar gatilhos mentais: promessa específica, curiosidade, prova social, empatia.
- Descrições longas (até 1500 chars) com keywords semânticas, timestamps e CTAs.
- Hashtags em camadas: brand + animal + problema + música + formato.
"""

from __future__ import annotations

import json
import logging
import random
from pathlib import Path
from typing import Literal

from utils.channel_config import active_channel
from utils.paths import data_dir
from utils.state_lock import state_lock

log = logging.getLogger(__name__)


def _title_used_file() -> Path:
    """Caminho de used_titles.json no diretorio do canal ativo."""
    return data_dir() / "used_titles.json"


# Tamanho do historico de titulos usado para o anti-repeat.
_USED_TITLES_MAX = 120


def record_used_title(title: str) -> None:
    """Persiste um titulo ja usado (list, mais recente primeiro).

    Escrito pelos geradores logo apos gravar o metadata e pelos uploads
    quando um video e publicado. Com lock, como os outros JSON de _data.
    Best-effort: falha de I/O loga e nao derruba o gerador.
    """
    if not title:
        return
    used_file = _title_used_file()
    with state_lock(used_file):
        try:
            data = json.loads(used_file.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                data = []
        except Exception:
            data = []
        data = [title, *(t for t in data if t != title)][:_USED_TITLES_MAX]
        try:
            used_file.parent.mkdir(parents=True, exist_ok=True)
            used_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            log.warning("Falha ao salvar used_titles.json: %s", exc)


def recent_titles() -> list[str]:
    """Titulos recentes ja usados (mais recente primeiro). Ausente/corrompido = []."""
    try:
        data = json.loads(_title_used_file().read_text(encoding="utf-8"))
        return [t for t in data if isinstance(t, str)] if isinstance(data, list) else []
    except Exception as exc:
        log.debug("used_titles.json ausente/corrompido: %s", exc)
        return []


# Palavras de marca/constantes que todo titulo carrega ("Pata", "Jazz"). Como
# aparecem em 100% dos titulos, nao discriminam nada e so inflariam a
# similaridade; sao ignoradas no anti-repeat.
_TITLE_STOP_WORDS = frozenset({
    "pata", "jazz", "cat", "dog", "kitten", "puppy",
    "for", "to", "and", "the", "a", "music",
})


def title_similarity(a: str, b: str) -> float:
    """Similaridade de Jaccard das palavras (alfanumericas) de dois titulos.

    1.0 = mesmas palavras; 0.0 = nenhuma palavra em comum. As mesmas palavras
    em outra ordem contam como repeticao. Ignora stop words de marca e
    conectores comuns.
    """
    words_a = {w for w in a.lower().split() if w.isalnum() and w not in _TITLE_STOP_WORDS}
    words_b = {w for w in b.lower().split() if w.isalnum() and w not in _TITLE_STOP_WORDS}
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / max(len(words_a), len(words_b))


def title_is_too_repetitive(title: str, threshold: float = 0.65) -> bool:
    """True se o titulo e quase-duplicado de algum recente (anti-repeat).

    Titulos identicos/near-duplicados sao um dos sinais de conteudo em
    massa que o YouTube penaliza e faz o publico sentir "mesma coisa de
    sempre". O gerador usa isso para trocar de padrao antes de gravar.
    """
    return any(title_similarity(title, t) > threshold for t in recent_titles())


def _title_pattern_performance_file() -> Path:
    """Caminho de title_pattern_performance.json no diretorio do canal ativo."""
    return data_dir() / "title_pattern_performance.json"


# YouTube aceita ate 15 hashtags, mas descricoes com muitas leem como spam;
# 8-10 cobre marca + animal + problema + musica + formato sem exagerar.
_MAX_HASHTAGS = 10

# Keywords de alto volume real para o nicho pet + relaxation + jazz.
# Fonte: buscas reais do YouTube/Google (volume aproximado, em ingles).
HIGH_VOLUME_KEYWORDS: dict[str, object] = {
    "primary": [
        "music for cats",
        "music for dogs",
        "relaxing music for cats",
        "relaxing music for dogs",
        "calming music for dogs",
        "calming music for cats",
        "pet anxiety music",
        "music for pets",
        "jazz for cats",
        "jazz for dogs",
    ],
    "long_tail": [
        "music for cats to sleep",
        "music for dogs to sleep",
        "calming music for anxious dogs",
        "calming music for anxious cats",
        "music to calm dogs during fireworks",
        "music for dogs home alone",
        "sleep music for cats and kittens",
        "relaxing music for hyperactive dogs",
        "music for rescue dogs",
        "music for cats with anxiety",
        "jazz music to relax my cat",
        "soft jazz for pets",
        "soothing music for pets",
        "music for pets while owners are away",
        "deep sleep music for dogs",
    ],
    "trending": [
        "thunderstorm music for dogs",
        "fireworks anxiety music for pets",
        "new years eve pet calming music",
        "4th of july dog calming music",
        "halloween music for anxious dogs",
    ],
    "emotion": [
        "stress relief",
        "anxiety relief",
        "deep sleep",
        "relaxation",
        "peaceful",
        "tranquil",
        "calming",
        "soothing",
    ],
    "animal_specific": {
        "cat": [
            "cat sleep music",
            "music for kittens",
            "cat calming music",
            "music for cats to relax",
            "cat anxiety relief",
        ],
        "dog": [
            "dog sleep music",
            "music for puppies",
            "dog calming music",
            "music for dogs to relax",
            "dog anxiety relief",
        ],
    },
}

# Emoções e benefícios que geram engajamento (usados em descrições)
EMOCAO_BENEFICIOS = {
    "happy": ["joy", "happiness", "smiles", "well-being"],
    "calm": ["peace", "tranquility", "serenity", "relaxation"],
    "comfort": ["coziness", "comfort", "warmth", "love"],
    "focus": ["concentration", "focus", "productivity", "clarity"],
    "sleep": ["deep sleep", "rest", "sweet dreams", "unwinding"],
    "relief": ["stress relief", "anxiety relief", "calm down", "soothing"],
}

# CTAs otimizados para conversão (inscrição, like, comentário, sessão)
CTAS = [
    "🐾 Subscribe if this helped your pet relax — new videos every day.",
    "🔔 Hit the bell so YouTube notifies you when the next calm track drops.",
    "💬 Comment 'calm' if your pet is more relaxed right now.",
    "👍 Like this video — it tells YouTube to recommend it to more pet parents.",
    "🔗 Share this with someone whose pet needs to calm down.",
    "📺 Watch the next one — it picks up right where this calm moment ends.",
    "😴 Save this playlist for bedtime with your pet.",
    "🐾 Tell us in the comments: cat person or dog person?",
]

# Gatilhos mentais para títulos de alto CTR
TRIGGERS = {
    "promise": [
        "A calm {seconds}-second pause for your {animal}",
        "A gentle moment for your {animal}",
        "Soft music for {animal}s at rest",
        "A quiet reset for anxious {animal}s",
    ],
    "curiosity": [
        "Why do {animal}s love this music?",
        "A little jazz moment for your {animal}",
    ],
    "empathy": [
        "For the {animal} that misses you",
        "When your {animal} is anxious, play this",
        "For {animal}s who get scared home alone",
    ],
    "result": [
        "A softer moment for your {animal}",
        "A peaceful pause with your {animal}",
        "A gentle wind-down for pets",
    ],
}

# Hashtags estratégicas por categoria
HASHTAGS_POR_CATEGORIA = {
    "brand": ["#PataJazz", "#PetJazz", "#JazzForPets"],
    "animal": ["#Cats", "#Dogs", "#Kittens", "#Puppies", "#Pets"],
    "problem": ["#PetAnxiety", "#CalmMyPet", "#SleepMusic", "#StressRelief"],
    "musica": ["#Jazz", "#RelaxingMusic", "#SmoothJazz", "#MusicForPets"],
    "formato": ["#Shorts", "#YouTubeShorts"],
}

# Padrões de títulos de alto impacto (Operação Zeus).
# 60% SEO clássico (palavra-chave na frente) e 40% gatilho mental.
TITLE_PATTERNS: dict[str, list[str]] = {
    "short": [
        # SEO-first: palavra-chave de alto volume na frente
        "{keyword_primary} 🐾 {emoji}",
        "{keyword_long_tail} | a cozy {animal} moment {emoji}",
        "{keyword_animal} | gentle {animal} + jazz {emoji}",
        "{keyword_primary} in {seconds} seconds {emoji}",
        # Gatilhos mentais
        "{trigger} {emoji}",
        "{scenario}? A gentle reset for your {animal} {emoji}",
        "If your {animal} is {problem}, try this {emoji}",
        "A little {keyword_style} for your {animal} {emoji}",
        "{scenario}? This music helps {animal}s relax {emoji}",
        "Watch my {animal} fall asleep to {keyword_style} {emoji}",
        # A5: padrões que promovem playlists temáticas explicitamente -
        # referenciar o problema/cenario especifico aumenta CTR em buscas
        # long-tail e direciona para a playlist correspondente.
        "{scenario}? Calm music for {animal}s — full playlist {emoji}",
        "The {keyword_style} playlist for anxious {animal}s {emoji}",
        "A calm playlist for your {animal} | {keyword_long_tail} {emoji}",
    ],
}

# Cenários/problemas para gatilhos
SCENARIOS = {
    "cat": [
        "home alone",
        "can't sleep",
        "anxious",
        "hyper at night",
        "scared of thunder",
        "hiding under the bed",
    ],
    "dog": [
        "home alone",
        "anxious",
        "scared of fireworks",
        "won't stop barking",
        "hyperactive",
        "afraid of storms",
    ],
}

# Estilos musicais para SEO
MUSIC_STYLE_BY_MOOD: dict[str, list[str]] = {
    "relax": ["smooth jazz", "chill jazz", "soft jazz", "calming jazz"],
    "fofura": ["lofi jazz", "cozy lofi jazz", "mellow lofi jazz"],
    "diversao": ["upbeat jazz", "swing jazz", "playful jazz"],
    "sleep": ["sleep jazz", "deep sleep jazz", "night jazz"],
    "anxiety": ["anxiety relief jazz", "calming jazz", "peaceful jazz"],
}


def music_style_for_mood(mood: str) -> str:
    """Frase de estilo musical pro title/description, alinhada ao mood real."""
    options = MUSIC_STYLE_BY_MOOD.get(mood)
    if not options and mood:
        if "sleep" in mood:
            options = MUSIC_STYLE_BY_MOOD["sleep"]
        elif "anxiety" in mood or "stress" in mood:
            options = MUSIC_STYLE_BY_MOOD["anxiety"]
        elif "relax" in mood:
            options = MUSIC_STYLE_BY_MOOD["relax"]
    if not options:
        options = ["relaxing jazz"]
    return random.choice(options)


def trending_keywords() -> list[str]:
    """Retorna keywords trending do nicho pet/jazz, mesclando o banco
    estatico (HIGH_VOLUME_KEYWORDS["trending"]) com keywords dinamicas
    coletadas por scripts/sync_trending.py em _data/trending_keywords.json.

    Trending dinamicas tem prioridade (sao o que esta bombando AGORA), mas
    as estaticas (thunderstorm/fireworks/etc sazonais) permanecem como
    fallback quando o sync ainda nao rodou ou esta vazio.

    Usado por _select_description_keywords e _format_pattern_with_seo para
    injetar trending terms em títulos e descrições, aumentando CTR em
    buscas que estao em alta no momento.
    """
    static_trending = HIGH_VOLUME_KEYWORDS.get("trending", [])
    if not isinstance(static_trending, list):
        static_trending = []
    try:
        trending_file = data_dir() / "trending_keywords.json"
        data = json.loads(trending_file.read_text(encoding="utf-8"))
        dynamic = data.get("keywords", []) if isinstance(data, dict) else []
        if isinstance(dynamic, list):
            dynamic = [str(k) for k in dynamic if isinstance(k, str)]
        else:
            dynamic = []
    except Exception:
        dynamic = []
    # Dinamicas primeiro (sem duplicar), depois estaticas.
    merged = list(dict.fromkeys([*dynamic, *static_trending]))
    return merged


def _title_pattern_weights() -> dict[str, float]:
    """Le _data/title_pattern_performance.json."""
    try:
        data = json.loads(_title_pattern_performance_file().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        log.debug("title_pattern_performance.json ausente/corrompido: %s", exc)
        return {}


def pick_title_pattern(kind: Literal["short"]) -> str:
    """Seleciona um padrao de título otimizado, ponderado por performance real."""
    patterns = active_channel.title_patterns.get(kind, active_channel.title_patterns["short"])
    weights_by_pattern = _title_pattern_weights()
    if not weights_by_pattern:
        return random.choice(patterns)
    weights = [weights_by_pattern.get(p, 1.0) for p in patterns]
    return random.choices(patterns, weights=weights, k=1)[0]


def _animal_kind(animal: str) -> str:
    """Retorna 'cat' ou 'dog' para animal."""
    a = animal.lower()
    if "cat" in a or "kitten" in a:
        return "cat"
    if "dog" in a or "puppy" in a:
        return "dog"
    return "cat"  # fallback


def _keywords_for_animal(keywords: list[str], animal: str) -> list[str]:
    """Filtra termos que prometem musica para o animal errado.

    Um titulo de gato com "music for dogs" parece automatizado e prejudica
    satisfacao do espectador. Termos genericos ("for pets") continuam
    elegiveis, mas referencias explicitas ao outro animal sao removidas.
    """
    kind = _animal_kind(animal)
    forbidden = ("dog", "dogs", "puppy", "puppies") if kind == "cat" else ("cat", "cats", "kitten", "kittens")
    filtered = [keyword for keyword in keywords if not any(word in keyword.lower() for word in forbidden)]
    return filtered or keywords


def _format_trigger(trigger: str, animal: str, seconds: int = 30) -> str:
    """Preenche variáveis do gatilho."""
    problem = random.choice(["anxious", "stressed", "hyper", "scared"])
    return (
        trigger.replace("{animal}", animal)
        .replace("{seconds}", str(seconds))
        .replace("{problem}", problem)
    )


def _format_pattern_with_seo(
    pattern: str,
    animal: str,
    estilo_musical: str,
    emoji: str,
    mood: str = "relax",
    seconds: int = 30,
) -> str:
    """Preenche variáveis SEO + gatilhos no padrão de título."""
    kind = _animal_kind(animal)

    # Escolhe palavras-chave de alto volume
    primary_keywords = HIGH_VOLUME_KEYWORDS["primary"]
    long_tail_keywords = HIGH_VOLUME_KEYWORDS["long_tail"]
    assert isinstance(primary_keywords, list)
    assert isinstance(long_tail_keywords, list)
    primary = random.choice(_keywords_for_animal(primary_keywords, animal))
    # 25% de chance: usar uma trending keyword dinamica (do sync_trending)
    # em vez de long_tail estatica - reflete o que esta bombando em busca
    # real do YouTube no momento, aumentando CTR em buscas em alta.
    trending = trending_keywords()
    if trending and random.random() < 0.25:  # noqa: S311 - nao e seguranca
        long_tail = random.choice(_keywords_for_animal(trending, animal))
    else:
        long_tail = random.choice(_keywords_for_animal(long_tail_keywords, animal))
    animal_specific = HIGH_VOLUME_KEYWORDS["animal_specific"]
    assert isinstance(animal_specific, dict)
    animal_keywords = animal_specific.get(kind, [])
    assert isinstance(animal_keywords, list)
    keyword_animal = random.choice(animal_keywords) if animal_keywords else f"{animal} music"

    # Gatilhos
    trigger_category = random.choice(list(TRIGGERS.keys()))
    trigger = random.choice(TRIGGERS[trigger_category])
    trigger_text = _format_trigger(trigger, animal, seconds)

    # Cenário/problema
    scenario = random.choice(SCENARIOS.get(kind, SCENARIOS["cat"]))
    problem_word = random.choice(["anxious", "stressed", "restless", "scared", "hyper"])

    try:
        title = pattern.format(
            keyword_primary=primary,
            keyword_long_tail=long_tail,
            keyword_animal=keyword_animal,
            keyword_style=estilo_musical,
            animal=animal,
            emoji=emoji,
            seconds=seconds,
            trigger=trigger_text,
            scenario=scenario,
            problem=problem_word,
            mood=mood,
        )
    except KeyError:
        title = f"{primary} {emoji}"

    return " ".join(title.split()).strip()


def generate_title_with_pattern(
    animal: str,
    acao: str,
    estilo_musical: str,
    kind: Literal["short"],
    emoji: str,
    duracao: int | None = None,
    pattern: str | None = None,
) -> tuple[str, str]:
    """Gera título otimizado para SEO de alto volume e retorna o padrao usado."""
    all_patterns = active_channel.title_patterns.get(kind, active_channel.title_patterns["short"])
    chosen = pattern if pattern and pattern in all_patterns else pick_title_pattern(kind)

    seconds = duracao * 60 if duracao else 30
    title = _format_pattern_with_seo(
        chosen, animal, estilo_musical, emoji, mood=acao or "relax", seconds=seconds
    )

    # Anti-repeat: evita títulos quase duplicados
    if title_is_too_repetitive(title):
        for _attempt in range(5):
            chosen = pick_title_pattern(kind)
            title = _format_pattern_with_seo(
                chosen, animal, estilo_musical, emoji, mood=acao or "relax", seconds=seconds
            )
            if not title_is_too_repetitive(title):
                break

    # Garante prefixo de marca
    brand_prefix = active_channel.brand_prefix

    # Garante keyword primária ou long-tail de alto volume no título
    title_lower = title.lower()
    primary_keywords = HIGH_VOLUME_KEYWORDS["primary"]
    long_tail_keywords = HIGH_VOLUME_KEYWORDS["long_tail"]
    assert isinstance(primary_keywords, list)
    assert isinstance(long_tail_keywords, list)
    all_keywords = _keywords_for_animal(primary_keywords + long_tail_keywords, animal)
    has_strong_keyword = any(kw in title_lower for kw in all_keywords)
    if not has_strong_keyword:
        keyword = random.choice(all_keywords)
        suffix = f" | {keyword}"
        if len(title) + len(suffix) <= 100:
            title = f"{title}{suffix}"
        elif len(keyword) + 3 <= 100:
            title = f"{brand_prefix}{keyword}"[:100]
    if not title.startswith(brand_prefix.removesuffix(" |")):
        title = f"{brand_prefix} {title}"

    # Limita a 100 chars (limite YouTube)
    title = title[:100]

    return title, chosen


def generate_title(
    animal: str,
    acao: str,
    estilo_musical: str,
    kind: Literal["short"],
    emoji: str,
    duracao: int | None = None,
) -> str:
    """Gera título otimizado usando padrões de alta performance."""
    title, _pattern = generate_title_with_pattern(
        animal=animal,
        acao=acao,
        estilo_musical=estilo_musical,
        kind=kind,
        emoji=emoji,
        duracao=duracao,
    )
    return title


def generate_hashtags(
    animal: str,
    categoria: str = "relaxation",
    kind: Literal["short"] = "short",
) -> list[str]:
    """Gera conjunto estratégico de hashtags em camadas.

    Orçamento: brand(2) + animal(2) + problema(2) + música(2) + formato(2) = 10.
    """
    hashtags: list[str] = []

    # Brand
    hashtags.extend(HASHTAGS_POR_CATEGORIA["brand"][:2])

    # Animal
    a = animal.lower()
    if "cat" in a or "kitten" in a:
        hashtags.extend(["#Cats", "#CatLover"])
    elif "dog" in a or "puppy" in a:
        hashtags.extend(["#Dogs", "#DogLover"])
    else:
        hashtags.extend(HASHTAGS_POR_CATEGORIA["animal"][:2])

    # Problema/Cenário
    if categoria in ("relaxation", "sleep"):
        hashtags.extend(["#PetAnxiety", "#SleepMusic"])
    elif categoria in ("anxiety", "stress"):
        hashtags.extend(["#AnxietyRelief", "#CalmMyPet"])
    elif categoria in ("fun", "diversao"):
        hashtags.extend(["#HappyPets", "#FunPets"])
    else:
        hashtags.extend(HASHTAGS_POR_CATEGORIA["problem"][:2])

    # Música
    hashtags.extend(HASHTAGS_POR_CATEGORIA["musica"][:2])

    # Formato
    hashtags.extend(HASHTAGS_POR_CATEGORIA["formato"][:2])

    return list(dict.fromkeys(hashtags))[:_MAX_HASHTAGS]


def _select_description_keywords(animal: str, mood: str) -> list[str]:
    """Escolhe keywords semânticas para descrição longa."""
    kind = _animal_kind(animal)
    primary_keywords = HIGH_VOLUME_KEYWORDS["primary"]
    long_tail_keywords = HIGH_VOLUME_KEYWORDS["long_tail"]
    animal_specific = HIGH_VOLUME_KEYWORDS["animal_specific"]
    assert isinstance(primary_keywords, list)
    assert isinstance(long_tail_keywords, list)
    assert isinstance(animal_specific, dict)
    keywords: list[str] = []
    keywords.extend(primary_keywords)
    keywords.extend(long_tail_keywords)
    # Trending keywords dinamicas (do sync_trending.py) - aumenta CTR em
    # buscas que estao em alta no momento.
    keywords.extend(trending_keywords())
    animal_specific_keywords = animal_specific.get(kind, [])
    assert isinstance(animal_specific_keywords, list)
    keywords.extend(animal_specific_keywords)
    if mood in ("sleep", "relax"):
        keywords.extend(["deep sleep music", "sleep music for pets", "relaxing bedtime music"])
    if mood in ("anxiety", "stress"):
        keywords.extend(["anxiety relief music", "stress relief for pets", "calming music for anxious pets"])
    random.shuffle(keywords)
    return keywords[:6]


def generate_description(
    hook: str,
    kind: Literal["short"],
    hashtags: list[str],
    include_cta: bool = True,
    animal: str = "cat",
    mood: str = "relax",
    title: str = "",
) -> tuple[str, str]:
    """Gera descrição longa e otimizada para SEO (até ~1500 chars).

    Retorna (description, cta_text).
    """
    keywords = _select_description_keywords(animal, mood)
    keyword_block = ", ".join(keywords)

    # Introdução com hook + promessa
    intro_templates = [
        f"{hook} 🐾 This Pata Jazz short was made to help {animal}s relax, sleep, and feel safe.",
        f"{hook} 🎷 A calm moment for {animal}s and the humans who love them.",
        f"Need to calm your {animal}? {hook} 💫 Try this 30-second relaxation break.",
        f"{hook} 🐾 Perfect for anxious {animal}s, bedtime, or anytime your pet needs to unwind.",
    ]
    intro = random.choice(intro_templates)

    # Bloco SEO semântico
    seo_block = (
        f"\n\n🔍 Keywords: {keyword_block}. "
        f"This video combines real {animal} footage with smooth, pet-friendly jazz designed to reduce anxiety, "
        f"promote deep sleep, and create a peaceful environment for pets at home."
    )

    # Bloco de uso/cenário
    use_block_templates = [
        f"\n\n✅ Best used when your {animal} is home alone, anxious, hyperactive, or struggling to sleep. "
        f"Play it before leaving the house, during thunderstorms, fireworks, or anytime your pet needs comfort.",
        f"\n\n✅ Play this during bedtime, naptime, or stressful moments. "
        f"Many pet parents use our tracks to help rescue {animal}s, "
        f"senior {animal}s, and pets with separation anxiety.",
    ]
    use_block = random.choice(use_block_templates)

    # Timestamps (para shorts, ajuda no SEO e acessibilidade)
    timestamps = (
        "\n\n🕒 00:00 Calm intro\n"
        "00:05 Pet + jazz moment\n"
        "00:25 Soft outro"
    ) if kind == "short" else ""

    # CTA
    cta_text = ""
    cta = ""
    if include_cta:
        cta_text = random.choice(CTAS)
        cta = f"\n\n{cta_text}"

    # Hashtags
    hashtags_str = " ".join(hashtags[:_MAX_HASHTAGS])

    description = f"{intro}{seo_block}{use_block}{timestamps}{cta}\n\n{hashtags_str}"

    # Limita a ~1500 chars (limite útil do YouTube)
    if len(description) > 1500:
        description = description[:1497] + "..."

    return description, cta_text


def optimize_for_search(title: str, description: str, animal: str | None = None) -> tuple[str, str]:
    """Otimização final para busca do YouTube.

    Quando o animal e conhecido, a keyword adicionada precisa se referir ao
    mesmo publico do video. Isso preserva relevancia e evita prometer musica
    para cachorros em um Short de gato (ou o inverso).
    """
    title_lower = title.lower()
    primary_keywords = HIGH_VOLUME_KEYWORDS["primary"]
    long_tail_keywords = HIGH_VOLUME_KEYWORDS["long_tail"]
    assert isinstance(primary_keywords, list)
    assert isinstance(long_tail_keywords, list)
    candidates = primary_keywords + long_tail_keywords
    if animal:
        candidates = _keywords_for_animal(candidates, animal)
    has_keyword = any(kw in title_lower for kw in candidates)

    if not has_keyword:
        keyword = random.choice(_keywords_for_animal(primary_keywords, animal) if animal else primary_keywords)
        if len(title) + len(keyword) + 3 <= 90:
            title = f"{title} | {keyword}"

    # Garante termos semânticos na descrição
    related_terms = [
        "relaxation", "meditation", "studying", "working", "focus",
        "inner peace", "well-being", "deep sleep", "anxiety relief", "stress relief",
    ]
    if not any(term in description.lower() for term in related_terms):
        term = random.choice(related_terms)
        description += f"\n\nGreat for moments of {term}."

    return title, description


# ---------------------------------------------------------------------------
# SEO multilingue (A3): 1 a cada 6 uploads em PT-BR, 1 a cada 12 em ES,
# resto em EN. YouTube nao suporta multiplos titulos por video, entao
# rotacionamos o idioma do upload para capturar publico lusofono e
# hispanofono sem custo adicional (mesmo pipeline visual, so muda texto).
# ---------------------------------------------------------------------------

# Keywords de alto volume em PT-BR para o nicho pet + relaxamento + jazz.
# Espelham HIGH_VOLUME_KEYWORDS mas em portugues, para que títulos PT-BR
# tambem espelhem o que as pessoas digitam (volume de busca em PT e
# significativo no YouTube, especialmente Brasil/Portugal).
HIGH_VOLUME_KEYWORDS_PT: dict[str, list[str]] = {
    "primary": [
        "musica para gatos",
        "musica para cachorros",
        "musica relaxante para gatos",
        "musica relaxante para cachorros",
        "musica calmante para cachorros",
        "musica calmante para gatos",
        "musica para ansiedade de pets",
        "musica para pets",
        "jazz para gatos",
        "jazz para cachorros",
    ],
    "long_tail": [
        "musica para gatos dormirem",
        "musica para cachorro dormir",
        "musica calmante para cachorros ansiosos",
        "musica para cachorro sozinho em casa",
        "musica para acalmar gatos",
        "jazz relaxante para pets",
        "musica para ansiedade em cachorros",
        "musica para acalmar gato assustado",
    ],
}

# Keywords de alto volume em ES para o nicho pet + relaxamento + jazz.
# Mercado hispanofono e ~2x o lusofono em volume de busca no YouTube.
HIGH_VOLUME_KEYWORDS_ES: dict[str, list[str]] = {
    "primary": [
        "musica para gatos",
        "musica para perros",
        "musica relajante para gatos",
        "musica relajante para perros",
        "musica calmante para perros",
        "musica calmante para gatos",
        "musica para ansiedad de mascotas",
        "musica para mascotas",
        "jazz para gatos",
        "jazz para perros",
    ],
    "long_tail": [
        "musica para gatos dormir",
        "musica para perros dormir",
        "musica calmante para perros ansiosos",
        "musica para perros solos en casa",
        "musica para calmar gatos",
        "jazz relajante para mascotas",
        "musica para ansiedad en perros",
        "musica para calmar gato asustado",
    ],
}


def _upload_language_counter_file() -> Path:
    return data_dir() / "upload_language_counter.json"


def pick_upload_language() -> str:
    """Decide o idioma do próximo upload baseado num contador persistente.

    Estratégia: a cada 6 uploads, o 7o e PT-BR; a cada 12, o 13o e ES;
    os demais sao EN. Isso da ~83% EN, ~14% PT-BR, ~3% ES - o volume de
    busca em EN e dominante, mas PT-BR e ES capturam publicos que EN nunca
    alcancaria, sem custo adicional (mesmo pipeline, so muda texto).

    Retorna "en", "pt" ou "es". Em erro de leitura, cai em "en".
    """
    try:
        counter_file = _upload_language_counter_file()
        with state_lock(counter_file):
            try:
                data = json.loads(counter_file.read_text(encoding="utf-8"))
            except Exception:
                data = {"count": 0}
            count = int(data.get("count", 0)) + 1
            try:
                counter_file.parent.mkdir(parents=True, exist_ok=True)
                counter_file.write_text(json.dumps({"count": count}), encoding="utf-8")
            except Exception:
                pass
    except Exception:
        count = 1
    # ES primeiro (a cada 12) para que 12/24/36 virem ES e nao PT.
    # PT depois (a cada 6 exceto multiplos de 12, que ja viraram ES).
    if count % 12 == 0:
        return "es"
    if count % 6 == 0:
        return "pt"
    return "en"


def keywords_for_language(lang: str) -> dict[str, object]:
    """Retorna o banco de keywords de alto volume para o idioma dado.

    "en" usa HIGH_VOLUME_KEYWORDS (estatico + trending dinamico), "pt"
    usa HIGH_VOLUME_KEYWORDS_PT, "es" usa HIGH_VOLUME_KEYWORDS_ES. Idioma
    desconhecido cai em EN.
    """
    if lang == "pt":
        return HIGH_VOLUME_KEYWORDS_PT  # type: ignore[return-value]
    if lang == "es":
        return HIGH_VOLUME_KEYWORDS_ES  # type: ignore[return-value]
    # EN: mescla estatico com trending dinamico
    result: dict[str, object] = {}
    for key, val in HIGH_VOLUME_KEYWORDS.items():
        result[key] = val
    return result
