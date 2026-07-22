"""Global audience helpers for Wild Brief Shorts.

The channel should feel international by default: simple English,
universal nature discovery terms and publish windows spread across
major time zones. This module keeps those choices in one place so the
automation can expand globally without hard-coding one target country.
"""

from __future__ import annotations

from datetime import datetime, timezone

GLOBAL_HASHTAGS = ["Shorts", "NatureFacts", "WildBrief", "EarthScience", "Nature"]

GLOBAL_SEARCH_TAGS = [
    "nature facts",
    "earth science",
    "wildlife",
    "natural phenomena",
    "nature",
    "nature shorts",
    "biology",
    "geology",
    "wild brief",
]


def _region_for_hour(hour: int) -> tuple[str, list[str]]:
    if 0 <= hour <= 3:
        return "Americas evening and late scroll", ["North America", "Latin America"]
    if 4 <= hour <= 8:
        return "Asia/Oceania evening", ["India", "Southeast Asia", "East Asia", "Australia"]
    if 9 <= hour <= 15:
        return "Europe/Africa daytime", ["Europe", "Africa", "Middle East"]
    return "Americas daytime", ["North America", "Latin America"]


def _two_hourly_window(hour: int) -> dict:
    """Return one UTC publishing slot for the every-2-hours Shorts cadence.

    Was a 10-minute grid (144 slots/day); YouTube's own account-level
    upload cap (`uploadLimitExceeded`, independent of this repo's own
    quota guard) started rejecting uploads at that volume combined with
    the mix's cadence, so this is deliberately sparse -- 12 slots/day,
    only even hours -- not literally every hour of the day.
    """
    label, regions = _region_for_hour(hour)
    return {"slot": f"{hour:02d}:00", "utc_hour": hour, "label": label, "regions": regions}


GLOBAL_PUBLISH_WINDOWS = [_two_hourly_window(hour) for hour in range(0, 24, 2)]


def _clean_token(value: str) -> str:
    return "".join(ch for ch in str(value).strip().lstrip("#") if ch.isalnum())


def merge_hashtags(discovery: list[str] | tuple[str, ...] | None, *, limit: int = 6) -> list[str]:
    """Return globally useful hashtags while preserving topic signals."""
    seen: set[str] = set()
    out: list[str] = []
    for tag in [*GLOBAL_HASHTAGS, *(discovery or [])]:
        cleaned = _clean_token(str(tag))
        key = cleaned.lower()
        if not cleaned or key in seen:
            continue
        out.append(cleaned)
        seen.add(key)
        if len(out) >= limit:
            break
    return out


def merge_search_tags(queue_tags: list[str] | tuple[str, ...] | None, category: str) -> list[str]:
    """Blend subject tags with global discovery tags for YouTube search."""
    evergreen = [str(category or "").lower(), f"{str(category or '').lower()} facts"]
    seen: set[str] = set()
    out: list[str] = []
    for tag in [*(queue_tags or []), *GLOBAL_SEARCH_TAGS, *evergreen, "wild brief", "shorts"]:
        cleaned = str(tag).strip().lower().lstrip("#")
        if not cleaned or cleaned in seen:
            continue
        out.append(cleaned)
        seen.add(cleaned)
        if len(out) >= 15:
            break
    return out


def global_strategy() -> dict:
    """Public metadata for reports and .done markers."""
    return {
        "mode": "global",
        "language_strategy": "simple_english_global",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "publish_windows": GLOBAL_PUBLISH_WINDOWS,
        "principle": (
            "Do not target one country; publish and package for viewers across "
            "Asia/Oceania, Europe/Africa and the Americas."
        ),
    }
