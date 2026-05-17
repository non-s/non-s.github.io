#!/usr/bin/env python3
"""Weekly site audit — checks posts for quality issues and generates _data/audit_report.json"""
import json
import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

from utils.frontmatter import parse as parse_frontmatter, get_str, get_list

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

_ROOT       = Path(__file__).resolve().parent
POSTS_DIR   = _ROOT / "_posts"
DATA_DIR    = _ROOT / "_data"
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
    posts_without_faq: list[str] = []
    posts_without_keypoints: list[str] = []
    old_posts: list[str] = []
    duplicate_titles: dict[str, list[str]] = {}
    category_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}
    lang_counts: dict[str, int] = {}

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

        # Track duplicate titles across the corpus — same headline twice
        # usually means a feed deduped imperfectly or a dupe slipped past
        # the URL-based check.
        title_key = title.lower().strip()
        if title_key:
            duplicate_titles.setdefault(title_key, []).append(slug)

        # Track source diversity — if one outlet dominates, the front
        # page reads like a Reuters mirror.
        src = get_str(fm, "source_name").strip()
        if src:
            source_counts[src] = source_counts.get(src, 0) + 1

        # Track language split (en vs pt-br) for monitoring translation
        # coverage.
        lang = get_str(fm, "lang", "en").strip().lower()
        lang_counts[lang] = lang_counts.get(lang, 0) + 1

        # Posts that skipped FAQ / key_points usually scored low at the
        # AI quality gate — useful to spot drift if % goes up over time.
        if not fm.get("faq"):
            posts_without_faq.append(slug)
        if not fm.get("key_points"):
            posts_without_keypoints.append(slug)

        post_date: datetime | None = None
        date_str = get_str(fm, "date")
        if date_str:
            try:
                # Accept "2026-01-19 14:00:00 +0000" or "2026-01-19"
                date_part = date_str[:10]
                post_date = datetime.strptime(date_part, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                post_date = None
        if post_date is None:
            # Fall back to extracting from filename: YYYY-MM-DD-slug.md.
            # Runs whether `date_str` was missing OR malformed — otherwise
            # bad-date posts silently dodge the cutoff check.
            name_parts = post_path.stem.split("-", 3)
            if len(name_parts) >= 3:
                try:
                    post_date = datetime(
                        int(name_parts[0]), int(name_parts[1]), int(name_parts[2]),
                        tzinfo=timezone.utc
                    )
                except (ValueError, IndexError):
                    post_date = None
        if post_date is not None and post_date < cutoff:
            old_posts.append(slug)

    # categories with fewer than MIN_POSTS_PER_CATEGORY
    thin_categories = {k: v for k, v in category_counts.items() if v < MIN_POSTS_PER_CATEGORY}

    # Read persisted feed health (written by fetch_news.py) so the audit
    # report shows which feeds are silently failing.
    feed_health: dict[str, int] = {}
    try:
        fh_path = DATA_DIR / "feed_health.json"
        if fh_path.exists():
            feed_health = json.loads(fh_path.read_text(encoding="utf-8"))
    except Exception:
        pass
    dead_feeds = {name: fails for name, fails in feed_health.items() if fails >= 3}

    # Duplicate titles → list only those that actually collide.
    dupe_titles_report = {k: v for k, v in duplicate_titles.items() if len(v) > 1}

    issues_count = (
        len(posts_without_image)
        + len(posts_without_description)
        + len(posts_without_tags)
        + len(posts_without_categories)
        + len(posts_short_title)
        + len(dupe_titles_report)
    )

    report = {
        "date": now.strftime("%Y-%m-%d %H:%M UTC"),
        "total_posts": total_posts,
        "posts_without_image": posts_without_image,
        "posts_without_description": posts_without_description,
        "posts_without_tags": posts_without_tags,
        "posts_without_categories": posts_without_categories,
        "posts_short_title": posts_short_title,
        "posts_without_faq": posts_without_faq[:50],
        "posts_without_keypoints": posts_without_keypoints[:50],
        "duplicate_titles": dupe_titles_report,
        "category_counts": dict(sorted(category_counts.items(), key=lambda x: x[1], reverse=True)),
        "source_counts": dict(sorted(source_counts.items(), key=lambda x: x[1], reverse=True)),
        "lang_counts": lang_counts,
        "thin_categories": thin_categories,
        "old_posts_count": len(old_posts),
        "old_posts": old_posts,
        "dead_feeds": dead_feeds,
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
