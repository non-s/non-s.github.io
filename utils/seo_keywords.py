"""
utils/seo_keywords.py — SEO agressivo para o Liquid Wire.

Títulos, descrições e hashtags são otimizados para palavras-chave de alto
volume real no nicho "generative art visuals". O objetivo é dominar buscas como
"procedural animation", "ambient visuals" e "generative art music".

Regras editoriais:
- 100% em inglês (volume de busca global é muito maior).
- Títulos devem espelhar o que as pessoas digitam no YouTube.
- Usar gatilhos mentais: promessa específica, curiosidade, prova social, empatia.
- Descrições longas (até 1500 chars) com keywords semânticas, timestamps e CTAs.
- Hashtags em camadas: brand + estilo + mood + música + formato.
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
_HISTORICAL_UNSAFE_TERMS = (
    "anxiety relief", "stress relief", "calm down", "deep sleep",
    "separation anxiety", "reduce anxiety", "reduce stress",
    "healing", "cure", "treatment", "therapy", "medical",
)


def _is_safe_title_history_entry(title: str) -> bool:
    lowered = title.lower()
    return not any(term in lowered for term in _HISTORICAL_UNSAFE_TERMS)


def record_used_title(title: str) -> None:
    """Persiste um titulo ja usado (list, mais recente primeiro).

    Escrito pelos geradores logo apos gravar o metadata e pelos uploads
    quando um video e publicado. Com lock, como os outros JSON de _data.
    Best-effort: falha de I/O loga e nao derruba o gerador.
    """
    if not title or not _is_safe_title_history_entry(title):
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
        if isinstance(data, list):
            return [t for t in data if isinstance(t, str) and _is_safe_title_history_entry(t)]
        return []
    except Exception as exc:
        log.debug("used_titles.json ausente/corrompido: %s", exc)
        return []


# Palavras de marca/constantes que todo titulo carrega ("Liquid", "Wire"). Como
# aparecem em 100% dos titulos, nao discriminam nada e so inflariam a
# similaridade; sao ignoradas no anti-repeat.
_TITLE_STOP_WORDS = frozenset({
    "liquid", "wire", "generative", "procedural", "ambient", "visual",
    "for", "to", "and", "the", "a", "music", "art",
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
# 8-10 cobre marca + estilo + mood + musica + formato sem exagerar.
_MAX_HASHTAGS = 10

# SEO must not imply medical, therapeutic, or behavioral outcomes. These
# phrases are excluded from generated description keyword blocks and copy.
UNSUPPORTED_OUTCOME_TERMS = (
    "anxiety relief",
    "stress relief",
    "calm down",
    "deep sleep",
    "to sleep",
    "reduce anxiety",
    "reduce stress",
    "healing music",
    "cure",
    "treatment",
    "therapy music",
    "medical",
)


def has_unsupported_outcome_claim(text: str) -> bool:
    """Return whether text makes a prohibited outcome claim."""
    lowered = text.lower()
    return any(term in lowered for term in UNSUPPORTED_OUTCOME_TERMS)

# Keywords de alto volume real para o nicho generative art + ambient visuals.
# Fonte: buscas reais do YouTube/Google (volume aproximado, em ingles).
HIGH_VOLUME_KEYWORDS: dict[str, object] = {
    "primary": [
        "generative art",
        "procedural animation",
        "ambient visuals",
        "abstract video",
        "liquid wireframe",
        "relaxing visuals",
        "visual art music",
        "procedural visuals",
        "generative visuals",
    ],
    "long_tail": [
        "slow generative ambient visuals",
        "procedural art for focus",
        "ambient wireframe motion",
        "abstract visual for studying",
        "generative art stream",
        "procedural visual radio",
        "liquid wireframe flow",
        "slowform ambient visual",
        "calm wireframe animation",
        "ambient loop for reading",
        "generative art for deep work",
    ],
    "trending": [
        "ai generated art video",
        "procedural music visualizer",
        "ambient live wallpaper",
        "generative art short",
        "wireframe art loop",
    ],
    "emotion": [
        "relaxation",
        "peaceful",
        "tranquil",
        "calming",
        "hypnotic",
        "focus",
        "late night",
    ],
    "style_specific": {
        "wireframe": [
            "liquid wireframe motion",
            "wireframe flow art",
            "procedural wireframe",
        ],
        "organic": [
            "organic generative art",
            "fluid mesh visual",
            "corral growth animation",
        ],
        "geometric": [
            "geometric generative art",
            "crystal lattice visual",
            "abstract geometry loop",
        ],
        "nebula": [
            "nebula generative visual",
            "particle cloud art",
            "cosmic ambient visual",
        ],
    },
}

# Emoções e benefícios que geram engajamento (usados em descrições)
EMOCAO_BENEFICIOS = {
    "happy": ["joy", "happiness", "smiles", "well-being"],
    "calm": ["peace", "tranquility", "serenity", "relaxation"],
    "comfort": ["coziness", "comfort", "warmth", "love"],
    "focus": ["concentration", "focus", "productivity", "clarity"],
    "sleep": ["rest", "sweet dreams", "unwinding", "quiet time"],
    "relief": ["quiet", "cozy", "gentle", "soothing"],
}

# CTAs otimizados para conversão (inscrição, like, comentário, sessão)
CTAS = [
    "✨ Subscribe for more generative visuals and original music.",
    "🔔 Hit the bell so YouTube notifies you when the next piece drops.",
    "💬 Tell us which visual moment caught your eye.",
    "👍 Like this video — it tells YouTube to recommend it to more art lovers.",
    "🔗 Share this with someone who enjoys ambient visuals.",
    "📺 Watch the next one — every piece is unique, generated from math.",
    "🌙 Save this playlist for focus sessions or late-night calm.",
    "🎨 Tell us in the comments: which style do you want to see next?",
]

# Gatilhos mentais para títulos de alto CTR
TRIGGERS = {
    "promise": [
        "A calm {seconds}-second drift of generative art",
        "A gentle visual moment for focus",
        "Soft procedural visuals for a quiet pause",
        "A slow ambient moment for late nights",
    ],
    "curiosity": [
        "Every piece is unique — this one is yours",
        "A little generative moment you won't see again",
    ],
    "empathy": [
        "For the moments between tasks",
        "A gentle pause for your eyes and ears",
        "For a quiet moment of abstract beauty",
    ],
    "result": [
        "A softer moment of visual art",
        "A peaceful pause with ambient sound",
        "A gentle wind-down for the mind",
    ],
}

# Hashtags estratégicas por categoria
HASHTAGS_POR_CATEGORIA = {
    "brand": ["#LiquidWire", "#GenerativeArt", "#ProceduralVisuals"],
    "style": ["#Wireframe", "#AmbientVisuals", "#AbstractArt", "#Procedural"],
    "mood": ["#FocusMusic", "#Ambient", "#LateNight", "#CalmVisuals"],
    "musica": ["#AmbientMusic", "#ProceduralMusic", "#Synthwave", "#LoFi"],
    "formato": ["#Shorts", "#YouTubeShorts"],
}

# Padrões de títulos de alto impacto.
# 60% SEO clássico (palavra-chave na frente) e 40% gatilho mental.
TITLE_PATTERNS: dict[str, list[str]] = {
    "short": [
        # SEO-first: palavra-chave de alto volume na frente
        "{keyword_primary} ✨ {emoji}",
        "{keyword_long_tail} | a generative ambient moment {emoji}",
        "{keyword_style} | procedural visual + original music {emoji}",
        "{keyword_primary} in {seconds} seconds {emoji}",
        # Gatilhos mentais
        "{trigger} {emoji}",
        "{scenario}? A visual reset for your mind {emoji}",
        "A generative {keyword_style} moment for focus {emoji}",
        "A little {keyword_style} for your next break {emoji}",
        "{scenario}? An ambient visual + original music moment {emoji}",
        "A quiet visual moment with {keyword_style} {emoji}",
        # A5: padrões que promovem playlists temáticas explicitamente
        "{scenario}? Ambient visuals — full playlist {emoji}",
        "The {keyword_style} playlist for focus sessions {emoji}",
        "A generative art playlist | {keyword_long_tail} {emoji}",
    ],
}

# Cenários/problemas para gatilhos
SCENARIOS = {
    "focus": [
        "need to focus",
        "studying",
        "deep work",
        "can't concentrate",
        "writing late",
        "need background visuals",
    ],
    "relax": [
        "winding down",
        "can't sleep",
        "stressed",
        "need a break",
        "late night",
        "quiet moment",
    ],
}

# Estilos musicais para SEO (alinhados aos gêneros do motor musical universal)
MUSIC_STYLE_BY_MOOD: dict[str, list[str]] = {
    "relax": ["ambient", "lo-fi", "calm synth", "drone ambient"],
    "focus": ["ambient", "synthwave", "lo-fi", "minimalist"],
    "energetic": ["electronic", "EDM", "synthwave", "funk"],
    "sleep": ["ambient", "drone", "dark ambient", "sleep ambient"],
    "upbeat": ["electronic", "rock", "funk", "hip-hop"],
}


def music_style_for_mood(mood: str) -> str:
    """Frase de estilo musical pro title/description, alinhada ao mood real."""
    options = MUSIC_STYLE_BY_MOOD.get(mood)
    if not options and mood:
        if "sleep" in mood:
            options = MUSIC_STYLE_BY_MOOD["sleep"]
        elif "focus" in mood or "study" in mood:
            options = MUSIC_STYLE_BY_MOOD["focus"]
        elif "relax" in mood:
            options = MUSIC_STYLE_BY_MOOD["relax"]
    if not options:
        options = ["ambient"]
    return random.choice(options)


def trending_keywords() -> list[str]:
    """Retorna keywords trending do nicho generative art, mesclando o banco
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


