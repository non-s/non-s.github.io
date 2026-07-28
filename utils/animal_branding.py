"""
utils/animal_branding.py — identidade visual e verbal do Pata Jazz.

Agora o canal só publica conteúdo de gatos e cachorros com jazz real.
Nenhuma outra categoria de animal ou gênero musical é permitida.

Hooks em ingles (mesmo motivo do resto do pipeline: mais volume de busca
pro mesmo conteudo visual/instrumental). Cada cena tem varias variacoes de
hook - um unico hook fixo por cena produzia titulos quase-identicos entre
videos nao relacionados (mesma cena sorteada = mesmo texto, sempre).
"""

from __future__ import annotations

import random
import time

from utils.ai_helper import ai_text, is_safe_ai_text
from utils.channel_config import ChannelConfig, active_channel

_AI_HOOK_CACHE: dict[tuple[str, str], tuple[str, float]] = {}
_AI_HOOK_TTL = 3600.0  # 1h

# Historico dos ultimos 10 hooks gerados por cena para evitar repeticao
# proxima (similares em >80% das palavras-chave).
_AI_HOOK_HISTORY: dict[str, list[str]] = {}
_AI_HOOK_HISTORY_MAX = 10

# Tamanho ideal do hook (chars). Fora de [min, max] rejeita.
_AI_HOOK_MIN_LEN = 20
_AI_HOOK_MAX_LEN = 70
_AI_HOOK_IDEAL_MIN = 30
_AI_HOOK_IDEAL_MAX = 60

# Palavras com viés negativo que nao combinam com tom cute/jazzy.
_AI_HOOK_NEGATIVE_WORDS = {"sad", "dead", "angry", "hate"}

# Subconjunto permitido: apenas gatos e cachorros. Cada cena tem 3+ hooks
# para variar o texto entre videos que caem na mesma cena.
HOOK_BY_SCENE: dict[str, list[tuple[str, str]]] = {
    "cat": [
        ("Cute Cat Being Mischievous", "\U0001f431"),
        ("This Cat's Morning Mood", "\U0001f431"),
        ("Cat Being Extra Today", "\U0001f431"),
    ],
    "kitten": [
        ("Cutest Kitten of the Day", "\U0001f408"),
        ("This Kitten Will Melt Your Heart", "\U0001f408"),
        ("Tiny Kitten, Big Cuteness", "\U0001f408"),
    ],
    "puppy": [
        ("Puppy Being Way Too Cute", "\U0001f436"),
        ("This Puppy Is Too Much Cuteness", "\U0001f436"),
        ("Puppy Having the Best Day", "\U0001f436"),
    ],
    "dog": [
        ("Cute Dog Having Fun", "\U0001f415"),
        ("This Dog's Playful Side", "\U0001f415"),
        ("Dog Being Adorable", "\U0001f415"),
    ],
    "sleepy cat": [
        ("Cat Napping the Cutest Way", "\U0001f634"),
        ("Sleepy Cat, Peaceful Moment", "\U0001f634"),
        ("This Cat Fell Asleep So Fast", "\U0001f634"),
    ],
    "sleepy dog": [
        ("Dog Sleeping Peacefully", "\U0001f634"),
        ("Sleepy Dog, Cozy Nap", "\U0001f634"),
        ("This Dog Is Out Like a Light", "\U0001f634"),
    ],
    "playful dog": [
        ("Playful and Happy Dog", "\U0001f60a"),
        ("This Dog Can't Stop Playing", "\U0001f60a"),
        ("Dog Having the Time of Its Life", "\U0001f60a"),
    ],
    "cat playing": [
        ("Cat Having Fun and Playing", "\U0001f431"),
        ("This Cat Won't Stop Playing", "\U0001f431"),
        ("Playtime With a Silly Cat", "\U0001f431"),
    ],
    "puppy playing": [
        ("Puppy Playing Around", "\U0001f436"),
        ("This Puppy Is All Energy", "\U0001f436"),
        ("Puppy Playtime Cuteness", "\U0001f436"),
    ],
    "dog relaxing": [
        ("Dog Relaxing Peacefully", "\U0001f615"),
        ("This Dog Is Fully Chilled Out", "\U0001f615"),
        ("Dog's Cozy Relax Moment", "\U0001f615"),
    ],
    "cat relaxing": [
        ("Cat Relaxing in the Sun", "\U0001f431"),
        ("This Cat Found Its Zen", "\U0001f431"),
        ("Cat's Cozy Relax Moment", "\U0001f431"),
    ],
}

ALL_SCENES: list[str] = list(HOOK_BY_SCENE.keys())


