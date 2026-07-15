#!/usr/bin/env python3
"""SEO Watchdog: Automatically mutates titles of videos with low performance."""
import sys
import json
import logging
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from upload_youtube import get_youtube_service

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("seo_watchdog")


def _build_ai_prompt(title: str, tags: list[str]) -> str:
    tags_str = ", ".join(tags[:10])
    return (
        f"Generate exactly 1 new click-worthy YouTube title to replace this underperforming one:\n"
        f"Old Title: {title}\n"
        f"Tags: {tags_str}\n"
        "Rules: Max 60 chars. Must create intense curiosity (Zeigarnik effect). "
        "No emojis. Return ONLY the title text."
    )


def run():
    post24_file = Path("_data/post24_review.json")
    if not post24_file.exists():
        log.info("No post24_review.json found.")
        return

    data = json.loads(post24_file.read_text())
    videos = data.get("videos", [])
    try:
        youtube = get_youtube_service()
    except Exception as e:
        log.error(f"No YouTube service available: {e}")
        return

    for v in videos:
        # Actionable states for SEO mutation
        if v.get("classification") in ["repair_package", "rewrite_hook"]:
            vid = v.get("video_id")
            new_title = v.get("repair_suggestions", [""])[0] if v.get("repair_suggestions") else ""
            if not vid or not new_title:
                continue
                
            try:
                # 1. Get current video details
                video_response = youtube.videos().list(id=vid, part="snippet").execute()
                if not video_response.get("items"):
                    continue
                snippet = video_response["items"][0]["snippet"]
                
                # 2. Update the title with an aggressive variant (e.g. from the AI repair suggestions)
                old_title = snippet["title"]
                snippet["title"] = f"🔥 {new_title}"[:100]  # Ensure it fits
                
                # 3. Update tags to include "viral" and "shocking" equivalents
                tags = snippet.get("tags", [])
                tags.extend(["viral nature", "wildlife caught on camera"])
                snippet["tags"] = list(set(tags))
                
                youtube.videos().update(
                    part="snippet",
                    body={
                        "id": vid,
                        "snippet": snippet
                    }
                ).execute()
                
                log.info(f"SEO Watchdog mutated video {vid}: '{old_title}' -> '{snippet['title']}'")
            except Exception as e:
                log.error(f"Failed to update video {vid}: {e}")

if __name__ == "__main__":
    run()
