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

from utils.frontmatter import parse as _parse_fm, get_str, get_list
from utils.retry import retry_call

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
COOLDOWN_S = 10        # seconds between posts (rate-limit hygiene)
COOLDOWN_429_S = 60    # extra cooldown after a 429
PT_POSTS_DIR = POSTS_DIR / "pt"

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


def _image_url_usable(url: str) -> bool:
    """
    Return True iff `url` looks like a serveable image (≥3KB, image/* MIME).
    Used to skip Bluesky posts that would otherwise ship with broken cards.
    Same-origin paths (/assets/images/...) are absolute-URL'd before HEAD.
    Tolerates HEAD-blocking hosts with a streaming GET fallback.
    """
    if not url:
        return False
    if url.startswith("/"):
        url = SITE_BASE + url
    if not url.startswith(("http://", "https://")):
        return False
    try:
        r = requests.head(url, timeout=10, allow_redirects=True)
        if r.status_code in (401, 403, 405):
            r = requests.get(url, timeout=10, stream=True)
            r.close()
        if r.status_code != 200:
            return False
        ctype = (r.headers.get("Content-Type") or "").lower()
        if "image/" not in ctype and "octet-stream" not in ctype:
            return False
        clen = r.headers.get("Content-Length")
        if clen and clen.isdigit() and int(clen) < 3 * 1024:
            return False
        return True
    except Exception:
        return False


def build_post_url(filename: str, fm: dict, lang: str = "en") -> str:
    stem  = filename.removesuffix(".md")
    parts = stem.split("-", 3)
    if len(parts) < 4:
        return SITE_BASE + "/"
    year, month, day, slug = parts
    cats     = get_list(fm, "categories")
    category = (cats[0] if cats else "news").strip()
    if lang == "pt":
        return f"{SITE_BASE}/pt/{category}/{year}/{month}/{day}/{slug}/"
    return f"{SITE_BASE}/{category}/{year}/{month}/{day}/{slug}/"


def find_new_posts(lang: str = "en") -> list[dict]:
    """
    Finds new posts by diffing the last commit (git diff HEAD~1 --name-only).
    Falls back to mtime-based detection if git is unavailable or the repo has
    only one commit.

    `lang` controls which posts directory we scan:
      - "en" (default) → `_posts/*.md` (skips anything under `_posts/pt/`)
      - "pt" → `_posts/pt/*.md`
    """
    posts_dir = POSTS_DIR if lang == "en" else PT_POSTS_DIR
    if not posts_dir.exists():
        return []
    results = []
    posts_prefix = "_posts/pt/" if lang == "pt" else "_posts/"

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
            for path in sorted(posts_dir.glob("*.md"), reverse=True):
                # When scanning English, ignore PT entries.
                if lang == "en" and "/pt/" in str(path):
                    continue
                rel = f"{posts_prefix}{path.name}"
                if rel in changed_files or path.name in changed_files:
                    text = path.read_text(encoding="utf-8", errors="replace")
                    fm   = _parse_fm(text)
                    url  = build_post_url(path.name, fm, lang=lang)
                    results.append({"filename": path.name, "url": url, "fm": fm, "lang": lang})
                    if len(results) >= MAX_POSTS:
                        break
            if results:
                return results
    except Exception as exc:
        log.debug("git diff detection failed (%s), falling back to mtime", exc)

    # ── mtime fallback ────────────────────────────────────────────
    cutoff = time.time() - LOOKBACK_H * 3600
    for path in sorted(posts_dir.glob("*.md"), reverse=True):
        if lang == "en" and "/pt/" in str(path):
            continue
        if path.stat().st_mtime < cutoff:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        fm   = _parse_fm(text)
        url  = build_post_url(path.name, fm, lang=lang)
        results.append({"filename": path.name, "url": url, "fm": fm, "lang": lang})
        if len(results) >= MAX_POSTS:
            break
    return results


def get_session(handle: str, password: str) -> dict:
    def _auth():
        resp = requests.post(
            f"{BSKY_API}/com.atproto.server.createSession",
            json={"identifier": handle, "password": password},
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()
    result = retry_call(_auth, max_attempts=3, base_delay=5.0, default=None)
    if result is None:
        raise RuntimeError("Bluesky auth failed after 3 attempts")
    return result


def upload_image_blob(token: str, image_url: str) -> dict | None:
    """Download image_url and upload as a Bluesky blob. Retries on transient errors."""
    def _upload():
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
                "Authorization": f"Bearer {token}",
                "Content-Type":  content_type,
            },
            data=data,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("blob")
    return retry_call(_upload, max_attempts=2, base_delay=3.0, default=None)


def create_post(session: dict, text: str, url: str, title: str, description: str = "", image_url: str = "", lang: str = "en") -> bool:
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
        "langs":     ["pt-BR"] if lang == "pt" else ["en"],
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

    def _post():
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
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", str(COOLDOWN_429_S)))
            log.warning("Bluesky rate limited (429) — sleeping %ds before retry", retry_after)
            time.sleep(retry_after)
            raise requests.exceptions.HTTPError("429 rate limited", response=resp)
        if resp.status_code >= 400:
            log.error("Bluesky API HTTP %d for %s | body=%s",
                      resp.status_code, url, resp.text[:300])
        resp.raise_for_status()
        return True

    result = retry_call(_post, max_attempts=3, base_delay=5.0, default=False)
    if result:
        log.info("✅ Posted to Bluesky — %s", url)
    else:
        log.warning("⚠️ Failed to post to Bluesky after 3 retries — %s", url)
    return bool(result)