def _style_kind(style: str) -> str:
    """Retorna a categoria de estilo visual ('wireframe', 'organic', etc.)."""
    s = style.lower()
    for kind in ("wireframe", "organic", "geometric", "nebula"):
        if kind in s:
            return kind
    return "wireframe"  # fallback


def _keywords_for_style(keywords: list[str], style: str) -> list[str]:
    """Filtra termos que não pertencem ao estilo visual atual.

    Um título de wireframe com 'organic growth' parece inconsistente. Termos
    genéricos ('generative art') continuam elegíveis.
    """
    kind = _style_kind(style)
    other_kinds = [k for k in ("wireframe", "organic", "geometric", "nebula") if k != kind]
    filtered = [keyword for keyword in keywords if not any(k in keyword.lower() for k in other_kinds)]
    return filtered or keywords


def _format_trigger(trigger: str, style: str, seconds: int = 30) -> str:
    """Preenche variáveis do gatilho."""
    return (
        trigger.replace("{style}", style)
        .replace("{seconds}", str(seconds))
    )


def _format_pattern_with_seo(
    pattern: str,
    scene: str,
    estilo_musical: str,
    emoji: str,
    mood: str = "relax",
    seconds: int = 30,
) -> str:
    """Preenche variáveis SEO + gatilhos no padrão de título."""
    kind = _style_kind(scene)

    # Escolhe palavras-chave de alto volume
    primary_keywords = HIGH_VOLUME_KEYWORDS["primary"]
    long_tail_keywords = HIGH_VOLUME_KEYWORDS["long_tail"]
    assert isinstance(primary_keywords, list)
    assert isinstance(long_tail_keywords, list)
    primary = random.choice(_keywords_for_style(primary_keywords, scene))
    # 25% de chance: usar uma trending keyword dinamica
    trending = trending_keywords()
    if trending and random.random() < 0.25:  # noqa: S311 - nao e seguranca
        long_tail = random.choice(_keywords_for_style(trending, scene))
    else:
        long_tail = random.choice(_keywords_for_style(long_tail_keywords, scene))
    style_specific = HIGH_VOLUME_KEYWORDS["style_specific"]
    assert isinstance(style_specific, dict)
    style_keywords = style_specific.get(kind, [])
    assert isinstance(style_keywords, list)
    keyword_style = random.choice(style_keywords) if style_keywords else f"{scene} art"

    # Gatilhos
    trigger_category = random.choice(list(TRIGGERS.keys()))
    trigger = random.choice(TRIGGERS[trigger_category])
    trigger_text = _format_trigger(trigger, scene, seconds)

    # Cenário/problema
    scenario = random.choice(SCENARIOS.get(mood, SCENARIOS["relax"]))

    try:
        title = pattern.format(
            keyword_primary=primary,
            keyword_long_tail=long_tail,
            keyword_style=keyword_style,
            keyword_scene=keyword_style,
            style=estilo_musical,
            scene=scene,
            emoji=emoji,
            seconds=seconds,
            trigger=trigger_text,
            scenario=scenario,
            mood=mood,
        )
    except KeyError:
        title = f"{primary} {emoji}"

    return " ".join(title.split()).strip()


