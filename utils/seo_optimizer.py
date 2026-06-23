"""Deterministic SEO polish for Wild Brief Shorts metadata."""

from __future__ import annotations

import os
import re

_ANIMAL_ALIASES = {
    "bear": "Bears",
    "bears": "Bears",
    "ant": "Ants",
    "ants": "Ants",
    "bat": "Bats",
    "bats": "Bats",
    "bee": "Bees",
    "bees": "Bees",
    "beetle": "Beetles",
    "beetles": "Beetles",
    "bird": "Birds",
    "birds": "Birds",
    "butterfly": "Butterflies",
    "butterflies": "Butterflies",
    "cat": "Cats",
    "cats": "Cats",
    "kitten": "Kittens",
    "kittens": "Kittens",
    "chameleon": "Chameleons",
    "chameleons": "Chameleons",
    "chicken": "Chickens",
    "chickens": "Chickens",
    "coral": "Corals",
    "corals": "Corals",
    "cow": "Cows",
    "cows": "Cows",
    "crocodile": "Crocodiles",
    "crocodiles": "Crocodiles",
    "deer": "Deer",
    "dog": "Dogs",
    "dogs": "Dogs",
    "puppy": "Puppies",
    "puppies": "Puppies",
    "dolphin": "Dolphins",
    "dolphins": "Dolphins",
    "dragonfly": "Dragonflies",
    "dragonflies": "Dragonflies",
    "duck": "Ducks",
    "ducks": "Ducks",
    "duckling": "Ducklings",
    "ducklings": "Ducklings",
    "eagle": "Eagles",
    "eagles": "Eagles",
    "elephant": "Elephants",
    "elephants": "Elephants",
    "fish": "Fish",
    "firefly": "Fireflies",
    "fireflies": "Fireflies",
    "flamingo": "Flamingos",
    "flamingos": "Flamingos",
    "fox": "Foxes",
    "foxes": "Foxes",
    "gecko": "Geckos",
    "geckos": "Geckos",
    "goat": "Goats",
    "goats": "Goats",
    "hedgehog": "Hedgehogs",
    "hedgehogs": "Hedgehogs",
    "hummingbird": "Hummingbirds",
    "hummingbirds": "Hummingbirds",
    "horse": "Horses",
    "horses": "Horses",
    "iguana": "Iguanas",
    "iguanas": "Iguanas",
    "ladybird": "Ladybirds",
    "ladybirds": "Ladybirds",
    "ladybug": "Ladybugs",
    "ladybugs": "Ladybugs",
    "lemur": "Lemurs",
    "lemurs": "Lemurs",
    "leopard": "Leopards",
    "leopards": "Leopards",
    "lion": "Lions",
    "lions": "Lions",
    "octopus": "Octopuses",
    "octopuses": "Octopuses",
    "owl": "Owls",
    "owls": "Owls",
    "macaque": "Macaques",
    "macaques": "Macaques",
    "macaw": "Macaws",
    "macaws": "Macaws",
    "mallard": "Ducks",
    "mallards": "Ducks",
    "mantis": "Mantises",
    "mantises": "Mantises",
    "monkey": "Monkeys",
    "monkeys": "Monkeys",
    "orangutan": "Orangutans",
    "orangutans": "Orangutans",
    "parrot": "Parrots",
    "parrots": "Parrots",
    "penguin": "Penguins",
    "penguins": "Penguins",
    "rat": "Rats",
    "rats": "Rats",
    "seal": "Seals",
    "seals": "Seals",
    "shark": "Sharks",
    "sharks": "Sharks",
    "sheep": "Sheep",
    "snake": "Snakes",
    "snakes": "Snakes",
    "tiger": "Tigers",
    "tigers": "Tigers",
    "turtle": "Turtles",
    "turtles": "Turtles",
    "whale": "Whales",
    "whales": "Whales",
    "walrus": "Walruses",
    "walruses": "Walruses",
    "wolf": "Wolves",
    "wolves": "Wolves",
}

