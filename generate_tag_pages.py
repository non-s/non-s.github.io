#!/usr/bin/env python3
"""Generates static tag pages under _tags/ for Jekyll (GitHub Pages compatible)."""
import re
from pathlib import Path

POSTS_DIR = Path(__file__).parent / "_posts"
TAGS_DIR = Path(__file__).parent / "_tags"


def extract_tags(text):
    """Extract tags from post frontmatter."""
    if not text.startswith("---"):
        return []
    parts = text.split("---", 2)
    if len(parts) < 3:
        return []
    fm_text = parts[1]

    # Find tags: line(s)
    # Handle inline list: tags: [a, b, c]
    inline = re.search(r"^tags:\s*\[([^\]]*)\]", fm_text, re.MULTILINE)
    if inline:
        raw = inline.group(1)
        return [t.strip().strip('"').strip("'") for t in raw.split(",") if t.strip()]

    # Handle block list:
    # tags:
    #   - a
    #   - b
    block = re.search(r"^tags:\s*\n((?:\s*-\s+.+\n?)+)", fm_text, re.MULTILINE)
    if block:
        items = re.findall(r"^\s*-\s+(.+)", block.group(1), re.MULTILINE)
        return [t.strip().strip('"').strip("'") for t in items if t.strip()]

    return []


def tag_to_slug(tag):
    """Convert tag to URL-safe slug (matches Jekyll's slugify filter)."""
    slug = tag.lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = slug.strip("-")
    return slug


def generate_tag_file(tag):
    """Return the content for a tag page."""
    return f"""---
layout: tag
title: "Posts tagged '{tag}'"
tag: {tag}
permalink: /tag/{tag_to_slug(tag)}/
---
"""


def main():
    TAGS_DIR.mkdir(exist_ok=True)

    # Collect all unique tags from posts
    all_tags = set()
    for path in POSTS_DIR.glob("*.md"):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            tags = extract_tags(text)
            all_tags.update(t for t in tags if t)
        except Exception:
            pass

    generated = 0
    for tag in sorted(all_tags):
        slug = tag_to_slug(tag)
        out_path = TAGS_DIR / f"{slug}.md"
        content = generate_tag_file(tag)

        # Idempotent: skip if file already has same content
        if out_path.exists() and out_path.read_text(encoding="utf-8") == content:
            continue

        out_path.write_text(content, encoding="utf-8")
        generated += 1

    print(f"Generated {generated} tag pages")


if __name__ == "__main__":
    main()