def generate_title_with_pattern(
    scene: str,
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
        chosen, scene, estilo_musical, emoji, mood=acao or "relax", seconds=seconds
    )

    # Anti-repeat: evita títulos quase duplicados
    if title_is_too_repetitive(title):
        for _attempt in range(5):
            chosen = pick_title_pattern(kind)
            title = _format_pattern_with_seo(
                chosen, scene, estilo_musical, emoji, mood=acao or "relax", seconds=seconds
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
    all_keywords = _keywords_for_style(primary_keywords + long_tail_keywords, scene)
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
    scene: str,
    acao: str,
    estilo_musical: str,
    kind: Literal["short"],
    emoji: str,
    duracao: int | None = None,
) -> str:
    """Gera título otimizado usando padrões de alta performance."""
    title, _pattern = generate_title_with_pattern(
        scene=scene,
        acao=acao,
        estilo_musical=estilo_musical,
        kind=kind,
        emoji=emoji,
        duracao=duracao,
    )
    return title


def generate_hashtags(
    scene: str,
    categoria: str = "relaxation",
    kind: Literal["short"] = "short",
) -> list[str]:
    """Gera conjunto estratégico de hashtags em camadas.

    Orçamento: brand(2) + style(2) + mood(2) + música(2) + formato(2) = 10.
    """
    hashtags: list[str] = []

    # Brand
    hashtags.extend(HASHTAGS_POR_CATEGORIA["brand"][:2])

    # Style
    s = scene.lower()
    if "wireframe" in s or "wire" in s:
        hashtags.extend(["#Wireframe", "#WireframeArt"])
    elif "organic" in s or "coral" in s or "fluid" in s:
        hashtags.extend(["#OrganicArt", "#FluidArt"])
    elif "geometric" in s or "crystal" in s:
        hashtags.extend(["#GeometricArt", "#AbstractGeometry"])
    elif "nebula" in s or "particle" in s:
        hashtags.extend(["#NebulaArt", "#ParticleArt"])
    else:
        hashtags.extend(HASHTAGS_POR_CATEGORIA["style"][:2])

    # Mood/Cenário
    if categoria in ("relaxation", "sleep", "ambient"):
        hashtags.extend(["#Ambient", "#CalmVisuals"])
    elif categoria in ("focus", "study"):
        hashtags.extend(["#FocusMusic", "#DeepWork"])
    elif categoria in ("energetic", "upbeat"):
        hashtags.extend(["#Electronic", "#Synthwave"])
    else:
        hashtags.extend(HASHTAGS_POR_CATEGORIA["mood"][:2])

    # Música
    hashtags.extend(HASHTAGS_POR_CATEGORIA["musica"][:2])

    # Formato
    hashtags.extend(HASHTAGS_POR_CATEGORIA["formato"][:2])

    return list(dict.fromkeys(hashtags))[:_MAX_HASHTAGS]


