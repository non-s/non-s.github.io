"""Regras determinísticas para auditar metadados públicos do Pata Jazz."""

from __future__ import annotations

import re

_CAT_RE = re.compile(r"\b(cat|cats|kitten|kittens|kitty|kitties)\b", re.IGNORECASE)
_DOG_RE = re.compile(r"\b(dog|dogs|puppy|puppies)\b", re.IGNORECASE)


def audit_title(title: str) -> list[str]:
    """Retorna problemas verificáveis de coerência no título público."""
    normalized = " ".join(title.split())
    if not normalized:
        return ["empty_title"]

    issues: list[str] = []
    has_cat = bool(_CAT_RE.search(normalized))
    has_dog = bool(_DOG_RE.search(normalized))
    if has_cat and has_dog:
        issues.append("mixed_cat_dog_keywords")
    if normalized.lower().count("pata jazz") > 1:
        issues.append("repeated_brand")
    return issues


def audit_description(title: str, description: str) -> list[str]:
    """Return species conflicts between a public title and description."""
    title_has_cat = bool(_CAT_RE.search(title))
    title_has_dog = bool(_DOG_RE.search(title))
    description_has_cat = bool(_CAT_RE.search(description))
    description_has_dog = bool(_DOG_RE.search(description))

    if title_has_cat and not title_has_dog and description_has_dog:
        return ["description_conflicts_with_cat_title"]
    if title_has_dog and not title_has_cat and description_has_cat:
        return ["description_conflicts_with_dog_title"]
    return []
