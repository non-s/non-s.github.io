#!/usr/bin/env python3
"""
post_pinterest.py
Auto-posts new articles to Pinterest as Pins.

Reads _posts/ for files added in the last commit (git diff HEAD~1),
then creates a Pin for each article using the Pinterest API v5.

Env vars required:
  PINTEREST_ACCESS_TOKEN — OAuth2 Bearer token
  PINTEREST_BOARD_ID     — ID of the target board (numeric string)
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
        logging.FileHandler("pinterest_post.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

POSTS_DIR = Path(__file__).parent / "_posts"
SITE_BASE = "https://non-s.github.io"
PINTEREST_API = "https://api.pinterest.com/v5"
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


def create_pin(access_token: str, board_id: str, post: dict) -> bool:
    fm = post["fm"]
    title = fm.get("title", "New Article").strip('"').strip("'")
    description = fm.get("description", "").strip('"').strip("'")
    link = post["url"]
    image_url = fm.get("image", "").strip('"').strip("'")

    # Pinterest title limit: 100 chars; description: 500 chars
    if len(title) > 100:
        title = title[:97] + "…"
    if len(description) > 500:
        description = description[:497] + "…"

    payload: dict = {
        "board_id": board_id,
        "title": title,
        "description": description,
        "link": link,
    }

    if image_url:
        payload["media_source"] = {
            "source_type": "image_url",
            "url": image_url,
        }
    else:
        # Pinterest requires a media source; skip if no image
        log.warning("No image for %s — skipping Pinterest pin.", post["filename"])
        return False

    try:
        resp = requests.post(
            f"{PINTEREST_API}/pins",
            json=payload,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            timeout=30,
        )
        if resp.status_code in (200, 201):
            pin_id = resp.json().get("id", "unknown")
            log.info("Created Pinterest pin %s — %s", pin_id, link)
            return True
        log.warning("Pinterest API HTTP %s: %s", resp.status_code, resp.text[:300])
        return False
    except Exception as exc:
        log.error("Pinterest API exception: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    access_token = os.environ.get("PINTEREST_ACCESS_TOKEN", "").strip()
    board_id = os.environ.get("PINTEREST_BOARD_ID", "").strip()

    if not access_token or not board_id:
        log.warning("PINTEREST_ACCESS_TOKEN or PINTEREST_BOARD_ID not set — skipping.")
        sys.exit(0)

    posts = find_new_posts()
    if not posts:
        log.info("No new posts found — nothing to share on Pinterest.")
        sys.exit(0)

    log.info("Found %d new post(s) to share on Pinterest.", len(posts))

    ok = 0
    for post in posts:
        if create_pin(access_token, board_id, post):
            ok += 1
        time.sleep(3)  # Pinterest rate-limit: be polite

    log.info("Done — %d/%d post(s) pinned on Pinterest.", ok, len(posts))


if __name__ == "__main__":
    main()
