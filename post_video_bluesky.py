#!/usr/bin/env python3
"""
post_video_bluesky.py
Cross-posts newly uploaded YouTube videos to Bluesky.

Reads _videos/*.done files uploaded in the last 2 hours and creates
an engaging Bluesky post with emoji, description excerpt, YouTube link,
and relevant hashtags.

Env vars required:
  BLUESKY_HANDLE       — e.g. globalbrnews.bsky.social
  BLUESKY_APP_PASSWORD — App Password from Settings → App Passwords
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("bluesky_video.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

VIDEOS_DIR = Path("_videos")
BSKY_API   = "https://bsky.social/xrpc"
LOOKBACK_H = 2
MAX_POSTS  = 5

CATEGORY_EMOJIS = {
    "world": "🌍", "politics": "🏛️", "war": "⚔️", "business": "💼",
    "technology": "💻", "science": "🔬", "health": "🏥", "sports": "⚽",
    "food": "🍕", "entertainment": "🎬", "environment": "🌱",
    "travel": "✈️", "ai": "🤖", "security": "🔒",
    "gadgets": "📱", "startups": "🚀", "mobile": "📲",
    "roundup": "📺", "shorts": "⚡",
}

CATEGORY_HASHTAGS = {
    "world": ["#WorldNews", "#BreakingNews"],
    "politics": ["#Politics", "#GlobalPolitics"],
    "war": ["#War", "#Conflict"],
    "business": ["#Business", "#Economy"],
    "technology": ["#Tech", "#Technology"],
    "science": ["#Science"],
    "health": ["#Health"],
    "sports": ["#Sports"],
    "ai": ["#AI", "#ArtificialIntelligence"],
    "security": ["#CyberSecurity"],
    "environment": ["#Climate", "#Environment"],
    "roundup": ["#NewsRoundup", "#WorldNews"],
    "shorts": ["#Shorts", "#NewsShorts"],
}


def find_new_videos() -> list[dict]:
    """Find .done files uploaded in the last LOOKBACK_H hours."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_H)
    results = []
    for done_file in sorted(VIDEOS_DIR.glob("*.done"), reverse=True):
        try:
            data = json.loads(done_file.read_text(encoding="utf-8"))
            uploaded_at = datetime.fromisoformat(data.get("uploaded_at", ""))
            if uploaded_at.tzinfo is None:
                uploaded_at = uploaded_at.replace(tzinfo=timezone.utc)
            if uploaded_at >= cutoff:
                results.append(data)
                if len(results) >= MAX_POSTS:
                    break
        except Exception as exc:
            log.debug(f"Could not read {done_file.name}: {exc}")
    return results


