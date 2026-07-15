#!/usr/bin/env python3
"""
Sniper Radar: Monitor major YouTube competitor channels and generate highly-viral comments.
Using YouTube RSS feeds (0 API quota) and Gemini 1.5 to craft "Top Comment" candidates.
"""

import os
import json
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from utils.ai_helper import ai_text

# Top Animal / Nature Channels for the Sniper Radar
TARGET_CHANNELS = {
    "Nat Geo WILD": "UC7Pq3Ko42YpkCB_Q4E981jw",
    "Animal Planet": "UCkEBDbzLyH-LbB2BgNxWPFA",
    "Brave Wilderness": "UC6E2mP01ZLH_kbAyeazCNdg",
    "BBC Earth": "UCwmZiChSryoWQCZMIQezgTg",
    "Casual Geographic": "UC5Yo88QF-chdugJbAnB2tUw",
}

HISTORY_FILE = ROOT / "_data" / "sniper_history.json"
OPPORTUNITIES_FILE = ROOT / "sniper_opportunities.md"

def load_history() -> set:
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def save_history(history: set):
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(list(history), f, indent=2)

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
        link = entry.find('atom:link', ns)
        
        if video_id is not None and title is not None and published is not None:
            href = link.attrib.get("href", "") if link is not None else ""
            videos.append({
                "video_id": video_id.text,
                "title": title.text,
                "published": published.text,
                "url": href
            })
    return videos

def generate_sniper_comments(channel_name: str, video_title: str) -> str:
    print(f"Generating sniper comments for: [{channel_name}] {video_title}...")
    prompt = (
        f"You are a master of YouTube growth hacking. A giant channel named '{channel_name}' "
        f"just uploaded a video titled: '{video_title}'.\n\n"
        "Your mission is to write 3 short, extremely viral, and engaging English comments to be posted on this video.\n"
        "The goal of these comments is to get thousands of likes (Top Comment) so that people click our profile (we run an animal facts channel).\n\n"
        "Rules:\n"
        "1. Write in plain, casual, and highly engaging native English.\n"
        "2. Comment 1 should be a mind-blowing addition or scientific curiosity related to the title.\n"
        "3. Comment 2 should be a funny, relatable joke about the animal/subject.\n"
        "4. Comment 3 should be a slightly controversial or debate-sparking question to drive replies.\n"
        "5. Do NOT mention our channel name or beg for subs. We want organic profile clicks out of sheer curiosity.\n"
        "6. Format the output cleanly with numbers and emojis."
    )
    
    try:
        response = ai_text(prompt, task="sniper_comments", timeout=45)
        return response.strip()
    except Exception as e:
        print(f"AI generation failed: {e}")
        return ""

def main():
    print("🎯 Initiating Sniper Radar...")
    history = load_history()
    new_opportunities = []
    
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=1)
    
    for name, channel_id in TARGET_CHANNELS.items():
        print(f"Scanning {name}...")
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
                comments = generate_sniper_comments(name, video["title"])
                if comments:
                    new_opportunities.append({
                        "channel": name,
                        "title": video["title"],
                        "url": video["url"],
                        "comments": comments
                    })
                    history.add(vid_id)
                    save_history(history)
            else:
                break

    if not new_opportunities:
        print("✅ Radar complete. No new giant videos in the last 24h.")
        return

    print(f"🔥 Found {len(new_opportunities)} new sniping opportunities!")
    with open(OPPORTUNITIES_FILE, "a", encoding="utf-8") as f:
        for opp in new_opportunities:
            f.write(f"## 🎯 Alvo: {opp['channel']} - {opp['title']}\n")
            f.write(f"🔗 **Link:** {opp['url']}\n\n")
            f.write(f"### Sugestões de Comentários (Escolha uma e copie):\n")
            f.write(f"{opp['comments']}\n\n")
            f.write("---\n\n")
            
    print(f"📝 Sugestões salvas no arquivo: {OPPORTUNITIES_FILE}")

if __name__ == "__main__":
    main()