_ANIMAL_WORDS = set(_ANIMAL_ALIASES)
_NON_ANIMAL_CATEGORIES = {
    "astronomy",
    "chemistry",
    "conservation",
    "discoveries",
    "earth_from_space",
    "ecosystems",
    "forests",
    "fungi",
    "geology",
    "microscopy",
    "mountains",
    "physics",
    "plants",
    "rare_phenomena",
    "rivers",
    "trees",
    "volcanoes",
    "weather",
}


def _words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9']+", text or "")


def _animal_from_text(*parts: str) -> str:
    for part in parts:
        for word in re.findall(r"[a-z]+", (part or "").lower()):
            if word in _ANIMAL_ALIASES:
                return _ANIMAL_ALIASES[word]
    return ""


def _category_key(category: str) -> str:
    return str(category or "").strip().lower().replace("-", "_")


def _is_non_animal_category(category: str, *parts: str) -> bool:
    return _category_key(category) in _NON_ANIMAL_CATEGORIES and not _animal_from_text(*parts)


def _clean_title(title: str) -> str:
    title = (title or "").replace("’", "'")
    title = re.sub(r"[^\w\s'—-]", "", title or "", flags=re.UNICODE)
    title = re.sub(r"\s+", " ", title).strip(" -—")
    return title[:1].upper() + title[1:] if title else ""


def _frontload_title(title: str, animal: str) -> str:
    cleaned = _clean_title(title)
    if not animal:
        return cleaned
    cleaned = _drop_redundant_category_prefix(cleaned, animal)
    first_words = [w.lower() for w in _words(cleaned)[:3]]
    if first_words and first_words[0] in _ANIMAL_WORDS:
        return cleaned
    animal_root = animal.lower()[:-1] if animal.lower().endswith("s") else animal.lower()
    if any(
        word.replace("'s", "") == animal_root or word.replace("'s", "") == animal_root + "s" for word in first_words
    ):
        return cleaned
    lower = cleaned.lower()
    for prefix in ("why ", "how "):
        if lower.startswith(prefix):
            rest = cleaned[len(prefix) :].strip()
            rest_words = [w.lower() for w in _words(rest)[:1]]
            if rest_words and rest_words[0] in _ANIMAL_WORDS:
                return rest[:1].upper() + rest[1:]
            return f"{animal} {rest}".strip()
    if lower.startswith(("this ", "these ", "they ")):
        return f"{animal} {cleaned}".strip()
    return f"{animal} {cleaned}".strip()


def _drop_redundant_category_prefix(title: str, animal: str) -> str:
    """Remove generic category prefixes such as 'Birds This black bird...'."""
    words = _words(title)
    if len(words) < 2:
        return title
    first = words[0].lower()
    canonical = animal.lower()
    singular = canonical[:-1] if canonical.endswith("s") else canonical
    if first not in {canonical, singular}:
        return title
    next_window = " ".join(words[1:5]).lower().replace("'s", "")
    if re.search(rf"\b{re.escape(singular)}s?\b", next_window):
        return re.sub(r"^\s*\S+\s+", "", title, count=1).strip()
    if words[1].lower() in {"this", "these", "white", "black", "gray", "grey", "baby"}:
        return re.sub(r"^\s*\S+\s+", "", title, count=1).strip()
    return title


def optimise_title(
    title: str, *, hook: str = "", script: str = "", tags: list[str] | None = None, category: str = ""
) -> str:
    """Return a compact title with the animal/search keyword front-loaded."""
    animal = _animal_from_text(title, hook, script, " ".join(tags or []), category)
    out = _frontload_title(title, animal)
    out = re.sub(r"\bwhy\b", "", out, flags=re.I).strip()
    out = re.sub(r"\s+", " ", out).strip(" -—")
    out = out[:1].upper() + out[1:] if out else out
    if len(out) > 60:
        out = out[:57].rstrip(" .,;:-—") + "..."
    return out or _clean_title(title)


