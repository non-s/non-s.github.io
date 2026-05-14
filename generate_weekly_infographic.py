#!/usr/bin/env python3
"""
generate_weekly_infographic.py
Generates a weekly stats infographic image and posts it to Bluesky.

Reads _posts/ for the last 7 days, computes stats, generates a 1200x630
image with Pillow, and posts to Bluesky with the image embedded.

Env vars required:
  BLUESKY_HANDLE
  BLUESKY_APP_PASSWORD
"""

import json
import logging
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

POSTS_DIR  = Path("_posts")
BSKY_API   = "https://bsky.social/xrpc"
OUT_IMAGE  = Path("_infographic.jpg")

# Color palette
BG        = (8, 12, 23)
SURFACE   = (13, 18, 36)
ACCENT    = (249, 115, 22)
TEXT      = (241, 245, 249)
MUTED     = (100, 116, 139)
WHITE     = (255, 255, 255)
GREEN     = (34, 197, 94)
BORDER    = (30, 42, 58)


def get_font(size: int, bold: bool = False):
    from PIL import ImageFont
    candidates_bold = [
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    ]
    candidates_reg = [
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    ]
    for path in (candidates_bold if bold else candidates_reg):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def parse_frontmatter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    fm = {}
    for line in parts[1].splitlines():
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        k = k.strip(); v = v.strip().strip('"').strip("'")
        if v.startswith("[") and v.endswith("]"):
            fm[k] = [x.strip().strip('"').strip("'") for x in v[1:-1].split(",") if x.strip()]
        else:
            fm[k] = v
    return fm


def collect_stats() -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    posts = []
    categories = Counter()
    breaking = 0
    sources = Counter()

    for path in POSTS_DIR.glob("*.md"):
        m = re.match(r'^(\d{4})-(\d{2})-(\d{2})-', path.name)
        if not m:
            continue
        try:
            post_date = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)
        except ValueError:
            continue
        if post_date < cutoff:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            fm = parse_frontmatter(text)
            if "roundup" in path.name or "digest" in path.name:
                continue
            cats = fm.get("categories", [])
            cat = (cats[0] if isinstance(cats, list) and cats else "news").strip()
            categories[cat] += 1
            if fm.get("breaking") == "true":
                breaking += 1
            source = fm.get("source_name", "")
            if source:
                sources[source] += 1
            posts.append(path.name)
        except Exception:
            continue

    return {
        "total": len(posts),
        "categories": dict(categories.most_common(5)),
        "breaking": breaking,
        "top_sources": dict(sources.most_common(3)),
        "week": datetime.now(timezone.utc).strftime("Week of %B %d, %Y"),
    }


