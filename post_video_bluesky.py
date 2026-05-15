#!/usr/bin/env python3
"""
post_video_bluesky.py
Cross-posts newly uploaded YouTube videos to Bluesky.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

from utils.retry import retry_call

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
LOOKBACK_H = int(os.environ.get("VIDEO_LOOKBACK_H", "2"))
MAX_POSTS  = int(os.environ.get("VIDEO_MAX_POSTS", "5"))

CATEGORY_EMOJIS = {
    "world": "🌍", "politics": "🏛️", "war": "⚔️", "business": "💼",
    "technology": "💻", "science": "🔬", "health": "🏥", "sports": "⚽",
    "food": "🍕", "entertainment": "🎬", "environment": "🌱",
    "travel": "✈️", "ai": "🤖", "security": "🔒",
    "gadgets": "📱", "startups": "🚀", "mobile": "📲",
    "roundup": "📺", "shorts": "⚡",
}

CATEGORY_HASHTAGS = {
    "world":       ["#WorldNews", "#BreakingNews"],
    "politics":    ["#Politics", "#GlobalPolitics"],
    "war":         ["#War", "#Conflict"],
    "business":    ["#Business", "#Economy"],
    "technology":  ["#Tech", "#Technology"],
    "science":     ["#Science"],
    "health":      ["#Health"],
    "sports":      ["#Sports"],
    "ai":          ["#AI", "#ArtificialIntelligence"],
    "security":    ["#CyberSecurity"],
    "environment": ["#Climate", "#Environment"],
    "roundup":     ["#NewsRoundup", "#WorldNews"],
    "shorts":      ["#Shorts", "#NewsShorts"],
}


def find_new_videos() -> list[dict]:
    cutoff  = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_H)
    results: list[dict] = []
    if not VIDEOS_DIR.exists():
        return results
    for done_file in sorted(VIDEOS_DIR.glob("*.done"), reverse=True):
        try:
            data        = json.loads(done_file.read_text(encoding="utf-8"))
            uploaded_at = datetime.fromisoformat(data.get("uploaded_at", ""))
            if uploaded_at.tzinfo is None:
                uploaded_at = uploaded_at.replace(tzinfo=timezone.utc)
            if uploaded_at >= cutoff:
                results.append(data)
                if len(results) >= MAX_POSTS:
                    break
        except Exception as exc:
            log.debug("Could not read %s: %s", done_file.name, exc)
    return results


def build_post_text(video: dict) -> str:
    title       = (video.get("title") or "New Video").strip()
    url         = video.get("url", "")
    description = (video.get("description") or "").strip()
    is_short    = video.get("is_short", False)
    category    = (video.get("category") or "roundup").lower().strip()

    if is_short:
        emoji    = "⚡"
        cat_tags = ["#Shorts", "#NewsShorts", "#GlobalBRNews"]
    else:
        emoji    = CATEGORY_EMOJIS.get(category, "📺")
        cat_tags = CATEGORY_HASHTAGS.get(category, ["#NewsRoundup"]) + ["#GlobalBRNews", "#YouTube"]

    desc_excerpt = ""
    if description:
        desc_excerpt = description[:120]
        if len(description) > 120:
            last_space = desc_excerpt.rfind(" ")
            desc_excerpt = (desc_excerpt[:last_space] if last_space > 80 else desc_excerpt) + "…"

    hashtags = " ".join(cat_tags)

    def _assemble(title_text: str, desc_text: str) -> str:
        parts = [f"🎬 {emoji} {title_text}"]
        if desc_text:
            parts.append(f"\n{desc_text}")
        parts.append(f"\n▶️ {url}")
        parts.append(f"\n{hashtags}")
        return "\n".join(parts)

    text = _assemble(title, desc_excerpt)

    if len(text) > 300:
        budget = 300 - len(_assemble(title, "").replace("\n\n", "\n"))
        desc_excerpt = (desc_excerpt[:budget - 1] + "…") if budget > 20 else ""
        text = _assemble(title, desc_excerpt)

    if len(text) > 300:
        overhead  = len(text) - len(title)
        max_title = 300 - overhead - 3
        if max_title > 10:
            title = title[:max_title] + "…"
        text = _assemble(title, "")

    return text


def main() -> None:
    handle   = os.environ.get("BLUESKY_HANDLE", "").strip()
    password = os.environ.get("BLUESKY_APP_PASSWORD", "").strip()
    if not handle or not password:
        log.warning("Bluesky credentials not set — skipping.")
        sys.exit(0)

    videos = find_new_videos()
    if not videos:
        log.info("No new videos found — nothing to share.")
        sys.exit(0)

    log.info("Found %d new video(s) to share.", len(videos))

    def _auth():
        r = requests.post(
            f"{BSKY_API}/com.atproto.server.createSession",
            json={"identifier": handle, "password": password},
            timeout=20,
        )
        r.raise_for_status()
        return r.json()

    session = retry_call(_auth, max_attempts=3, base_delay=5.0, default=None)
    if not session:
        log.error("Bluesky auth failed")
        sys.exit(1)
    log.info("Authenticated as %s", session.get("handle"))

    ok = 0
    for video in videos:
        text  = build_post_text(video)
        url   = video.get("url", "")
        title = video.get("title", "")
        desc  = (video.get("description") or "")[:300]

        url_start = text.find(url) if url else -1
        record: dict = {
            "$type":     "app.bsky.feed.post",
            "text":      text,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "langs":     ["en"],
            "embed": {
                "$type":    "app.bsky.embed.external",
                "external": {"uri": url, "title": title[:300], "description": desc},
            },
        }
        if url_start >= 0:
            record["facets"] = [{
                "index": {
                    "byteStart": len(text[:url_start].encode("utf-8")),
                    "byteEnd":   len(text[:url_start + len(url)].encode("utf-8")),
                },
                "features": [{"$type": "app.bsky.richtext.facet#link", "uri": url}],
            }]

        def _do_post(rec=record):
            r = requests.post(
                f"{BSKY_API}/com.atproto.repo.createRecord",
                headers={"Authorization": f"Bearer {session['accessJwt']}"},
                json={"repo": session["did"], "collection": "app.bsky.feed.post", "record": rec},
                timeout=20,
            )
            r.raise_for_status()
            return True

        if retry_call(_do_post, max_attempts=3, base_delay=5.0, default=False):
            log.info("Posted video: %s", url)
            ok += 1
        time.sleep(2)

    log.info("Done — %d/%d video(s) shared.", ok, len(videos))


if __name__ == "__main__":
    main()
