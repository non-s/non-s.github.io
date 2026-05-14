#!/usr/bin/env python3
"""
post_mastodon.py
Auto-posts new articles to Mastodon using the standard Mastodon API.

Reads _posts/ for files modified in the last 2 hours and creates
a public toot with title + URL + hashtags.

Env vars required:
  MASTODON_INSTANCE     — instance URL, e.g. https://mastodon.social
  MASTODON_ACCESS_TOKEN — token from Settings → Development → New application
"""

import logging
import os
import sys
import time
from pathlib import Path

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("mastodon_post.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

POSTS_DIR  = Path(__file__).parent / "_posts"
SITE_BASE  = "https://non-s.github.io"
LOOKBACK_H = 2
MAX_TOOTS  = 5


def parse_frontmatter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    data: dict = {}
    for line in parts[1].splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if val.startswith("[") and val.endswith("]"):
            data[key] = [v.strip().strip('"').strip("'") for v in val[1:-1].split(",")]
        else:
            data[key] = val
    return data


def build_post_url(filename: str, fm: dict) -> str:
    stem  = filename.removesuffix(".md")
    parts = stem.split("-", 3)
    if len(parts) < 4:
        return SITE_BASE + "/"
    year, month, day, slug = parts
    cats     = fm.get("categories", [])
    category = (cats[0] if isinstance(cats, list) and cats else "news").strip()
    return f"{SITE_BASE}/{category}/{year}/{month}/{day}/{slug}/"


def find_new_posts() -> list[dict]:
    cutoff  = time.time() - LOOKBACK_H * 3600
    results = []
    for path in sorted(POSTS_DIR.glob("*.md"), reverse=True):
        if path.stat().st_mtime < cutoff:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        fm   = parse_frontmatter(text)
        url  = build_post_url(path.name, fm)
        results.append({"filename": path.name, "url": url, "fm": fm})
        if len(results) >= MAX_TOOTS:
            break
    return results


def build_toot(post: dict) -> str:
    fm    = post["fm"]
    title = fm.get("title", "").strip('"').strip("'") or "Breaking News"
    url   = post["url"]
    cats  = fm.get("categories", [])
    cat   = (cats[0] if isinstance(cats, list) and cats else "news").strip()

    tags_raw = fm.get("tags", [])
    tags = tags_raw if isinstance(tags_raw, list) else []
    hashtags = " ".join(f"#{t.replace('-', '').replace(' ', '')}" for t in [cat] + tags[:3] if t)

    toot = f"{title}\n\n{url}\n\n{hashtags} #GlobalBRNews #news"

    # Mastodon limit: 500 characters
    if len(toot) > 500:
        max_title = 500 - len(f"\n\n{url}\n\n{hashtags} #GlobalBRNews #news") - 3
        toot = f"{title[:max_title]}…\n\n{url}\n\n{hashtags} #GlobalBRNews #news"
    return toot


def post_toot(instance: str, token: str, status: str) -> bool:
    instance = instance.rstrip("/")
    resp = requests.post(
        f"{instance}/api/v1/statuses",
        headers={"Authorization": f"Bearer {token}"},
        data={
            "status":     status,
            "visibility": "public",
            "language":   "en",
        },
        timeout=20,
    )
    if resp.status_code in (200, 201):
        toot_url = resp.json().get("url", "?")
        log.info("Toot publicado — %s", toot_url)
        return True
    log.warning("Falha ao publicar toot — HTTP %s: %s", resp.status_code, resp.text[:200])
    return False


def main() -> None:
    instance = os.environ.get("MASTODON_INSTANCE", "").strip().rstrip("/")
    token    = os.environ.get("MASTODON_ACCESS_TOKEN", "").strip()

    if not instance or not token:
        log.warning("MASTODON_INSTANCE ou MASTODON_ACCESS_TOKEN não definidos — pulando.")
        sys.exit(0)

    posts = find_new_posts()
    if not posts:
        log.info("Nenhum post novo — nada para toar.")
        sys.exit(0)

    log.info("Encontrados %d post(s) para publicar no Mastodon.", len(posts))

    ok = 0
    for post in posts:
        status = build_toot(post)
        if post_toot(instance, token, status):
            ok += 1
        time.sleep(2)

    log.info("Pronto — %d/%d toot(s) publicados.", ok, len(posts))


if __name__ == "__main__":
    main()
