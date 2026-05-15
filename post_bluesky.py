#!/usr/bin/env python3
"""
post_bluesky.py
Auto-posts new articles to Bluesky using the AT Protocol HTTP API.

Reads _posts/ for files added in the last commit (git diff HEAD~1 --name-only),
builds their permalink, and creates an engaging post on Bluesky with emoji,
description excerpt, link, and relevant hashtags.

Env vars required:
  BLUESKY_HANDLE       — your handle, e.g. globalbrnews.bsky.social
  BLUESKY_APP_PASSWORD — App Password from Settings → App Passwords
"""

import logging
import os
import subprocess
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

POSTS_DIR  = Path(__file__).parent / "_posts"
SITE_BASE  = "https://non-s.github.io"
BSKY_API   = "https://bsky.social/xrpc"
LOOKBACK_H = 2
MAX_POSTS  = 5

CATEGORY_EMOJIS = {
    "world": "🌍", "politics": "🏛️", "war": "⚔️", "business": "💼",
    "technology": "💻", "science": "🔬", "health": "🏥", "sports": "⚽",
    "food": "🍕", "entertainment": "🎬", "environment": "🌱",
    "travel": "✈️", "ai": "🤖", "security": "🔒",
    "gadgets": "📱", "startups": "🚀", "mobile": "📲",
}