def seo_score(title: str, *, subject: str = "", category: str = "") -> dict:
    words = _words(title)
    first = [w.lower() for w in words[:3]]
    issues: list[str] = []
    score = 100
    weak_front = bool(first and first[0] in {"why", "how", "this", "these"})
    non_animal_category = _is_non_animal_category(category, title, subject)
    if weak_front:
        score -= 10
        issues.append("weak_search_front")
    if not non_animal_category and (not first or first[0] not in _ANIMAL_WORDS):
        score -= 28
        issues.append("animal_not_front_loaded")
    if len(title or "") < 32:
        score -= 8
        issues.append("title_too_short_for_search")
    if len(title or "") > 60:
        score -= 10
        issues.append("title_too_long_for_shorts")
    return {"score": max(0, score), "issues": issues}


def lint_metadata(meta: dict, recent_titles: list[str] | None = None, *, strict: bool | None = None) -> dict:
    """Return deterministic SEO/search lint for generated metadata."""
    enabled = os.environ.get("SEO_METADATA_LINT_ENABLED", "1").strip().lower() not in {"0", "false", "no"}
    if not enabled:
        return {"enabled": False, "approved": True, "score": 100, "errors": [], "warnings": []}
    strict = (
        os.environ.get("SEO_METADATA_LINT_STRICT", "0").strip().lower() in {"1", "true", "yes", "on"}
        if strict is None
        else strict
    )
    title = str(meta.get("title") or "")
    description = str(meta.get("description") or "")
    tags = [str(tag).strip().lstrip("#") for tag in (meta.get("tags") or []) if str(tag).strip()]
    title_score = seo_score(
        title,
        subject=str(meta.get("subject") or meta.get("animal") or ""),
        category=str(meta.get("category") or ""),
    )
    score = int(title_score.get("score", 0))
    errors: list[str] = []
    warnings: list[str] = list(title_score.get("issues") or [])
    if not title:
        errors.append("title_missing")
    if len(title) > 100:
        errors.append("title_over_youtube_limit")
    if title.lower().strip() in {"animal fact of the day", "nature fact of the day"}:
        errors.append("generic_title")
        score -= 20
    if len(description) > 5000:
        errors.append("description_over_youtube_limit")
    for tag in ("#Shorts", "#NatureFacts", "#WildBrief"):
        if tag.lower() not in {part.lower() for part in description.split() if part.startswith("#")}:
            warnings.append(f"missing_{tag.lstrip('#').lower()}_hashtag")
            score -= 4
    lowered = [tag.lower() for tag in tags]
    if len(lowered) != len(set(lowered)):
        warnings.append("duplicate_tags")
        score -= 6
    if len(tags) < 3:
        warnings.append("thin_tag_set")
        score -= 6
    recent = {str(item).strip().lower() for item in recent_titles or [] if str(item).strip()}
    if title.strip().lower() in recent:
        errors.append("repeated_title")
        score -= 18
    score = max(0, min(100, score))
    approved = not errors and (score >= (82 if strict else 70))
    return {
        "enabled": True,
        "approved": approved,
        "strict": strict,
        "score": score,
        "errors": errors,
        "warnings": sorted(set(warnings)),
    }


def optimise_story(story: dict) -> dict:
    out = dict(story)
    title = str(out.get("seo_title") or out.get("title") or "")
    optimised = optimise_title(
        title,
        hook=str(out.get("hook") or ""),
        script=str(out.get("script") or ""),
        tags=[str(t) for t in (out.get("yt_tags") or [])],
        category=str(out.get("category") or ""),
    )
    out["seo_title"] = optimised
    out["title"] = optimised
    out["seo_optimisation"] = {
        "applied": optimised != title,
        "before_title": title,
        "after_title": optimised,
        **seo_score(
            optimised,
            subject=str(out.get("subject") or out.get("animal") or ""),
            category=str(out.get("category") or ""),
        ),
    }
    return out
