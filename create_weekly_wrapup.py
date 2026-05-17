#!/usr/bin/env python3
"""
create_weekly_wrapup.py — Friday-evening weekly recap, AI-authored.

Aggregates the top 20 stories of the last 7 days, asks the AI fallback
chain to produce a long-form editorial wrap-up grouped by category, and
saves it as a flagship post (`category: [wrapup]`). Designed to live in
the /wrapup/ category and feed search-engine "Top Stories" / weekly digests.

Runs only on Fridays unless overridden via WEEKLY_FORCE=1.
"""
from __future__ import annotations

import logging
import os
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from utils.frontmatter import parse, get_str, get_list
from utils.text import sanitize_text
from utils.ai_helper import ai_text

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

POSTS_DIR = Path(__file__).parent / "_posts"
MIN_POSTS = int(os.environ.get("WRAPUP_MIN_POSTS", "10"))
TOP_N     = int(os.environ.get("WRAPUP_TOP_N", "20"))
SKIP      = {"briefing", "roundup", "digest", "milestone", "stats", "wrapup"}


def _week_window() -> tuple[date, date]:
    today = date.today()
    return today - timedelta(days=6), today


def _recent_posts() -> list[tuple[Path, dict, date]]:
    start, end = _week_window()
    items: list[tuple[Path, dict, date]] = []
    for path in POSTS_DIR.glob("*.md"):
        if any(s in path.stem for s in SKIP):
            continue
        try:
            y, m, d = path.stem.split("-")[:3]
            dt = date(int(y), int(m), int(d))
        except Exception:
            continue
        if not (start <= dt <= end):
            continue
        try:
            fm = parse(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        items.append((path, fm, dt))
    return items


def _score(fm: dict, dt: date) -> int:
    score = 0
    if str(get_str(fm, "breaking", "")).lower() == "true":
        score += 50
    if str(get_str(fm, "featured", "")).lower() == "true":
        score += 30
    if get_str(fm, "fact_check") == "verified":
        score += 10
    if get_str(fm, "tl_dr"):
        score += 5
    if get_str(fm, "image"):
        score += 3
    # Recent days weight slightly higher (recency bias).
    age = (date.today() - dt).days
    score += max(0, 6 - age)
    return score


def _build_post_url(path: Path, fm: dict) -> str:
    parts = path.stem.split("-", 3)
    if len(parts) < 4:
        return ""
    y, m, d, slug = parts
    cats = get_list(fm, "categories")
    cat = (cats[0] if cats else "news").strip()
    return f"/{cat}/{y}/{m}/{d}/{slug}/"


def _ai_wrapup(by_category: dict[str, list[tuple[Path, dict]]]) -> str:
    today = date.today()
    start, end = _week_window()
    sections = []
    for cat, items in by_category.items():
        bullets = []
        for path, fm in items[:5]:  # top 5 per category in the prompt
            t = get_str(fm, "title", "Untitled")
            d = get_str(fm, "description", "")
            src = get_str(fm, "source_name", "")
            url = _build_post_url(path, fm)
            bullets.append(f"- {t} — {d[:140]} (source: {src}; permalink: {url})")
        sections.append(f"### {cat.capitalize()}\n" + "\n".join(bullets))
    catalog = "\n\n".join(sections)

    prompt = (
        f"You are a world-class news editor writing the GlobalBR News Weekly Wrap-up for the "
        f"week of {start.strftime('%B %-d')} – {end.strftime('%B %-d, %Y')}.\n\n"
        f"Below are this week's top stories grouped by category. Produce a long-form recap of "
        f"900-1200 words structured as:\n"
        f"1. Opening 'Week in 60 seconds' bullet list (5-7 punchy lines, no fluff).\n"
        f"2. One ## H2 section per category that had ≥3 stories. Each section: 2-3 paragraphs that "
        f"weave the stories into a coherent narrative.\n"
        f"3. Closing ## What we'll be watching next week — 4-5 bullet points.\n\n"
        f"RULES:\n"
        f"- Every claim must cite via Markdown link to the permalink in parentheses, e.g. "
        f"[More on the Senate vote](/politics/2026/05/14/some-slug/).\n"
        f"- AP style. No 'crucial', 'pivotal', 'delve', 'landscape', 'game-changer'.\n"
        f"- Cite at least 8 distinct stories.\n"
        f"- Open with the most important development of the week, not throat-clearing.\n\n"
        f"This week's catalog:\n{catalog}\n"
    )

    return (ai_text(prompt, seed=int(today.strftime("%Y%W")) % 9999, timeout=60) or "").strip()


def _frontmatter(top: list[tuple[Path, dict, date]], body: str) -> str:
    today = date.today()
    start, end = _week_window()
    iso = datetime.now(timezone.utc).isoformat()
    headline = (
        f"Weekly Wrap-up — {start.strftime('%b %-d')}–{end.strftime('%b %-d, %Y')}: "
        f"the {len(top)} stories that mattered"
    )

    image = ""
    for _, fm, _dt in top:
        if get_str(fm, "image"):
            image = get_str(fm, "image")
            break

    cited_yaml = "cited_posts:\n" + "".join(
        f'  - "{_build_post_url(p, fm)}"\n' for p, fm, _ in top if _build_post_url(p, fm)
    )

    return (
        "---\n"
        "layout: post\n"
        f'title: "{sanitize_text(headline)}"\n'
        f"date: {iso}\n"
        "categories: [wrapup, world]\n"
        "tags: [weekly-wrapup, recap, editorial]\n"
        'author: "GlobalBR News Desk"\n'
        f'description: "Editorial recap of the {len(top)} most important stories from '
        f'{start.strftime("%B %-d")} to {end.strftime("%B %-d, %Y")}."\n'
        'content_type: "analysis"\n'
        f'image: "{image}"\n'
        f'image_alt: "GlobalBR News Weekly Wrap-up"\n'
        'sentiment: "neutral"\n'
        'lang: "en"\n'
        "featured: true\n"
        f"{cited_yaml}"
        "---\n\n"
        f"{body}\n"
    )


def main() -> None:
    if not os.environ.get("WEEKLY_FORCE") and date.today().weekday() != 4:
        log.info("Today is not Friday — skipping weekly wrap-up. Set WEEKLY_FORCE=1 to override.")
        return

    POSTS_DIR.mkdir(exist_ok=True)
    items = _recent_posts()
    if len(items) < MIN_POSTS:
        log.info("Only %d post(s) this week (need ≥%d) — skipping wrap-up.", len(items), MIN_POSTS)
        return

    items.sort(key=lambda triple: _score(triple[1], triple[2]), reverse=True)
    top = items[:TOP_N]

    by_category: dict[str, list[tuple[Path, dict]]] = defaultdict(list)
    for path, fm, _dt in top:
        cat = (get_list(fm, "categories") or ["world"])[0].lower()
        by_category[cat].append((path, fm))

    today = date.today()
    slug = f"{today.strftime('%Y-%m-%d')}-weekly-wrapup"
    out_path = POSTS_DIR / f"{slug}.md"
    if out_path.exists():
        log.info("This week's wrap-up already exists at %s — skipping.", out_path.name)
        return

    body = _ai_wrapup(by_category)
    if not body or len(body) < 600:
        log.warning("AI returned short body (%d chars) — aborting.", len(body or ""))
        return

    out_path.write_text(_frontmatter(top, body), encoding="utf-8")
    log.info("✅ Weekly wrap-up created: %s (%d cited)", out_path.name, len(top))


if __name__ == "__main__":
    main()
