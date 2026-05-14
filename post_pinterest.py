#!/usr/bin/env python3
"""
post_pinterest.py
Auto-pins new articles to a Pinterest board using the Pinterest API v5.

Reads _posts/ for files added in the last commit (git diff HEAD~1),
builds their permalink, and creates a Pin for each post that has an image.

Env vars required:
  PINTEREST_ACCESS_TOKEN — OAuth2 bearer token (from Pinterest Developer portal)
  PINTEREST_BOARD_ID     — board ID to pin to (e.g. "1234567890123456789")
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
        logging.FileHandler("pinterest_post.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

POSTS_DIR = Path(__file__).parent / "_posts"
SITE_BASE = "https://non-s.github.io"
MAX_POSTS = 5
PINTEREST_API = "https://api.pinterest.com/v5"


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
# Pinterest API helper
# ---------------------------------------------------------------------------

def create_pin(token: str, board_id: str, post: dict) -> bool:
    fm = post["fm"]
    title = fm.get("title", "").strip('"').strip("'") or "New Article"
    description = fm.get("description", "").strip('"').strip("'")
    url = post["url"]
    image_url = fm.get("image", "").strip('"').strip("'")

    if not image_url:
        log.info("Skipping %s — no image URL (Pinterest requires an image).", post["filename"])
        return False

    # Pinterest title limit: 100 chars; description: 500 chars
    if len(title) > 100:
        title = title[:97] + "…"
    if len(description) > 500:
        description = description[:497] + "…"

    payload: dict = {
        "board_id": board_id,
        "title": title,
        "link": url,
        "media_source": {
            "source_type": "image_url",
            "url": image_url,
        },
    }
    if description:
        payload["description"] = description

    try:
        resp = requests.post(
            f"{PINTEREST_API}/pins",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            data=json.dumps(payload),
            timeout=30,
        )
        if resp.status_code in (200, 201):
            pin_id = resp.json().get("id", "unknown")
            log.info("Pin created (id=%s) — %s", pin_id, url)
            return True
        log.warning(
            "Pinterest API failed (HTTP %s): %s",
            resp.status_code,
            resp.text[:300],
        )
        return False
    except Exception as exc:
        log.warning("Pinterest post exception: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    token = os.environ.get("PINTEREST_ACCESS_TOKEN", "").strip()
    board_id = os.environ.get("PINTEREST_BOARD_ID", "").strip()

    if not token or not board_id:
        log.warning("PINTEREST_ACCESS_TOKEN or PINTEREST_BOARD_ID not set — skipping.")
        sys.exit(0)

    posts = find_new_posts()
    if not posts:
        log.info("No new posts found — nothing to pin on Pinterest.")
        sys.exit(0)

    log.info("Found %d new post(s) to pin on Pinterest.", len(posts))

    ok = 0
    for post in posts:
        try:
            if create_pin(token, board_id, post):
                ok += 1
        except Exception as exc:
            log.error("Unexpected error pinning %s: %s", post.get("url"), exc)
        time.sleep(2)  # Pinterest rate-limit buffer

    log.info("Done — %d/%d post(s) pinned on Pinterest.", ok, len(posts))


if __name__ == "__main__":
    main()