# Tags Jamendo: apenas jazz, mas com variedade de energia - antes so tinha
# termos "relax" (smooth/soft/coffee/relaxing), entao cenas de mood
# "diversao" (playful dog, cat playing) nunca tinham musica animada de
# verdade pra combinar - MOOD_GENRES["diversao"] (utils/media_pool.py) exigia
# swing/bebop/fusion/upbeat, generos que o pool nunca continha porque nunca
# eram buscados. jazz lento (relax/fofura) + jazz animado (diversao) +
# lofi jazz (fofura/relax, tom mais contemporaneo) agora tem representacao.
JAMENDO_SEARCH_TERMS: list[str] = [
    # Lento / relaxante
    "jazz",
    "smooth jazz",
    "bossa nova",
    "coffee jazz",
    "relaxing jazz",
    "soft jazz",
    "jazz instrumental",
    # Animado / energetico (mood "diversao")
    "swing jazz",
    "bebop jazz",
    "upbeat jazz",
    "jazz fusion",
    # Lofi jazz (mood "fofura"/"relax", tom contemporaneo)
    "lofi jazz",
    "jazzhop",
]

# Palavras-chave Pixabay restritas a gatos e cachorros REAIS.
# Queries evitam termos genericos que trazem animacao/cartoon.
BROLL_QUERIES: list[str] = [
    "real cat",
    "real kitten",
    "cute cat real",
    "cat playing real",
    "adorable cat",
    "cute kitten real",
    "real puppy",
    "real dog",
    "cute puppy real",
    "dog playing real",
    "happy dog real",
    "cute dog real",
    "puppy playing real",
    "sleepy cat real",
    "sleepy dog real",
    "cat relaxing real",
    "dog relaxing real",
    "kitten playing real",
    "puppy dog real",
]

# Categorias Pixabay permitidas no filtro local.
ALLOWED_ANIMAL_KEYWORDS: set[str] = {
    "cat", "cats", "kitten", "kitty", "dog", "dogs", "puppy", "puppies",
    "animal", "pet", "feline", "canine",
}

# Palavras que indicam cartoon, animacao, ilustracao ou conteudo nao-real.
BLOCKED_BROLL_KEYWORDS: set[str] = {
    "cartoon",
    "animation",
    "animated",
    "3d",
    "3 d",
    "3d render",
    "illustration",
    "drawing",
    "vector",
    "clipart",
    "artificial",
    "ai generated",
    "ai-generated",
    "ai art",
    "cute illustration",
    "motion graphic",
    "graphic",
    "sticker",
    "emoji",
    "sketch",
    "comic",
    "manga",
    "anime",
    "render",
    "cgi",
    "vfx",
    "after effects",
    "stock footage",
    "loop animation",
    "2d animation",
    "stop motion",
    "puppet",
    "toy",
    "plush",
    "figurine",
    "statue",
    "sculpture",
}


def random_scene(channel: ChannelConfig | None = None) -> str:
    ch = channel or active_channel
    scenes = [s for group in ch.scene_categories.values() for s in group]
    return random.choice(scenes if scenes else ALL_SCENES)



# Angulos de retencao pra variar o *tipo* de hook entre videos, nao so o
# texto - um unico estilo sempre "cute e jazzy" fica previsivel depois de
# algumas dezenas de Shorts. Cada entrada e uma instrucao curta que muda
# COMO o gancho e construido (curiosidade, POV, pergunta, etc), mantendo
# as mesmas regras de tamanho/tom/seguranca do prompt base.
_HOOK_ANGLES = [
    "Use a curiosity-gap angle - imply something surprising happens without spoiling it.",
    "Use a POV angle - phrase it like 'POV:' from the pet's perspective.",
    "Use a relatable-moment angle - describe a small, instantly recognizable pet moment.",
    "Use a direct-cute angle - a warm, simple statement about how cute this moment is.",
    "Use a playful-question angle - end with an implied question that makes viewers want the answer.",
]


