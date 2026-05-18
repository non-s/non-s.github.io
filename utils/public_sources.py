"""
utils/public_sources.py — Trending discovery from public APIs (no keys required).

Pulls headline-grade items from:
  - Reddit (sub-specific JSON; no auth)
  - Hacker News (Firebase API; no auth)
  - Wikipedia Current Events Portal (parsed from the dated subpage)
  - Google Trends RSS daily feed (no auth)
  - GDELT Project DOC API (no auth, optional)

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


# ── Google Trends — daily search trends RSS ──────────────────────
#
# Google Trends publishes a per-region RSS of the top daily searches.
# No auth, no key. The titles are not news stories themselves but they
# are the keywords most people are Googling RIGHT NOW — which is exactly
# what our hooks should be tuned to.
#
# Returns items in the same normalised shape as the other sources so
# fetch_news.py can mix them into the queue. The `link` field points to
# the related-news article Google attaches to each trending topic, so
# clicking through yields a real news URL.

_TRENDS_REGIONS = (
    # (geo, source_label, category_hint)
    ("US", "Google Trends US",    "world"),
    ("GB", "Google Trends UK",    "world"),
    ("IN", "Google Trends India", "world"),
    ("BR", "Google Trends Brazil","world"),
    ("JP", "Google Trends Japan", "world"),
)
_TRENDS_URL = "https://trends.google.com/trends/trendingsearches/daily/rss?geo={geo}"


def fetch_google_trends(per_region: int = 5) -> list[dict]:
    """Pull the daily Google Trends RSS per region. Free, no key.

    The RSS embeds related news links under each trending search term.
    We surface those as proper news entries (one per term, attached to
    the first related article), so the AI ranker can score them like
    any other story.
    """
    out: list[dict] = []
    s = _session()
    for geo, source_label, category in _TRENDS_REGIONS:
        url = _TRENDS_URL.format(geo=geo)
        try:
            r = s.get(url, timeout=_TIMEOUT, headers={"Accept": "application/rss+xml"})
            if r.status_code != 200:
                log.debug("google trends %s → %d", geo, r.status_code)
                continue
            xml = r.text
        except Exception as e:
            log.debug("google trends %s error: %s", geo, e)
            continue

        # Coarse parse — keep the dependency footprint small. Trends RSS
        # follows a stable shape we can pattern-match without lxml.
        items = re.findall(r"<item>(.*?)</item>", xml, re.DOTALL)
        kept_this_region = 0
        for item_xml in items:
            title_m = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", item_xml, re.DOTALL)
            if not title_m:
                continue
            term = title_m.group(1).strip()
            if not term or len(term) < 3:
                continue
            traffic_m = re.search(r"<ht:approx_traffic>(.+?)</ht:approx_traffic>", item_xml)
            traffic = traffic_m.group(1).strip() if traffic_m else ""
            news_url_m = re.search(r"<ht:news_item_url>(.+?)</ht:news_item_url>", item_xml, re.DOTALL)
            news_title_m = re.search(
                r"<ht:news_item_title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</ht:news_item_title>",
                item_xml, re.DOTALL,
            )
            news_snippet_m = re.search(
                r"<ht:news_item_snippet>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</ht:news_item_snippet>",
                item_xml, re.DOTALL,
            )
            news_picture_m = re.search(r"<ht:news_item_picture>(.+?)</ht:news_item_picture>", item_xml)
            news_url = (news_url_m.group(1).strip() if news_url_m else "")
            news_title = (news_title_m.group(1).strip() if news_title_m else term)
            snippet = (news_snippet_m.group(1).strip() if news_snippet_m else "")
            picture = (news_picture_m.group(1).strip() if news_picture_m else "")

            if not news_url or not news_url.startswith(("http://", "https://")):
                continue

            description = (snippet or news_title or term)[:400]
            if traffic:
                description = f"[Trending {traffic}] {description}"

            out.append({
                "title":       news_title[:240],
                "link":        news_url,
                "description": description,
                "image":       picture,
                "published":   datetime.now(timezone.utc),
                "source":      source_label,
                "category":    category,
                "tags":        ["trending", "google-trends", f"geo-{geo.lower()}"],
                # Keep the trending term separately so the ranker can
                # bias toward it without polluting the title.
                "trending_term": term,
                "trending_traffic": traffic,
            })
            kept_this_region += 1
            if kept_this_region >= per_region:
                break
    return out


def trending_keywords(items: list[dict] | None = None) -> set[str]:
    """Extract a lowercase set of trending phrases from Google Trends items.

    Used by `fetch_news.py` to boost RSS stories whose title mentions
    something currently trending. Falls back to fetching trends fresh
    if `items` is None.
    """
    if items is None:
        items = fetch_google_trends(per_region=8)
    out: set[str] = set()
    for it in items:
        term = (it.get("trending_term") or "").lower().strip()
        if 3 <= len(term) <= 60:
            out.add(term)
        # Also index individual significant tokens so headlines that
        # mention just one word ("Powell" vs "Jerome Powell") still match.
        for tok in re.findall(r"[A-Za-z][A-Za-z\-']{2,}", term):
            if len(tok) >= 4 and tok.lower() not in {"news", "update", "latest", "today", "live"}:
                out.add(tok.lower())
    return out


# ── GDELT Project DOC API ────────────────────────────────────────
#
# GDELT indexes news from ~thousands of outlets worldwide and exposes
# a free DOC search API at https://api.gdeltproject.org/api/v2/doc/doc
# No auth, no key. We pull a small high-tone, high-volume slice of
# the last hour as a fallback when RSS feeds are quiet.

_GDELT_API = "https://api.gdeltproject.org/api/v2/doc/doc"


def fetch_gdelt_recent(themes: tuple[str, ...] = ("WB_2433_CONFLICT_AND_VIOLENCE", "ECON_STOCKMARKET", "TAX_FNCACT_TECH"),
                       limit: int = 15) -> list[dict]:
    """
    Best-effort pull of recent high-impact news from GDELT's DOC API.
    Each theme returns a few articles; deduped by URL on aggregation.
    """
    out: list[dict] = []
    s = _session()
    for theme in themes:
        try:
            r = s.get(
                _GDELT_API,
                params={
                    "query": f"theme:{theme} sourcelang:eng",
                    "mode": "ArtList",
                    "format": "json",
                    "maxrecords": str(limit),
                    "sort": "DateDesc",
                    "timespan": "1h",
                },
                timeout=_TIMEOUT,
                headers={"Accept": "application/json"},
            )
            if r.status_code != 200:
                log.debug("gdelt %s → %d", theme, r.status_code)
                continue
            data = r.json()
        except Exception as e:
            log.debug("gdelt %s error: %s", theme, e)
            continue

        # Map themes to coarse categories the rest of the pipeline knows.
        cat = {
            "WB_2433_CONFLICT_AND_VIOLENCE": "world",
            "ECON_STOCKMARKET":              "business",
            "TAX_FNCACT_TECH":               "technology",
        }.get(theme, "world")

        for art in data.get("articles", []) or []:
            link = (art.get("url") or "").strip()
            if not link or not link.startswith(("http://", "https://")):
                continue
            title = (art.get("title") or "").strip()
            if len(title) < 25:
                continue
            try:
                pub = datetime.strptime(art.get("seendate", ""), "%Y%m%dT%H%M%SZ")
                pub = pub.replace(tzinfo=timezone.utc)
            except Exception:
                pub = datetime.now(timezone.utc)
            out.append({
                "title":       title[:240],
                "link":        link,
                "description": title[:400],
                "image":       (art.get("socialimage") or "").strip(),
                "published":   pub,
                "source":      art.get("domain", "GDELT"),
                "category":    cat,
                "tags":        ["gdelt", cat, theme.lower()],
            })
    return out


# ── Unified entry point ──────────────────────────────────────────

def fetch_all_public_sources(include_trends: bool = True, include_gdelt: bool = True) -> list[dict]:
    """Aggregate all keyless sources, dropping internal dupes by link.

    `include_trends` / `include_gdelt` let callers opt out of the slower
    networks when on a tight wall-clock budget.
    """
    seen: set[str] = set()
    merged: list[dict] = []
    batches: list[list[dict]] = [
        fetch_reddit_trending(),
        fetch_hackernews_top(),
        fetch_wikipedia_current_events(),
    ]
    if include_trends:
        batches.append(fetch_google_trends())
    if include_gdelt:
        batches.append(fetch_gdelt_recent())

    for batch in batches:
        for it in batch:
            key = (it.get("link") or "").rstrip("/").lower()
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(it)
    return merged
