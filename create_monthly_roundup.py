#!/usr/bin/env python3
"""Generate a monthly best-of roundup post."""
from __future__ import annotations

import logging
import os
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

from utils.frontmatter import parse, get_str
from utils.ai_helper import ai_text
from utils.digest import build_post_url

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

_ROOT      = Path(__file__).resolve().parent
POSTS_DIR  = _ROOT / "_posts"
MIN_POSTS  = int(os.environ.get("ROUNDUP_MIN_POSTS", "5"))
_SKIP      = ("roundup", "digest", "milestone", "stats", "best-of")


def _intro_text(month_name: str, total: int, titles_sample: str) -> str:
    """Try the shared ai_text helper (handles retries + rate limit) and
    fall back to a static line if the API is unreachable."""
    prompt = (
        f"Write a 2-sentence journalistic intro for a monthly news roundup "
        f"for {month_name}. {total} articles were published. "
        f"Top stories: {titles_sample}. Be concise and engaging."
    )
    body = ai_text(prompt, max_tokens=120, timeout=25)
    if body:
        return body.strip()
    return f"Here's a look back at {month_name} — {total} articles across many categories."


def main() -> None:
    today = date.today()
    if today.month == 1:
        year, month = today.year - 1, 12
    else:
        year, month = today.year, today.month - 1

    month_str  = f"{year}-{month:02d}"
    month_name = datetime(year, month, 1).strftime("%B %Y")

    posts: list[dict] = []
    for path in sorted(POSTS_DIR.glob(f"{month_str}-*.md")):
        if any(x in path.stem for x in _SKIP):
            continue
        try:
            fm    = parse(path.read_text(encoding="utf-8", errors="replace"))
            title = get_str(fm, "title")
            cat   = get_str(fm, "categories", "news")
            desc  = get_str(fm, "description")
            if title:
                posts.append({"path": path, "fm": fm, "title": title, "cat": cat, "desc": desc})
        except Exception as exc:
            log.warning("Skipping %s: %s", path.name, exc)

    if len(posts) < MIN_POSTS:
        log.info("Only %d posts in %s (min %d) — skipping roundup", len(posts), month_name, MIN_POSTS)
        return

    cat_counts: Counter = Counter(p["cat"] for p in posts if p["cat"])
    total      = len(posts)
    top_cats   = cat_counts.most_common(5)

    featured: list[dict] = []
    for cat, _ in top_cats[:5]:
        cat_posts = [p for p in posts if p["cat"] == cat]
        if cat_posts:
            featured.append(cat_posts[0])

    titles_sample = "; ".join(p["title"] for p in posts[:10])
    intro = _intro_text(month_name, total, titles_sample)
    log.info("Intro generated (%d chars)", len(intro))

    body = f"{intro}\n\n## By the Numbers\n\n| Category | Articles |\n|---|---|\n"
    for cat, count in top_cats:
        body += f"| {cat.capitalize()} | {count} |\n"
    body += f"\n**Total:** {total} articles\n\n## Top Stories\n\n"

    for p in featured:
        url = build_post_url(p["path"], p["fm"])
        if url:
            body += f"- [{p['title']}]({url})"
            if p["desc"]:
                body += f" — {p['desc'][:100]}"
            body += "\n"

    slug     = f"{today.strftime('%Y-%m-%d')}-monthly-roundup-{month_str}"
    filepath = POSTS_DIR / f"{slug}.md"

    if filepath.exists():
        log.info("Roundup already exists: %s", filepath)
        return

    frontmatter = (
        f"---\n"
        f'title: "Month in Review: {month_name}"\n'
        f"date: {datetime.now(timezone.utc).isoformat()}\n"
        f"categories: [roundup]\n"
        f'tags: [monthly, roundup, {month_name.lower().replace(" ", "-")}]\n'
        f'description: "A look back at {month_name}: {total} articles across {len(cat_counts)} categories."\n'
        f"featured: true\n"
        f"---\n"
    )

    filepath.write_text(frontmatter + "\n" + body, encoding="utf-8")
    log.info("Monthly roundup created: %s", filepath)


if __name__ == "__main__":
    main()
