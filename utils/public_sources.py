"""
utils/public_sources.py — Trending discovery from public APIs (no keys required).

Pulls headline-grade items from:
  - Reddit (sub-specific JSON; no auth)
  - Hacker News (Firebase API; no auth)
  - Wikipedia Current Events Portal (parsed from the dated subpage)

Each function returns a list of normalised dicts compatible with
fetch_news.py's downstream pipeline:

    {
        "title":       str,
        "link":        str,    # canonical external URL
        "description": str,
        "image":       str,    # may be empty
        "published":   datetime (UTC, aware),
        "source":      str,
        "category":    str,
        "tags":        list[str],
    }

Functions are defensive: any single network error returns an empty list
rather than raising — fetch_news.py treats these sources as best-effort.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone, timedelta

import requests

log = logging.getLogger(__name__)

_USER_AGENT = "GlobalBR-News-Bot/4.0 (+https://non-s.github.io)"
_TIMEOUT = 12


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": _USER_AGENT, "Accept": "application/json"})
    return s


# ── Reddit ───────────────────────────────────────────────────────

_REDDIT_SUBS = (
    # sub                     category       tags
    ("worldnews",             "world",       ["reddit", "world"]),
    ("politics",              "politics",    ["reddit", "us-politics"]),
    ("technology",            "technology",  ["reddit", "tech"]),
    ("science",               "science",     ["reddit", "research"]),
    ("space",                 "science",     ["reddit", "space"]),
    ("environment",           "environment", ["reddit", "climate"]),
    ("MachineLearning",       "ai",          ["reddit", "ai", "machine-learning"]),
    ("cybersecurity",         "security",    ["reddit", "infosec"]),
    ("UpliftingNews",         "world",       ["reddit", "good-news"]),
    ("InternationalNews",     "world",       ["reddit", "world"]),
    ("Economics",             "business",    ["reddit", "economy"]),
)


def fetch_reddit_trending(per_sub: int = 5, min_score: int = 200) -> list[dict]:
    """Pull top-of-day links from curated news subs. Reddit JSON is public."""
    out: list[dict] = []
    s = _session()
    for sub, category, tags in _REDDIT_SUBS:
        try:
            r = s.get(
                f"https://www.reddit.com/r/{sub}/top.json?t=day&limit={per_sub}",
                timeout=_TIMEOUT,
            )
            if r.status_code != 200:
                log.debug("reddit r/%s → %d", sub, r.status_code)
                continue
            data = r.json()
        except Exception as e:
            log.debug("reddit r/%s error: %s", sub, e)
            continue

        for child in data.get("data", {}).get("children", []):
            post = child.get("data", {})
            if post.get("over_18") or post.get("stickied"):
                continue
            if (post.get("score") or 0) < min_score:
                continue
            link = post.get("url_overridden_by_dest") or post.get("url") or ""
            # Skip Reddit self-posts; we want external news links.
            if not link or "reddit.com" in link:
                continue
            if not link.startswith(("http://", "https://")):
                continue
            title = (post.get("title") or "").strip()
            if not title:
                continue
            created_ts = post.get("created_utc") or 0
            try:
                pub = datetime.fromtimestamp(float(created_ts), tz=timezone.utc)
            except Exception:
                pub = datetime.now(timezone.utc)
            preview = ""
            try:
                preview = (
                    post.get("preview", {})
                    .get("images", [{}])[0]
                    .get("source", {})
                    .get("url", "")
                )
                preview = preview.replace("&amp;", "&") if preview else ""
            except Exception:
                preview = ""
            out.append({
                "title":       title,
                "link":        link,
                "description": (post.get("selftext") or title)[:400],
                "image":       preview,
                "published":   pub,
                "source":      "Reddit r/" + sub,
                "category":    category,
                "tags":        tags,
            })
    return out


# ── Hacker News ──────────────────────────────────────────────────

def fetch_hackernews_top(limit: int = 25, min_score: int = 100) -> list[dict]:
    """Pull HN front page (no auth). Filter to high-scoring story links."""
    out: list[dict] = []
    s = _session()
    try:
        ids = s.get(
            "https://hacker-news.firebaseio.com/v0/topstories.json",
            timeout=_TIMEOUT,
        ).json()
    except Exception as e:
        log.debug("hn topstories error: %s", e)
        return []

    for hn_id in ids[:limit]:
        try:
            item = s.get(
                f"https://hacker-news.firebaseio.com/v0/item/{hn_id}.json",
                timeout=_TIMEOUT,
            ).json() or {}
        except Exception:
            continue
        if item.get("type") != "story" or item.get("dead") or item.get("deleted"):
            continue
        score = item.get("score") or 0
        if score < min_score:
            continue
        link = item.get("url") or ""
        if not link or not link.startswith(("http://", "https://")):
            continue
        title = (item.get("title") or "").strip()
        if not title:
            continue
        ts = item.get("time") or 0
        try:
            pub = datetime.fromtimestamp(float(ts), tz=timezone.utc)
        except Exception:
            pub = datetime.now(timezone.utc)
        # Crude category guess from title keywords.
        lower = title.lower()
        if any(k in lower for k in ("ai", "ml", "llm", "gpt", "claude", "gemini", "machine learning")):
            cat = "ai"
        elif any(k in lower for k in ("breach", "ransomware", "cve", "exploit", "vulnerab", "hack")):
            cat = "security"
        elif any(k in lower for k in ("startup", "funding", "raises", "yc ", "y combinator")):
            cat = "startups"
        else:
            cat = "technology"
        out.append({
            "title":       title,
            "link":        link,
            "description": title,
            "image":       "",
            "published":   pub,
            "source":      "Hacker News",
            "category":    cat,
            "tags":        ["hackernews", cat],
        })
    return out


# ── Wikipedia Current Events Portal ───────────────────────────────
#
# Wikipedia maintains a curated "Portal:Current_events" with a per-day
# subpage like /wiki/Portal:Current_events/2026_May_15. The summary
# REST API doesn't expose the structured event list, but the parsed
# HTML does. We pull the day's page, extract bullet-pointed events and
# their citation URLs, and emit one item per cited story.

_WIKI_DAY_FMT = "Portal:Current_events/%Y_%B_%-d"
_WIKI_HTML_TIMEOUT = 15


def fetch_wikipedia_current_events(days: int = 1) -> list[dict]:
    out: list[dict] = []
    s = _session()
    today = datetime.now(timezone.utc)
    for delta in range(days):
        day = today - timedelta(days=delta)
        slug = day.strftime(_WIKI_DAY_FMT).replace(" ", "_")
        url = f"https://en.wikipedia.org/api/rest_v1/page/html/{slug}"
        try:
            r = s.get(url, timeout=_WIKI_HTML_TIMEOUT,
                      headers={"Accept": "text/html"})
            if r.status_code != 200:
                continue
            html = r.text
        except Exception as e:
            log.debug("wikipedia current events %s: %s", slug, e)
            continue

        # Extract category header + bullet items + external citations.
        # Wikipedia uses headings like "Armed conflicts and attacks",
        # "Disasters and accidents", "Politics and elections" etc.
        # We do a coarse parse with regex to keep dependencies minimal.
        for m in re.finditer(
            r'<li[^>]*>(.+?)</li>',
            html,
            flags=re.DOTALL,
        ):
            chunk = m.group(1)
            # Find an external citation link (rel="nofollow" anchors).
            ext = re.search(
                r'<a[^>]+rel="[^"]*nofollow[^"]*"[^>]+href="(https?://[^"]+)"',
                chunk,
            )
            if not ext:
                continue
            link = ext.group(1)
            # Strip HTML tags to get a readable title.
            text = re.sub(r'<[^>]+>', '', chunk)
            text = re.sub(r'\s+', ' ', text).strip()
            if len(text) < 40 or len(text) > 320:
                continue
            # Skip items that are clearly meta (refs section, see also).
            if text.lower().startswith(("see ", "main article")):
                continue
            out.append({
                "title":       text[:140].rstrip(),
                "link":        link,
                "description": text[:400],
                "image":       "",
                "published":   day.replace(hour=12, minute=0, second=0, microsecond=0),
                "source":      "Wikipedia Current Events",
                "category":    "world",
                "tags":        ["wikipedia", "current-events"],
            })
    return out


# ── Unified entry point ──────────────────────────────────────────

def fetch_all_public_sources() -> list[dict]:
    """Aggregate all keyless sources, dropping internal dupes by link."""
    seen: set[str] = set()
    merged: list[dict] = []
    for batch in (
        fetch_reddit_trending(),
        fetch_hackernews_top(),
        fetch_wikipedia_current_events(),
    ):
        for it in batch:
            key = (it.get("link") or "").rstrip("/").lower()
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(it)
    return merged
