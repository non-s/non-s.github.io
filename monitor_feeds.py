#!/usr/bin/env python3
"""
monitor_feeds.py
Checks all RSS feeds used by fetch_news.py for health (HTTP status, response time).
Generates _data/feed_health.json with results.
"""
import json, logging, sys, time
from datetime import datetime, timezone
from pathlib import Path
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("feed_monitor.log", encoding="utf-8"), logging.StreamHandler(sys.stdout)])
log = logging.getLogger(__name__)

DATA_DIR = Path("_data")

# All feeds from fetch_news.py — keep in sync
FEEDS = [
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://feeds.bbci.co.uk/news/technology/rss.xml",
    "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
    "https://feeds.bbci.co.uk/news/health/rss.xml",
    "https://feeds.bbci.co.uk/news/business/rss.xml",
    "https://rss.cnn.com/rss/edition_world.rss",
    "https://feeds.reuters.com/reuters/topNews",
    "https://feeds.npr.org/1001/rss.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    "https://feeds.theguardian.com/theguardian/world/rss",
    "https://www.aljazeera.com/xml/rss/all.xml",
    "https://techcrunch.com/feed/",
    "https://www.wired.com/feed/rss",
    "https://www.theverge.com/rss/index.xml",
    "https://feeds.arstechnica.com/arstechnica/index",
    "https://www.sciencedaily.com/rss/all.xml",
    "https://www.nasa.gov/rss/dyn/breaking_news.rss",
]

def check_feed(url: str) -> dict:
    start = time.time()
    try:
        resp = requests.head(url, timeout=10, allow_redirects=True,
            headers={"User-Agent": "GlobalBRNews-Monitor/1.0"})
        elapsed = round(time.time() - start, 2)
        ok = resp.status_code < 400
        return {
            "url": url, "status": resp.status_code,
            "ok": ok, "latency_s": elapsed,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        elapsed = round(time.time() - start, 2)
        return {
            "url": url, "status": 0, "ok": False,
            "latency_s": elapsed, "error": str(e)[:100],
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

def main():
    log.info("Checking %d feeds...", len(FEEDS))
    results = []
    dead = []
    slow = []

    for url in FEEDS:
        r = check_feed(url)
        results.append(r)
        status = "OK" if r["ok"] else "DEAD"
        log.info("%s %s — HTTP %s (%ss)", status, url[:60], r["status"], r["latency_s"])
        if not r["ok"]:
            dead.append(url)
        elif r["latency_s"] > 5:
            slow.append(url)

    DATA_DIR.mkdir(exist_ok=True)
    DATA_DIR.joinpath("feed_health.json").write_text(
        json.dumps({"checked_at": datetime.now(timezone.utc).isoformat(),
                    "total": len(FEEDS), "healthy": len(results) - len(dead),
                    "dead": dead, "slow": slow, "feeds": results}, indent=2),
        encoding="utf-8"
    )
    log.info("Feed health saved to _data/feed_health.json")
    log.info("Summary: %d healthy, %d dead, %d slow", len(FEEDS)-len(dead), len(dead), len(slow))

    if dead:
        log.warning("Dead feeds: %s", dead)

if __name__ == "__main__":
    main()
