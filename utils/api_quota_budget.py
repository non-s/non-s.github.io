"""Estimated YouTube/Pexels API quota budget ledger.

This is intentionally conservative and centralized: when platform costs
change, update METHOD_COSTS in one place.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from utils.time_semantics import quota_day_pt

METHOD_COSTS = {
    "youtube.videos.insert": 1600,
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
    "pixabay.search": 1,
}

DEFAULT_DAILY_BUDGET = int(os.environ.get("YOUTUBE_DAILY_QUOTA_BUDGET", "10000"))
LEDGER_FILE = Path("_data/analytics/api_quota_ledger.jsonl")
LATEST_FILE = Path("_data/analytics/api_quota_latest.json")


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


def estimate_cost(calls: dict[str, int]) -> int:
    return int(sum(METHOD_COSTS.get(method, 1) * int(count or 0) for method, count in calls.items()))


def estimate_fetch_content_cost(search_calls: int = 12, enrichment_calls: int = 0) -> dict:
    calls = {"pexels.search": search_calls, "pixabay.search": max(0, search_calls // 3)}
    if enrichment_calls:
        calls["youtube.analytics.reports.query"] = enrichment_calls
    return {"workflow": "fetch-content", "calls": calls, "estimated_units": estimate_cost(calls)}


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


def daily_spend(path: Path = LEDGER_FILE, *, day: str | None = None) -> int:
    day = day or quota_day_pt()
    return int(
        sum(
            int(row.get("estimated_units") or 0)
            for row in _read_rows(path)
            if str(row.get("quota_day_pt") or row.get("timestamp_utc", ""))[:10] == day
        )
    )


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
    spent = daily_spend(path)
    projected = spent + int(estimate.get("estimated_units") or 0)
    ratio = projected / max(daily_budget, 1)
    block = bool(enabled and mode == "block" and ratio > max_ratio)
    return {
        "enabled": enabled,
        "mode": mode,
        "block": block,
        "reason": "quota_ratio_exceeded" if block else "within_budget_or_observe",
        "spent_today": spent,
        "projected_today": projected,
        "daily_budget": daily_budget,
        "projected_ratio": round(ratio, 4),
        "max_daily_ratio": max_ratio,
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
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "quota_day_pt": quota_day_pt(),
        "workflow": estimate.get("workflow", ""),
        "calls": estimate.get("calls", {}),
        "estimated_units": int(estimate.get("estimated_units") or 0),
        "guard": guard,
    }
