"""Canonical adaptive publish schedule for Wild Brief."""

from __future__ import annotations

import json
import os
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

from utils.audience_expansion import GLOBAL_PUBLISH_WINDOWS

ANALYTICS_FILE = Path("_data/analytics/latest.json")
SCHEDULE_FILE = Path("_data/publish_schedule.json")
CANONICAL_SLOTS_UTC = tuple(str(item["slot"]) for item in GLOBAL_PUBLISH_WINDOWS)
DEFAULT_RECOMMENDED_SLOTS_UTC = CANONICAL_SLOTS_UTC
DECISIONS_FILE = Path("_data/publish_slot_decisions.jsonl")


def _env_bool(name: str, default: bool = False, env: dict | None = None) -> bool:
    value = (env or os.environ).get(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float, env: dict | None = None) -> float:
    try:
        return float((env or os.environ).get(name, default))
    except Exception:
        return default


def _env_int(name: str, default: int, env: dict | None = None) -> int:
    try:
        return int((env or os.environ).get(name, default))
    except Exception:
        return default


def _normalise_slot(slot: str) -> str:
    hour, minute = str(slot).strip().split(":", 1)
    return f"{int(hour):02d}:{int(minute):02d}"


def _parse_slot(slot: str) -> time:
    label = _normalise_slot(slot)
    hour, minute = label.split(":")
    return time(int(hour), int(minute), tzinfo=timezone.utc)


def _parse_cron_values(field: str, *, minimum: int, maximum: int) -> list[int]:
    if str(field or "").strip() == "*":
        return list(range(minimum, maximum + 1))
    values: list[int] = []
    for part in str(field or "").split(","):
        part = part.strip()
        if not part.isdigit():
            continue
        value = int(part)
        if minimum <= value <= maximum and value not in values:
            values.append(value)
    return values


def _event_schedule_cron(env: dict | None = None) -> str:
    env = env or os.environ
    return str(env.get("PUBLISH_EVENT_SCHEDULE_CRON") or env.get("GITHUB_EVENT_SCHEDULE") or "").strip()


def _event_schedule_max_delay(env: dict | None = None) -> int:
    return max(0, _env_int("PUBLISH_EVENT_MAX_DELAY_MINUTES", 360, env))


def _recovery_delay_minutes(env: dict | None = None) -> int:
    return max(0, _env_int("PUBLISH_RECOVERY_DELAY_MINUTES", 40, env))


def _target_slot_from_scheduled_time(scheduled: datetime) -> str:
    scheduled = scheduled.astimezone(timezone.utc)
    canonical_minutes = {int(str(slot).split(":", 1)[1]) for slot in CANONICAL_SLOTS_UTC}
    if scheduled.minute in canonical_minutes:
        target = scheduled
    elif scheduled.minute in {2, 20, 22, 40, 42}:
        target = scheduled.replace(minute=0)
    elif scheduled.minute == 43:
        # Legacy recovery cron: :43 recovered the previous :23 slot.
        target = scheduled - timedelta(minutes=80)
    else:
        target = scheduled - timedelta(minutes=_recovery_delay_minutes())
    return f"{target.hour:02d}:{target.minute:02d}"


def feature_flags(env: dict | None = None) -> dict:
    """Return publish schedule flags and thresholds from the environment."""
    return {
        "adaptive_cadence_enabled": _env_bool("ADAPTIVE_CADENCE_ENABLED", False, env),
        "allow_flex_slot": _env_bool("ALLOW_FLEX_SLOT", False, env),
        "min_slot_publish_score": _env_float("MIN_SLOT_PUBLISH_SCORE", 72.0, env),
        "min_queue_opportunity_score": _env_float("MIN_QUEUE_OPPORTUNITY_SCORE", 50.0, env),
    }


def canonical_slots(env: dict | None = None) -> list[str]:
    """Return canonical UTC evaluation slots, with an optional operator flex slot."""
    slots = list(CANONICAL_SLOTS_UTC)
    flags = feature_flags(env)
    flex = (env or os.environ).get("FLEX_SLOT_UTC", "")
    if flags["allow_flex_slot"] and flex:
        try:
            normalised = _normalise_slot(flex)
        except Exception:
            normalised = ""
        if normalised and normalised not in slots:
            slots.append(normalised)
    return sorted(slots)


def _schedule_slots(schedule: dict | None = None, env: dict | None = None) -> list[str]:
    schedule = schedule if isinstance(schedule, dict) else {}
    slots = schedule.get("recommended_slots") or DEFAULT_RECOMMENDED_SLOTS_UTC
    normalised = []
    for slot in slots:
        try:
            normalised.append(_normalise_slot(str(slot)))
        except Exception:
            continue
    if feature_flags(env)["allow_flex_slot"]:
        for slot in canonical_slots(env):
            if slot not in normalised and slot not in CANONICAL_SLOTS_UTC:
                normalised.append(slot)
    return normalised or list(DEFAULT_RECOMMENDED_SLOTS_UTC)


