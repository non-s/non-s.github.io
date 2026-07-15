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
    
    existing_files = list(BGM_DIR.glob("jamendo_*.mp3"))
    if len(existing_files) >= MAX_TRACKS:
        random.shuffle(existing_files)
        for f in existing_files[:2]:
            f.unlink()
            log.info(f"Removed old track {f.name} to rotate library.")
            
    # Download a relaxing/cinematic track using yt-dlp
    import subprocess
    queries = [
        "ytsearch1:No Copyright Background Music Cinematic Documentary",
        "ytsearch1:No Copyright Relaxing Nature Background Music",
        "ytsearch1:No Copyright Deep Ocean Ambient Music"
    ]
    query = random.choice(queries)
    log.info(f"Downloading BGM using yt-dlp query: {query}")
    
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "-x", "--audio-format", "mp3",
        "--audio-quality", "5",
        "-o", str(BGM_DIR / "jamendo_%(id)s.%(ext)s"),
        query
    ]
    
    try:
        subprocess.run(cmd, check=True)
        log.info("BGM synced successfully via yt-dlp.")
    except Exception as e:
        log.error(f"Failed to sync BGM: {e}")

if __name__ == "__main__":
    main()
