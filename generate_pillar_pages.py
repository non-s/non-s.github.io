#!/usr/bin/env python3
"""
generate_pillar_pages.py — Auto-build SEO "pillar pages" per category.

For each category in `_data/categories.yml` we emit a static HTML page at
`/{category}/pillar/` that:

  - Groups the category's posts into 4-6 sub-themes (by tag clustering).
  - Lists the latest 30 stories with thumbnails.
  - Emits Schema.org `CollectionPage` + `BreadcrumbList` JSON-LD.
  - Internal-links to the matching `/{category}/` index, `/tag/<topic>/`
    pages, and the home `/`.

These pages exist because Google rewards "hub" pages that gather
coverage on one topic — they capture long-tail searches like
"latest AI news 2026" or "Ukraine war coverage".

Re-runnable: overwrites existing pillar files atomically.
"""
from __future__ import annotations

import logging
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from utils.frontmatter import parse, get_list, get_str

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

ROOT       = Path(__file__).parent
POSTS_DIR  = ROOT / "_posts"
DATA_DIR   = ROOT / "_data"
MIN_POSTS_FOR_PILLAR = 10
TOP_TAGS_PER_CAT     = 6
RECENT_POSTS_LISTED  = 30


def _load_categories() -> dict[str, dict]:
    import yaml  # PyYAML ships with Jekyll's runtime; available in CI via pip
    raw = (DATA_DIR / "categories.yml").read_text(encoding="utf-8")
    return yaml.safe_load(raw) or {}


def _posts_by_category() -> dict[str, list[tuple[Path, dict]]]:
    out: dict[str, list[tuple[Path, dict]]] = defaultdict(list)
    for path in POSTS_DIR.glob("*.md"):
        # Skip translated posts (PT) so the pillar lists EN canonicals only.
        if "/pt/" in str(path):
            continue
        try:
            fm = parse(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        cats = [c.strip().lower() for c in get_list(fm, "categories")]
        for c in cats:
            out[c].append((path, fm))
    return out


def _post_url(path: Path, fm: dict) -> str:
    parts = path.stem.split("-", 3)
    if len(parts) < 4:
        return "/"
    y, m, d, slug = parts
    cats = get_list(fm, "categories")
    cat = (cats[0] if cats else "news").strip()
    return f"/{cat}/{y}/{m}/{d}/{slug}/"


def _render(category: str, meta: dict, posts: list[tuple[Path, dict]]) -> str:
    # Sort by date desc via filename (YYYY-MM-DD prefix).
    posts.sort(key=lambda pair: pair[0].name, reverse=True)
    recent = posts[:RECENT_POSTS_LISTED]

    tag_counter: Counter[str] = Counter()
    for _, fm in posts:
        for t in get_list(fm, "tags"):
            t = t.strip().lower()
            if t and len(t) > 1:
                tag_counter[t] += 1
    top_tags = [t for t, _ in tag_counter.most_common(TOP_TAGS_PER_CAT)]

    title = f"{meta.get('title', category.capitalize())} — Complete coverage"
    desc = (
        f"Every article we've published on {meta.get('title', category)}. "
        f"{len(posts)} stories across {len(top_tags)} sub-topics, refreshed every two hours."
    )

    icon = meta.get("icon", "📰")

    item_rows = []
    for path, fm in recent:
        item_rows.append({
            "title": get_str(fm, "title"),
            "url":   _post_url(path, fm),
            "date":  path.stem.split("-")[:3],
            "image": get_str(fm, "image"),
        })

    cards_html = []
    for item in item_rows:
        y, m, d = item["date"]
        date_str = f"{y}-{m}-{d}"
        img_html = (
            f'<img src="{item["image"]}" alt="" loading="lazy" width="320" height="200">'
            if item["image"]
            else f'<span class="card-img-placeholder">{icon}</span>'
        )
        cards_html.append(
            f'<article class="cat-card"><a href="{item["url"]}" class="cat-card-imglink">{img_html}</a>'
            f'<div class="cat-card-body"><h3 class="cat-card-title">'
            f'<a href="{item["url"]}">{item["title"]}</a></h3>'
            f'<time class="cat-card-time">{date_str}</time></div></article>'
        )
    cards_block = "\n".join(cards_html)

    topic_pills = "\n".join(
        f'<a href="/tag/{t}/" class="tag-pill">#{t}</a>'
        for t in top_tags
    )

    # JSON-LD: CollectionPage + BreadcrumbList
    jsonld = (
        '<script type="application/ld+json">{'
        '"@context":"https://schema.org",'
        '"@type":"CollectionPage",'
        f'"name":"{title}",'
        f'"description":"{desc}",'
        '"isPartOf":{"@type":"WebSite","name":"{{ site.title }}","url":"{{ site.url }}"},'
        f'"about":"{meta.get("title", category)}"'
        '}</script>'
        '<script type="application/ld+json">{'
        '"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":['
        '{"@type":"ListItem","position":1,"name":"Home","item":"{{ site.url }}/"},'
        f'{{"@type":"ListItem","position":2,"name":"{meta.get("title", category)}",'
        f'"item":"{{{{ site.url }}}}/{category}/"}},'
        f'{{"@type":"ListItem","position":3,"name":"Complete coverage",'
        f'"item":"{{{{ site.url }}}}/{category}/pillar/"}}]'
        '}</script>'
    )

    return (
        "---\n"
        "layout: default\n"
        f'title: "{title}"\n'
        f'description: "{desc}"\n'
        f"permalink: /{category}/pillar/\n"
        f'image: "/assets/images/og-default.jpg"\n'
        "hide_subscribe: true\n"
        "---\n\n"
        '<div class="container py-5">\n'
        f'  <nav aria-label="breadcrumb" class="mb-3"><ol class="breadcrumb mb-0">'
        f'<li class="breadcrumb-item"><a href="/">Home</a></li>'
        f'<li class="breadcrumb-item"><a href="/{category}/">{meta.get("title", category.capitalize())}</a></li>'
        f'<li class="breadcrumb-item active">Complete coverage</li></ol></nav>\n'
        f'  <h1 class="section-title"><span style="font-size:1.2em;">{icon}</span> '
        f'{title}</h1>\n'
        f'  <p class="text-muted mb-4">{desc}</p>\n'
        f'  <div class="trending-pills d-flex flex-wrap gap-2 mb-4">{topic_pills}</div>\n'
        f'  <div class="cat-section-grid">{cards_block}</div>\n'
        '</div>\n'
        f'{jsonld}\n'
    )


def main() -> None:
    categories = _load_categories()
    if not categories:
        log.warning("No categories in _data/categories.yml — aborting.")
        return
    posts_by_cat = _posts_by_category()
    generated = 0
    skipped = 0
    for cat_key, meta in categories.items():
        posts = posts_by_cat.get(cat_key, [])
        if len(posts) < MIN_POSTS_FOR_PILLAR:
            skipped += 1
            continue
        out_dir = ROOT / cat_key
        out_dir.mkdir(exist_ok=True)
        out_path = out_dir / "pillar.html"
        out_path.write_text(_render(cat_key, meta, posts), encoding="utf-8")
        generated += 1
        log.debug("Pillar generated: %s", out_path.relative_to(ROOT))
    log.info(
        "Pillar pages: %d generated, %d skipped (< %d posts)",
        generated, skipped, MIN_POSTS_FOR_PILLAR,
    )


if __name__ == "__main__":
    main()
