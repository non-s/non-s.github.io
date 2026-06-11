"""Free signal normalization for Wild Brief topic discovery."""

from __future__ import annotations

import csv
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

NATURE_TERMS = {
    "animal",
    "animals",
    "ocean",
    "plant",
    "plants",
    "fungi",
    "mushroom",
    "forest",
    "weather",
    "storm",
    "volcano",
    "earth",
    "geology",
    "reef",
    "coral",
    "river",
    "glacier",
    "wildlife",
    "conservation",
    "science",
}


def _clean(value: object) -> str:
    return " ".join(str(value or "").split())


def _topic_key(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _clean(value).lower()).strip()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_google_trends_snapshots(path: Path) -> list[dict]:
    """Load operator-dropped Trends CSV/JSON snapshots from a file or folder."""
    paths = [path] if path.is_file() else sorted(path.glob("*")) if path.exists() else []
    rows: list[dict] = []
    for item in paths:
        if item.suffix.lower() == ".csv":
            with item.open(encoding="utf-8", newline="") as handle:
                for row in csv.DictReader(handle):
                    topic = row.get("topic") or row.get("query") or row.get("search term") or row.get("title")
                    if topic:
                        rows.append(
                            {
                                "source": "google_trends_snapshot",
                                "topic": _clean(topic),
                                "score": row.get("score") or row.get("value") or row.get("interest") or 50,
                                "observed_at": row.get("date") or row.get("observed_at") or _now(),
                                "url": row.get("url") or "",
                            }
                        )
        elif item.suffix.lower() == ".json":
            try:
                data = json.loads(item.read_text(encoding="utf-8"))
            except Exception:
                continue
            entries = data if isinstance(data, list) else data.get("items") if isinstance(data, dict) else []
            for row in entries or []:
                if isinstance(row, dict) and (row.get("topic") or row.get("title")):
                    rows.append(
                        {
                            "source": row.get("source") or "google_trends_snapshot",
                            "topic": _clean(row.get("topic") or row.get("title")),
                            "score": row.get("score") or row.get("interest") or 50,
                            "observed_at": row.get("observed_at") or _now(),
                            "url": row.get("url") or "",
                        }
                    )
    return rows


def normalize_rss_items(source: str, payload: str) -> list[dict]:
    """Normalize RSS/Atom XML into trend rows. Invalid XML returns [] safely."""
    try:
        root = ET.fromstring(payload)
    except Exception:
        return []
    rows: list[dict] = []
    for item in root.findall(".//item") + root.findall(".//{http://www.w3.org/2005/Atom}entry"):
        title_node = item.find("title") or item.find("{http://www.w3.org/2005/Atom}title")
        link_node = item.find("link") or item.find("{http://www.w3.org/2005/Atom}link")
        title = _clean(title_node.text if title_node is not None else "")
        if not title:
            continue
        link = ""
        if link_node is not None:
            link = link_node.attrib.get("href") or _clean(link_node.text)
        rows.append(
            {
                "source": source,
                "topic": title,
                "score": score_topic_candidate({"topic": title, "source": source}),
                "observed_at": _now(),
                "url": link,
            }
        )
    return rows


def score_topic_candidate(item: dict) -> float:
    """Score candidate fit for nature-science Shorts without external calls."""
    text = _topic_key(" ".join(str(item.get(k) or "") for k in ("topic", "title", "summary", "source")))
    words = set(text.split())
    score = 35.0
    if words & NATURE_TERMS:
        score += 28
    if any(word in text for word in ("video", "caught", "first", "rare", "mystery", "why", "how")):
        score += 12
    if any(word in text for word in ("celebrity", "stock", "crypto", "politics", "war")):
        score -= 18
    if len(words) <= 3:
        score -= 8
    return max(0.0, min(100.0, round(score, 2)))


def build_topic_candidates(rows: list[dict]) -> list[dict]:
    """Merge duplicate external signal rows into topic candidates."""
    grouped: dict[str, dict] = {}
    for row in rows:
        topic = _clean(row.get("topic"))
        key = _topic_key(topic)
        if not key:
            continue
        score = float(row.get("score") or score_topic_candidate(row))
        current = grouped.setdefault(
            key,
            {
                "topic": topic,
                "score": 0.0,
                "sources": [],
                "urls": [],
                "observed_at": row.get("observed_at") or _now(),
                "latest_observed_at": row.get("observed_at") or _now(),
                "signal_count": 0,
            },
        )
        current["score"] = max(float(current["score"]), score)
        current["signal_count"] = int(current.get("signal_count", 0) or 0) + 1
        observed_at = _clean(row.get("observed_at")) or _now()
        if observed_at > str(current.get("latest_observed_at") or ""):
            current["latest_observed_at"] = observed_at
        source = _clean(row.get("source"))
        if source and source not in current["sources"]:
            current["sources"].append(source)
        url = _clean(row.get("url"))
        if url and url not in current["urls"]:
            current["urls"].append(url)
    candidates = list(grouped.values())
    for item in candidates:
        item["score"] = round(float(item["score"]) + min(12, len(item["sources"]) * 3), 2)
        item["freshness_score"] = item["score"]
        item["signal_window"] = "fresh" if int(item.get("signal_count", 0) or 0) >= 2 else "single_signal"
    return sorted(candidates, key=lambda row: row["score"], reverse=True)
