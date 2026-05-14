#!/usr/bin/env python3
"""Generate a monthly best-of roundup post."""
import os
import glob
import logging
from collections import Counter
from datetime import date, datetime
from pathlib import Path

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    data: dict = {}
    for line in parts[1].splitlines():
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if v.startswith("[") and v.endswith("]"):
            data[k] = [x.strip().strip('"').strip("'") for x in v[1:-1].split(",")]
        else:
            data[k] = v
    return data, parts[2].strip()


def main():
    today = date.today()
    # Last month
    if today.month == 1:
        year, month = today.year - 1, 12
    else:
        year, month = today.year, today.month - 1

    month_str = f"{year}-{month:02d}"
    month_name = datetime(year, month, 1).strftime("%B %Y")

    # Find last month's posts
    posts = []
    for path in glob.glob(f"_posts/{month_str}-*.md"):
        stem = Path(path).stem
        # Skip meta-posts
        if any(x in stem for x in ("roundup", "digest", "milestone", "stats")):
            continue
        try:
            text = Path(path).read_text(encoding="utf-8")
            fm, body = parse_frontmatter(text)
            title = fm.get("title", "").strip('"').strip("'")
            cats = fm.get("categories", [])
            cat = (cats[0] if isinstance(cats, list) and cats else "").strip()
            desc = fm.get("description", "").strip('"').strip("'")
            posts.append({"path": path, "title": title, "cat": cat, "desc": desc, "fm": fm})
        except Exception:
            pass

    if len(posts) < 5:
        logging.info(f"Only {len(posts)} posts in {month_name}, skipping roundup")
        return

    # Stats
    cat_counts: Counter = Counter(p["cat"] for p in posts if p["cat"])
    total = len(posts)
    top_cats = cat_counts.most_common(5)

    # Pick first post of each top category
    featured = []
    for cat, _ in top_cats[:5]:
        cat_posts = [p for p in posts if p["cat"] == cat]
        if cat_posts:
            featured.append(cat_posts[0])

    # Use Groq to write intro
    groq_key = os.getenv("GROQ_API_KEY")
    intro = (
        f"Here's a look back at {month_name} — {total} articles published "
        f"across {len(cat_counts)} categories."
    )

    if groq_key:
        try:
            titles_sample = "; ".join(p["title"] for p in posts[:10])
            r = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
                json={
                    "model": "llama-3.1-8b-instant",
                    "messages": [{
                        "role": "user",
                        "content": (
                            f"Write a 2-sentence journalistic intro for a monthly news roundup "
                            f"for {month_name}. {total} articles were published. "
                            f"Top stories: {titles_sample}. Be concise and engaging."
                        ),
                    }],
                    "max_tokens": 100,
                },
                timeout=20,
            )
            if r.status_code == 200:
                intro = r.json()["choices"][0]["message"]["content"].strip()
        except Exception:
            pass

    # Build markdown body
    body = f"{intro}\n\n## By the Numbers\n\n| Category | Articles |\n|---|---|\n"
    for cat, count in top_cats:
        body += f"| {cat.capitalize()} | {count} |\n"
    body += f"\n**Total:** {total} articles\n\n## Top Stories\n\n"

    for p in featured:
        stem = Path(p["path"]).stem
        parts = stem.split("-", 3)
        if len(parts) >= 4:
            y, mo, d, slug = parts[0], parts[1], parts[2], parts[3]
            url = f"/{p['cat']}/{y}/{mo}/{d}/{slug}/"
            body += f"- [{p['title']}]({url})"
            if p["desc"]:
                body += f" — {p['desc'][:100]}"
            body += "\n"

    # Build post
    slug = f"{today.strftime('%Y-%m-%d')}-monthly-roundup-{month_str}"
    filepath = f"_posts/{slug}.md"

    if Path(filepath).exists():
        logging.info(f"Roundup already exists: {filepath}")
        return

    frontmatter = (
        f"---\n"
        f'title: "Month in Review: {month_name}"\n'
        f'date: {datetime.utcnow().isoformat()}\n'
        f'categories: [roundup]\n'
        f'tags: [monthly, roundup, {month_name.lower().replace(" ", "-")}]\n'
        f'description: "A look back at {month_name}: {total} articles across {len(cat_counts)} categories."\n'
        f'featured: true\n'
        f"---\n"
    )

    content = frontmatter + "\n" + body
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    logging.info(f"Monthly roundup created: {filepath}")


if __name__ == "__main__":
    main()
