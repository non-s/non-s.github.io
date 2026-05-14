#!/usr/bin/env python3
"""
post_telegram.py
Auto-posts new articles to a Telegram channel.

Reads _posts/ for files modified in the last commit (git diff HEAD~1),
then sends each as a formatted message with title, description, link,
and image (sendPhoto if image exists, sendMessage otherwise).

Env vars required:
  TELEGRAM_BOT_TOKEN  — Bot token from @BotFather
  TELEGRAM_CHANNEL_ID — Channel username (@mychannel) or numeric chat ID
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
        logging.FileHandler("telegram_post.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

POSTS_DIR = Path(__file__).parent / "_posts"
SITE_BASE = "https://non-s.github.io"
MAX_POSTS = 5


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
        # Fallback: recently modified files
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


def escape_html(text: str) -> str:
    """Minimal HTML escaping for Telegram parse_mode=HTML."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_caption(post: dict) -> str:
    fm = post["fm"]
    title = escape_html(fm.get("title", "New Article").strip('"').strip("'"))
    description = escape_html(fm.get("description", "").strip('"').strip("'"))
    url = post["url"]
    cats = fm.get("categories", [])
    category = (cats[0] if isinstance(cats, list) and cats else "news").strip()
    tag = f"#{category.replace(' ', '').replace('-', '')}"

    caption = f"<b>{title}</b>"
    if description:
        # Telegram caption limit is 1024 chars; keep description short
        max_desc = 800 - len(title) - len(url)
        if max_desc > 0 and description:
            short_desc = description[:max_desc].rstrip()
            if len(description) > max_desc:
                short_desc += "…"
            caption += f"\n\n{short_desc}"
    caption += f"\n\n🔗 {url}\n\n{tag} #GlobalBRNews"

    # Telegram caption hard limit: 1024 chars
    if len(caption) > 1024:
        caption = caption[:1021] + "…"
    return caption


def send_photo(token: str, channel_id: str, image_url: str, caption: str) -> bool:
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    payload = {
        "chat_id": channel_id,
        "photo": image_url,
        "caption": caption,
        "parse_mode": "HTML",
        "disable_notification": False,
    }
    try:
        resp = requests.post(url, json=payload, timeout=30)
        if resp.status_code == 200:
            return True
        log.warning("sendPhoto HTTP %s: %s", resp.status_code, resp.text[:300])
        # If image fails (e.g. bad URL), fall back to text
        return False
    except Exception as exc:
        log.warning("sendPhoto exception: %s", exc)
        return False


def send_message(token: str, channel_id: str, caption: str) -> bool:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": channel_id,
        "text": caption,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        resp = requests.post(url, json=payload, timeout=30)
        if resp.status_code == 200:
            return True
        log.warning("sendMessage HTTP %s: %s", resp.status_code, resp.text[:300])
        return False
    except Exception as exc:
        log.warning("sendMessage exception: %s", exc)
        return False


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
        fm = post["fm"]
        image_url = fm.get("image", "").strip('"').strip("'")
        caption = build_caption(post)

        sent = False
        if image_url:
            sent = send_photo(token, channel_id, image_url, caption)
            if not sent:
                log.info("Photo send failed — falling back to text message.")

        if not sent:
            sent = send_message(token, channel_id, caption)

        if sent:
            log.info("Posted to Telegram — %s", post["url"])
            ok += 1
        else:
            log.error("Failed to post to Telegram — %s", post["url"])

        time.sleep(2)  # Telegram rate-limit: be polite

    log.info("Done — %d/%d post(s) shared on Telegram.", ok, len(posts))


if __name__ == "__main__":
    main()
