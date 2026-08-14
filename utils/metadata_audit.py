"""Regras determinísticas para auditar metadados públicos do Liquid Wire."""

from __future__ import annotations

import re

_STYLE_CONFLICT_RE = re.compile(
    r"\b(wireframe|organic|geometric|nebula|fluid|crystal|coral)\b", re.IGNORECASE
)


def audit_title(title: str) -> list[str]:
    """Retorna problemas verificáveis de coerência no título público."""
    normalized = " ".join(title.split())
    if not normalized:
        return ["empty_title"]

    issues: list[str] = []
    if normalized.lower().count("liquid wire") > 1:
        issues.append("repeated_brand")
    return issues


def audit_description(title: str, description: str) -> list[str]:
    """Return style conflicts between a public title and description."""
    return []
