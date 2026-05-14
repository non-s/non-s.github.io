#!/usr/bin/env python3
"""
post_discord.py
Auto-posts new articles to a Discord channel via webhook.

Reads _posts/ for files added in the last commit (git diff HEAD~1),
builds their permalink, and sends a Discord Embed for each post.

Env vars required:
  DISCORD_WEBHOOK_URL — full webhook URL from Discord channel settings
"""

import json
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
EMBED_COLOR = 0x1A73E8  # Google-blue, consistent brand color


# ---------------------------------------------------------------------------
# Frontmatter / URL helpers (same pattern as post_bluesky.py)
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
    """Return posts added in the last commit."""
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD~1", "--name-only", "_posts/"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent,
            timeout=30,
        )
        filenames = [
            line.strip()
            for line in result.stdout.splitlines()
            if line.strip().endswith(".md")
        ]
    except Exception as exc:
        log.warning("git diff failed: %s", exc)
        filenames = []

    posts = []
    for rel in filenames[:MAX_POSTS]:
        path = Path(__file__).parent / rel
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            fm = parse_frontmatter(text)
            url = build_post_url(path.name, fm)
            posts.append({"filename": path.name, "url": url, "fm": fm})
        except Exception as exc:
            log.warning("Could not read %s: %s", path, exc)

    return posts


# ---------------------------------------------------------------------------
# Discord webhook helper
# ---------------------------------------------------------------------------

def build_embed(post: dict) -> dict:
    fm = post["fm"]
    title = fm.get("title", "").strip('"').strip("'") or "New Article"
    description = fm.get("description", "").strip('"').strip("'")
    url = post["url"]
    image_url = fm.get("image", "").strip('"').strip("'")

    # Discord embed description limit is 4096 chars; keep it readable
    if len(description) > 300:
        description = description[:300].rstrip() + "…"

    embed: dict = {
        "title": title[:256],  # Discord title limit
        "url": url,
        "color": EMBED_COLOR,
        "footer": {"text": "GlobalBR News"},
    }

    if description:
        embed["description"] = description

    if image_url:
        embed["image"] = {"url": image_url}

    return embed


def send_to_discord(webhook_url: str, post: dict) -> bool:
    embed = build_embed(post)
    payload = {"embeds": [embed]}

    try:
        resp = requests.post(
            webhook_url,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        # Discord returns 204 No Content on success
        if resp.status_code in (200, 204):
            log.info("Posted to Discord — %s", post["url"])
            return True
        log.warning(
            "Discord webhook failed (HTTP %s): %s",
            resp.status_code,
            resp.text[:200],
        )
        return False
    except Exception as exc:
        log.warning("Discord post exception: %s", exc)
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
        try:
            if send_to_discord(webhook_url, post):
                ok += 1
        except Exception as exc:
            log.error("Unexpected error posting %s: %s", post.get("url"), exc)
        time.sleep(1)  # Discord rate-limit: 5 requests / 2 seconds per webhook

    log.info("Done — %d/%d post(s) shared on Discord.", ok, len(posts))


if __name__ == "__main__":
    main()
