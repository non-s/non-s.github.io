#!/usr/bin/env python3
"""
post_roundup_thread_bluesky.py
Posts the daily roundup as a structured Bluesky thread.
One post per top category, preceded by a stats intro post.

Env vars: BLUESKY_HANDLE, BLUESKY_APP_PASSWORD
"""
import json, logging, os, re, sys, time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import defaultdict
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("bluesky_roundup.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

POSTS_DIR = Path("_posts")
BSKY_API  = "https://bsky.social/xrpc"
SITE_BASE = "https://non-s.github.io"
LOOKBACK_H = 25  # slightly more than 24h to catch all of today

CATEGORY_EMOJIS = {
    "world": "🌍", "politics": "🏛️", "war": "⚔️", "business": "💼",
    "technology": "💻", "science": "🔬", "health": "🏥", "sports": "⚽",
    "environment": "🌱", "ai": "🤖", "entertainment": "🎬",
}

def get_frontmatter_value(content: str, key: str) -> str:
    m = re.search(rf'^{key}:\s*["\']?(.+?)["\']?\s*$', content, re.MULTILINE)
    return m.group(1).strip() if m else ""

def get_today_posts() -> dict[str, list]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_H)
    by_category = defaultdict(list)
    for md in sorted(POSTS_DIR.glob("*.md"), reverse=True):
        if "roundup" in md.name or "video" in md.name:
            continue
        try:
            date_match = re.match(r"(\d{4}-\d{2}-\d{2})", md.name)
            if not date_match:
                continue
            post_date = datetime.strptime(date_match.group(1), "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if post_date < cutoff:
                continue
            content = md.read_text(encoding="utf-8")
            title    = get_frontmatter_value(content, "title").strip('"\'')
            category = get_frontmatter_value(content, "categories").strip("[]").split(",")[0].strip().strip('"\'') or "world"
            desc     = get_frontmatter_value(content, "description").strip('"\'')
            breaking = get_frontmatter_value(content, "breaking") == "true"
            if title:
                by_category[category].append({
                    "title": title, "description": desc,
                    "breaking": breaking, "url": f"{SITE_BASE}/{md.stem}/",
                })
        except Exception as e:
            log.debug(f"Skip {md.name}: {e}")
    return dict(by_category)

def get_session(handle: str, password: str) -> dict:
    resp = requests.post(f"{BSKY_API}/com.atproto.server.createSession",
        json={"identifier": handle, "password": password}, timeout=20)
    resp.raise_for_status()
    return resp.json()

def create_record(session: dict, record: dict) -> dict | None:
    resp = requests.post(f"{BSKY_API}/com.atproto.repo.createRecord",
        headers={"Authorization": f"Bearer {session['accessJwt']}"},
        json={"repo": session["did"], "collection": "app.bsky.feed.post", "record": record},
        timeout=20)
    if resp.status_code == 200:
        return resp.json()
    log.warning("Failed: %s", resp.text[:200])
    return None

def main():
    handle   = os.environ.get("BLUESKY_HANDLE", "").strip()
    password = os.environ.get("BLUESKY_APP_PASSWORD", "").strip()
    if not handle or not password:
        log.warning("Credentials not set — skipping.")
        sys.exit(0)

    by_cat = get_today_posts()
    if not by_cat:
        log.info("No posts today — skipping.")
        sys.exit(0)

    total = sum(len(v) for v in by_cat.values())
    today_str = datetime.now(timezone.utc).strftime("%A, %B %d")
    log.info("Building roundup thread: %d articles, %d categories", total, len(by_cat))

    try:
        session = get_session(handle, password)
    except Exception as e:
        log.error("Auth failed: %s", e)
        sys.exit(1)

    # Intro post
    cat_summary = " · ".join(f"{CATEGORY_EMOJIS.get(c,'📰')} {c.capitalize()} ({len(v)})"
                              for c, v in list(by_cat.items())[:5])
    intro = f"📰 GlobalBR News Daily Roundup · {today_str}\n\n{total} articles published today:\n{cat_summary}\n\n🌐 non-s.github.io\n#GlobalBRNews #DailyNews #WorldNews"
    if len(intro) > 300:
        intro = f"📰 GlobalBR News · {today_str}\n\n{total} articles across {len(by_cat)} categories today.\n\n🌐 non-s.github.io\n#GlobalBRNews #DailyNews"

    now = datetime.now(timezone.utc)
    result = create_record(session, {
        "$type": "app.bsky.feed.post",
        "text": intro,
        "createdAt": now.isoformat(),
        "langs": ["en"],
    })
    if not result:
        log.error("Failed to post intro")
        sys.exit(1)

    root_ref   = {"uri": result["uri"], "cid": result["cid"]}
    parent_ref = root_ref
    time.sleep(1)

    # One post per top category (max 4 categories)
    for category, articles in list(by_cat.items())[:4]:
        emoji = CATEGORY_EMOJIS.get(category, "📰")
        top = articles[0]
        others = len(articles) - 1
        title   = top["title"][:100]
        url     = top["url"]
        more    = f"\n+{others} more {category} stories" if others > 0 else ""
        text = f"{emoji} {category.upper()}\n\n{title}{more}\n\n▶️ {url}\n#GlobalBRNews #{category.capitalize()}"
        if len(text) > 300:
            text = f"{emoji} {category.upper()}: {title[:120]}\n▶️ {url}"

        result = create_record(session, {
            "$type": "app.bsky.feed.post",
            "text": text,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "langs": ["en"],
            "reply": {"root": root_ref, "parent": parent_ref},
            "embed": {
                "$type": "app.bsky.embed.external",
                "external": {"uri": url, "title": title, "description": top["description"][:200]},
            },
        })
        if result:
            parent_ref = {"uri": result["uri"], "cid": result["cid"]}
        time.sleep(1.5)

    log.info("Daily roundup thread posted.")

if __name__ == "__main__":
    main()
