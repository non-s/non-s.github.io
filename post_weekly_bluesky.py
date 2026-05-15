#!/usr/bin/env python3
"""
post_weekly_bluesky.py
Posts a weekly "Top 5" thread to Bluesky every Sunday.
Reads _posts/ for the last 7 days and selects top articles.

Env vars: BLUESKY_HANDLE, BLUESKY_APP_PASSWORD
"""
import json, logging, os, sys, time, re
from datetime import datetime, timezone, timedelta
from pathlib import Path
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("bluesky_weekly.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

POSTS_DIR = Path("_posts")
BSKY_API  = "https://bsky.social/xrpc"
SITE_BASE = "https://non-s.github.io"

def get_frontmatter_value(content: str, key: str) -> str:
    m = re.search(rf'^{key}:\s*["\']?(.+?)["\']?\s*$', content, re.MULTILINE)
    return m.group(1).strip() if m else ""

def get_recent_posts(days: int = 7) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    posts = []
    for md in sorted(POSTS_DIR.glob("*.md"), reverse=True):
        try:
            date_match = re.match(r"(\d{4}-\d{2}-\d{2})", md.name)
            if not date_match:
                continue
            post_date = datetime.strptime(date_match.group(1), "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if post_date < cutoff:
                break
            content = md.read_text(encoding="utf-8")
            title = get_frontmatter_value(content, "title").strip('"\'')
            category = get_frontmatter_value(content, "categories").strip("[]").split(",")[0].strip().strip('"\'')
            description = get_frontmatter_value(content, "description").strip('"\'')
            breaking = get_frontmatter_value(content, "breaking") == "true"
            # Skip roundups, video posts, shorts
            if any(x in md.name for x in ["roundup", "video"]):
                continue
            if title:
                slug = md.stem
                posts.append({
                    "title": title,
                    "category": category,
                    "description": description,
                    "breaking": breaking,
                    "url": f"{SITE_BASE}/{slug}/",
                    "date": post_date,
                })
        except Exception as e:
            log.debug(f"Skip {md.name}: {e}")
    # Prioritize breaking news, then sort by date
    posts.sort(key=lambda p: (not p["breaking"], -p["date"].timestamp()))
    return posts[:5]

def get_session(handle: str, password: str) -> dict:
    resp = requests.post(
        f"{BSKY_API}/com.atproto.server.createSession",
        json={"identifier": handle, "password": password},
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()

def create_record(session: dict, record: dict) -> dict | None:
    resp = requests.post(
        f"{BSKY_API}/com.atproto.repo.createRecord",
        headers={"Authorization": f"Bearer {session['accessJwt']}"},
        json={"repo": session["did"], "collection": "app.bsky.feed.post", "record": record},
        timeout=20,
    )
    if resp.status_code == 200:
        return resp.json()
    log.warning("Post failed: %s", resp.text[:200])
    return None

def main():
    handle   = os.environ.get("BLUESKY_HANDLE", "").strip()
    password = os.environ.get("BLUESKY_APP_PASSWORD", "").strip()
    if not handle or not password:
        log.warning("Bluesky credentials not set — skipping.")
        sys.exit(0)

    posts = get_recent_posts(7)
    if not posts:
        log.info("No posts this week — skipping.")
        sys.exit(0)

    log.info("Found %d top posts for weekly thread", len(posts))

    try:
        session = get_session(handle, password)
        log.info("Authenticated as %s", session.get("handle"))
    except Exception as e:
        log.error("Auth failed: %s", e)
        sys.exit(1)

    now = datetime.now(timezone.utc)
    week_str = now.strftime("%b %d, %Y")

    # Post 1: intro
    intro_text = f"🗞️ GlobalBR News — Weekly Top {len(posts)} · {week_str}\n\nThe biggest stories this week from around the world. Thread below 👇\n\n#GlobalBRNews #WeeklyNews #WorldNews"
    intro_record = {
        "$type": "app.bsky.feed.post",
        "text": intro_text,
        "createdAt": now.isoformat(),
        "langs": ["en"],
    }
    result = create_record(session, intro_record)
    if not result:
        log.error("Failed to post intro")
        sys.exit(1)

    root_ref   = {"uri": result["uri"], "cid": result["cid"]}
    parent_ref = root_ref
    time.sleep(1)

    # Posts 2-N: one per story
    EMOJIS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
    for i, post in enumerate(posts):
        emoji = EMOJIS[i] if i < len(EMOJIS) else f"{i+1}."
        cat_label = f"[{post['category'].upper()}] " if post['category'] else ""
        breaking  = "🔴 BREAKING · " if post['breaking'] else ""
        title = post['title'][:120]
        desc  = post['description'][:100] + "…" if len(post['description']) > 100 else post['description']
        url   = post['url']

        text = f"{emoji} {breaking}{cat_label}{title}\n\n{desc}\n\n▶️ {url}"
        if len(text) > 300:
            text = f"{emoji} {breaking}{cat_label}{title[:150]}\n\n▶️ {url}"

        record = {
            "$type": "app.bsky.feed.post",
            "text": text,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "langs": ["en"],
            "reply": {"root": root_ref, "parent": parent_ref},
            "embed": {
                "$type": "app.bsky.embed.external",
                "external": {
                    "uri": url,
                    "title": title,
                    "description": post['description'][:200],
                },
            },
        }
        result = create_record(session, record)
        if result:
            parent_ref = {"uri": result["uri"], "cid": result["cid"]}
            log.info("Posted story %d: %s", i+1, title[:50])
        time.sleep(1.5)

    log.info("Weekly thread posted successfully.")

if __name__ == "__main__":
    main()
