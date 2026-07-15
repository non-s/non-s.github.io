#!/usr/bin/env python3
"""Sync free cinematic music from Jamendo API."""
import os
import sys
import json
import random
import logging
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("jamendo_sync")

CLIENT_ID = "04ff30b1"
BGM_DIR = ROOT / "_assets" / "audio" / "bgm"
MAX_TRACKS = 10

def main():
    BGM_DIR.mkdir(parents=True, exist_ok=True)
    
    # Clean up old tracks to rotate library
    existing_files = list(BGM_DIR.glob("jamendo_*.mp3"))
    if len(existing_files) >= MAX_TRACKS:
        # Delete random old files to make room for 2 new ones
        random.shuffle(existing_files)
        for f in existing_files[:2]:
            f.unlink()
            log.info(f"Removed old track {f.name} to rotate library.")
            
    # Search for cinematic, ambient, epic, nature, or documentary
    tags = random.choice(["cinematic", "ambient", "documentary", "epic", "nature"])
    url = f"https://api.jamendo.com/v3.0/tracks/?client_id={CLIENT_ID}&format=json&limit=5&tags={tags}&order=popularity_week&audioformat=mp32"
    
    log.info(f"Querying Jamendo API for tag: {tags}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "WildBrief-Bot/3.0"})
        resp = urllib.request.urlopen(req, timeout=15).read().decode()
        data = json.loads(resp)
        results = data.get("results", [])
        
        if not results:
            log.warning("No results from Jamendo.")
            return

        for track in results:
            track_id = track.get("id")
            dl_url = track.get("audiodownload")
            
            if not track_id or not dl_url:
                continue
                
            dest = BGM_DIR / f"jamendo_{track_id}.mp3"
            if dest.exists():
                continue
                
            log.info(f"Downloading track {track_id}: {track.get('name')} by {track.get('artist_name')}...")
            dl_req = urllib.request.Request(dl_url, headers={"User-Agent": "WildBrief-Bot/3.0"})
            audio_data = urllib.request.urlopen(dl_req, timeout=30).read()
            
            with open(dest, "wb") as f:
                f.write(audio_data)
            
            log.info(f"Saved {dest.name} ({len(audio_data) // 1024} KB)")
            break # Just download 1 per run to not overload
            
    except Exception as e:
        log.error(f"Failed to sync Jamendo music: {e}")

if __name__ == "__main__":
    main()
