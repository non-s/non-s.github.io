#!/usr/bin/env python3
"""Sync copyright-free gameplay videos for split-screen overstimulation."""
import os
import sys
import json
import random
import logging
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("gameplay_sync")

GAMEPLAY_DIR = ROOT / "_assets" / "video" / "gameplay"
MAX_VIDEOS = 3

def main():
    GAMEPLAY_DIR.mkdir(parents=True, exist_ok=True)
    
    existing_files = list(GAMEPLAY_DIR.glob("*.mp4"))
    if len(existing_files) >= MAX_VIDEOS:
        log.info(f"Gameplay library already has {len(existing_files)} videos. Skipping sync.")
        return
        
    queries = [
        "ytsearch1:Minecraft Parkour Gameplay No Copyright background",
        "ytsearch1:GTA V Mega Ramp No Copyright background",
        "ytsearch1:Satisfying Kinetic Sand No Copyright"
    ]
    target_url = random.choice(queries)
    log.info(f"Downloading gameplay video using query: {target_url}...")
    
    # Use yt-dlp to download 720p/1080p mp4
    cmd = [
        "yt-dlp",
        "-f", "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4][height<=1080]",
        "-o", str(GAMEPLAY_DIR / "%(id)s.%(ext)s"),
        "--no-playlist",
        target_url
    ]
    
    try:
        subprocess.run(cmd, check=True)
        log.info("Gameplay video downloaded successfully.")
    except subprocess.CalledProcessError as e:
        log.error(f"Failed to download gameplay video: {e}")

if __name__ == "__main__":
    main()