def build_post_text(post: dict) -> str:
    """
    Builds an engaging Bluesky post text with emoji, description excerpt,
    link, and relevant hashtags. Fits within the 300-grapheme limit.
    """
    fm          = post["fm"]
    title       = get_str(fm, "title", "New Article")
    cats        = get_list(fm, "categories")
    category    = (cats[0] if cats else "news").strip().lower()
    url         = post["url"]
    description = get_str(fm, "description")
    tags_fm     = get_list(fm, "tags")
    key_points  = get_list(fm, "key_points")
    breaking    = str(get_str(fm, "breaking", "")).lower() == "true"
    featured    = str(get_str(fm, "featured", "")).lower() == "true"
    fact_check  = get_str(fm, "fact_check", "")

    emoji = CATEGORY_EMOJIS.get(category, "📰")

    # ── Hashtags (with contextual signals) ────────────────────────
    contextual: list[str] = []
    if breaking:
        contextual.append("#Breaking")
    if featured and not breaking:
        contextual.append("#MustRead")
    if fact_check == "verified":
        contextual.append("#FactChecked")
    cat_tags = CATEGORY_HASHTAGS.get(category, [f"#{category.replace(' ', '')}"])
    # Pick short post tags (≤15 chars as hashtag, no spaces, no duplicates)
    post_tags = []
    seen_lower = {t.lstrip("#").lower() for t in (contextual + cat_tags)}
    for t in (tags_fm if isinstance(tags_fm, list) else []):
        ht = "#" + t.replace("-", "").replace(" ", "")
        if len(ht) <= 15 and ht.lstrip("#").lower() not in seen_lower:
            post_tags.append(ht)
            seen_lower.add(ht.lstrip("#").lower())
        if len(post_tags) >= 2:  # leave room for contextual tags
            break
    hashtags = " ".join(contextual + cat_tags + post_tags + ["#GlobalBRNews"])

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

    if not handle:
        log.error("❌ BLUESKY_HANDLE not set in environment — cannot post.")
        sys.exit(0)
    if not password:
        log.error("❌ BLUESKY_APP_PASSWORD not set in environment — cannot post.")
        log.error("   Generate one at https://bsky.app → Settings → App Passwords")
        sys.exit(0)
    log.info("→ Bluesky handle: %s", handle)

    en_posts = find_new_posts(lang="en")
    pt_posts = find_new_posts(lang="pt") if PT_POSTS_DIR.exists() else []
    posts = en_posts + pt_posts
    log.info("→ New posts to share: %d EN + %d PT = %d total",
             len(en_posts), len(pt_posts), len(posts))
    if not posts:
        log.info("No new posts found — nothing to share on Bluesky.")
        sys.exit(0)

    try:
        session = get_session(handle, password)
        log.info("✅ Authenticated as %s (did=%s)", session.get("handle"), session.get("did"))
    except Exception as exc:
        # Surface the failure prominently so the workflow log is actionable.
        log.error("❌ Bluesky auth failed: %s", exc)
        log.error("   Common causes:")
        log.error("   • App password expired/revoked → regenerate at Bluesky → Settings → App Passwords")
        log.error("   • Handle typo (must be full handle: name.bsky.social)")
        log.error("   • Account locked / 2FA blocking app password")
        sys.exit(1)

    ok = 0
    skipped = 0
    for idx, post in enumerate(posts):
        post_url = post["url"]
        lang = post.get("lang", "en")

        # Validate the post URL is reachable before sharing
        try:
            check = requests.head(post_url, timeout=10, allow_redirects=True)
            if check.status_code >= 400:
                log.warning("Skipping — URL returned %d: %s", check.status_code, post_url)
                skipped += 1
                continue
        except requests.exceptions.RequestException:
            pass  # network error — still try to post (GitHub Pages may not be live yet)

        text        = build_post_text(post)
        title       = get_str(post["fm"], "title")
        description = get_str(post["fm"], "description")
        image_url   = get_str(post["fm"], "image")
        # Validate the cover image actually serves a usable file. Posts
        # without a working thumbnail produce ugly link cards on Bluesky.
        if not image_url or not _image_url_usable(image_url):
            log.warning("Skipping — no usable cover image for %s", post_url)
            skipped += 1
            continue
        if create_post(session, text, post_url, title, description, image_url, lang=lang):
            ok += 1
        else:
            skipped += 1
        # Cool down between posts to avoid Bluesky rate limits.
        if idx < len(posts) - 1:
            time.sleep(COOLDOWN_S)

    log.info("Done — %d posted, %d skipped (of %d total).", ok, skipped, len(posts))


if __name__ == "__main__":
    main()
