#!/usr/bin/env python3
"""
post_telegram.py
Auto-posts new articles to a Telegram channel.

Reads _posts/ for files modified in the last commit (git diff HEAD~1),
builds their permalink, and sends a formatted message or photo to the channel.

Env vars required:
  TELEGRAM_BOT_TOKEN  — bot token from @BotFather
  TELEGRAM_CHANNEL_ID — channel username or numeric ID (e.g. @mychannel or -1001234567890)
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
        logging.FileHandler("telegram_post.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

POSTS_DIR = Path(__file__).parent / "_posts"
SITE_BASE = "https://non-s.github.io"
MAX_POSTS = 5
TG_API = "https://api.telegram.org/bot{token}/{method}"


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
    """Return posts added in the last commit (same method as bluesky script)."""
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
        log.warning("git diff failed: %s — falling back to mtime scan", exc)
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
# Telegram API helpers
# ---------------------------------------------------------------------------

def _tg_url(token: str, method: str) -> str:
    return TG_API.format(token=token, method=method)


def send_photo(token: str, channel_id: str, photo_url: str, caption: str) -> bool:
    try:
        resp = requests.post(
            _tg_url(token, "sendPhoto"),
            json={
                "chat_id": channel_id,
                "photo": photo_url,
                "caption": caption,
                "parse_mode": "HTML",
            },
            timeout=30,
        )
        if resp.status_code == 200 and resp.json().get("ok"):
            return True
        # If photo upload failed (e.g. bad URL), fall back to text
        log.warning(
            "sendPhoto failed (HTTP %s): %s — will try sendMessage",
            resp.status_code,
            resp.text[:200],
        )
        return False
    except Exception as exc:
        log.warning("sendPhoto exception: %s", exc)
        return False


def send_message(token: str, channel_id: str, text: str) -> bool:
    try:
        resp = requests.post(
            _tg_url(token, "sendMessage"),
            json={
                "chat_id": channel_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            },
            timeout=30,
        )
        if resp.status_code == 200 and resp.json().get("ok"):
            return True
        log.warning(
            "sendMessage failed (HTTP %s): %s",
            resp.status_code,
            resp.text[:200],
        )
        return False
    except Exception as exc:
        log.warning("sendMessage exception: %s", exc)
        return False


def build_caption(post: dict) -> str:
    fm = post["fm"]
    title = fm.get("title", "").strip('"').strip("'") or "New Article"
    description = fm.get("description", "").strip('"').strip("'")
    url = post["url"]
    cats = fm.get("categories", [])
    category = (cats[0] if isinstance(cats, list) and cats else "news").strip()
    tag = f"#{category.replace(' ', '')}"

    lines = [f"<b>{title}</b>"]
    if description:
        # Keep description short for Telegram caption (1024 char limit)
        desc_limit = 200
        if len(description) > desc_limit:
            description = description[:desc_limit].rstrip() + "…"
        lines.append(f"\n{description}")
    lines.append(f"\n<a href=\"{url}\">Read more →</a>")
    lines.append(f"\n{tag} #GlobalBRNews")

    return "\n".join(lines)


def post_to_telegram(token: str, channel_id: str, post: dict) -> bool:
    caption = build_caption(post)
    image_url = post["fm"].get("image", "").strip('"').strip("'")

    if image_url:
        success = send_photo(token, channel_id, image_url, caption)
        if success:
            log.info("Sent photo to Telegram — %s", post["url"])
            return True
        # Photo failed — fall through to text message

    # Plain text message (also used as fallback when photo fails)
    success = send_message(token, channel_id, caption)
    if success:
        log.info("Sent message to Telegram — %s", post["url"])
    return success


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    channel_id = os.environ.get("TELEGRAM_CHANNEL_ID", "").strip()

    if not token or not channel_id:
        log.warning("TELEGRAM_BOT_TOKEN or TELEGRAM_CHANNEL_ID not set — skipping.")
        sys.exit(0)

    posts = find_new_posts()
    if not posts:
        log.info("No new posts found — nothing to share on Telegram.")
        sys.exit(0)

    log.info("Found %d new post(s) to share on Telegram.", len(posts))

    ok = 0
    for post in posts:
        try:
            if post_to_telegram(token, channel_id, post):
                ok += 1
        except Exception as exc:
            log.error("Unexpected error posting %s: %s", post.get("url"), exc)
        time.sleep(1)  # respect Telegram rate limits

    log.info("Done — %d/%d post(s) shared on Telegram.", ok, len(posts))


if __name__ == "__main__":
    main()
