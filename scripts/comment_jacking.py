#!/usr/bin/env python3
"""Comment Jacking: Post engaging trivia on trending nature videos."""
import os
import sys
import logging
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("comment_jacking")

from upload_youtube import get_youtube_service
from utils.ai_helper import ai_text

def run():
    try:
        youtube = get_youtube_service()
    except Exception as e:
        log.error(f"No YouTube service available: {e}")
        return

    if not youtube:
        log.error("No YouTube service available.")
        return

    # 1. Ask AI for a brilliant trivia question to post
    prompt = (
        "Generate a short, viral YouTube comment trivia question about nature or wildlife. "
        "It must have options A and B, and a hook that makes people want to click our channel to find the answer. "
        "Keep it under 300 characters. Example: 'Did you know the immortal jellyfish can reverse its age? A) True B) False. Check out our channel for the mind-blowing answer!'"
    )
    comment_text = ai_text(prompt, timeout=20)
    if not comment_text:
        log.error("Failed to generate trivia text.")
        return
        
    comment_text = comment_text.strip().strip('"\'')
    
    # 2. Find the top 3 most recent videos about wildlife
    try:
        search_response = youtube.search().list(
            q="wildlife documentary | animal facts",
            part="id,snippet",
            maxResults=3,
            order="date", # Most recent
            type="video"
        ).execute()
        
        videos = search_response.get("items", [])
        for video in videos:
            video_id = video["id"]["videoId"]
            log.info(f"Posting trivia to video {video_id}: {video['snippet']['title']}")
            
            try:
                youtube.commentThreads().insert(
                    part="snippet",
                    body={
                        "snippet": {
                            "videoId": video_id,
                            "topLevelComment": {
                                "snippet": {
                                    "textOriginal": comment_text
                                }
                            }
                        }
                    }
                ).execute()
                log.info("Successfully posted comment.")
            except Exception as e:
                log.warning(f"Failed to post on {video_id}: {e}")
                
    except Exception as e:
        log.error(f"Search API failed: {e}")

if __name__ == "__main__":
    run()
