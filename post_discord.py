#!/usr/bin/env python3
"""
post_discord.py
Auto-posts new articles to a Discord channel via Webhook.

Reads _posts/ for files added in the last commit (git diff HEAD~1),
then sends a rich Embed for each article.

Env var required:
  DISCORD_WEBHOOK_URL — Full webhook URL from Discord channel settings
"""

import logging
import os
import subprocess
import sys
import time
from pathlib import Path

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("discord_post.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

POSTS_DIR = Path(__file__).parent / "_posts"
SITE_BASE = "https://non-s.github.io"
MAX_POSTS = 5
EMBED_COLOR = 0x1A73E8  # Google blue — change as desired


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
    stem = filename.removesuffix(".md")
    parts = stem.split("-", 3)
    if len(parts) < 4:
        return SITE_BASE + "/"
    year, month, day, slug = parts
    cats = fm.get("categories", [])
    category = (cats[0] if isinstance(cats, list) and cats else "news").strip()
    return f"{SITE_BASE}/{category}/{year}/{month}/{day}/{slug}/"


def find_new_posts() -> list[dict]:
    """Return posts added in the most recent commit, up to MAX_POSTS."""
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD~1", "--name-only", "--diff-filter=A", "_posts/"],
            capture_output=True, text=True, check=True,
            cwd=POSTS_DIR.parent,
        )
        filenames = [
            line.strip() for line in result.stdout.splitlines()
            if line.strip().endswith(".md")
        ]
    except subprocess.CalledProcessError as exc:
        log.warning("git diff failed: %s — falling back to mtime scan", exc)
        filenames = []

    posts = []

    if filenames:
        for rel in filenames[:MAX_POSTS]:
            path = POSTS_DIR.parent / rel
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            fm = parse_frontmatter(text)
            url = build_post_url(path.name, fm)
            posts.append({"filename": path.name, "url": url, "fm": fm})
    else:
        import time as _time
        cutoff = _time.time() - 2 * 3600
        for path in sorted(POSTS_DIR.glob("*.md"), reverse=True):
            if path.stat().st_mtime < cutoff:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            fm = parse_frontmatter(text)
            url = build_post_url(path.name, fm)
            posts.append({"filename": path.name, "url": url, "fm": fm})
            if len(posts) >= MAX_POSTS:
                break

    return posts


def build_embed(post: dict) -> dict:
    fm = post["fm"]
    title = fm.get("title", "New Article").strip('"').strip("'")
    description = fm.get("description", "").strip('"').strip("'")
    url = post["url"]
    image_url = fm.get("image", "").strip('"').strip("'")
    cats = fm.get("categories", [])
    category = (cats[0] if isinstance(cats, list) and cats else "news").strip().title()

    # Discord embed description limit: 4096 chars; keep it short
    if len(description) > 300:
        description = description[:297] + "…"

    embed: dict = {
        "title": title[:256],
        "description": description,
        "url": url,
        "color": EMBED_COLOR,
        "footer": {"text": "GlobalBR News"},
        "author": {"name": category},
    }

    if image_url:
        embed["image"] = {"url": image_url}

    return embed


def send_embed(webhook_url: str, embed: dict) -> bool:
    payload = {"embeds": [embed]}
    try:
        resp = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        # Discord returns 204 No Content on success
        if resp.status_code in (200, 204):
            return True
        log.warning("Discord webhook HTTP %s: %s", resp.status_code, resp.text[:300])
        return False
    except Exception as exc:
        log.error("Discord webhook exception: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()

    if not webhook_url:
        log.warning("DISCORD_WEBHOOK_URL not set — skipping.")
        sys.exit(0)

    posts = find_new_posts()
    if not posts:
        log.info("No new posts found — nothing to share on Discord.")
        sys.exit(0)

    log.info("Found %d new post(s) to share on Discord.", len(posts))

    ok = 0
    for post in posts:
        embed = build_embed(post)
        if send_embed(webhook_url, embed):
            log.info("Posted to Discord — %s", post["url"])
            ok += 1
        else:
            log.error("Failed to post to Discord — %s", post["url"])
        time.sleep(2)  # Discord rate-limit: 5 req/s per webhook, be conservative

    log.info("Done — %d/%d post(s) shared on Discord.", ok, len(posts))


if __name__ == "__main__":
    main()
