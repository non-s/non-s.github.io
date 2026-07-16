#!/usr/bin/env python3
"""
Newsjacking Radar (Trend Hijacker)
Fetches Google News RSS for "wildlife discovery" or "animal news".
Uses Gemini to filter for viral-worthy breaking news, and injects it into the story queue!
"""

import json
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from utils.ai_helper import ai_text

QUEUE_FILE = ROOT / "_data" / "stories_queue.json"
HISTORY_FILE = ROOT / "_data" / "newsjacking_history.json"

RSS_URL = "https://news.google.com/rss/search?q=wildlife+discovery+OR+rare+animal+OR+new+species&hl=en-US&gl=US&ceid=US:en"

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

def fetch_news() -> list[dict]:
    req = urllib.request.Request(RSS_URL, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            xml_data = response.read()
    except Exception as e:
        print(f"Failed to fetch News RSS: {e}")
        return []

    root = ET.fromstring(xml_data)
    items = []
    for item in root.findall('./channel/item'):
        title = item.find('title')
        pubDate = item.find('pubDate')
        link = item.find('link')
        if title is not None and pubDate is not None and link is not None:
            items.append({
                "title": title.text,
                "pubDate": pubDate.text,
                "link": link.text
            })
    return items

def evaluate_news_virality(title: str) -> dict:
    prompt = (
        f"You are a YouTube Shorts viral strategist. Evaluate this news headline for a wildlife/animal channel:\n"
        f"Headline: '{title}'\n\n"
        "If this is boring or highly local news (like a local zoo event, or political animal news), reject it.\n"
        "If it is a mind-blowing discovery, a rare animal sighting, a scary encounter, or extremely fascinating, approve it.\n"
        "Respond in pure JSON format: {\"approved\": true/false, \"topic\": \"A 3-word engaging topic for the video based on the news\"}"
    )
    
    try:
        response = ai_text(prompt, task="news_evaluation")
        
        # Cleanup markdown fences if present
        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
            
        return json.loads(response.strip())
    except Exception as e:
        print(f"AI evaluation failed: {e}")
        return {"approved": False, "topic": ""}

def inject_to_queue(topic: str):
    queue = []
    if QUEUE_FILE.exists():
        with open(QUEUE_FILE, "r", encoding="utf-8") as f:
            queue = json.load(f)
            
    # Check if already in queue
    for q in queue:
        if q.get("theme") == topic or q.get("query") == topic:
            return
            
    # Insert at the very top of the queue for priority (Newsjacking)
    new_entry = {
        "theme": topic,
        "query": topic,
        "priority": "BREAKING_NEWS",
        "added_at": datetime.now(timezone.utc).isoformat()
    }
    queue.insert(0, new_entry)
    
    QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(queue, f, indent=2)
    print(f"🚀 INJECTED TO TOP OF QUEUE: {topic}")

def main():
    print("🌍 Initiating Newsjacking Radar...")
    history = load_history()
    news_items = fetch_news()
    
    for item in news_items:
        # Simple ID is the title since it's an RSS search
        news_id = item["title"]
        if news_id in history:
            continue
            
        print(f"Evaluating: {item['title']}")
        eval_result = evaluate_news_virality(item['title'])
        
        if eval_result.get("approved"):
            topic = eval_result.get("topic")
            print(f"✅ VIRAL WORTHY! Topic: {topic}")
            inject_to_queue(topic)
            
        history.add(news_id)
        save_history(history)
        
        # Only process a few to save API quota
        if len(history) % 5 == 0:
            break

    print("✅ Newsjacking Radar complete.")

if __name__ == "__main__":
    main()
