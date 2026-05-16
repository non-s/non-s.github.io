#!/usr/bin/env python3
"""Pick the best article of the day and post to Bluesky as featured."""
from __future__ import annotations

import logging
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import requests

from utils.frontmatter import parse, get_str, get_list
from utils.retry import retry_call

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

POSTS_DIR = Path("_posts")
SITE_BASE = "https://non-s.github.io"
BSKY_API  = "https://bsky.social/xrpc"

CATEGORY_EMOJIS = {
    "world": "🌍", "politics": "🏛️", "war": "⚔️", "business": "💼",
    "technology": "💻", "science": "🔬", "health": "🏥", "sports": "⚽",
    "food": "🍕", "entertainment": "🎬", "environment": "🌱",
    "travel": "✈️", "ai": "🤖", "security": "🔒",
}

_SKIP_STEMS = ("roundup", "digest", "milestone", "stats", "best-of")


def pick_best_post() -> tuple[Path, dict] | None:
    today = date.today().strftime("%Y-%m-%d")
    scored: list[tuple[int, Path, dict]] = []
    for path in sorted(POSTS_DIR.glob(f"{today}-*.md"), reverse=True):
        if any(x in path.stem for x in _SKIP_STEMS):
            continue
        try:
            fm = parse(path.read_text(encoding="utf-8", errors="replace"))
            title = get_str(fm, "title")
            desc  = get_str(fm, "description")
            score = 0
            if get_str(fm, "featured") == "true": score += 10
            if get_str(fm, "breaking")  == "true": score += 5
            if desc:  score += 3
            if len(title) > 40: score += 1
            scored.append((score, path, fm))
        except Exception:
            pass

    if not scored:
        log.info("No posts today — skipping best-of")
        return None
    scored.sort(reverse=True)
    _, path, fm = scored[0]
    log.info("Best post today: %s", path.name)
    return path, fm


def _mistral_commentary(title: str, description: str) -> str:
    key = os.getenv("MISTRAL_API_KEY", "")
    if not key:
        return ""
    model = os.getenv("MISTRAL_MODEL", "mistral-small-latest")

    def _call():
        r = requests.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": (
                    f"Write ONE engaging sentence (max 15 words) introducing this news for "
                    f"social media. Journalistic, not clickbait. "
                    f"Title: {title}. Description: {description[:200]}"
                )}],
                "max_tokens": 60,
            },
            timeout=20,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip().strip('"')

    result = retry_call(_call, max_attempts=2, base_delay=5.0, default="")
    return result or ""


def build_url(path: Path, fm: dict) -> str:
    parts = path.stem.split("-", 3)
    if len(parts) < 4:
        return SITE_BASE + "/"
    year, month, day, slug = parts
    cat = get_str(fm, "categories", "news")
    return f"{SITE_BASE}/{cat}/{year}/{month}/{day}/{slug}/"


def post_to_bluesky(text: str, url: str, title: str, handle: str, password: str) -> bool:
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
        return False

    record: dict = {
        "$type":     "app.bsky.feed.post",
        "text":      text,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "langs":     ["en"],
        "embed": {
            "$type":    "app.bsky.embed.external",
            "external": {"uri": url, "title": title[:300], "description": ""},
        },
    }
    url_start = text.find(url)
    if url_start >= 0:
        record["facets"] = [{
            "index": {
                "byteStart": len(text[:url_start].encode()),
                "byteEnd":   len(text[:url_start + len(url)].encode()),
            },
            "features": [{"$type": "app.bsky.richtext.facet#link", "uri": url}],
        }]

    def _do_post():
        r = requests.post(
            f"{BSKY_API}/com.atproto.repo.createRecord",
            headers={"Authorization": f"Bearer {session['accessJwt']}"},
            json={"repo": session["did"], "collection": "app.bsky.feed.post", "record": record},
            timeout=20,
        )
        r.raise_for_status()
        return True

    result = retry_call(_do_post, max_attempts=3, base_delay=5.0, default=False)
    if result:
        log.info("Posted best-of to Bluesky: %s", url)
    return bool(result)


def main() -> None:
    handle   = os.environ.get("BLUESKY_HANDLE", "").strip()
    password = os.environ.get("BLUESKY_APP_PASSWORD", "").strip()
    if not handle or not password:
        log.warning("Bluesky credentials not set — skipping")
        sys.exit(0)

    result = pick_best_post()
    if not result:
        sys.exit(0)

    path, fm = result
    title       = get_str(fm, "title", "New Article")
    description = get_str(fm, "description")
    cat         = get_str(fm, "categories", "news")
    emoji       = CATEGORY_EMOJIS.get(cat, "📰")
    url         = build_url(path, fm)
    commentary  = _mistral_commentary(title, description)

    text = f"⭐ Article of the Day\n\n{emoji} {title}\n\n"
    if commentary:
        text += f"{commentary}\n\n"
    text += f"🔗 {url}\n\n#GlobalBRNews #BestOf"

    if len(text) > 300:
        text = text[:297] + "…"

    post_to_bluesky(text, url, title, handle, password)


if __name__ == "__main__":
    main()