def _select_description_keywords(scene: str, mood: str) -> list[str]:
    """Escolhe keywords semânticas para descrição longa."""
    kind = _style_kind(scene)
    primary_keywords = HIGH_VOLUME_KEYWORDS["primary"]
    long_tail_keywords = HIGH_VOLUME_KEYWORDS["long_tail"]
    style_specific = HIGH_VOLUME_KEYWORDS["style_specific"]
    assert isinstance(primary_keywords, list)
    assert isinstance(long_tail_keywords, list)
    assert isinstance(style_specific, dict)
    keywords: list[str] = []
    keywords.extend(primary_keywords)
    keywords.extend(long_tail_keywords)
    # Trending keywords dinamicas (do sync_trending.py)
    keywords.extend(trending_keywords())
    style_specific_keywords = style_specific.get(kind, [])
    assert isinstance(style_specific_keywords, list)
    keywords.extend(style_specific_keywords)
    if mood in ("sleep", "relax", "ambient"):
        keywords.extend(["dark ambient", "night ambient visual", "slow drift ambient"])
    if mood in ("focus", "study"):
        keywords.extend(["focus ambient", "procedural art for studying", "deep work visuals"])
    keywords = [keyword for keyword in keywords if not has_unsupported_outcome_claim(keyword)]
    random.shuffle(keywords)
    return keywords[:6]


