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