CATEGORY_HASHTAGS = {
    "world": ["#WorldNews", "#BreakingNews"],
    "politics": ["#Politics", "#GlobalPolitics"],
    "war": ["#War", "#Conflict", "#BreakingNews"],
    "business": ["#Business", "#Economy", "#Markets"],
    "technology": ["#Tech", "#Technology"],
    "science": ["#Science", "#Research"],
    "health": ["#Health", "#Medicine"],
    "sports": ["#Sports"],
    "food": ["#Food", "#FoodNews"],
    "entertainment": ["#Entertainment", "#Culture"],
    "environment": ["#Climate", "#Environment"],
    "travel": ["#Travel"],
    "ai": ["#AI", "#ArtificialIntelligence", "#Tech"],
    "security": ["#CyberSecurity", "#Security", "#Tech"],
    "gadgets": ["#Gadgets", "#Tech"],
    "startups": ["#Startups", "#Tech"],
    "mobile": ["#Mobile", "#Tech"],
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
    """
    Finds new posts by diffing the last commit (git diff HEAD~1 --name-only).
    Falls back to mtime-based detection if git is unavailable or the repo has
    only one commit.
    """
    results = []

    # ── Git-based detection (reliable in CI) ─────────────────────
    try:
        proc = subprocess.run(
            ["git", "diff", "HEAD~1", "--name-only", "--diff-filter=A"],
            cwd=str(POSTS_DIR.parent),
            capture_output=True,
            text=True,
            timeout=15,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            changed_files = set(proc.stdout.strip().splitlines())
            for path in sorted(POSTS_DIR.glob("*.md"), reverse=True):
                # Match both "_posts/filename.md" and "filename.md" formats
                rel = f"_posts/{path.name}"
                if rel in changed_files or path.name in changed_files:
                    text = path.read_text(encoding="utf-8", errors="replace")
                    fm   = parse_frontmatter(text)
                    url  = build_post_url(path.name, fm)
                    results.append({"filename": path.name, "url": url, "fm": fm})
                    if len(results) >= MAX_POSTS:
                        break
            if results:
                return results
    except Exception as exc:
        log.debug("git diff detection failed (%s), falling back to mtime", exc)

    # ── mtime fallback ────────────────────────────────────────────
    cutoff = time.time() - LOOKBACK_H * 3600
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


def upload_image_blob(token: str, image_url: str) -> dict | None:
    """Download image_url and upload as a Bluesky blob. Returns blob ref dict or None."""
    try:
        r = requests.get(image_url, timeout=20, stream=True)
        r.raise_for_status()
        content_type = r.headers.get("Content-Type", "image/jpeg").split(";")[0].strip()
        if not content_type.startswith("image/"):
            content_type = "image/jpeg"
        data = r.content
        if len(data) < 100:
            return None
        resp = requests.post(
            f"{BSKY_API}/com.atproto.repo.uploadBlob",
            headers={
                "Authorization":  f"Bearer {token}",
                "Content-Type":   content_type,
            },
            data=data,
            timeout=30,
        )
        if resp.status_code == 200:
            return resp.json().get("blob")
        log.debug("Blob upload failed HTTP %s", resp.status_code)
    except Exception as exc:
        log.debug("Image upload skipped (%s)", exc)
    return None


def create_post(session: dict, text: str, url: str, title: str, description: str = "", image_url: str = "") -> bool:
    """Create a Bluesky post with an embedded link card and optional thumbnail."""
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

    # Upload thumbnail if we have an image URL
    thumb_blob = None
    if image_url:
        thumb_blob = upload_image_blob(token, image_url)

    # Embed external link card with optional thumbnail
    card_description = description[:300] if description else ""
    external: dict = {
        "uri":         url,
        "title":       title[:300],
        "description": card_description,
    }
    if thumb_blob:
        external["thumb"] = thumb_blob
    record["embed"] = {
        "$type":    "app.bsky.embed.external",
        "external": external,
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
    """
    Builds an engaging Bluesky post text with emoji, description excerpt,
    link, and relevant hashtags. Fits within the 300-grapheme limit.
    """
    fm          = post["fm"]
    title       = fm.get("title", "").strip('"').strip("'") or "New Article"
    cats        = fm.get("categories", [])
    category    = (cats[0] if isinstance(cats, list) and cats else "news").strip().lower()
    url         = post["url"]
    description = fm.get("description", "").strip('"').strip("'").strip()
    tags_fm     = fm.get("tags", [])
    key_points  = fm.get("key_points", [])

    emoji = CATEGORY_EMOJIS.get(category, "📰")

    # ── Hashtags ──────────────────────────────────────────────────
    cat_tags = CATEGORY_HASHTAGS.get(category, [f"#{category.replace(' ', '')}"])
    # Pick short post tags (≤15 chars as hashtag, no spaces, no duplicates)
    post_tags = []
    seen_lower = {t.lstrip("#").lower() for t in cat_tags}
    for t in (tags_fm if isinstance(tags_fm, list) else []):
        ht = "#" + t.replace("-", "").replace(" ", "")
        if len(ht) <= 15 and ht.lstrip("#").lower() not in seen_lower:
            post_tags.append(ht)
            seen_lower.add(ht.lstrip("#").lower())
        if len(post_tags) >= 3:
            break
    hashtags = " ".join(cat_tags + post_tags + ["#GlobalBRNews"])

    # ── Description excerpt (~120 chars) ─────────────────────────
    desc_excerpt = ""
    if description:
        desc_excerpt = description[:120]
        if len(description) > 120:
            # truncate at last space to avoid mid-word cut
            last_space = desc_excerpt.rfind(" ")
            if last_space > 80:
                desc_excerpt = desc_excerpt[:last_space] + "…"
            else:
                desc_excerpt = desc_excerpt + "…"

    # If no description, try the first key_point as a highlight
    if not desc_excerpt and key_points and isinstance(key_points, list) and key_points:
        first_kp = str(key_points[0]).strip().strip('"').strip("'")
        if first_kp:
            desc_excerpt = first_kp[:120]

    # ── Assemble post ─────────────────────────────────────────────
    def _assemble(title_text: str, desc_text: str) -> str:
        parts = [f"{emoji} {title_text}"]
        if desc_text:
            parts.append(f"\n{desc_text}")
        parts.append(f"\n🔗 {url}")
        parts.append(f"\n{hashtags}")
        return "\n".join(parts)

    text = _assemble(title, desc_excerpt)

    # ── Trim to 300 graphemes ─────────────────────────────────────
    if len(text) > 300:
        # First reduce description
        if desc_excerpt:
            budget = 300 - len(_assemble(title, "").replace("\n\n", "\n"))
            if budget > 20:
                desc_excerpt = desc_excerpt[:budget - 1] + "…"
            else:
                desc_excerpt = ""
            text = _assemble(title, desc_excerpt)

    if len(text) > 300:
        # Then trim title
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
        text        = build_post_text(post)
        title       = post["fm"].get("title", "").strip('"').strip("'")
        description = post["fm"].get("description", "").strip('"').strip("'")
        image_url   = post["fm"].get("image", "").strip('"').strip("'")
        if create_post(session, text, post["url"], title, description, image_url):
            ok += 1
        time.sleep(2)  # be polite to the API

    log.info("Done — %d/%d post(s) shared on Bluesky.", ok, len(posts))


if __name__ == "__main__":
    main()
