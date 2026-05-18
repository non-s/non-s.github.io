"""
utils/youtube_quota.py — Estimate-and-track YouTube Data API quota usage.

YouTube doesn't expose a quota-remaining endpoint, but its quota costs
are documented. We estimate burn from our own operations and append to
`_data/quota_log.jsonl`, then the workflow summary can show "used X of
10 000 units today" so the operator knows when they're cutting it close.

Per-operation costs (Data API v3, May 2026):
  videos.insert           1600
  videos.list             1
  thumbnails.set          50
  playlistItems.insert    50
  playlists.insert        50
  commentThreads.insert   50
  channels.list           1

Each ledger entry is one JSON line:
  {"ts": 1715900000.0, "op": "videos.insert", "cost": 1600,
   "video_id": "abc123", "channel": "en"}

`daily_used()` reads back the last N hours' entries and returns the
total cost. `record()` appends one entry — call it right after the
matching API call.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None

log = logging.getLogger(__name__)

QUOTA_LOG = Path(os.environ.get("YOUTUBE_QUOTA_LOG", "_data/quota_log.jsonl"))
DAILY_BUDGET = int(os.environ.get("YOUTUBE_QUOTA_DAILY", "10000"))
WARN_AT = float(os.environ.get("YOUTUBE_QUOTA_WARN_AT", "0.80"))  # 80 %

# Canonical cost table. Source: developers.google.com/youtube/v3/determine_quota_cost
OPERATION_COSTS = {
    "videos.insert":         1600,
    "videos.list":           1,
    "thumbnails.set":        50,
    "playlistItems.insert":  50,
    "playlists.insert":      50,
    "commentThreads.insert": 50,
    "channels.list":         1,
    "search.list":           100,
}

_write_lock = threading.Lock()


def cost_of(op: str) -> int:
    """Return the documented unit cost for an op. 0 for unknown ops."""
    return OPERATION_COSTS.get(op, 0)


def record(op: str, *, channel: str = "en",
            video_id: str = "", extra: dict | None = None) -> int:
    """Append a quota usage entry. Returns the cost recorded.

    Best-effort: any write failure is logged but never raised — quota
    tracking must never block an upload that already succeeded.
    """
    cost = cost_of(op)
    if cost == 0:
        log.debug("quota: unknown op %r, recording cost=0", op)
    entry = {
        "ts":       time.time(),
        "iso":      datetime.now(timezone.utc).isoformat(),
        "op":       op,
        "cost":     cost,
        "channel":  channel,
        "video_id": video_id,
    }
    if extra:
        entry.update(extra)
    try:
        QUOTA_LOG.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(entry, ensure_ascii=False) + "\n"
        with _write_lock:
            if fcntl is None:
                with QUOTA_LOG.open("a", encoding="utf-8") as fh:
                    fh.write(line)
            else:
                with QUOTA_LOG.open("a", encoding="utf-8") as fh:
                    try:
                        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
                        fh.write(line)
                    finally:
                        try:
                            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
                        except Exception:
                            pass
    except Exception as exc:
        log.debug("quota: write failed: %s", exc)
    return cost


def _iter_entries(path: Path = QUOTA_LOG):
    if not path.exists():
        return
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue
    except Exception:
        return


def daily_used(now: float | None = None, path: Path = QUOTA_LOG) -> int:
    """Sum the costs of every operation in the UTC day containing `now`.

    YouTube resets quota at midnight Pacific Time, but the Pacific-vs-
    UTC offset would only matter at hour-zero; treating it as a UTC
    day is close enough for an "are we near the cap" alert.
    """
    now = now or time.time()
    today = datetime.fromtimestamp(now, tz=timezone.utc).date()
    total = 0
    for e in _iter_entries(path):
        ts = e.get("ts")
        if not isinstance(ts, (int, float)):
            continue
        d = datetime.fromtimestamp(ts, tz=timezone.utc).date()
        if d == today:
            total += int(e.get("cost", 0) or 0)
    return total


def warn_if_near_cap(now: float | None = None, path: Path = QUOTA_LOG) -> str:
    """Returns a human-readable warning string if usage > WARN_AT, else ""."""
    used = daily_used(now=now, path=path)
    if used / DAILY_BUDGET >= WARN_AT:
        return (f"⚠ YouTube quota: {used}/{DAILY_BUDGET} units used "
                f"({used / DAILY_BUDGET * 100:.0f}% of daily cap)")
    return ""


def summary(now: float | None = None, path: Path = QUOTA_LOG) -> dict:
    """Concise stats for the workflow summary step."""
    used = daily_used(now=now, path=path)
    return {
        "used":            used,
        "budget":          DAILY_BUDGET,
        "remaining":       max(0, DAILY_BUDGET - used),
        "pct_used":        round(100.0 * used / DAILY_BUDGET, 1) if DAILY_BUDGET else 0.0,
        "warning":         warn_if_near_cap(now=now, path=path),
    }


def prune_older_than(days: int = 30, path: Path = QUOTA_LOG) -> int:
    """Rewrite the file dropping entries older than `days`. Returns kept count."""
    if not path.exists():
        return 0
    cutoff = time.time() - days * 86400
    kept: list[dict] = []
    for e in _iter_entries(path):
        ts = e.get("ts", 0)
        if isinstance(ts, (int, float)) and ts >= cutoff:
            kept.append(e)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with _write_lock:
        with tmp.open("w", encoding="utf-8") as fh:
            for e in kept:
                fh.write(json.dumps(e, ensure_ascii=False) + "\n")
        tmp.replace(path)
    return len(kept)
