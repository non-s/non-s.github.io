#!/usr/bin/env python3
"""
post_pinterest.py
Auto-posts new articles as Pinterest Pins using the Pinterest API v5.

Reads _posts/ for files modified in the last 2 hours, builds their permalink,
and creates a Pin with image + title + description + link.

Env vars required:
  PINTEREST_ACCESS_TOKEN — OAuth2 token from developers.pinterest.com
  PINTEREST_BOARD_ID     — Board ID to post pins to (get from board URL)
"""

import json
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
        logging.FileHandler("pinterest_post.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

POSTS_DIR  = Path(__file__).parent / "_posts"
SITE_BASE  = "https://non-s.github.io"
PINTEREST_API = "https://api.pinterest.com/v5"
LOOKBACK_H = 2
MAX_PINS   = 5


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
        if len(results) >= MAX_PINS:
            break
    return results


def create_pin(token: str, board_id: str, post: dict) -> bool:
    fm          = post["fm"]
    title       = fm.get("title", "").strip('"').strip("'") or "Global News"
    description = fm.get("description", "").strip('"').strip("'")
    image_url   = fm.get("image", "").strip('"').strip("'")
    link        = post["url"]

    # Build pin note: description + tags
    cats = fm.get("categories", [])
    cat  = (cats[0] if isinstance(cats, list) and cats else "news").strip()
    tags_raw = fm.get("tags", [])
    tags = tags_raw if isinstance(tags_raw, list) else []
    hashtags = " ".join(f"#{t.replace('-', '')}" for t in tags[:5] if t)
    note = f"{description}\n\n#{cat} #GlobalBRNews #news {hashtags}".strip()[:500]

    payload = {
        "board_id":   board_id,
        "title":      title[:100],
        "description": note,
        "link":        link,
        "alt_text":   title[:500],
    }

    # Use image URL if available, otherwise use Pollinations for a unique image
    if image_url and image_url.startswith("http"):
        payload["media_source"] = {
            "source_type": "image_url",
            "url": image_url,
        }
    else:
        # Fallback: use a relevant category image from Pollinations
        from urllib.parse import quote
        scene_map = {
            "world": "global world news editorial journalism", "politics": "political government",
            "war": "conflict military editorial", "business": "finance business professional",
            "science": "laboratory science discovery", "health": "medical health care",
            "food": "gourmet food photography", "sports": "athletic sports competition",
            "entertainment": "entertainment movies music", "technology": "technology futuristic",
            "ai": "artificial intelligence neural network", "security": "cybersecurity digital",
            "environment": "nature environment green energy",
        }
        scene   = scene_map.get(cat, "editorial news journalism")
        prompt  = quote(f"photorealistic {scene} 9:16 vertical high quality no text")
        seed    = abs(hash(title)) % 99999
        fallback_url = f"https://image.pollinations.ai/prompt/{prompt}?width=1000&height=1500&nologo=true&seed={seed}&model=flux"
        payload["media_source"] = {
            "source_type": "image_url",
            "url": fallback_url,
        }

    resp = requests.post(
        f"{PINTEREST_API}/pins",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
        },
        json=payload,
        timeout=30,
    )

    if resp.status_code in (200, 201):
        pin_id = resp.json().get("id", "?")
        log.info("Pin criado — %s (id=%s)", link, pin_id)
        return True

    log.warning("Falha ao criar pin — HTTP %s: %s", resp.status_code, resp.text[:300])
    return False


def main() -> None:
    token    = os.environ.get("PINTEREST_ACCESS_TOKEN", "").strip()
    board_id = os.environ.get("PINTEREST_BOARD_ID", "").strip()

    if not token or not board_id:
        log.warning("PINTEREST_ACCESS_TOKEN ou PINTEREST_BOARD_ID não definidos — pulando.")
        sys.exit(0)

    posts = find_new_posts()
    if not posts:
        log.info("Nenhum post novo — nada para pinar.")
        sys.exit(0)

    log.info("Encontrados %d post(s) para pinar.", len(posts))

    ok = 0
    for post in posts:
        if create_pin(token, board_id, post):
            ok += 1
        time.sleep(3)

    log.info("Pronto — %d/%d pin(s) criados.", ok, len(posts))


if __name__ == "__main__":
    main()
