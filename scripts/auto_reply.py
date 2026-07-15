#!/usr/bin/env python3
"""Auto-Reply Bot: Cultivate a highly active community by replying to comments."""
import sys
import logging
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("auto_reply")

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

    try:
        # Get channel's own uploads playlist to find recent videos
        channels_response = youtube.channels().list(
            mine=True,
            part="contentDetails"
        ).execute()
        
        if not channels_response.get("items"):
            log.warning("Could not find the channel.")
            return
            
        uploads_playlist_id = channels_response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        
        # Get the latest 3 videos
        playlist_response = youtube.playlistItems().list(
            playlistId=uploads_playlist_id,
            part="snippet",
            maxResults=3
        ).execute()
        
        for item in playlist_response.get("items", []):
            video_id = item["snippet"]["resourceId"]["videoId"]
            log.info(f"Checking comments for video: {video_id}")
            
            # Fetch recent comments
            comments_response = youtube.commentThreads().list(
                videoId=video_id,
                part="snippet,replies",
                maxResults=10,
                textFormat="plainText"
            ).execute()
            
            for thread in comments_response.get("items", []):
                top_comment = thread["snippet"]["topLevelComment"]
                comment_id = top_comment["id"]
                text = top_comment["snippet"]["textDisplay"]
                author = top_comment["snippet"]["authorDisplayName"]
                
                # Check if we already replied
                replies = thread.get("replies", {}).get("comments", [])
                already_replied = any(
                    r["snippet"]["authorChannelId"]["value"] == channels_response["items"][0]["id"] 
                    for r in replies
                )
                
                if already_replied:
                    continue
                
                log.info(f"New comment from {author}: {text}")
                
                # Ask AI to generate a reply
                prompt = (
                    f"A fan named {author} commented this on our wildlife YouTube channel: '{text}'. "
                    "Write a very short, engaging, and friendly reply (max 2 sentences). "
                    "Make them feel special to build a cult-like community."
                )
                reply_text = ai_text(prompt, timeout=15)
                
                if reply_text:
                    reply_text = reply_text.strip().strip('"\'')
                    try:
                        youtube.comments().insert(
                            part="snippet",
                            body={
                                "snippet": {
                                    "parentId": comment_id,
                                    "textOriginal": reply_text
                                }
                            }
                        ).execute()
                        log.info(f"Replied: {reply_text}")
                    except Exception as e:
                        log.error(f"Failed to reply to comment {comment_id}: {e}")
                
    except Exception as e:
        log.error(f"Auto-reply failed: {e}")

if __name__ == "__main__":
    run()
