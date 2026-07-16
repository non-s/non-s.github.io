#!/usr/bin/env python3
"""
Competitor Spy: Reverse Engineer psychological hooks from giant channels.
Reads RSS feeds from top channels, uses Gemini to analyze why they went viral,
and extracts the psychological hook formula into _data/hook_formulas.json.
"""

import os
import json
import random
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from utils.ai_helper import ai_text

# Target Giant Channels
TARGET_CHANNELS = {
    "Nat Geo WILD": "UC7Pq3Ko42YpkCB_Q4E981jw",
    "BBC Earth": "UCwmZiChSryoWQCZMIQezgTg",
    "Brave Wilderness": "UC6E2mP01ZLH_kbAyeazCNdg",
    "Casual Geographic": "UC5Yo88QF-chdugJbAnB2tUw",
}

HISTORY_FILE = ROOT / "_data" / "spy_history.json"
HOOKS_FILE = ROOT / "_data" / "hook_formulas.json"

def load_json(path: Path) -> list:
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def fetch_latest_videos(channel_id: str) -> list[dict]:
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            xml_data = response.read()
    except Exception as e:
        print(f"Failed to fetch RSS for {channel_id}: {e}")
        return []

    root = ET.fromstring(xml_data)
    ns = {'yt': 'http://www.youtube.com/xml/schemas/2015', 'atom': 'http://www.w3.org/2005/Atom'}
    
    videos = []
    for entry in root.findall('atom:entry', ns):
        video_id = entry.find('yt:videoId', ns)
        title = entry.find('atom:title', ns)
        published = entry.find('atom:published', ns)
        
        if video_id is not None and title is not None:
            videos.append({
                "video_id": video_id.text,
                "title": title.text,
                "published": published.text
            })
    return videos

def extract_hook_formula(title: str, channel_name: str) -> str:
    prompt = (
        f"You are a psychological analyst for YouTube viral content.\n"
        f"A massive channel '{channel_name}' just posted a video titled: '{title}'.\n\n"
        "Reverse engineer the psychological hook formula they used. "
        "What makes this title irresistible? Extract the abstract formula.\n"
        "Example Formula: 'The [Adjective] [Animal] that can [Impossible Action]'.\n\n"
        "Respond ONLY with the abstract formula and a 1 sentence explanation of why it works."
    )
    
    try:
        response = ai_text(prompt, task="competitor_spy")
        return response.strip()
    except Exception as e:
        print(f"AI spy failed: {e}")
        return ""

def main():
    print("🕵️‍♂️ Initiating Competitor Spy...")
    history = set(load_json(HISTORY_FILE))
    hooks = load_json(HOOKS_FILE)
    
    new_hooks_found = 0
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=2) # Only look at videos from last 48h
    
    for name, channel_id in TARGET_CHANNELS.items():
        print(f"Spying on {name}...")
        videos = fetch_latest_videos(channel_id)
        
        for video in videos:
            vid_id = video["video_id"]
            if vid_id in history:
                continue
                
            try:
                pub_date_str = video["published"].replace('Z', '+00:00')
                pub_date = datetime.fromisoformat(pub_date_str)
            except Exception:
                continue
                
            if pub_date >= cutoff:
                print(f"Analyzing viral DNA of: {video['title']}")
                formula = extract_hook_formula(video["title"], name)
                if formula:
                    hooks.append({
                        "channel": name,
                        "title": video["title"],
                        "formula": formula,
                        "discovered_at": now.isoformat()
                    })
                    new_hooks_found += 1
                history.add(vid_id)
            else:
                break
                
    if new_hooks_found > 0:
        save_json(HOOKS_FILE, hooks)
        save_json(HISTORY_FILE, list(history))
        print(f"✅ Extracted {new_hooks_found} new viral hook formulas!")
    else:
        print("✅ Spy complete. No new viral DNA extracted today.")

if __name__ == "__main__":
    main()
