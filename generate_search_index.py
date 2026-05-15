#!/usr/bin/env python3
"""Generates search-index.json with post metadata + excerpt for client-side search."""
from __future__ import annotations

import json
import re
from pathlib import Path

from utils.frontmatter import parse, get_list, get_str

POSTS_DIR = Path(__file__).parent / "_posts"
OUT       = Path(__file__).parent / "search-index.json"

_CODE_BLOCK_RE  = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`]+`")
_IMAGE_RE       = re.compile(r"!\[.*?\]\(.*?\)")
_LINK_RE        = re.compile(r"\[([^\]]+)\]\([^\)]+\)")
_HEADING_RE     = re.compile(r"#{1,6}\s+")
_BOLD_RE        = re.compile(r"[*_]{1,2}([^*_]+)[*_]{1,2}")
_LIST_RE        = re.compile(r"^\s*[-*+]\s+", re.MULTILINE)
_HTML_TAG_RE    = re.compile(r"<[^>]+>")
_WS_RE          = re.compile(r"\s+")


def strip_markdown(text: str) -> str:
    text = _CODE_BLOCK_RE.sub("", text)
    text = _INLINE_CODE_RE.sub("", text)
    text = _IMAGE_RE.sub("", text)
    text = _LINK_RE.sub(r"\1", text)
    text = _HEADING_RE.sub("", text)
    text = _BOLD_RE.sub(r"\1", text)
    text = _LIST_RE.sub("", text)
    text = _HTML_TAG_RE.sub(" ", text)
    return _WS_RE.sub(" ", text).strip()


def parse_post(path: Path) -> dict | None:
    text = path.read_text(encoding="utf-8", errors="replace")
    fm = parse(text)
    if not fm:
        return None

    parts = text.split("---", 2)
    body = parts[2] if len(parts) >= 3 else ""

    stem = path.stem
    date_parts = stem.split("-", 3)
    if len(date_parts) < 4:
        return None
    year, month, day, slug = date_parts
    if not (year.isdigit() and month.isdigit() and day.isdigit()):
        return None

    cats = get_list(fm, "categories")
    category = cats[0].strip() if cats else "news"
    title = get_str(fm, "title")
    if not title:
        return None

    return {
        "title":       title,
        "url":         f"/{category}/{year}/{month}/{day}/{slug}/",
        "date":        get_str(fm, "date")[:10],
        "category":    category,
        "tags":        get_list(fm, "tags"),
        "description": get_str(fm, "description"),
        "content":     strip_markdown(body)[:600],
        "image":       get_str(fm, "image"),
        "sentiment":   get_str(fm, "sentiment", "neutral"),
        "source":      get_str(fm, "source_name"),
    }


def main() -> None:
    index = []
    for path in sorted(POSTS_DIR.glob("*.md"), reverse=True):
        try:
            item = parse_post(path)
            if item:
                index.append(item)
        except Exception as exc:
            print(f"Warning: skipping {path.name} — {exc}")

    OUT.write_text(
        json.dumps(index, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"search-index.json: {len(index)} posts indexed")


if __name__ == "__main__":
    main()