def slot_label(now: datetime | None = None) -> str:
    """Return the current UTC slot label in HH:MM form."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    return f"{current.hour:02d}:{current.minute:02d}"


def event_schedule_slot_label(
    now: datetime | None = None,
    schedule: dict | None = None,
    env: dict | None = None,
) -> str:
    """Return the intended slot from a delayed GitHub schedule event."""
    env = env or os.environ
    if str(env.get("GITHUB_EVENT_NAME") or "").lower() != "schedule":
        return ""
    cron = _event_schedule_cron(env)
    parts = cron.split()
    if len(parts) < 2:
        return ""
    minutes = _parse_cron_values(parts[0], minimum=0, maximum=59)
    hours = _parse_cron_values(parts[1], minimum=0, maximum=23)
    if not minutes or not hours:
        return ""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    max_delay = timedelta(minutes=_event_schedule_max_delay(env))
    candidates = []
    for day_offset in (-1, 0):
        slot_date = current.date() + timedelta(days=day_offset)
        for hour in hours:
            for minute in minutes:
                scheduled = datetime.combine(slot_date, time(hour, minute, tzinfo=timezone.utc), tzinfo=timezone.utc)
                delay = current - scheduled
                if timedelta(0) <= delay <= max_delay:
                    target = _target_slot_from_scheduled_time(scheduled)
                    if target in _schedule_slots(schedule, env):
                        candidates.append((scheduled, target))
    if not candidates:
        return ""
    return max(candidates, key=lambda item: item[0])[1]


def active_slot_label(now: datetime | None = None, schedule: dict | None = None, env: dict | None = None) -> str:
    """Return the intended UTC slot label when now is inside its recovery window."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    grace = max(0, _env_int("PUBLISH_SLOT_GRACE_MINUTES", 90, env))
    today = current.date()
    candidates = []
    for slot in _schedule_slots(schedule, env):
        slot_time = _parse_slot(slot)
        for day_offset in (-1, 0):
            slot_date = today + timedelta(days=day_offset)
            candidate = datetime.combine(slot_date, slot_time, tzinfo=timezone.utc)
            delay = current - candidate
            if timedelta(0) <= delay <= timedelta(minutes=grace):
                candidates.append((candidate, slot))
    if not candidates:
        return event_schedule_slot_label(current, schedule, env)
    return max(candidates, key=lambda item: item[0])[1]


def is_active_slot(now: datetime | None = None, schedule: dict | None = None, env: dict | None = None) -> bool:
    """Return True when the current slot should be allowed to publish."""
    flags = feature_flags(env)
    if not flags["adaptive_cadence_enabled"]:
        return True
    return bool(active_slot_label(now, schedule, env))


def next_slot(now: datetime | None = None, schedule: dict | None = None, env: dict | None = None) -> str:
    """Return the next recommended UTC slot label."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    today = current.date()
    candidates = []
    for slot in _schedule_slots(schedule, env):
        slot_time = _parse_slot(slot)
        candidate = datetime.combine(today, slot_time, tzinfo=timezone.utc)
        if candidate <= current:
            candidate += timedelta(days=1)
        candidates.append(candidate)
    winner = min(candidates)
    return f"{winner.hour:02d}:{winner.minute:02d}"


def _safe_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def recommend_schedule(analytics: dict | None = None) -> dict:
    analytics = analytics or _safe_json(ANALYTICS_FILE)
    global_slots = [str(item["slot"]) for item in GLOBAL_PUBLISH_WINDOWS]

    # MrBeast Heatmap Dynamic Scheduling
    if _env_bool("MRBEAST_HEATMAP_ENABLED", False):
        peak_hours = {16, 17, 18, 19, 20, 21, 22}
        slots = [s for s in global_slots if int(s.split(":")[0]) in peak_hours]
        if not slots:
            slots = global_slots  # fallback
    else:
        slots = global_slots

    cadence = len(slots)
    backlog_target = max(0, _env_int("QUEUE_TARGET_PENDING", 24))
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "timezone": "UTC",
        "canonical_slots": list(CANONICAL_SLOTS_UTC),
        "recommended_slots": slots,
        "recommended_shorts_per_day": cadence,
        "rolling_batch_size": backlog_target or 1,
        "queue_target_pending": backlog_target,
        "target_regions": GLOBAL_PUBLISH_WINDOWS,
        "feature_flags": feature_flags(),
        "reason": "operator_day_zero_hourly_publish_with_quality_and_quota_guards",
    }


def write_schedule(path: Path = SCHEDULE_FILE) -> dict:
    schedule = recommend_schedule()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(schedule, indent=2, ensure_ascii=False), encoding="utf-8")
    return schedule
