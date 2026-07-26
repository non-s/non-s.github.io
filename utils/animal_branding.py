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


# Tags Jamendo: apenas jazz.
JAMENDO_SEARCH_TERMS: list[str] = [
    "jazz",
    "smooth jazz",
    "bossa nova",
    "coffee jazz",
    "relaxing jazz",
    "soft jazz",
    "jazz instrumental",
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


def random_scene() -> str:
    return random.choice(ALL_SCENES)


def hook_for_scene(scene: str) -> tuple[str, str]:
    return random.choice(HOOK_BY_SCENE.get(scene, HOOK_BY_SCENE["cat"]))


def is_allowed_animal_text(text: str) -> bool:
    lowered = text.lower()
    # Normaliza underscores para espacos para matching (ex: ai_art -> ai art)
    normalized = lowered.replace("_", " ")
    combined = f"{lowered} {normalized}"
    if any(kw in combined for kw in BLOCKED_BROLL_KEYWORDS):
        return False
    return any(kw in combined for kw in ALLOWED_ANIMAL_KEYWORDS)


def channel_title_prefix() -> str:
    return "Pata Jazz"
