"""
utils/frontmatter.py — Centralized Jekyll frontmatter parser.

Single source of truth used by all scripts. Avoids 6+ copies of the same
inline parser scattered across the codebase.
"""
from __future__ import annotations

import re

_ARRAY_RE = re.compile(r'^\[([^\]]*)\]$')


def parse(text: str) -> dict[str, str | list[str]]:
    """
    Parse Jekyll YAML frontmatter into a dict.

    Supports:
      - Scalar values:  key: value  /  key: "value"  /  key: 'value'
      - Inline arrays:  key: [a, b, c]
      - Block arrays:   key:\n  - a\n  - b

    Returns empty dict if text has no frontmatter.
    """
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}

    fm_text = parts[1]
    data: dict[str, str | list[str]] = {}
    lines = fm_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if ":" not in line or line.startswith(" ") or line.startswith("\t"):
            i += 1
            continue
        key, _, raw = line.partition(":")
        key = key.strip()
        raw = raw.strip()

        # Block list: key:\n  - item
        if raw == "" and i + 1 < len(lines) and lines[i + 1].lstrip().startswith("- "):
            items: list[str] = []
            i += 1
            while i < len(lines) and lines[i].lstrip().startswith("- "):
                item = lines[i].lstrip()[2:].strip().strip('"').strip("'")
                items.append(item)
                i += 1
            data[key] = items
            continue

        # Inline array: key: [a, b]
        m = _ARRAY_RE.match(raw)
        if m:
            data[key] = [
                v.strip().strip('"').strip("'")
                for v in m.group(1).split(",")
                if v.strip()
            ]
        else:
            data[key] = raw.strip('"').strip("'")

        i += 1

    return data


def get_str(fm: dict, key: str, default: str = "") -> str:
    """Return a string field, coercing list→first item."""
    val = fm.get(key, default)
    if isinstance(val, list):
        return val[0] if val else default
    return val or default


def get_list(fm: dict, key: str) -> list[str]:
    """Return a list field, coercing str→[str]."""
    val = fm.get(key, [])
    if isinstance(val, str):
        return [val] if val else []
    return val or []
