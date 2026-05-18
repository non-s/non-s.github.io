#!/usr/bin/env python3
"""Generates static tag pages under _tags/ for Jekyll (GitHub Pages compatible).

Only emits a page when a tag has at least MIN_POSTS_PER_TAG posts —
single-use tags create thin-content pages that hurt SEO more than they
help (with 1.9k posts we used to ship 16k tag pages, 97% with one post
each). Tags below the threshold are still kept in post frontmatter so
they show up in lists/clouds; we just don't generate a dedicated
landing page that Google can index as thin content.

Override with `MIN_POSTS_PER_TAG=1` env var if you need the old
behaviour (e.g. to migrate or audit).
"""
from __future__ import annotations

import logging
import os
import re
from collections import Counter
from pathlib import Path

from utils.frontmatter import parse, get_list

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

POSTS_DIR = Path(__file__).parent / "_posts"
TAGS_DIR  = Path(__file__).parent / "_tags"

# Default threshold tuned for this corpus: 3 posts is the sweet spot
# between SEO health and keeping niche topics discoverable.
MIN_POSTS_PER_TAG = int(os.environ.get("MIN_POSTS_PER_TAG", "3"))

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

    tag_counts: Counter[str] = Counter()
    for path in POSTS_DIR.glob("*.md"):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            fm   = parse(text)
            for tag in get_list(fm, "tags"):
                tag = (tag or "").strip()
                if tag:
                    tag_counts[tag] += 1
        except Exception as e:
            log.warning("Could not read %s: %s", path.name, e)

    # Only keep tags that meet the threshold. The rest still appear in
    # post frontmatter so cloud/list views render them, but we don't
    # create a dedicated indexable landing page.
    eligible_tags = {t for t, n in tag_counts.items() if n >= MIN_POSTS_PER_TAG}
    expected_slugs = {tag_to_slug(t) for t in eligible_tags}

    generated = 0
    for tag in sorted(eligible_tags):
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
            except Exception as e:
                log.warning("Could not remove %s: %s", existing.name, e)

    skipped = sum(1 for n in tag_counts.values() if n < MIN_POSTS_PER_TAG)
    log.info(
        "Tags: %d total / %d eligible (>= %d posts) / "
        "%d skipped as thin content. "
        "%d page(s) generated/updated, %d orphan(s) removed.",
        len(tag_counts), len(eligible_tags), MIN_POSTS_PER_TAG,
        skipped, generated, removed,
    )


if __name__ == "__main__":
    main()
