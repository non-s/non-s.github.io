#!/usr/bin/env python3
"""
create_video_blog_post.py
Creates a Jekyll blog post for each newly uploaded YouTube video.

Reads _videos/*.done files from the last 2 hours and creates
a post in _posts/ with the YouTube embed, description, and metadata.
This ensures every video also appears on the blog and in the RSS feed.
"""

import json
import logging
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("video_blog.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

VIDEOS_DIR = Path("_videos")
POSTS_DIR  = Path("_posts")
LOOKBACK_H = 2
SITE_BASE  = "https://non-s.github.io"


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text[:80].strip("-")


def find_new_videos() -> list[dict]:
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
        except Exception as exc:
            log.debug(f"Could not read {done_file.name}: {exc}")
    return results


def sanitize(text: str) -> str:
    return text.replace('"', "'").replace("\n", " ").strip()


def create_video_post(video: dict) -> bool:
    title       = video.get("title", "").strip()
    youtube_url = video.get("url", "")
    video_id    = video.get("video_id", "")
    description = video.get("description", "").strip()
    tags        = video.get("tags", [])
    is_short    = video.get("is_short", False)
    uploaded_at = video.get("uploaded_at", datetime.now(timezone.utc).isoformat())
    category    = (video.get("category", "video") or "video").lower().strip()

    if not title or not video_id:
        log.warning("Skipping video with missing title or video_id")
        return False

    try:
        pub_date = datetime.fromisoformat(uploaded_at)
        if pub_date.tzinfo is None:
            pub_date = pub_date.replace(tzinfo=timezone.utc)
    except Exception:
        pub_date = datetime.now(timezone.utc)

    slug     = slugify(title)
    date_str = pub_date.strftime("%Y-%m-%d")
    filename = f"{date_str}-video-{slug}.md"
    post_path = POSTS_DIR / filename

    if post_path.exists():
        log.info(f"Post already exists: {filename}")
        return False

    # Extract first 160 chars of description as meta_description
    meta_desc = description[:160].strip()
    if len(description) > 160:
        last_space = meta_desc.rfind(" ")
        if last_space > 100:
            meta_desc = meta_desc[:last_space] + "…"

    # Build tags list
    post_tags = ["video", "youtube"]
    if is_short:
        post_tags.append("shorts")
    # Add up to 5 tags from video metadata
    for t in tags[:5]:
        clean_t = slugify(str(t))
        if clean_t and clean_t not in post_tags and len(clean_t) < 30:
            post_tags.append(clean_t)

    tags_yaml = "[" + ", ".join(post_tags) + "]"
    date_yaml = pub_date.strftime("%Y-%m-%d %H:%M:%S +0000")
    thumbnail_url = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
    content_type  = "shorts" if is_short else "video"

    # Build frontmatter
    frontmatter = f"""---
layout: post
title: "{sanitize(title)}"
date: {date_yaml}
categories: [video]
tags: {tags_yaml}
author: "GlobalBR News"
description: "{sanitize(meta_desc)}"
image: "{thumbnail_url}"
image_alt: "{sanitize(title[:100])}"
source_url: "{youtube_url}"
source_name: "YouTube — GlobalBR News"
sentiment: "neutral"
content_type: "{content_type}"
youtube_id: "{video_id}"
youtube_url: "{youtube_url}"
lang: "en"
---
"""

    # Build full description paragraphs
    paragraphs = []
    for para in description.split("\n\n"):
        para = para.strip()
        if para and len(para) > 30:
            paragraphs.append(para)

    body_text = "\n\n".join(paragraphs[:3]) if paragraphs else description[:500]

    video_type_label = "YouTube Short" if is_short else "video"

    content = f"""{body_text}

<!--more-->

## Watch on YouTube

<div class="video-embed-wrap" style="position:relative;padding-bottom:56.25%;height:0;overflow:hidden;border-radius:.75rem;margin:1.5rem 0;">
  <iframe
    src="https://www.youtube.com/embed/{video_id}"
    title="{sanitize(title)}"
    frameborder="0"
    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
    allowfullscreen
    style="position:absolute;top:0;left:0;width:100%;height:100%;">
  </iframe>
</div>

▶️ [Watch on YouTube]({youtube_url})

---

*This {video_type_label} was produced by [GlobalBR News](https://non-s.github.io) — world news every hour.*
"""

    post_path.write_text(frontmatter + "\n" + content, encoding="utf-8")
    log.info(f"✅ Blog post created: {filename}")
    return True


def main() -> None:
    videos = find_new_videos()
    if not videos:
        log.info("No new videos found — nothing to post.")
        sys.exit(0)

    log.info(f"Found {len(videos)} new video(s) to post to blog.")
    created = 0
    for video in videos:
        if create_video_post(video):
            created += 1

    log.info(f"Done — {created}/{len(videos)} blog post(s) created.")


if __name__ == "__main__":
    main()
