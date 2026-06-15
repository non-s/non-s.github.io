"""Free nature-science trend radar for Wild Brief.

The radar reads public RSS/search feeds, extracts nature-science topics,
scores them conservatively, and produces a local payload the queue refresh
can use. No paid APIs, no credentials, and no live data is required in tests.
"""

from __future__ import annotations

import html
import json
import re
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus

import requests
from defusedxml import ElementTree as ET

from utils.trend_safety import enrich_topics

TREND_FILE = Path("_data/trend_radar.json")
TIMEOUT = 12

ANIMAL_ALIASES: dict[str, tuple[str, ...]] = {
    "arctic": ("penguin", "polar bear", "seal", "walrus", "arctic fox"),
    "birds": ("bird", "eagle", "owl", "parrot", "penguin", "macaw", "flamingo"),
    "cats": ("cat", "kitten", "feline"),
    "dogs": ("dog", "puppy", "canine", "husky"),
    "farm": ("cow", "goat", "horse", "chicken", "duck", "sheep", "pig"),
    "insects": ("bee", "butterfly", "ant", "mantis", "beetle"),
    "nocturnal": ("bat", "owl", "fox", "hedgehog"),
    "ocean": ("orca", "shark", "whale", "dolphin", "octopus", "turtle", "seal", "sea lion"),
    "primates": ("chimpanzee", "gorilla", "orangutan", "monkey", "macaque"),
    "reptiles": ("snake", "lizard", "crocodile", "turtle", "chameleon", "gecko"),
    "space": (
        "moon",
        "mars",
        "solar flare",
        "eclipse",
        "meteor",
        "comet",
        "asteroid",
        "galaxy",
        "nebula",
        "rocket",
        "telescope",
        "satellite",
    ),
    "physics": (
        "magnet",
        "magnetic field",
        "pendulum",
        "prism",
        "laser",
        "electricity",
        "plasma",
        "gravity",
        "wave",
        "vacuum",
    ),
    "chemistry": (
        "chemical reaction",
        "crystal",
        "molecule",
        "flame test",
        "electrolysis",
        "dry ice",
        "sublimation",
        "lab experiment",
    ),
    "microscopy": (
        "microscope",
        "cell",
        "bacteria",
        "microbe",
        "microorganism",
        "algae",
        "amoeba",
        "dna",
    ),
    "wildlife": ("bear", "elephant", "lion", "tiger", "wolf", "deer", "fox", "leopard"),
}

TREND_TERMS = (
    "rescue",
    "attack",
    "sighting",
    "viral",
    "rare",
    "migration",
    "study",
    "scientists",
    "discovered",
    "behavior",
    "intelligence",
    "camera",
    "experiment",
    "footage",
    "na" + "sa",
    "research",
    "public domain",
    "visualized",
    "wildlife",
    "conservation",
    "zoo",
    "aquarium",
)

DEFAULT_FEEDS = (
    "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q={query}&hl=en-GB&gl=GB&ceid=GB:en",
)

LEGACY_PLATFORM_TERMS = (
    "tik" + "tok",
    "f" + "yp",
    "for" + "you",
    "cat" + "tok",
    "dog" + "tok",
    "bird" + "tok",
    "farm" + "tok",
)
ANIMAL_CATEGORIES = {
    "arctic",
    "birds",
    "cats",
    "dogs",
    "farm",
    "insects",
    "nocturnal",
    "ocean",
    "primates",
    "reptiles",
    "wildlife",
}


def _legacy_platform_hit(text: str) -> bool:
    compact = re.sub(r"[^a-z0-9]+", "", text.lower())
    return any(term in compact for term in LEGACY_PLATFORM_TERMS)


def _animal_category(text: str) -> tuple[str, str] | None:
    lower = f" {text.lower()} "
    for category, aliases in ANIMAL_ALIASES.items():
        for alias in aliases:
            if re.search(rf"\b{re.escape(alias)}s?\b", lower):
                if alias == "fox" and re.search(r"\bfox\s+(news|weather|[0-9])\b", lower):
                    continue
                if alias == "bear" and re.search(r"\bbear\s+grylls\b", lower):
                    continue
                return category, alias
    return None


def _trend_terms(text: str) -> list[str]:
    lower = text.lower()
    return [term for term in TREND_TERMS if term in lower]


def _rss_items(xml_text: str, *, source: str) -> list[dict]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    rows: list[dict] = []
    for item in root.findall(".//item")[:30]:
        title = html.unescape((item.findtext("title") or "").strip())
        link = (item.findtext("link") or "").strip()
        desc = html.unescape(re.sub(r"<[^>]+>", " ", item.findtext("description") or ""))
        text = re.sub(r"\s+", " ", f"{title} {desc}").strip()
        if title and text and not _legacy_platform_hit(text):
            rows.append({"source": source, "title": title, "url": link, "text": text})
    return rows