def generate_description(
    hook: str,
    kind: Literal["short"],
    hashtags: list[str],
    include_cta: bool = True,
    scene: str = "wireframe",
    mood: str = "relax",
    title: str = "",
) -> tuple[str, str]:
    """Gera descrição longa e otimizada para SEO (até ~1500 chars).

    Retorna (description, cta_text).
    """
    _select_description_keywords(scene, mood)

    # Introdução com hook + promessa
    intro_templates = [
        f"{hook} ✨ A Liquid Wire moment — unique generative visuals with original procedural music.",
        f"{hook} 🎨 A calm moment of abstract art and ambient sound.",
        f"{hook} 💫 A {30}-second drift through procedural wireframes and synthesized soundscapes.",
        f"{hook} ✨ A generative art moment for a quiet break or focus session.",
    ]
    intro = random.choice(intro_templates)

    # Bloco SEO semântico
    seo_block = (
        "\n\nThis video combines procedurally generated visuals with original "
        "synthesized music for a calm, abstract atmosphere."
    )
    use_block_templates = [
        "\n\n✅ Enjoy this during a quiet break, while reading, or as ambient background.",
        "\n\n✅ A generative art moment for focus time or late-night calm.",
    ]
    use_block = random.choice(use_block_templates)

    # Timestamps
    timestamps = (
        "\n\n🕒 00:00 Calm intro\n"
        "00:05 Generative visual moment\n"
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

    if len(description) > 1500:
        description = description[:1497] + "..."

    return description, cta_text


def optimize_for_search(title: str, description: str, scene: str | None = None) -> tuple[str, str]:
    """Otimização final para busca do YouTube.

    Quando o estilo visual e conhecido, a keyword adicionada precisa se referir ao
    mesmo estilo do video.
    """
    title_lower = title.lower()
    primary_keywords = HIGH_VOLUME_KEYWORDS["primary"]
    long_tail_keywords = HIGH_VOLUME_KEYWORDS["long_tail"]
    assert isinstance(primary_keywords, list)
    assert isinstance(long_tail_keywords, list)
    candidates = primary_keywords + long_tail_keywords
    if scene:
        candidates = _keywords_for_style(candidates, scene)
    has_keyword = any(kw in title_lower for kw in candidates)

    if not has_keyword:
        keyword = random.choice(_keywords_for_style(primary_keywords, scene) if scene else primary_keywords)
        if len(title) + len(keyword) + 3 <= 90:
            title = f"{title} | {keyword}"

    # Garante termos semânticos na descrição
    related_terms = [
        "relaxation", "focus", "studying", "working", "ambient",
        "quiet time", "generative art", "abstract visuals", "a gentle break", "background visuals",
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

# Keywords de alto volume em PT-BR para o nicho arte generativa + ambient.
HIGH_VOLUME_KEYWORDS_PT: dict[str, list[str]] = {
    "primary": [
        "arte generativa",
        "visuais ambient",
        "animacao procedural",
        "video abstrato",
        "wireframe liquido",
        "visuais relaxantes",
        "arte procedural",
        "visualizador musical",
        "visuais gerativos",
    ],
    "long_tail": [
        "visuais ambient para foco",
        "arte generativa para estudar",
        "animacao wireframe loops",
        "video abstrato para relaxar",
        "arte generativa em tempo real",
        "visual procedural para trabalho",
        "wireframe liquido em movimento",
        "arte generativa para foco profundo",
    ],
}

# Keywords de alto volume em ES para o nicho arte generativa + ambient.
HIGH_VOLUME_KEYWORDS_ES: dict[str, list[str]] = {
    "primary": [
        "arte generativa",
        "visuales ambient",
        "animacion procedural",
        "video abstracto",
        "wireframe liquido",
        "visuales relajantes",
        "arte procedural",
        "visualizador musical",
        "visuales generativos",
    ],
    "long_tail": [
        "visuales ambient para concentracion",
        "arte generativa para estudiar",
        "animacion wireframe loops",
        "video abstracto para relajar",
        "arte generativa en tiempo real",
        "visual procedural para trabajo",
        "wireframe liquido en movimiento",
        "arte generativa para enfoque profundo",
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
