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

# Palavras-chave Pixabay restritas a gatos e cachorros.
BROLL_QUERIES: list[str] = [
    "cute cat",
    "kitten playing",
    "sleepy cat",
    "cat playing",
    "adorable cat",
    "funny cat",
    "cute kitten",
    "kitten sleeping",
    "playful kitten",
    "cute puppy",
    "puppy playing",
    "sleepy puppy",
    "dog playing",
    "happy dog",
    "cute dog",
    "adorable puppy",
    "puppy dog",
]

# Tags Jamendo: apenas jazz.
JAMENDO_SEARCH_TERMS: list[str] = ["jazz", "smooth jazz", "bossa nova"]

# Categorias Pixabay permitidas no filtro local.
ALLOWED_ANIMAL_KEYWORDS: set[str] = {"cat", "cats", "kitten", "kitty", "dog", "dogs", "puppy", "puppies"}


def random_scene() -> str:
    return random.choice(ALL_SCENES)


def hook_for_scene(scene: str) -> tuple[str, str]:
    return HOOK_BY_SCENE.get(scene, HOOK_BY_SCENE["cat"])


def is_allowed_animal_text(text: str) -> bool:
    lowered = text.lower()
    return any(kw in lowered for kw in ALLOWED_ANIMAL_KEYWORDS)


def channel_title_prefix() -> str:
    return "Pata Jazz"
