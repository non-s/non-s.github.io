"""
utils/text.py — Pure text utilities for Wild Brief.
No global state, no external HTTP calls, fully testable.
"""

from __future__ import annotations

import re
import unicodedata

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


# ── TTS-friendly text normaliser ───────────────────────────────────
# Strips markdown / HTML / entity noise so edge-tts doesn't literally
# pronounce "asterisk asterisk" when fed a string like **important**.

_MD_CODEBLOCK_RE = re.compile(r"```.*?```", re.DOTALL)
_MD_INLINECODE_RE = re.compile(r"`([^`]+)`")
_MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^\)]*\)")
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\([^\)]+\)")
_MD_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+", re.MULTILINE)
_MD_BLOCKQUOTE_RE = re.compile(r"^\s{0,3}>\s?", re.MULTILINE)
_MD_HRULE_RE = re.compile(r"^\s{0,3}([-*_])\s*\1\s*\1[\s\1]*$", re.MULTILINE)
_MD_LIST_BULLET_RE = re.compile(r"^\s*[-*+]\s+", re.MULTILINE)
_MD_LIST_NUMBER_RE = re.compile(r"^\s*\d+\.\s+", re.MULTILINE)
_MD_EMPHASIS_RE = re.compile(r"[*_]+")
_HTML_ENTITIES_TTS = {
    "&amp;": " and ",
    "&nbsp;": " ",
    "&lt;": " ",
    "&gt;": " ",
    "&quot;": '"',
    "&#39;": "'",
    "&apos;": "'",
    "&hellip;": "...",
    "&mdash;": " — ",
    "&ndash;": " – ",
}

# Abbreviations that read awkwardly when spoken literally. Order matters:
# longer patterns first so "U.S.A." matches before "U.S.". Word boundaries
# avoid eating substrings of normal words.
_TTS_ABBREVIATIONS = [
    (re.compile(r"\bU\.S\.A\.?"), "U S A"),
    (re.compile(r"\bU\.S\.\B|\bU\.S\.\s"), "U S "),
    (re.compile(r"\bU\.K\.\B|\bU\.K\.\s"), "U K "),
    (re.compile(r"\bE\.U\.\B|\bE\.U\.\s"), "E U "),
    (re.compile(r"\bDr\.\s+"), "Doctor "),
    (re.compile(r"\bMr\.\s+"), "Mister "),
    (re.compile(r"\bMrs\.\s+"), "Missus "),
    (re.compile(r"\bMs\.\s+"), "Miz "),
    (re.compile(r"\bProf\.\s+"), "Professor "),
    (re.compile(r"\bSen\.\s+"), "Senator "),
    (re.compile(r"\bRep\.\s+"), "Representative "),
    (re.compile(r"\bGov\.\s+"), "Governor "),
    (re.compile(r"\bvs\.\s+"), "versus "),
    (re.compile(r"\betc\."), "et cetera"),
    (re.compile(r"\bInc\."), "Incorporated"),
    (re.compile(r"\bCorp\."), "Corporation"),
    (re.compile(r"\bLtd\."), "Limited"),
    (re.compile(r"\s+&\s+"), " and "),
    (
        re.compile(r"\$(\d+(?:\.\d+)?)\s*(billion|million|trillion)\b", re.IGNORECASE),
        lambda m: f"{m.group(1)} {m.group(2).lower()} dollars",
    ),
    (re.compile(r"\$(\d+(?:\.\d+)?)\b"), r"\1 dollars"),
    # Percentages: "30%" → "30 percent"
    (re.compile(r"(\d+(?:\.\d+)?)\s*%"), r"\1 percent"),
]


def humanize_for_tts(text: str) -> str:
    """Strip markdown/HTML noise so TTS engines read prose, not syntax.

    The asterisks, underscores, hashes, backticks, brackets, and URLs
    that look invisible to a reader are read literally by edge-tts —
    "asterisk asterisk important asterisk asterisk", "hashtag hashtag
    section heading", etc. This collapses all of that to plain prose.
    """
    if not text:
        return ""
    t = text
    # Order matters: code/images/links before emphasis (so we don't
    # eat their delimiters first and leave dangling text).
    t = _MD_CODEBLOCK_RE.sub(" ", t)
    t = _MD_IMAGE_RE.sub(" ", t)
    t = _MD_LINK_RE.sub(r"\1", t)
    t = _MD_INLINECODE_RE.sub(r"\1", t)
    t = _MD_HEADING_RE.sub("", t)
    t = _MD_BLOCKQUOTE_RE.sub("", t)
    t = _MD_HRULE_RE.sub("", t)
    t = _MD_LIST_BULLET_RE.sub("", t)
    t = _MD_LIST_NUMBER_RE.sub("", t)
    # Strip all remaining * and _ (used for emphasis with arbitrary nesting).
    t = _MD_EMPHASIS_RE.sub("", t)
    # Strip lingering HTML tags.
    t = _HTML_RE.sub(" ", t)
    # Decode the most common entities; drop anything else by killing &xxx;.
    for entity, replacement in _HTML_ENTITIES_TTS.items():
        t = t.replace(entity, replacement)
    t = _ENTITY_RE.sub(" ", t)
    # Expand abbreviations that sound robotic when spoken letter-by-letter
    # or skipped entirely by TTS engines (e.g. "U.S." becomes silence).
    for pattern, replacement in _TTS_ABBREVIATIONS:
        t = pattern.sub(replacement, t)
    # Collapse whitespace (newlines become single spaces — TTS handles
    # pauses via punctuation, not line breaks).
    t = _WHITESPACE_RE.sub(" ", t).strip()
    return t
