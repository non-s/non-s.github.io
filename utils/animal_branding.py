"""
utils/animal_branding.py — identidade visual e verbal do Pata Jazz.

Agora o canal só publica conteúdo de gatos e cachorros com jazz real.
Nenhuma outra categoria de animal ou gênero musical é permitida.
"""

from __future__ import annotations

import random

# Subconjunto permitido: apenas gatos e cachorros.
HOOK_BY_SCENE: dict[str, tuple[str, str]] = {
    "cat": ("Gatinho Fofo Fazendo Manha", "\U0001f431"),
    "kitten": ("Filhote de Gato Mais Fofo do Dia", "\U0001f408"),
    "puppy": ("Filhote de Cachorro Fofo Demais", "\U0001f436"),
    "dog": ("Cachorro Fofo Brincando", "\U0001f415"),
    "sleepy cat": ("Gatinho Dormindo de um Jeito Fofo", "\U0001f634"),
    "playful dog": ("Cachorrinho Brincalhao e Feliz", "\U0001f60a"),
}

ALL_SCENES: list[str] = list(HOOK_BY_SCENE.keys())


# Tags Jamendo: apenas jazz.
JAMENDO_SEARCH_TERMS: list[str] = ["jazz", "smooth jazz", "bossa nova"]

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
]

# Categorias Pixabay permitidas no filtro local.
ALLOWED_ANIMAL_KEYWORDS: set[str] = {"cat", "cats", "kitten", "kitty", "dog", "dogs", "puppy", "puppies", "animal", "pet"}

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


def random_scene() -> str:
    return random.choice(ALL_SCENES)


def hook_for_scene(scene: str) -> tuple[str, str]:
    return HOOK_BY_SCENE.get(scene, HOOK_BY_SCENE["cat"])


def is_allowed_animal_text(text: str) -> bool:
    lowered = text.lower()
    # Normaliza underscores para espacos para matching (ex: ai_art -> ai art)
    normalized = lowered.replace("_", " ")
    if any(kw in lowered or kw in normalized for kw in BLOCKED_BROLL_KEYWORDS):
        return False
    return any(kw in lowered or kw in normalized for kw in ALLOWED_ANIMAL_KEYWORDS)


def channel_title_prefix() -> str:
    return "Pata Jazz"
