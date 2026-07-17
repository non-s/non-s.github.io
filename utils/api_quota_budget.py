"""Estimated YouTube/API quota budget ledger.

This is intentionally conservative and centralized. YouTube upload calls use
their own daily bucket, so unit spend and upload count must be guarded
separately.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from utils.time_semantics import quota_day_pt

UNIT_METHOD_COSTS = {
    "youtube.videos.insert": 0,
    "youtube.videos.update": 50,
    "youtube.thumbnails.set": 50,
    "youtube.playlists.list": 1,
    "youtube.playlists.insert": 50,
    "youtube.playlistItems.list": 1,
    "youtube.playlistItems.insert": 50,
    "youtube.commentThreads.insert": 50,
    "youtube.commentThreads.list": 1,
    "youtube.comments.insert": 50,
    "youtube.analytics.reports.query": 1,
    "pexels.search": 1,
}

DEFAULT_DAILY_BUDGET = int(os.environ.get("YOUTUBE_DAILY_QUOTA_BUDGET", "10000"))
DEFAULT_DAILY_UPLOAD_BUDGET = int(os.environ.get("YOUTUBE_DAILY_UPLOAD_BUDGET", "100"))
LEDGER_FILE = Path("_data/analytics/api_quota_ledger.jsonl")
LATEST_FILE = Path("_data/analytics/api_quota_latest.json")
UPLOAD_METHOD = "youtube.videos.insert"
LIMITED_CALL_METHODS = (UPLOAD_METHOD,)


def _bool(name: str, default: bool = True, env: dict | None = None) -> bool:
    value = (env or os.environ).get(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _float(name: str, default: float, env: dict | None = None) -> float:
    try:
        return float((env or os.environ).get(name, default))
    except Exception:
        return default


def _int(name: str, default: int, env: dict | None = None) -> int:
    try:
        return int((env or os.environ).get(name, default))
    except Exception:
        return default


def estimate_cost(calls: dict[str, int]) -> int:
    return int(sum(UNIT_METHOD_COSTS.get(method, 1) * int(count or 0) for method, count in calls.items()))


def estimate_limited_calls(calls: dict[str, int]) -> dict[str, int]:
    return {method: int(calls.get(method) or 0) for method in LIMITED_CALL_METHODS if int(calls.get(method) or 0) > 0}


def estimate_publish_run_cost(
    videos: int = 1,
    playlists: int = 2,
    comments: int = 1,
    analytics_queries: int = 6,
) -> dict:
    calls = {
        "youtube.videos.insert": videos,
        "youtube.thumbnails.set": videos,
        "youtube.playlists.list": playlists,
        "youtube.playlistItems.list": playlists,
        "youtube.playlistItems.insert": playlists,
        "youtube.commentThreads.insert": comments,
        "youtube.analytics.reports.query": analytics_queries,
    }
    return {"workflow": "youtube-bot", "calls": calls, "estimated_units": estimate_cost(calls)}


def estimate_metadata_repair_cost(updates: int = 1) -> dict:
    calls = {"youtube.videos.update": updates}
    return {"workflow": "youtube-metadata-repair", "calls": calls, "estimated_units": estimate_cost(calls)}


def _read_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _estimate_units_from_row(row: dict) -> int:
    calls = row.get("calls")
    if isinstance(calls, dict) and calls:
        return estimate_cost(calls)
    return int(row.get("estimated_units") or 0)


def _estimate_units(estimate: dict) -> int:
    calls = estimate.get("calls")
    if isinstance(calls, dict) and calls:
        return estimate_cost(calls)
    return int(estimate.get("estimated_units") or 0)


def daily_spend(path: Path = LEDGER_FILE, *, day: str | None = None) -> int:
    day = day or quota_day_pt()
    return int(
        sum(
            _estimate_units_from_row(row)
            for row in _read_rows(path)
            if str(row.get("quota_day_pt") or row.get("timestamp_utc", ""))[:10] == day
        )
    )


def daily_method_calls(path: Path = LEDGER_FILE, *, method: str, day: str | None = None) -> int:
    day = day or quota_day_pt()
    total = 0
    for row in _read_rows(path):
        if str(row.get("quota_day_pt") or row.get("timestamp_utc", ""))[:10] != day:
            continue
        calls = row.get("calls")
        if isinstance(calls, dict):
            total += int(calls.get(method) or 0)
    return int(total)


def _daily_call_budget(method: str, env: dict | None = None) -> int:
    if method == UPLOAD_METHOD:
        return _int("YOUTUBE_DAILY_UPLOAD_BUDGET", DEFAULT_DAILY_UPLOAD_BUDGET, env)
    return 0


def should_block_run(
    estimate: dict,
    *,
    path: Path = LEDGER_FILE,
    env: dict | None = None,
    daily_budget: int = DEFAULT_DAILY_BUDGET,
) -> dict:
    env = env or os.environ
    mode = str(env.get("QUOTA_GUARD_MODE", "block")).lower()
    enabled = _bool("QUOTA_GUARD_ENABLED", True, env)
    max_ratio = _float("QUOTA_GUARD_MAX_DAILY_RATIO", 0.95, env)
    calls = estimate.get("calls") if isinstance(estimate.get("calls"), dict) else {}
    estimated_units = _estimate_units(estimate)
    spent = daily_spend(path)
    projected = spent + estimated_units
    ratio = projected / max(daily_budget, 1)
    unit_block = bool(enabled and mode == "block" and ratio > max_ratio)
    daily_call_buckets = {}
    call_block = False
    for method in LIMITED_CALL_METHODS:
        attempted_calls = int(calls.get(method) or 0)
        spent_calls = daily_method_calls(path, method=method)
        budget = _daily_call_budget(method, env)
        projected_calls = spent_calls + attempted_calls
        call_ratio = projected_calls / max(budget, 1)
        bucket_block = bool(enabled and mode == "block" and attempted_calls > 0 and call_ratio > max_ratio)
        daily_call_buckets[method] = {
            "attempted_today": attempted_calls,
            "spent_today": spent_calls,
            "projected_today": projected_calls,
            "daily_budget": budget,
            "projected_ratio": round(call_ratio, 4),
            "max_daily_ratio": max_ratio,
            "block": bucket_block,
        }
        call_block = call_block or bucket_block
    block = unit_block or call_block
    if unit_block:
        reason = "quota_ratio_exceeded"
    elif call_block:
        reason = "daily_call_limit_exceeded"
    else:
        reason = "within_budget_or_observe"
    return {
        "enabled": enabled,
        "mode": mode,
        "block": block,
        "reason": reason,
        "spent_today": spent,
        "projected_today": projected,
        "daily_budget": daily_budget,
        "projected_ratio": round(ratio, 4),
        "max_daily_ratio": max_ratio,
        "daily_call_buckets": daily_call_buckets,
    }


def write_quota_ledger_row(
    estimate: dict,
    *,
    path: Path = LEDGER_FILE,
    latest_path: Path = LATEST_FILE,
    env: dict | None = None,
) -> dict:
    env = env or os.environ
    row = quota_ledger_row(estimate, path=path, env=env)
    if _bool("QUOTA_LEDGER_ENABLED", True, env):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
        latest_path.parent.mkdir(parents=True, exist_ok=True)
        latest_path.write_text(json.dumps(row, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return row


def quota_ledger_row(
    estimate: dict,
    *,
    path: Path = LEDGER_FILE,
    env: dict | None = None,
) -> dict:
    env = env or os.environ
    guard = should_block_run(estimate, path=path, env=env)
    calls = estimate.get("calls") if isinstance(estimate.get("calls"), dict) else {}
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "quota_day_pt": quota_day_pt(),
        "workflow": estimate.get("workflow", ""),
        "calls": calls,
        "estimated_units": _estimate_units(estimate),
        "estimated_daily_calls": estimate_limited_calls(calls),
        "guard": guard,
    }
