"""
utils/categorise.py — Pure-Python category inference for YouTube titles.

Extracted so it can be unit-tested without pulling in the google-api
client stack that `youtube_analytics.py` requires at import time.

`infer_category_from_title()` maps a YouTube Short title (or any short
text) back to one of the coarse buckets the rest of the pipeline knows:
ai, technology, business, politics, world, health, science, environment,
security, sports, entertainment. Returns None when there's no signal.
"""
from __future__ import annotations


# Order matters — earlier rules win. Place sharper signals (named
# entities, tickers, fully-spelled phrases) before generic words.
# Tweak conservatively: changing the bucket for an existing keyword
# changes how fetch_news.py biases story selection on the next run.
_RULES: list[tuple[str, tuple[str, ...]]] = [
    # Hard-specific entities first so "ransomware attack on hospital"
    # routes to security, not health.
    ("security",      ("ransomware", "cve-", "exploit", "zero-day", "phishing",
                        "malware", "spyware", "data breach", "cyberattack")),
    ("ai",            ("artificial intelligence", "machine learning", "llm",
                        "claude", "anthropic", "openai", "gpt-", "gpt ")),
    ("technology",    ("iphone", "android", "ipad", "macbook", "chip ", "gpu",
                        "laptop", "samsung", "microsoft", "google ", "apple ",
                        "meta ", "tesla")),
    # Geopolitics — explicit country / region names beat generic politics.
    ("world",         ("ukraine", "russia", "gaza", "israel", "china", "iran",
                        "north korea", "south korea", "europe", "asia",
                        "africa", "nato", "un ", "united nations")),
    ("politics",      ("election", "senate", "president", "congress", "biden",
                        "trump", "white house", "vote", "policy", "parliament",
                        "prime minister")),
    ("business",      ("market", "stock", "fed", "inflation", "interest rate",
                        "earnings", "ceo", "ipo", "trading", "wall street",
                        "nasdaq", "s&p")),
    ("health",        ("covid", "vaccine", "disease", "hospital", "medicine",
                        "outbreak", "cancer", "mental health")),
    ("science",       ("nasa", "space", "rocket", "planet", "study", "research",
                        "telescope", "discovery", "physics")),
    ("environment",   ("climate", "emission", "warming", "carbon", "renewable",
                        "solar", "wind farm", "biodiversity")),
    ("sports",        ("nfl", "nba", "fifa", "olympic", "playoff", "championship",
                        "world cup", "uefa")),
    ("entertainment", ("movie", "film", "concert", "celebrity", "netflix",
                        "spotify", "grammy", "oscar")),
]


def infer_category_from_title(title: str | None) -> str | None:
    """Map a title (or any short text) to a category bucket. None if no signal."""
    if not title:
        return None
    t = title.lower()
    for cat, kws in _RULES:
        if any(k in t for k in kws):
            return cat
    return None
