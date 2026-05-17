#!/usr/bin/env python3
"""
create_daily_briefing.py — Original AI-authored daily briefing post.

Picks the top 10 most-relevant stories from today's posts, then asks
Mistral to produce a single ~600-word editorial roundup with proper
attribution. Output is a brand-new post in `_posts/` with category=briefing.

This is *original derivative content*: we cite every source by name and
URL, follow fair-use excerpting limits, and emit Schema.org `about`
references so search engines can join the dots back to the source posts.

Idempotent: skips if today's briefing already exists.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime, timezone
from pathlib import Path

from utils.frontmatter import get_str, get_list
from utils.text import sanitize_text
from utils.ai_helper import ai_text
from utils.digest import (
    AUTO_POST_SLUG_MARKERS,
    base_score,
    build_post_url,
    cited_posts_yaml,
    first_image,
    load_posts_in_window,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

POSTS_DIR    = Path(__file__).parent / "_posts"
MIN_POSTS    = int(os.environ.get("BRIEFING_MIN_POSTS", "5"))
MAX_STORIES  = int(os.environ.get("BRIEFING_MAX_STORIES", "10"))


def _today_posts() -> list[tuple[Path, dict]]:
    today = date.today()
    triples = load_posts_in_window(POSTS_DIR, today, today, AUTO_POST_SLUG_MARKERS)
    return [(p, fm) for p, fm, _dt in triples]


def _ai_briefing(stories: list[tuple[Path, dict]]) -> str:
    bullets = []
    for _path, fm in stories:
        title = get_str(fm, "title", "Untitled")
        desc  = get_str(fm, "description")
        cat   = (get_list(fm, "categories") or ["news"])[0]
        source = get_str(fm, "source_name", "")
        bullets.append(f"- [{cat.upper()}] {title} — {desc[:160]} (source: {source})")
    catalog = "\n".join(bullets)

    today = date.today().strftime("%B %-d, %Y")
    prompt = (
        f"You are a world-class news editor writing today's GlobalBR News Daily Briefing for {today}.\n\n"
        f"Below are the top {len(stories)} stories of the day. Produce an editorial roundup of "
        f"550-650 words structured as:\n"
        f"1. One opening paragraph naming the 2-3 biggest threads of the day (40-60 words).\n"
        f"2. For each top thread, a 2-paragraph section with a clear ## H2 heading. The first paragraph "
        f"explains the development; the second connects it to other stories of the day.\n"
        f"3. A closing 'What we're watching tomorrow' paragraph with 2-3 forward-looking items.\n\n"
        f"RULES:\n"
        f"- Inline every claim with a Markdown link to its source post (use the slug pattern "
        f"`/category/YYYY/MM/DD/slug/`). Example: [The Verge reports](/technology/2026/05/15/some-slug/).\n"
        f"- Cite at least 6 of the original stories.\n"
        f"- AP style. No 'crucial', 'pivotal', 'delve', 'landscape'.\n"
        f"- Open with the most important fact. No hype.\n"
        f"- End every section with a one-sentence implication.\n\n"
        f"Today's catalog:\n{catalog}\n"
    )

    body = ai_text(prompt, seed=int(date.today().strftime("%Y%m%d")) % 9999, timeout=45)
    return (body or "").strip()


def _frontmatter(stories: list[tuple[Path, dict]], body: str) -> str:
    today = date.today()
    today_iso = datetime.now(timezone.utc).isoformat()
    headline = (
        f"Daily Briefing — {today.strftime('%B %-d, %Y')}: "
        f"{len(stories)} stories that shaped the day"
    )

    cited_yaml = cited_posts_yaml(stories)
    image = first_image(stories)

    return (
        "---\n"
        "layout: post\n"
        f'title: "{sanitize_text(headline)}"\n'
        f"date: {today_iso}\n"
        "categories: [briefing, world]\n"
        "tags: [daily-briefing, roundup, editorial]\n"
        'author: "GlobalBR News Desk"\n'
        f'description: "Daily editorial roundup of the top stories of {today.strftime("%B %-d, %Y")} — '
        f'{len(stories)} stories synthesised into one read."\n'
        'content_type: "analysis"\n'
        f'image: "{image}"\n'
        f'image_alt: "GlobalBR News Daily Briefing — {today.strftime("%B %-d, %Y")}"\n'
        'sentiment: "neutral"\n'
        'lang: "en"\n'
        "featured: true\n"
        f'{cited_yaml}'
        "---\n\n"
        f"{body}\n"
    )


def main() -> None:
    POSTS_DIR.mkdir(exist_ok=True)
    stories = _today_posts()
    if len(stories) < MIN_POSTS:
        log.info(
            "Only %d post(s) today (need ≥%d) — skipping briefing.",
            len(stories), MIN_POSTS,
        )
        return

    stories.sort(key=lambda pair: base_score(pair[1]), reverse=True)
    stories = stories[:MAX_STORIES]

    today = date.today()
    slug = f"{today.strftime('%Y-%m-%d')}-daily-briefing"
    out_path = POSTS_DIR / f"{slug}.md"
    if out_path.exists():
        log.info("Today's briefing already exists at %s — skipping.", out_path.name)
        return

    body = _ai_briefing(stories)
    if not body or len(body) < 400:
        log.warning("AI returned suspiciously short body (%d chars); aborting briefing.", len(body or ""))
        return

    out = _frontmatter(stories, body)
    out_path.write_text(out, encoding="utf-8")
    log.info("✅ Daily briefing created: %s (%d stories cited)", out_path.name, len(stories))


if __name__ == "__main__":
    main()
