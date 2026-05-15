#!/usr/bin/env python3
"""Pick the best article of the day and post to Bluesky as featured."""
import os
import glob
import logging
from datetime import date, datetime, timezone
from pathlib import Path

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

SITE_BASE = "https://non-s.github.io"

CATEGORY_EMOJIS = {
    "world": "🌍", "politics": "🏛️", "war": "⚔️", "business": "💼",
    "technology": "💻", "science": "🔬", "health": "🏥", "sports": "⚽",
    "food": "🍕", "entertainment": "🎬", "environment": "🌱",
    "travel": "✈️", "ai": "🤖", "security": "🔒",
}


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
        k, _, v = line.partition(":")
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if v.startswith("[") and v.endswith("]"):
            data[k] = [x.strip().strip('"').strip("'") for x in v[1:-1].split(",")]
        else:
            data[k] = v
    return data


def pick_best_post():
    today = date.today().strftime("%Y-%m-%d")
    today_posts = []
    for path in glob.glob(f"_posts/{today}-*.md"):
        # Skip roundup/digest/milestone posts
        stem = Path(path).stem
        if any(x in stem for x in ("roundup", "digest", "milestone", "stats")):
            continue
        try:
            text = Path(path).read_text(encoding="utf-8")
            fm = parse_frontmatter(text)
            title = fm.get("title", "").strip('"').strip("'")
            desc = fm.get("description", "").strip('"').strip("'")
            # Score: featured > breaking > has description + long title
            score = 0
            if fm.get("featured") == "true":
                score += 10
            if fm.get("breaking") == "true":
                score += 5
            if desc:
                score += 3
            if len(title) > 40:
                score += 1
            today_posts.append((score, path, fm))
        except Exception:
            pass
    if not today_posts:
        logging.info("No posts today")
        return None
    today_posts.sort(reverse=True)
    _, path, fm = today_posts[0]
    return path, fm


def use_groq_for_commentary(title: str, description: str) -> str:
    key = os.getenv("GROQ_API_KEY")
    if not key:
        return ""
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [{
                    "role": "user",
                    "content": (
                        f"Write ONE engaging sentence (max 15 words) introducing this news for "
                        f"social media. Be journalistic, not clickbait. "
                        f"Title: {title}. Description: {description[:200]}"
                    ),
                }],
                "max_tokens": 60,
            },
            timeout=20,
        )
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"].strip().strip('"')
    except Exception:
        pass
    return ""


def build_url(filepath: str, fm: dict) -> str:
    stem = Path(filepath).stem
    # YYYY-MM-DD-slug
    parts = stem.split("-", 3)
    if len(parts) < 4:
        return SITE_BASE + "/"
    year, month, day, slug = parts[0], parts[1], parts[2], parts[3]
    cats = fm.get("categories", [])
    cat = (cats[0] if isinstance(cats, list) and cats else "news").strip()
    return f"{SITE_BASE}/{cat}/{year}/{month}/{day}/{slug}/"


def post_to_bluesky(text: str, url: str, title: str) -> None:
    handle = os.getenv("BLUESKY_HANDLE")
    password = os.getenv("BLUESKY_APP_PASSWORD")
    if not handle or not password:
        logging.info("Bluesky credentials not set")
        return
    try:
        sess = requests.post(
            "https://bsky.social/xrpc/com.atproto.server.createSession",
            json={"identifier": handle, "password": password},
            timeout=20,
        )
        sess.raise_for_status()
        s = sess.json()

        record = {
            "$type": "app.bsky.feed.post",
            "text": text,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "langs": ["en"],
            "embed": {
                "$type": "app.bsky.embed.external",
                "external": {"uri": url, "title": title[:300], "description": ""},
            },
        }
        # Add link facet
        url_start = text.find(url)
        if url_start >= 0:
            record["facets"] = [{
                "index": {
                    "byteStart": len(text[:url_start].encode()),
                    "byteEnd": len(text[:url_start + len(url)].encode()),
                },
                "features": [{"$type": "app.bsky.richtext.facet#link", "uri": url}],
            }]

        requests.post(
            "https://bsky.social/xrpc/com.atproto.repo.createRecord",
            headers={"Authorization": f"Bearer {s['accessJwt']}"},
            json={
                "repo": s["did"],
                "collection": "app.bsky.feed.post",
                "record": record,
            },
            timeout=20,
        )
        logging.info(f"Posted to Bluesky: {url}")
    except Exception as e:
        logging.error(f"Bluesky failed: {e}")


def main():
    result = pick_best_post()
    if not result:
        return
    filepath, fm = result
    title = fm.get("title", "").strip('"').strip("'")
    description = fm.get("description", "").strip('"').strip("'")
    cats = fm.get("categories", [])
    cat = (cats[0] if isinstance(cats, list) and cats else "news").strip()
    emoji = CATEGORY_EMOJIS.get(cat, "📰")
    url = build_url(filepath, fm)

    commentary = use_groq_for_commentary(title, description)

    text = f"⭐ Article of the Day\n\n{emoji} {title}\n\n"
    if commentary:
        text += f"{commentary}\n\n"
    text += f"🔗 {url}\n\n#GlobalBRNews #BestOf"

    if len(text) > 300:
        text = text[:297] + "..."

    post_to_bluesky(text, url, title)


if __name__ == "__main__":
    main()
