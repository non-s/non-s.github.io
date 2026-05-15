"""
utils/text.py — Pure text utilities for GlobalBR News.
No global state, no external HTTP calls, fully testable.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone

_HTML_RE = re.compile(r"<[^>]+>")
_ENTITY_RE = re.compile(r"&[a-z]+;|&#\d+;")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_WHITESPACE_RE = re.compile(r"\s+")


def slugify(text: str) -> str:
    """Converte texto em slug URL-amigável."""
    text = text.lower().strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-{2,}", "-", text)
    return text[:80].strip("-")


def sanitize_text(text: str) -> str:
    """Remove caracteres problemáticos para YAML/Markdown."""
    if not text:
        return ""
    text = text.replace('"', "'").replace("\n", " ").replace("\r", " ")
    text = _CONTROL_RE.sub("", text)
    return text.strip()


def extract_description(entry: object) -> str:
    """Extrai descrição/resumo do item RSS, priorizando conteúdo mais longo."""
    candidates: list[str] = []
    if hasattr(entry, "content"):
        for c in entry.content:  # type: ignore[union-attr]
            val = c.get("value", "")
            if val:
                candidates.append(val)
    if hasattr(entry, "summary"):
        candidates.append(entry.summary)  # type: ignore[union-attr]
    if hasattr(entry, "description"):
        candidates.append(entry.description)  # type: ignore[union-attr]

    best = ""
    for raw in candidates:
        clean = _HTML_RE.sub(" ", raw)
        clean = _ENTITY_RE.sub(" ", clean)
        clean = _WHITESPACE_RE.sub(" ", clean).strip()
        if len(clean) > len(best):
            best = clean
    return sanitize_text(best[:800])


def extract_image(entry: object) -> str:
    """Tenta extrair URL de imagem do item RSS."""
    if hasattr(entry, "media_content"):
        for m in entry.media_content:  # type: ignore[union-attr]
            if m.get("type", "").startswith("image"):
                url = m.get("url", "")
                if url:
                    return url
    if hasattr(entry, "media_thumbnail"):
        for t in entry.media_thumbnail:  # type: ignore[union-attr]
            url = t.get("url", "")
            if url:
                return url
    if hasattr(entry, "enclosures"):
        for e in entry.enclosures:  # type: ignore[union-attr]
            if e.get("type", "").startswith("image"):
                url = e.get("href", "")
                if url:
                    return url
    content = ""
    if hasattr(entry, "content"):
        content = entry.content[0].get("value", "")  # type: ignore[union-attr]
    elif hasattr(entry, "summary"):
        content = entry.summary  # type: ignore[union-attr]
    match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', content)
    if match:
        return match.group(1)
    return ""


def parse_date(entry: object) -> datetime:
    """Extrai data do item RSS como objeto datetime (UTC)."""
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)  # type: ignore[union-attr]
    if hasattr(entry, "updated_parsed") and entry.updated_parsed:
        return datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)  # type: ignore[union-attr]
    return datetime.now(timezone.utc)