def generate_hook_with_ai(scene: str, mood: str = "") -> str:
    """Gera hook curto via Gemini. Retorna "" se indisponivel ou inseguro.

    Cache em memoria por (scene, mood) por 1h evita chamar a IA a cada video
    do mesmo batch que cai na mesma cena.

    Validacao de qualidade (rejeita e pede outro, ate 1 retry):
    - Tamanho: 20-70 chars (ideal 30-60).
    - Sentimento: sem palavras negativas (sad, dead, angry, hate).
    - Repeticao proxima: >80% similar a um dos ultimos 10 hooks da cena.
    Apos esgotar retry, fallback para hook hardcoded da cena.
    """
    key = (scene, mood)
    now = time.time()
    cached = _AI_HOOK_CACHE.get(key)
    if cached and now - cached[1] < _AI_HOOK_TTL:
        return cached[0]

    mood_hint = f" Mood: {mood}." if mood else ""
    angle = random.choice(_HOOK_ANGLES)
    prompt = (
        f"Write a single hook (max 60 characters) for the first 1-2 seconds of a "
        f"vertical YouTube Short about a {scene} - viewers decide whether to keep "
        f"watching almost instantly, so it needs to earn attention immediately. "
        f"{angle} Cute and jazzy tone, no clickbait, no emojis, no quotes, in "
        f"English.{mood_hint} Return only the hook text."
    )

    hook = ""
    for _attempt in range(2):
        out = ai_text(prompt, task="hook")
        if not out or not is_safe_ai_text(out):
            break
        candidate = out.strip().strip('"').strip()
        if _validate_hook(candidate, scene):
            hook = candidate
            break

    if not hook:
        _AI_HOOK_CACHE[key] = ("", now)
        return ""

    if len(hook) > _AI_HOOK_IDEAL_MAX:
        hook = hook[:_AI_HOOK_IDEAL_MAX].rstrip()
    _AI_HOOK_CACHE[key] = (hook, now)
    _record_hook_history(scene, hook)
    return hook


def _validate_hook(hook: str, scene: str) -> bool:
    """Valida tamanho, sentimento e similaridade com historico recente.

    Retorna True se o hook for aceitavel, False caso contrario (para retry ou
    fallback). Tamanho rejeita <20 ou >70; ideal 30-60 (aceito, mas nao
    rejeita fora do ideal — apenas o limite duro rejeita). Sentimento rejeita
    palavras negativas. Similaridade rejeita >80% das palavras-chave em
    comum com um dos ultimos _AI_HOOK_HISTORY_MAX hooks da cena.
    """
    if not hook:
        return False
    if len(hook) < _AI_HOOK_MIN_LEN or len(hook) > _AI_HOOK_MAX_LEN:
        return False
    lowered = hook.lower()
    if any(word in lowered for word in _AI_HOOK_NEGATIVE_WORDS):
        return False
    if _is_similar_to_recent(hook, scene):
        return False
    return True


def _keyword_set(hook: str) -> set[str]:
    """Conjunto de palavras-chave (lowercased, alfanumericas) do hook."""
    return {w for w in hook.lower().split() if w.isalnum()}


def _is_similar_to_recent(hook: str, scene: str) -> bool:
    """True se hook compartilha >80% das palavras-chave com algum dos ultimos
    hooks gerados para a mesma cena."""
    history = _AI_HOOK_HISTORY.get(scene, [])
    if not history:
        return False
    new_words = _keyword_set(hook)
    if not new_words:
        return False
    for prev in history:
        prev_words = _keyword_set(prev)
        if not prev_words:
            continue
        intersection = new_words & prev_words
        smaller = min(len(new_words), len(prev_words))
        if smaller > 0 and len(intersection) / smaller > 0.8:
            return True
    return False


def _record_hook_history(scene: str, hook: str) -> None:
    """Adiciona hook ao historico da cena (mantendo os ultimos N)."""
    history = _AI_HOOK_HISTORY.setdefault(scene, [])
    history.append(hook)
    if len(history) > _AI_HOOK_HISTORY_MAX:
        del history[: len(history) - _AI_HOOK_HISTORY_MAX]


def hook_for_scene(scene: str, mood: str = "", use_ai: bool = True) -> tuple[str, str]:
    if use_ai:
        ai_hook = generate_hook_with_ai(scene, mood)
        if ai_hook:
            hooks = HOOK_BY_SCENE.get(scene, HOOK_BY_SCENE["cat"])
            emoji = hooks[0][1]
            return ai_hook, emoji
    return random.choice(HOOK_BY_SCENE.get(scene, HOOK_BY_SCENE["cat"]))


def is_allowed_animal_text(text: str) -> bool:
    lowered = text.lower()
    # Normaliza underscores para espacos para matching (ex: ai_art -> ai art)
    normalized = lowered.replace("_", " ")
    combined = f"{lowered} {normalized}"
    if any(kw in combined for kw in BLOCKED_BROLL_KEYWORDS):
        return False
    return any(kw in combined for kw in ALLOWED_ANIMAL_KEYWORDS)


def detect_animal(scene: str) -> str:
    """Retorna "cat" ou "dog" a partir da descricao da cena."""
    s = scene.lower()
    return "cat" if ("cat" in s or "kitten" in s) else "dog"


def channel_title_prefix(channel: ChannelConfig | None = None) -> str:
    ch = channel or active_channel
    return ch.name
