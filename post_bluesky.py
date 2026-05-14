#!/usr/bin/env python3
"""
post_bluesky.py
Auto-posts new articles to Bluesky using the AT Protocol HTTP API.

Reads _posts/ for files modified in the last 2 hours, builds their permalink,
and creates a post on Bluesky with title + URL + category tag.

Env vars required:
  BLUESKY_HANDLE       — your handle, e.g. globalbrnews.bsky.social
  BLUESKY_APP_PASSWORD — App Password from Settings → App Passwords
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("bluesky_post.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

POSTS_DIR    = Path(__file__).parent / "_posts"
SITE_BASE    = "https://non-s.github.io"
BSKY_API     = "https://bsky.social/xrpc"
LOOKBACK_H   = 2
MAX_POSTS    = 5


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
        if len(results) >= MAX_POSTS:
            break
    return results


def get_session(handle: str, password: str) -> dict:
    resp = requests.post(
        f"{BSKY_API}/com.atproto.server.createSession",
        json={"identifier": handle, "password": password},
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


def create_post(session: dict, text: str, url: str, title: str) -> bool:
    """Create a Bluesky post with an embedded link card."""
    did   = session["did"]
    token = session["accessJwt"]

    # Build facets for URL embedding
    url_start = text.index(url) if url in text else -1
    facets = []
    if url_start >= 0:
        facets.append({
            "index": {
                "byteStart": len(text[:url_start].encode("utf-8")),
                "byteEnd":   len(text[:url_start + len(url)].encode("utf-8")),
            },
            "features": [{"$type": "app.bsky.richtext.facet#link", "uri": url}],
        })

    record = {
        "$type":     "app.bsky.feed.post",
        "text":      text,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "langs":     ["en"],
    }
    if facets:
        record["facets"] = facets

    # Embed external link card
    record["embed"] = {
        "$type": "app.bsky.embed.external",
        "external": {
            "uri":         url,
            "title":       title[:300],
            "description": "",
        },
    }

    resp = requests.post(
        f"{BSKY_API}/com.atproto.repo.createRecord",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "repo":       did,
            "collection": "app.bsky.feed.post",
            "record":     record,
        },
        timeout=20,
    )
    if resp.status_code == 200:
        log.info("Posted to Bluesky — %s", url)
        return True
    log.warning("Failed to post — HTTP %s: %s", resp.status_code, resp.text[:200])
    return False


def build_post_text(post: dict) -> str:
    fm       = post["fm"]
    title    = fm.get("title", "").strip('"').strip("'") or "New Article"
    cats     = fm.get("categories", [])
    category = (cats[0] if isinstance(cats, list) and cats else "news").strip()
    url      = post["url"]

    tag  = f"#{category.replace(' ', '')}"
    text = f"{title}\n\n{url}\n\n{tag} #GlobalBRNews #news"

    # Bluesky limit: 300 graphemes
    if len(text) > 300:
        max_title = 300 - len(f"\n\n{url}\n\n{tag} #GlobalBRNews #news") - 3
        text = f"{title[:max_title]}…\n\n{url}\n\n{tag} #GlobalBRNews #news"
    return text


def main() -> None:
    handle   = os.environ.get("BLUESKY_HANDLE", "").strip()
    password = os.environ.get("BLUESKY_APP_PASSWORD", "").strip()

    if not handle or not password:
        log.warning("BLUESKY_HANDLE or BLUESKY_APP_PASSWORD not set — skipping.")
        sys.exit(0)

    posts = find_new_posts()
    if not posts:
        log.info("No new posts found — nothing to share on Bluesky.")
        sys.exit(0)

    log.info("Found %d new post(s) to share.", len(posts))

    try:
        session = get_session(handle, password)
        log.info("Authenticated as %s", session.get("handle"))
    except Exception as exc:
        log.error("Auth failed: %s", exc)
        sys.exit(1)

    ok = 0
    for post in posts:
        text  = build_post_text(post)
        title = post["fm"].get("title", "").strip('"').strip("'")
        if create_post(session, text, post["url"], title):
            ok += 1
        time.sleep(2)  # be polite to the API

    log.info("Done — %d/%d post(s) shared on Bluesky.", ok, len(posts))


if __name__ == "__main__":
    main()