def get_session(handle: str, password: str) -> dict:
    resp = requests.post(
        f"{BSKY_API}/com.atproto.server.createSession",
        json={"identifier": handle, "password": password},
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


def create_post(
    session: dict,
    text: str,
    url: str,
    title: str,
    description: str = "",
    reply_to: dict | None = None,
) -> dict | None:
    """Create a Bluesky post. Returns the result dict (uri, cid) or None on failure."""
    did   = session["did"]
    token = session["accessJwt"]

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

    # Ensure description is always populated with a meaningful excerpt
    card_description = (description.strip() or title)[:300]

    record = {
        "$type":     "app.bsky.feed.post",
        "text":      text,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "langs":     ["en"],
    }
    if facets:
        record["facets"] = facets

    record["embed"] = {
        "$type": "app.bsky.embed.external",
        "external": {
            "uri":         url,
            "title":       title[:300],
            "description": card_description,
        },
    }

    if reply_to:
        record["reply"] = {
            "root":   reply_to.get("root", reply_to),
            "parent": reply_to,
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
        log.info("Posted video to Bluesky — %s", url)
        return resp.json()
    log.warning("Failed to post — HTTP %s: %s", resp.status_code, resp.text[:200])
    return None


def post_thread(session: dict, posts_data: list[dict]) -> bool:
    """Post a thread of connected posts. posts_data is list of {text, url, title, description}."""
    parent_ref = None
    root_ref = None
    ok = True
    for i, data in enumerate(posts_data):
        record = {
            "$type": "app.bsky.feed.post",
            "text": data["text"],
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "langs": ["en"],
        }
        if data.get("embed"):
            record["embed"] = data["embed"]
        if parent_ref:
            record["reply"] = {
                "root": root_ref,
                "parent": parent_ref,
            }

        resp = requests.post(
            f"{BSKY_API}/com.atproto.repo.createRecord",
            headers={"Authorization": f"Bearer {session['accessJwt']}"},
            json={"repo": session["did"], "collection": "app.bsky.feed.post", "record": record},
            timeout=20,
        )
        if resp.status_code == 200:
            result = resp.json()
            ref = {"uri": result["uri"], "cid": result["cid"]}
            if i == 0:
                root_ref = ref
            parent_ref = ref
            time.sleep(1)
        else:
            log.warning("Thread post %d failed: %s", i + 1, resp.text[:200])
            ok = False
    return ok


def build_post_text(video: dict) -> str:
    title       = video.get("title", "New Video").strip()
    url         = video.get("url", "")
    description = video.get("description", "").strip()
    is_short    = video.get("is_short", False)
    category    = (video.get("category", "") or "roundup").lower().strip()
    tags        = video.get("tags", [])
    # key_points consumed separately in main() for threading

    if is_short:
        emoji = "⚡"
        cat_tags = ["#Shorts", "#NewsShorts", "#GlobalBRNews"]
    else:
        emoji = CATEGORY_EMOJIS.get(category, "📺")
        cat_tags = CATEGORY_HASHTAGS.get(category, ["#NewsRoundup"]) + ["#GlobalBRNews", "#YouTube"]

    # Short description excerpt
    desc_excerpt = ""
    if description:
        desc_excerpt = description[:120]
        if len(description) > 120:
            last_space = desc_excerpt.rfind(" ")
            if last_space > 80:
                desc_excerpt = desc_excerpt[:last_space] + "…"
            else:
                desc_excerpt = desc_excerpt + "…"

    hashtags = " ".join(cat_tags)

    def _assemble(title_text: str, desc_text: str) -> str:
        parts = [f"🎬 {emoji} {title_text}"]
        if desc_text:
            parts.append(f"\n{desc_text}")
        parts.append(f"\n▶️ {url}")
        parts.append(f"\n{hashtags}")
        return "\n".join(parts)

    text = _assemble(title, desc_excerpt)

    # Trim to 300 graphemes
    if len(text) > 300:
        budget = 300 - len(_assemble(title, "").replace("\n\n", "\n"))
        if budget > 20:
            desc_excerpt = desc_excerpt[:budget - 1] + "…"
        else:
            desc_excerpt = ""
        text = _assemble(title, desc_excerpt)

    if len(text) > 300:
        overhead = len(text) - len(title)
        max_title = 300 - overhead - 3
        if max_title > 10:
            title = title[:max_title] + "…"
        text = _assemble(title, "")

    return text


def main() -> None:
    handle   = os.environ.get("BLUESKY_HANDLE", "").strip()
    password = os.environ.get("BLUESKY_APP_PASSWORD", "").strip()

    if not handle or not password:
        log.warning("BLUESKY_HANDLE or BLUESKY_APP_PASSWORD not set — skipping.")
        sys.exit(0)

    videos = find_new_videos()
    if not videos:
        log.info("No new videos found — nothing to share on Bluesky.")
        sys.exit(0)

    log.info("Found %d new video(s) to share.", len(videos))

    try:
        session = get_session(handle, password)
        log.info("Authenticated as %s", session.get("handle"))
    except Exception as exc:
        log.error("Auth failed: %s", exc)
        sys.exit(1)

    ok = 0
    for video in videos:
        text       = build_post_text(video)
        title      = video.get("title", "")
        desc       = video.get("description", "")[:300]
        url        = video.get("url", "")
        key_points = video.get("key_points", [])

        if key_points and isinstance(key_points, list) and len(key_points) > 0:
            # Build a 2-post thread: post 1 = main post, post 2 = key points
            bullets = "\n".join(f"• {str(kp).strip()}" for kp in key_points[:5])
            kp_text = f"🔑 Key points:\n{bullets}"
            posts_data = [
                {
                    "text": text,
                    "embed": {
                        "$type": "app.bsky.embed.external",
                        "external": {
                            "uri":         url,
                            "title":       title[:300],
                            "description": (desc.strip() or title)[:300],
                        },
                    },
                },
                {"text": kp_text},
            ]
            if post_thread(session, posts_data):
                ok += 1
        else:
            result = create_post(session, text, url, title, desc)
            if result:
                ok += 1
        time.sleep(2)

    log.info("Done — %d/%d video(s) shared on Bluesky.", ok, len(videos))


if __name__ == "__main__":
    main()
