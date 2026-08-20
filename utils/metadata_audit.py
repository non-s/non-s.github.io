"""Regras determinísticas para auditar metadados públicos do Liquid Wire."""

from __future__ import annotations

import re

_STYLE_CONFLICT_RE = re.compile(
    r"\b(wireframe|organic|geometric|nebula|fluid|crystal|coral)\b", re.IGNORECASE
)
_CLICKBAIT_RE = re.compile(r"\b(shocking|must[- ]see|you won't believe|guaranteed|viral)\b", re.IGNORECASE)


def audit_title(title: str) -> list[str]:
    """Retorna problemas verificáveis de coerência no título público."""
    normalized = " ".join(title.split())
    if not normalized:
        return ["empty_title"]

    issues: list[str] = []
    if normalized.lower().count("liquid wire") > 1:
        issues.append("repeated_brand")
    if len(normalized) > 100:
        issues.append("title_too_long")
    if _CLICKBAIT_RE.search(normalized):
        issues.append("misleading_clickbait")
    return issues


def audit_description(title: str, description: str) -> list[str]:
    """Return style conflicts between a public title and description."""
    normalized = " ".join(description.split())
    issues: list[str] = []
    if not normalized:
        issues.append("empty_description")
    provenance = r"\b(procedural|generative|generated from code|code-generated)\b"
    if normalized and not re.search(provenance, normalized, re.I):
        issues.append("procedural_provenance_missing")
    if _CLICKBAIT_RE.search(title) or _CLICKBAIT_RE.search(description):
        issues.append("misleading_clickbait")
    return issues