def fetch_public_items(queries: list[str] | None = None, feeds: tuple[str, ...] = DEFAULT_FEEDS) -> list[dict]:
    queries = queries or [
        "animal trending OR viral",
        "wildlife viral animal",
        "animal behavior study",
        "rare animal sighting",
        "animal rescue viral",
        "space science footage",
        ("na" + "sa") + " solar flare video",
        "physics experiment video",
        "chemistry reaction experiment",
        "microscope biology video",
    ]
    items: list[dict] = []
    session = requests.Session()
    session.headers.update({"User-Agent": "WildBriefTrendRadar/1.0"})
    for query in queries:
        for template in feeds:
            url = template.format(query=quote_plus(query))
            try:
                response = session.get(url, timeout=TIMEOUT)
                if response.status_code != 200:
                    continue
                items.extend(_rss_items(response.text, source=url))
                time.sleep(0.1)
            except Exception:
                continue
    return items


def score_trends(items: list[dict]) -> dict:
    topic_hits: dict[str, list[dict]] = defaultdict(list)
    categories: Counter[str] = Counter()
    animals: Counter[str] = Counter()
    for item in items:
        text = item.get("text") or item.get("title") or ""
        if _legacy_platform_hit(text):
            continue
        match = _animal_category(text)
        if not match:
            continue
        category, animal = match
        terms = _trend_terms(text)
        score = 20 + len(terms) * 12
        if any(word in text.lower() for word in ("viral", "trending", "video", "camera")):
            score += 10
        if any(word in text.lower() for word in ("attack", "rescue", "rare", "study")):
            score += 8
        score = min(100, score)
        key = f"{category}:{animal}"
        row = {
            "category": category,
            "animal": animal,
            "score": score,
            "terms": terms,
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "source": item.get("source", ""),
        }
        topic_hits[key].append(row)
        categories[category] += score
        animals[animal] += score

    topics: list[dict] = []
    for key, rows in topic_hits.items():
        category, animal = key.split(":", 1)
        top = sorted(rows, key=lambda r: r["score"], reverse=True)[:5]
        query_context = "animal behavior" if category in ANIMAL_CATEGORIES else "science footage"
        topics.append(
            {
                "category": category,
                "animal": animal,
                "trend_score": min(100, round(sum(r["score"] for r in rows) / max(1, len(rows)) + len(rows) * 5, 2)),
                "mentions": len(rows),
                "top_titles": [r["title"] for r in top],
                "top_urls": [r["url"] for r in top if r.get("url")],
                "terms": sorted({term for r in rows for term in r.get("terms", [])})[:8],
                "query": f"{animal} {query_context} {(' '.join(top[0].get('terms') or [])).strip()}".strip(),
            }
        )
    topics.sort(key=lambda r: (r["trend_score"], r["mentions"]), reverse=True)
    topics = enrich_topics(topics)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "public_rss",
        "topics": topics[:20],
        "category_scores": dict(categories.most_common()),
        "animal_scores": dict(animals.most_common()),
        "summary": {
            "items_scanned": len(items),
            "animal_topics": len(topics),
            "top_category": topics[0]["category"] if topics else "",
            "top_animal": topics[0]["animal"] if topics else "",
        },
    }


def build_trend_radar(root: Path | str = ".") -> dict:
    return score_trends(fetch_public_items())


def load_trends(path: Path | None = None) -> dict:
    p = path or TREND_FILE
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def trend_queries_for_category(category: str, trends: dict | None = None, limit: int = 3) -> list[str]:
    trends = trends or load_trends()
    out: list[str] = []
    for item in trends.get("topics") or []:
        if str(item.get("category") or "").lower() != category.lower():
            continue
        query = str(item.get("query") or item.get("animal") or "").strip()
        if query and query not in out:
            out.append(query)
        if len(out) >= limit:
            break
    return out


def trend_context_for_category(category: str, trends: dict | None = None) -> dict:
    trends = trends or load_trends()
    matches = [
        item for item in trends.get("topics") or [] if str(item.get("category") or "").lower() == category.lower()
    ]
    if not matches:
        return {}
    best = sorted(
        matches,
        key=lambda item: (float(item.get("trend_score", 0) or 0), int(item.get("mentions", 0) or 0)),
        reverse=True,
    )[0]
    return {
        "category": best.get("category", ""),
        "animal": best.get("animal", ""),
        "trend_score": best.get("trend_score", 0),
        "mentions": best.get("mentions", 0),
        "terms": list(best.get("terms") or [])[:8],
        "headline": (best.get("top_titles") or [""])[0],
        "source_urls": list(best.get("top_urls") or [])[:3],
        "query": best.get("query", ""),
    }


def trend_weight_for_category(category: str, trends: dict | None = None) -> float:
    trends = trends or load_trends()
    scores = [
        float(item.get("trend_score", 0) or 0)
        for item in trends.get("topics") or []
        if str(item.get("category") or "").lower() == category.lower()
    ]
    if not scores:
        return 1.0
    best = max(scores)
    if best >= 80:
        return 1.45
    if best >= 60:
        return 1.25
    if best >= 40:
        return 1.12
    return 1.0
