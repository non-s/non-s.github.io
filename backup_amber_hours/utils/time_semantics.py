"""Shared UTC/Pacific time semantics for Wild Brief automation."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    PACIFIC: tzinfo | None = ZoneInfo("America/Los_Angeles")
except ZoneInfoNotFoundError:  # pragma: no cover - host-dependent
    PACIFIC = None
VIEWS_REGIME_CUTOVER = date(2025, 3, 31)
LEGACY_VIEWS_REGIME = "shorts_views_minimum_watch_legacy"
CURRENT_VIEWS_REGIME = "shorts_views_play_or_replay"


def ensure_utc(value: datetime | str | None = None) -> datetime:
    """Return a timezone-aware UTC datetime."""
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, str):
        text = value.strip().replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
    else:
        parsed = value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _nth_weekday(year: int, month: int, weekday: int, nth: int) -> date:
    current = date(year, month, 1)
    offset = (weekday - current.weekday()) % 7
    return current + timedelta(days=offset + (nth - 1) * 7)


def _pacific_fallback_offset(stamp: datetime) -> timezone:
    year = stamp.year
    dst_start = datetime.combine(_nth_weekday(year, 3, 6, 2), datetime.min.time(), tzinfo=timezone.utc) + timedelta(
        hours=10
    )
    dst_end = datetime.combine(_nth_weekday(year, 11, 6, 1), datetime.min.time(), tzinfo=timezone.utc) + timedelta(
        hours=9
    )
    return timezone(timedelta(hours=-7 if dst_start <= stamp < dst_end else -8))


def to_pacific(value: datetime | str | None = None) -> datetime:
    stamp = ensure_utc(value)
    if PACIFIC is not None:
        return stamp.astimezone(PACIFIC)
    return stamp.astimezone(_pacific_fallback_offset(stamp))


def pacific_day(value: datetime | str | None = None) -> str:
    """Return the YouTube operational day in Pacific time."""
    return to_pacific(value).date().isoformat()


def publish_day_pt(value: datetime | str | None = None) -> str:
    return pacific_day(value)


def quota_day_pt(value: datetime | str | None = None) -> str:
    return pacific_day(value)


def views_regime(value: datetime | str | None = None) -> str:
    """Return the Shorts views semantics active for a publish timestamp."""
    day = to_pacific(value).date()
    return CURRENT_VIEWS_REGIME if day >= VIEWS_REGIME_CUTOVER else LEGACY_VIEWS_REGIME


def temporal_fields(published_at: datetime | str | None = None, *, now: datetime | str | None = None) -> dict:
    """Build the durable temporal fields expected by metadata and analytics."""
    stamp = ensure_utc(published_at or now)
    return {
        "publish_ts_utc": stamp.isoformat(),
        "publish_day_pt": publish_day_pt(stamp),
        "quota_day_pt": quota_day_pt(stamp),
        "views_regime": views_regime(stamp),
    }


def canonical_slot_set(env: dict | None = None) -> tuple[str, ...]:
    """Return the canonical UTC slot labels from the publish schedule module."""
    from utils.publish_schedule import canonical_slots

    return tuple(canonical_slots(env))
