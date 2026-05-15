#!/usr/bin/env python3
"""Generates static tag pages under _tags/ for Jekyll (GitHub Pages compatible).
Also removes orphan tag pages whose tags no longer exist in any post.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from utils.frontmatter import parse, get_list

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

POSTS_DIR = Path(__file__).parent / "_posts"
TAGS_DIR  = Path(__file__).parent / "_tags"

_SLUG_RE  = re.compile(r"[^\w\s-]")
_SPACE_RE = re.compile(r"[\s_]+")


def tag_to_slug(tag: str) -> str:
    slug = tag.lower()
    slug = _SLUG_RE.sub("", slug)
    slug = _SPACE_RE.sub("-", slug)
    return slug.strip("-")


def generate_tag_file(tag: str) -> str:
    # Escape any single quote inside the tag for the YAML title.
    safe_tag = tag.replace("'", "''")
    return (
        f"---\n"
        f'layout: tag\n'
        f'title: "Posts tagged \'{safe_tag}\'"\n'
        f"tag: {tag}\n"
        f"permalink: /tag/{tag_to_slug(tag)}/\n"
        f"---\n"
    )


def main() -> None:
    TAGS_DIR.mkdir(exist_ok=True)

    all_tags: set[str] = set()
    for path in POSTS_DIR.glob("*.md"):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            fm   = parse(text)
            for tag in get_list(fm, "tags"):
                tag = (tag or "").strip()
                if tag:
                    all_tags.add(tag)
        except Exception as e:
            log.warning("Could not read %s: %s", path.name, e)

    expected_slugs = {tag_to_slug(tag) for tag in all_tags}

    generated = 0
    for tag in sorted(all_tags):
        slug = tag_to_slug(tag)
        if not slug:
            continue
        out_path = TAGS_DIR / f"{slug}.md"
        content = generate_tag_file(tag)
        if out_path.exists() and out_path.read_text(encoding="utf-8") == content:
            continue
        out_path.write_text(content, encoding="utf-8")
        generated += 1

    removed = 0
    for existing in TAGS_DIR.glob("*.md"):
        if existing.stem not in expected_slugs:
            try:
                existing.unlink()
                removed += 1
                log.info("Removed orphan tag page: %s", existing.name)
            except Exception as e:
                log.warning("Could not remove %s: %s", existing.name, e)

    log.info(
        "Tags: %d total, %d page(s) generated/updated, %d orphan(s) removed",
        len(all_tags), generated, removed,
    )


if __name__ == "__main__":
    main()
