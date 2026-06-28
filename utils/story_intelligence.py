"""Free story intelligence for growth-oriented Shorts production."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

FORMAT_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("animal_memory", ("remember", "recognize", "faces", "names", "grudge", "friend")),
    ("animal_intelligence", ("solve", "smart", "learn", "tool", "plan", "name", "map", "imprint", "compare")),
    ("earth_engine", ("lava", "volcano", "storm", "lightning", "river", "glacier", "erosion", "weather")),
    ("hidden_network", ("fungi", "mushroom", "mycelium", "roots", "signals", "network", "communicate")),
    ("rare_nature", ("aurora", "eclipse", "bioluminescent", "rare", "glow", "phenomenon")),
    ("conservation_signal", ("restore", "recover", "conservation", "reforestation", "biodiversity")),
    ("survival_trick", ("escape", "survive", "hide", "camouflage", "defense", "venom")),
    (
        "body_superpower",
        (
            "teeth",
            "bones",
            "eyes",
            "beak",
            "claw",
            "tail",
            "heart",
            "sense",
            "smell",
            "taste",
            "whisker",
            "pupil",
            "wing scales",
            "magnetic",
            "electric",
        ),
    ),
    ("myth_buster", ("not just", "isn't", "aren't", "myth", "think", "really")),
    ("cute_behavior", ("baby", "love", "play", "purr", "groom", "quietly", "bottle")),
)
NON_ANIMAL_CATEGORY_FORMATS = {
    "earth_from_space": "earth_engine",
    "weather": "earth_engine",
    "volcanoes": "earth_engine",
    "geology": "earth_engine",
    "rivers": "earth_engine",
    "mountains": "earth_engine",
    "ocean": "earth_engine",
    "forests": "hidden_network",
    "fungi": "hidden_network",
    "tree": "hidden_network",
    "trees": "hidden_network",
    "plants": "plant_mechanism",
    "ecosystems": "ecosystem_engine",
    "rare_phenomena": "rare_nature",
    "conservation": "conservation_signal",
    "discoveries": "science_clue",
    "space": "space_engine",
    "physics": "physics_demo",
    "chemistry": "chemistry_reaction",
    "microscopy": "micro_world",
}

TITLE_PATTERNS = (
    "{animal} can {surprising_ability}",
    "Why {animal} {behavior}",
    "{animal} remember {unexpected_thing}",
    "{animal} are not {common_belief}",
    "{animal} use {body_part} to {result}",
)

_ANIMAL_WORDS = {
    "bear",
    "bears",
    "bird",
    "birds",
    "cat",
    "cats",
    "chicken",
    "chickens",
    "deer",
    "dog",
    "dogs",
    "dolphin",
    "dolphins",
    "eagle",
    "elephant",
    "elephants",
    "goat",
    "goats",
    "macaw",
    "owl",
    "shark",
    "tiger",
    "whale",
    "whales",
    "wolf",
    "wolves",
    "cow",
    "cows",
    "duck",
    "duckling",
    "ducklings",
    "fox",
    "horse",
    "horses",
    "lion",
    "lions",
    "octopus",
    "octopuses",
    "parrot",
    "parrots",
    "penguin",
    "penguins",
    "seal",
    "seals",
    "snake",
    "snakes",
    "turtle",
    "turtles",
    "donkey",
    "donkeys",
    "sheep",
    "bee",
    "bees",
    "butterfly",
    "butterflies",
    "ant",
    "ants",
    "beetle",
    "beetles",
    "mantis",
    "mantises",
    "dragonfly",
    "dragonflies",
    "chameleon",
    "chameleons",
    "orangutan",
    "orangutans",
    "monkey",
    "monkeys",
    "plant",
    "plants",
    "leaf",
    "leaves",
    "flower",
    "flowers",
    "tree",
    "trees",
    "root",
    "roots",
    "forest",
    "forests",
    "fungi",
    "fungus",
    "mushroom",
    "mushrooms",
    "mycelium",
    "ocean",
    "sea",
    "coral",
    "reef",
    "river",
    "rivers",
    "waterfall",
    "mountain",
    "mountains",
    "glacier",
    "glaciers",
    "volcano",
    "volcanoes",
    "lava",
    "magma",
    "storm",
    "storms",
    "lightning",
    "tornado",
    "cloud",
    "clouds",
    "aurora",
    "eclipse",
    "rock",
    "rocks",
    "mineral",
    "minerals",
    "canyon",
    "cave",
    "ecosystem",
    "ecosystems",
    "earth",
    "planet",
    "atmosphere",
    "conservation",
    "biodiversity",
    "science",
    "fossil",
    "fossils",
    "biology",
    "space",
    "astronomy",
    "moon",
    "mars",
    "sun",
    "solar",
    "galaxy",
    "rocket",
    "satellite",
    "physics",
    "magnet",
    "magnets",
    "field",
    "fields",
    "wave",
    "waves",
    "light",
    "chemistry",
    "chemical",
    "reaction",
    "reactions",
    "crystal",
    "crystals",
    "microscope",
    "microscopy",
    "cell",
    "cells",
    "bacteria",
    "microbe",
    "microbes",
}
_STRICT_ANIMAL_WORDS = {
    "ant",
    "ants",
    "bat",
    "bats",
    "bear",
    "bears",
    "bee",
    "bees",
    "beetle",
    "beetles",
    "bird",
    "birds",
    "butterfly",
    "butterflies",
    "cat",
    "cats",
    "chameleon",
    "chameleons",
    "chicken",
    "chickens",
    "cow",
    "cows",
    "deer",
    "dog",
    "dogs",
    "dolphin",
    "dolphins",
    "duck",
    "duckling",
    "ducklings",
    "ducks",
    "eagle",
    "elephant",
    "elephants",
    "fish",
    "fox",
    "goat",
    "goats",
    "horse",
    "horses",
    "lion",
    "lions",
    "macaw",
    "mantis",
    "mantises",
    "monkey",
    "monkeys",
    "octopus",
    "octopuses",
    "orangutan",
    "orangutans",
    "owl",
    "parrot",
    "parrots",
    "penguin",
    "penguins",
    "seal",
    "seals",
    "shark",
    "sharks",
    "sheep",
    "snake",
    "snakes",
    "tiger",
    "turtle",
    "turtles",
    "whale",
    "whales",
    "wolf",
    "wolves",
}


@dataclass(frozen=True)
class Audit:
    score: int
    issues: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


def _has_strict_animal(text: str) -> bool:
    return any(word in _STRICT_ANIMAL_WORDS for word in re.findall(r"[a-z]+", (text or "").lower()))


def classify_format(text: str, category: str = "") -> str:
    lower = (text or "").lower()
    category_key = str(category or "").strip().lower()
    if category_key in NON_ANIMAL_CATEGORY_FORMATS and not _has_strict_animal(lower):
        return NON_ANIMAL_CATEGORY_FORMATS[category_key]
    if not _has_strict_animal(lower):
        for name in ("earth_engine", "hidden_network", "rare_nature", "conservation_signal"):
            needles = next((needles for rule, needles in FORMAT_RULES if rule == name), ())
            if any(needle in lower for needle in needles):
                return name
    for name, needles in FORMAT_RULES:
        if any(needle in lower for needle in needles):
            return name
    return "single_fact"


def _first_word(text: str) -> str:
    match = re.search(r"[A-Za-z][A-Za-z'-]*", text or "")
    return match.group(0).lower() if match else ""


def audit_hook(hook: str) -> Audit:
    words = re.findall(r"[A-Za-z0-9']+", hook or "")
    lower = (hook or "").lower().strip()
    score = 100
    issues: list[str] = []
    if not words:
        return Audit(score=0, issues=("missing_hook",))
    if len(words) > 10:
        score -= 18
        issues.append("hook_too_long")
    if _first_word(hook) in {"why", "how", "today", "this", "these"}:
        score -= 16
        issues.append("weak_first_word")
    if not any(word.lower() in _ANIMAL_WORDS for word in words[:4]):
        score -= 12
        issues.append("animal_not_front_loaded")
    if not re.search(
        r"\b(can|remember|recognize|use|survive|escape|heal|call|plan|love|have|are|is|"
        r"aim|carry|carries|cover|covered|fly|leave|lay|wear|taste|smell|sense|track|"
        r"steer|cool|imprint|compare|stabilize|trap|measure|detect|lock|sample)\b",
        lower,
    ):
        score -= 14
        issues.append("no_clear_payoff")
    if lower.endswith("?"):
        score -= 8
        issues.append("question_hook")
    return Audit(score=max(0, score), issues=tuple(issues))


def audit_title(title: str) -> Audit:
    words = re.findall(r"[A-Za-z0-9']+", title or "")
    lower = (title or "").lower()
    score = 100
    issues: list[str] = []
    if len(words) < 4:
        score -= 12
        issues.append("title_too_short")
    if len(title or "") > 68:
        score -= 14
        issues.append("title_too_long")
    if not any(word in lower for word in _ANIMAL_WORDS):
        score -= 18
        issues.append("missing_animal_keyword")
    if not any(word.lower() in _ANIMAL_WORDS for word in words[:3]):
        score -= 16
        issues.append("animal_not_front_loaded")
    if any(token in lower for token in ("won't believe", "shocking", "insane", "crazy")):
        score -= 20
        issues.append("clickbait_language")
    if any(
        token in lower
        for token in (
            "another signal hiding in plain sight",
            "another secret hiding in plain sight",
            "secret hiding in plain sight",
        )
    ):
        score -= 22
        issues.append("repetitive_template")
    if not any(
        token in lower
        for token in (
            "why",
            "can",
            "remember",
            "recognize",
            "use",
            "not",
            "love",
            "fake",
            "plan",
            "escape",
            "slide",
            "call",
            "hear",
            "hold",
            "keep",
            "keeps",
            "roar",
            "glow",
            "erupt",
            "build",
            "move",
            "signal",
            "survive",
            "protect",
            "form",
            "grow",
            "filter",
            "filters",
            "burn",
            "freeze",
            "breathe",
            "recover",
            "reveal",
            "reveals",
            "release",
            "releases",
            "reshape",
            "reshapes",
            "turn",
            "turns",
            "track",
            "tracks",
            "sort",
            "sorts",
            "slow",
            "slows",
            "steer",
            "steers",
            "trace",
            "traces",
            "make",
            "makes",
            "show",
            "shows",
            "map",
            "maps",
            "pull",
            "pulls",
        )
    ):
        score -= 10
        issues.append("weak_curiosity_shape")
    return Audit(score=max(0, score), issues=tuple(issues))


def postmortem(
    *, title: str, hook: str, views: int, views_per_hour: float, average_view_percentage: float, growth_score: float
) -> dict:
    hook_audit = audit_hook(hook)
    title_audit = audit_title(title)
    reasons: list[str] = []
    if hook_audit.score < 75:
        reasons.append("hook_needs_work")
    if title_audit.score < 75:
        reasons.append("title_needs_work")
    if average_view_percentage and average_view_percentage < 60:
        reasons.append("low_retention")
    if views_per_hour and views_per_hour < 5 and views < 500:
        reasons.append("low_initial_velocity")
    if growth_score < 60 and views < 500:
        reasons.append("weak_growth_signal")
    return {
        "story_format": classify_format(f"{title} {hook}"),
        "hook_audit": hook_audit.to_dict(),
        "title_audit": title_audit.to_dict(),
        "likely_causes": reasons,
    }
