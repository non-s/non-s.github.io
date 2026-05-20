"""
utils/tiktok_quota.py — Track TikTok Content Posting API rate-limit usage.

TikTok doesn't expose a daily quota the way YouTube does — it enforces
per-user rate limits at the endpoint level. The documented production
limits (May 2026):

  video.publish (Direct Post init)       6 / min, 30 / day per user
  video.upload (Inbox init)              6 / min, 30 / day per user
  publish/status/fetch                   30 / min per user
  video/list                              ~600 / min, soft cap

We still log every API call to `_data/tiktok_quota_log.jsonl` so the
workflow summary can show "we made N posts today" and warn if we're
approaching the daily ceiling.

Per-operation costs are conceptual ("1 post" rather than YouTube's
unit system) — the daily budget defaults to 30 posts/day which is
TikTok's own cap for unaudited apps. Operators with higher caps can
override via `TIKTOK_QUOTA_DAILY`.

Each ledger entry is one JSON line:
  {"ts": 1715900000.0, "op": "video.publish.init", "cost": 1,
   "publish_id": "v_inbox.123…", "channel": "en"}
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

QUOTA_LOG = Path(os.environ.get("TIKTOK_QUOTA_LOG", "_data/tiktok_quota_log.jsonl"))
DAILY_BUDGET = int(os.environ.get("TIKTOK_QUOTA_DAILY", "30"))
WARN_AT = float(os.environ.get("TIKTOK_QUOTA_WARN_AT", "0.80"))

# Conceptual cost table. Each successful "post" counts 1 against the
# daily cap; metadata calls are free.
OPERATION_COSTS = {
    "video.publish.init":   1,
    "video.upload.init":    1,
    "publish.status.fetch": 0,
    "user.info":            0,
    "video.list":           0,
    "video.query":          0,
}

_write_lock = threading.Lock()


def cost_of(op: str) -> int:
    """Documented cost for an op (in posts). 0 for read-only ops."""
    return OPERATION_COSTS.get(op, 0)


def record(op: str, *, channel: str = "en",
            publish_id: str = "", extra: dict | None = None) -> int:
    """Append a usage entry. Returns the cost recorded.

    Best-effort: any write failure is logged but never raised — quota
    tracking must never block an upload that already succeeded.
    """
    cost = cost_of(op)
    if cost == 0 and op not in OPERATION_COSTS:
        log.debug("tiktok_quota: unknown op %r, recording cost=0", op)
    entry = {
        "ts":         time.time(),
        "iso":        datetime.now(timezone.utc).isoformat(),
        "op":         op,
        "cost":       cost,
        "channel":    channel,
        "publish_id": publish_id,
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
        log.debug("tiktok_quota: write failed: %s", exc)
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
    """Sum costs of every op in the UTC day containing `now`."""
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
    """Human-readable warning if usage > WARN_AT, else ""."""
    used = daily_used(now=now, path=path)
    if used / DAILY_BUDGET >= WARN_AT:
        return (f"⚠ TikTok posts: {used}/{DAILY_BUDGET} today "
                f"({used / DAILY_BUDGET * 100:.0f}% of daily cap)")
    return ""


def summary(now: float | None = None, path: Path = QUOTA_LOG) -> dict:
    """Concise stats for the workflow summary step."""
    used = daily_used(now=now, path=path)
    return {
        "used":      used,
        "budget":    DAILY_BUDGET,
        "remaining": max(0, DAILY_BUDGET - used),
        "pct_used":  round(100.0 * used / DAILY_BUDGET, 1) if DAILY_BUDGET else 0.0,
        "warning":   warn_if_near_cap(now=now, path=path),
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
