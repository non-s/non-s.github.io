#!/usr/bin/env python3
"""
post_reddit.py
Auto-posts new articles to relevant subreddits using the Reddit API.

Reads _posts/ for files modified in the last 2 hours and submits each
to the most appropriate subreddit based on the article's category.

Env vars required:
  REDDIT_CLIENT_ID     — from reddit.com/prefs/apps
  REDDIT_CLIENT_SECRET — from reddit.com/prefs/apps
  REDDIT_USERNAME      — Reddit account username
  REDDIT_PASSWORD      — Reddit account password
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
        logging.FileHandler("reddit_post.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

POSTS_DIR  = Path(__file__).parent / "_posts"
SITE_BASE  = "https://non-s.github.io"
LOOKBACK_H = 2
MAX_POSTS  = 3  # conservative to avoid spam triggers

# Category → subreddit mapping (most accepting of news links)
SUBREDDIT_MAP = {
    "world":         "worldnews",
    "politics":      "worldpolitics",
    "war":           "worldnews",
    "business":      "economics",
    "science":       "science",
    "health":        "health",
    "sports":        "sports",
    "food":          "food",
    "entertainment": "entertainment",
    "environment":   "environment",
    "travel":        "travel",
    "technology":    "technology",
    "ai":            "artificial",
    "security":      "cybersecurity",
}
DEFAULT_SUBREDDIT = "worldnews"
USER_AGENT = "GlobalBRNews:1.0 (by /u/{username})"


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
        cats = fm.get("categories", [])
        cat  = (cats[0] if isinstance(cats, list) and cats else "news").strip()
        results.append({"filename": path.name, "url": url, "fm": fm, "category": cat})
        if len(results) >= MAX_POSTS:
            break
    return results


def get_token(client_id: str, secret: str, username: str, password: str) -> str:
    resp = requests.post(
        "https://www.reddit.com/api/v1/access_token",
        auth=(client_id, secret),
        data={"grant_type": "password", "username": username, "password": password},
        headers={"User-Agent": USER_AGENT.format(username=username)},
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def submit_link(token: str, username: str, subreddit: str, title: str, url: str) -> bool:
    headers = {
        "Authorization": f"bearer {token}",
        "User-Agent":    USER_AGENT.format(username=username),
    }
    data = {
        "kind":     "link",
        "sr":       subreddit,
        "title":    title[:300],
        "url":      url,
        "resubmit": True,
        "nsfw":     False,
        "spoiler":  False,
    }
    resp = requests.post(
        "https://oauth.reddit.com/api/submit",
        headers=headers,
        data=data,
        timeout=20,
    )
    body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}

    if resp.status_code == 200:
        errors = body.get("json", {}).get("errors", [])
        if not errors:
            permalink = body.get("json", {}).get("data", {}).get("url", "")
            log.info("Posted to r/%s — %s", subreddit, permalink or url)
            return True
        log.warning("Reddit errors for r/%s: %s", subreddit, errors)
        return False

    log.warning("Failed to post to r/%s — HTTP %s: %s", subreddit, resp.status_code, resp.text[:200])
    return False


def main() -> None:
    client_id = os.environ.get("REDDIT_CLIENT_ID", "").strip()
    secret    = os.environ.get("REDDIT_CLIENT_SECRET", "").strip()
    username  = os.environ.get("REDDIT_USERNAME", "").strip()
    password  = os.environ.get("REDDIT_PASSWORD", "").strip()

    if not all([client_id, secret, username, password]):
        log.warning("Reddit credentials not set — skipping.")
        sys.exit(0)

    posts = find_new_posts()
    if not posts:
        log.info("No new posts found — nothing to share on Reddit.")
        sys.exit(0)

    log.info("Found %d new post(s) to share.", len(posts))

    try:
        token = get_token(client_id, secret, username, password)
        log.info("Reddit auth OK")
    except Exception as exc:
        log.error("Auth failed: %s", exc)
        sys.exit(1)

    ok = 0
    for post in posts:
        fm        = post["fm"]
        title     = fm.get("title", "").strip('"').strip("'") or "Breaking News"
        subreddit = SUBREDDIT_MAP.get(post["category"], DEFAULT_SUBREDDIT)
        if submit_link(token, username, subreddit, title, post["url"]):
            ok += 1
        time.sleep(5)  # Reddit requires delay between posts

    log.info("Done — %d/%d post(s) shared on Reddit.", ok, len(posts))


if __name__ == "__main__":
    main()