def generate_image(stats: dict) -> Path:
    from PIL import Image, ImageDraw
    W, H = 1200, 630
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # Header bar
    draw.rectangle([0, 0, W, 80], fill=SURFACE)
    draw.rectangle([0, 78, W, 82], fill=ACCENT)

    # Logo text
    f_logo = get_font(28, bold=True)
    draw.text((40, 25), "⚡ GlobalBR News", font=f_logo, fill=ACCENT)

    # Week label
    f_week = get_font(16)
    draw.text((W - 40, 30), stats["week"], font=f_week, fill=MUTED, anchor="rt")

    # Title
    f_title = get_font(40, bold=True)
    draw.text((40, 110), "Weekly Stats", font=f_title, fill=TEXT)

    # Big number
    f_big = get_font(90, bold=True)
    total_str = str(stats["total"])
    draw.text((40, 155), total_str, font=f_big, fill=ACCENT)
    f_label = get_font(20)
    draw.text((40 + len(total_str) * 52, 220), "articles published", font=f_label, fill=MUTED)

    # Breaking news count
    if stats["breaking"]:
        draw.text((40, 275), f"🔴  {stats['breaking']} breaking news", font=f_label, fill=WHITE)

    # Category breakdown
    f_cat = get_font(18, bold=True)
    f_cat_val = get_font(18)
    y = 320
    draw.text((40, y - 25), "TOP CATEGORIES", font=get_font(13), fill=MUTED)
    for cat, count in list(stats["categories"].items())[:5]:
        bar_w = int((count / max(stats["categories"].values(), default=1)) * 300)
        draw.rectangle([40, y, 40 + bar_w, y + 20], fill=ACCENT)
        draw.text((360, y + 2), f"{cat.capitalize()} — {count}", font=f_cat_val, fill=TEXT)
        y += 35

    # Top sources (right column)
    x_right = 700
    y_src = 320
    draw.text((x_right, y_src - 25), "TOP SOURCES", font=get_font(13), fill=MUTED)
    for src, count in list(stats["top_sources"].items())[:3]:
        draw.text((x_right, y_src), f"• {src[:30]}", font=f_cat, fill=TEXT)
        draw.text((x_right + 380, y_src), str(count), font=f_cat_val, fill=ACCENT, anchor="rt")
        y_src += 38

    # Footer
    draw.rectangle([0, H - 50, W, H], fill=SURFACE)
    draw.text((40, H - 32), "non-s.github.io  |  News every hour", font=get_font(14), fill=MUTED)
    draw.text((W - 40, H - 32), "#GlobalBRNews  #WeeklyStats", font=get_font(14), fill=MUTED, anchor="rt")

    img.save(str(OUT_IMAGE), "JPEG", quality=90)
    log.info(f"Infographic saved: {OUT_IMAGE}")
    return OUT_IMAGE


def get_session(handle: str, password: str) -> dict:
    resp = requests.post(
        f"{BSKY_API}/com.atproto.server.createSession",
        json={"identifier": handle, "password": password},
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


def upload_image(session: dict, image_path: Path) -> str | None:
    token = session["accessJwt"]
    data  = image_path.read_bytes()
    resp  = requests.post(
        f"{BSKY_API}/com.atproto.repo.uploadBlob",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "image/jpeg"},
        data=data,
        timeout=30,
    )
    if resp.status_code == 200:
        return resp.json()["blob"]
    log.warning("Image upload failed: %s", resp.text[:200])
    return None


def post_infographic(session: dict, stats: dict, blob: str) -> bool:
    token = session["accessJwt"]
    total = stats["total"]
    top_cats = ", ".join(stats["categories"].keys())
    text = (
        f"📊 Weekly Stats — {stats['week']}\n\n"
        f"📰 {total} articles published\n"
        f"🔴 {stats['breaking']} breaking news\n"
        f"📂 Top categories: {top_cats}\n\n"
        f"#GlobalBRNews #WeeklyStats #NewsRoundup"
    )
    record = {
        "$type":     "app.bsky.feed.post",
        "text":      text[:300],
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "langs":     ["en"],
        "embed": {
            "$type": "app.bsky.embed.images",
            "images": [{"image": blob, "alt": f"GlobalBR News weekly stats: {total} articles"}],
        },
    }
    resp = requests.post(
        f"{BSKY_API}/com.atproto.repo.createRecord",
        headers={"Authorization": f"Bearer {token}"},
        json={"repo": session["did"], "collection": "app.bsky.feed.post", "record": record},
        timeout=20,
    )
    if resp.status_code == 200:
        log.info("Weekly infographic posted to Bluesky!")
        return True
    log.warning("Post failed: %s", resp.text[:200])
    return False


def main():
    handle   = os.environ.get("BLUESKY_HANDLE", "").strip()
    password = os.environ.get("BLUESKY_APP_PASSWORD", "").strip()
    if not handle or not password:
        log.warning("Bluesky credentials not set — skipping.")
        sys.exit(0)

    stats = collect_stats()
    log.info(f"Stats: {stats['total']} articles, {stats['breaking']} breaking")

    image_path = generate_image(stats)

    try:
        session = get_session(handle, password)
    except Exception as exc:
        log.error("Auth failed: %s", exc)
        sys.exit(1)

    blob = upload_image(session, image_path)
    if not blob:
        log.error("Could not upload image")
        sys.exit(1)

    post_infographic(session, stats, blob)
    image_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
