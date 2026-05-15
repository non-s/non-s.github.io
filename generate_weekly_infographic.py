#!/usr/bin/env python3
"""
generate_weekly_infographic.py
Generates a weekly stats infographic image and posts it to Bluesky.
"""
from __future__ import annotations

import logging
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

from utils.frontmatter import parse, get_str
from utils.retry import retry_call

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

POSTS_DIR = Path("_posts")
BSKY_API  = "https://bsky.social/xrpc"
OUT_IMAGE = Path("_infographic.jpg")

BG      = (8, 12, 23)
SURFACE = (13, 18, 36)
ACCENT  = (249, 115, 22)
TEXT    = (241, 245, 249)
MUTED   = (100, 116, 139)
WHITE   = (255, 255, 255)
BORDER  = (30, 42, 58)

_DATE_RE  = re.compile(r'^(\d{4})-(\d{2})-(\d{2})-')
_SKIP     = ("roundup", "digest")


def get_font(size: int, bold: bool = False):
    from PIL import ImageFont
    candidates = [
        "/usr/share/fonts/truetype/liberation/LiberationSans-{}.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-{}.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-{}.ttf",
    ]
    suffix = "Bold" if bold else "Regular"
    for tpl in candidates:
        path = Path(tpl.format(suffix))
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size)
            except Exception:
                continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def collect_stats() -> dict:
    cutoff     = datetime.now(timezone.utc) - timedelta(days=7)
    categories = Counter()
    sources    = Counter()
    breaking   = 0
    post_names: list[str] = []

    for path in POSTS_DIR.glob("*.md"):
        m = _DATE_RE.match(path.name)
        if not m:
            continue
        if any(x in path.name for x in _SKIP):
            continue
        try:
            pd = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)
            if pd < cutoff:
                continue
            fm  = parse(path.read_text(encoding="utf-8", errors="replace"))
            cat = get_str(fm, "categories", "news")
            categories[cat] += 1
            if get_str(fm, "breaking") == "true":
                breaking += 1
            src = get_str(fm, "source_name")
            if src:
                sources[src] += 1
            post_names.append(path.name)
        except Exception:
            continue

    return {
        "total":       len(post_names),
        "categories":  dict(categories.most_common(5)),
        "breaking":    breaking,
        "top_sources": dict(sources.most_common(3)),
        "week":        datetime.now(timezone.utc).strftime("Week of %B %d, %Y"),
    }


def generate_image(stats: dict) -> Path:
    from PIL import Image, ImageDraw
    W, H = 1200, 630
    img  = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    draw.rectangle([0, 0, W, 80], fill=SURFACE)
    draw.rectangle([0, 78, W, 82], fill=ACCENT)
    draw.text((40, 25), "⚡ GlobalBR News", font=get_font(28, bold=True), fill=ACCENT)
    draw.text((W - 40, 30), stats["week"], font=get_font(16), fill=MUTED, anchor="rt")

    draw.text((40, 110), "Weekly Stats",    font=get_font(40, bold=True), fill=TEXT)
    total_str = str(stats["total"])
    draw.text((40, 155), total_str,         font=get_font(90, bold=True), fill=ACCENT)
    draw.text((40 + len(total_str) * 52, 220), "articles published", font=get_font(20), fill=MUTED)

    if stats["breaking"]:
        draw.text((40, 275), f"🔴  {stats['breaking']} breaking news", font=get_font(20), fill=WHITE)

    y = 320
    draw.text((40, y - 25), "TOP CATEGORIES", font=get_font(13), fill=MUTED)
    max_count = max(stats["categories"].values(), default=1)
    for cat, count in list(stats["categories"].items())[:5]:
        bar_w = int((count / max_count) * 300)
        draw.rectangle([40, y, 40 + bar_w, y + 20], fill=ACCENT)
        draw.text((360, y + 2), f"{cat.capitalize()} — {count}", font=get_font(18), fill=TEXT)
        y += 35

    x_right, y_src = 700, 320
    draw.text((x_right, y_src - 25), "TOP SOURCES", font=get_font(13), fill=MUTED)
    for src, count in list(stats["top_sources"].items())[:3]:
        draw.text((x_right, y_src), f"• {src[:30]}", font=get_font(18, bold=True), fill=TEXT)
        draw.text((x_right + 380, y_src), str(count), font=get_font(18), fill=ACCENT, anchor="rt")
        y_src += 38

    draw.rectangle([0, H - 50, W, H], fill=SURFACE)
    draw.text((40, H - 32), "non-s.github.io  |  News every hour", font=get_font(14), fill=MUTED)
    draw.text((W - 40, H - 32), "#GlobalBRNews  #WeeklyStats", font=get_font(14), fill=MUTED, anchor="rt")

    img.save(str(OUT_IMAGE), "JPEG", quality=90)
    log.info("Infographic saved: %s", OUT_IMAGE)
    return OUT_IMAGE


def main() -> None:
    handle   = os.environ.get("BLUESKY_HANDLE", "").strip()
    password = os.environ.get("BLUESKY_APP_PASSWORD", "").strip()
    if not handle or not password:
        log.warning("Bluesky credentials not set — skipping.")
        sys.exit(0)

    stats = collect_stats()
    log.info("Stats: %d articles, %d breaking", stats["total"], stats["breaking"])

    image_path = generate_image(stats)

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

    def _upload():
        token = session["accessJwt"]
        data  = image_path.read_bytes()
        r = requests.post(
            f"{BSKY_API}/com.atproto.repo.uploadBlob",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "image/jpeg"},
            data=data,
            timeout=30,
        )
        r.raise_for_status()
        return r.json().get("blob")

    blob = retry_call(_upload, max_attempts=3, base_delay=5.0, default=None)
    if not blob:
        log.error("Image upload failed")
        sys.exit(1)

    total     = stats["total"]
    top_cats  = ", ".join(stats["categories"].keys())
    post_text = (
        f"📊 Weekly Stats — {stats['week']}\n\n"
        f"📰 {total} articles published\n"
        f"🔴 {stats['breaking']} breaking news\n"
        f"📂 Top categories: {top_cats}\n\n"
        f"#GlobalBRNews #WeeklyStats #NewsRoundup"
    )
    record = {
        "$type":     "app.bsky.feed.post",
        "text":      post_text[:300],
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "langs":     ["en"],
        "embed": {
            "$type":  "app.bsky.embed.images",
            "images": [{"image": blob, "alt": f"GlobalBR News weekly stats: {total} articles"}],
        },
    }

    def _do_post():
        r = requests.post(
            f"{BSKY_API}/com.atproto.repo.createRecord",
            headers={"Authorization": f"Bearer {session['accessJwt']}"},
            json={"repo": session["did"], "collection": "app.bsky.feed.post", "record": record},
            timeout=20,
        )
        r.raise_for_status()
        return True

    ok = retry_call(_do_post, max_attempts=3, base_delay=5.0, default=False)
    if ok:
        log.info("Weekly infographic posted to Bluesky!")
    else:
        log.warning("Bluesky post failed")

    image_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
