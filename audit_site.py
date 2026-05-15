#!/usr/bin/env python3
"""Weekly site audit — checks posts for quality issues and generates _data/audit_report.json"""
import json
import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

from utils.frontmatter import parse as parse_frontmatter, get_str, get_list

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

POSTS_DIR   = Path("_posts")
DATA_DIR    = Path("_data")
OUTPUT_FILE = DATA_DIR / "audit_report.json"

OLD_POST_DAYS          = int(os.environ.get("AUDIT_MAX_AGE_DAYS",      "90"))
SHORT_TITLE_CHARS      = int(os.environ.get("AUDIT_MIN_TITLE_CHARS",   "20"))
MIN_POSTS_PER_CATEGORY = int(os.environ.get("AUDIT_MIN_POSTS_PER_CAT", "3"))
SHORT_DESC_CHARS       = int(os.environ.get("AUDIT_MIN_DESC_CHARS",    "50"))


def main() -> None:
    if not POSTS_DIR.exists():
        logging.warning("_posts/ directory not found — nothing to audit")
        return

    DATA_DIR.mkdir(exist_ok=True)

    posts_without_image: list[str] = []
    posts_without_description: list[str] = []
    posts_without_tags: list[str] = []
    posts_without_categories: list[str] = []
    posts_short_title: list[str] = []
    old_posts: list[str] = []
    category_counts: dict[str, int] = {}

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=OLD_POST_DAYS)

    md_files = sorted(POSTS_DIR.glob("*.md"))
    total_posts = len(md_files)
    logging.info(f"Auditing {total_posts} post(s)…")

    for post_path in md_files:
        text = post_path.read_text(encoding="utf-8", errors="replace")
        fm   = parse_frontmatter(text)
        slug = post_path.name

        if not get_str(fm, "image"):
            posts_without_image.append(slug)

        desc = get_str(fm, "description")
        if not desc or len(desc) < SHORT_DESC_CHARS:
            posts_without_description.append(slug)

        tags = get_list(fm, "tags")
        if not tags:
            posts_without_tags.append(slug)

        cats = get_list(fm, "categories")
        if not cats:
            posts_without_categories.append(slug)
        else:
            for cat in cats:
                cat = cat.strip()
                if cat:
                    category_counts[cat] = category_counts.get(cat, 0) + 1

        title = get_str(fm, "title")
        if len(title) < SHORT_TITLE_CHARS:
            posts_short_title.append(slug)

        date_str = get_str(fm, "date")
        if date_str:
            try:
                # Accept "2026-01-19 14:00:00 +0000" or "2026-01-19"
                date_part = date_str[:10]
                post_date = datetime.strptime(date_part, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                if post_date < cutoff:
                    old_posts.append(slug)
            except ValueError:
                pass
        else:
            # Try to extract date from filename: YYYY-MM-DD-slug.md
            name_parts = post_path.stem.split("-", 3)
            if len(name_parts) >= 3:
                try:
                    post_date = datetime(
                        int(name_parts[0]), int(name_parts[1]), int(name_parts[2]),
                        tzinfo=timezone.utc
                    )
                    if post_date < cutoff:
                        old_posts.append(slug)
                except (ValueError, IndexError):
                    pass

    # categories with fewer than MIN_POSTS_PER_CATEGORY
    thin_categories = {k: v for k, v in category_counts.items() if v < MIN_POSTS_PER_CATEGORY}

    issues_count = (
        len(posts_without_image)
        + len(posts_without_description)
        + len(posts_without_tags)
        + len(posts_without_categories)
        + len(posts_short_title)
    )

    report = {
        "date": now.strftime("%Y-%m-%d %H:%M UTC"),
        "total_posts": total_posts,
        "posts_without_image": posts_without_image,
        "posts_without_description": posts_without_description,
        "posts_without_tags": posts_without_tags,
        "posts_without_categories": posts_without_categories,
        "posts_short_title": posts_short_title,
        "category_counts": dict(sorted(category_counts.items(), key=lambda x: x[1], reverse=True)),
        "thin_categories": thin_categories,
        "old_posts_count": len(old_posts),
        "old_posts": old_posts,
        "issues_count": issues_count,
    }

    OUTPUT_FILE.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    logging.info(f"Report written to {OUTPUT_FILE}")
    logging.info(f"Total posts: {total_posts}")
    logging.info(f"Issues found: {issues_count}")
    logging.info(f"Old posts (>{OLD_POST_DAYS}d): {len(old_posts)}")
    logging.info(f"Categories: {json.dumps(report['category_counts'])}")


if __name__ == "__main__":
    main()
