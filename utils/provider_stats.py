"""
utils/provider_stats.py — Track AI provider success rates and cooldown.

Why this exists
---------------
ai_helper.py now has a single real provider (Google Gemini). This
module still records every call's (provider, status) into
`_data/provider_stats.jsonl` so we can detect when Gemini is entering
cooldown (consecutive 429s) and so the ledger can be inspected later.
`preferred_chain()` is kept generic but, with only one provider in the
project, it mostly returns `["gemini"]`.

Decay: we look at the LAST 50 calls per provider. Older data is ignored
so a recovered provider climbs back quickly.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections import defaultdict
from pathlib import Path

log = logging.getLogger(__name__)

STATS_LOG = Path(os.environ.get("PROVIDER_STATS_LOG", "_data/provider_stats.jsonl"))
# How many recent calls to weigh per provider when computing the
# success rate. Smaller = adapts faster to current weather; larger =
# smoother. 50 lands at ~2 hours of typical traffic.
WINDOW_SIZE = int(os.environ.get("PROVIDER_STATS_WINDOW", "50"))

# Canonical ordering when we have no data yet (or the file is
# unreadable). Gemini is the only real provider in the project.
DEFAULT_ORDER: tuple[str, ...] = ("gemini",)
TASK_DEFAULTS: dict[str, tuple[str, ...]] = {
    "json": ("gemini",),
    "longform": ("gemini",),
    "rewrite": ("gemini",),
    "classification": ("gemini",),
    "creative": ("gemini",),
    "auto": DEFAULT_ORDER,
}
COOLDOWN_SECONDS = int(os.environ.get("PROVIDER_COOLDOWN_SECONDS", "900"))

_write_lock = threading.Lock()


def record(provider: str, success: bool, status: int | None = None) -> None:
    """Append a single call's outcome. Best-effort, never raises."""
    entry = {
        "ts": time.time(),
        "provider": provider,
        "ok": bool(success),
        "status": status,
    }
    try:
        STATS_LOG.parent.mkdir(parents=True, exist_ok=True)
        with _write_lock:
            with STATS_LOG.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as exc:
        log.debug("provider_stats record failed: %s", exc)


def _load_recent(path: Path = STATS_LOG) -> dict[str, list[bool]]:
    """Return {provider: [ok_bool, ...]} for the last WINDOW_SIZE entries each."""
    if not path.exists():
        return {}
    rows: list[dict] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except Exception:
        return {}
    by_provider: dict[str, list[bool]] = defaultdict(list)
    # Read newest-first so we can break early once each provider has
    # WINDOW_SIZE entries.
    for row in reversed(rows):
        provider = row.get("provider")
        if not provider:
            continue
        bucket = by_provider[provider]
        if len(bucket) >= WINDOW_SIZE:
            continue
        bucket.append(bool(row.get("ok")))
    return dict(by_provider)


def _load_recent_rows(path: Path = STATS_LOG) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except Exception:
        return []
    return rows


def success_rate(provider: str, path: Path | None = None) -> float | None:
    """Return success rate (0-1) for `provider`, or None if no data."""
    recent = _load_recent(path or STATS_LOG)
    samples = recent.get(provider, [])
    if not samples:
        return None
    return sum(1 for ok in samples if ok) / len(samples)


def cooldown_until(provider: str, path: Path | None = None, now: float | None = None) -> float:
    """Return unix timestamp until which provider should be avoided."""
    now = time.time() if now is None else now
    rows = _load_recent_rows(path or STATS_LOG)
    consecutive_429 = 0
    latest_ts = 0.0
    for row in reversed(rows):
        if row.get("provider") != provider:
            continue
        latest_ts = float(row.get("ts") or 0.0)
        if row.get("ok"):
            break
        if int(row.get("status") or 0) == 429:
            consecutive_429 += 1
            if consecutive_429 >= 2:
                return max(0.0, latest_ts + COOLDOWN_SECONDS)
        else:
            break
    return 0.0 if latest_ts <= now else latest_ts


def is_in_cooldown(provider: str, path: Path | None = None, now: float | None = None) -> bool:
    now = time.time() if now is None else now
    until = cooldown_until(provider, path=path, now=now)
    return bool(until and until > now)


def preferred_chain(*, default: tuple[str, ...] = DEFAULT_ORDER, path: Path | None = None) -> list[str]:
    """Return providers in the order ai_helper.py should try them.

    Logic:
      * "healthy" providers (recent rate ≥ 0.4) come first, sorted
        by rate descending.
      * "unknown" providers (no data) keep their default rank in
        the middle band — we'd rather give an unproven provider a
        shot than hit a known-failing one.
      * "dead" providers (rate < 0.4) go to the back.

    The 0.4 cutoff is conservative: a provider blipping at 50 %
    success rate is still worth trying first. Below 40 % means
    most calls fail; the wait + retry isn't worth it.
    """
    recent = _load_recent(path or STATS_LOG)
    if not recent:
        return list(default)
    default_idx = {p: i for i, p in enumerate(default)}

    now = time.time()

    def _key(p: str) -> tuple:
        if is_in_cooldown(p, path=path or STATS_LOG, now=now):
            return (3, default_idx[p])
        samples = recent.get(p, [])
        if not samples:
            return (1, default_idx[p])  # unknown: middle band
        rate = sum(1 for ok in samples if ok) / len(samples)
        if rate >= 0.4:
            return (0, -rate, default_idx[p])  # healthy: front, by rate
        return (2, default_idx[p])  # dead: back

    return sorted(default, key=_key)


def preferred_chain_for_task(
    task: str = "auto", *, json_mode: bool = False, prompt_chars: int = 0, path: Path | None = None
) -> list[str]:
    """Choose provider order for the actual job, then adapt by health.

    The task hint keeps expensive/slow providers for high-value work and
    sends simple rewrites/classification to faster providers. Recent
    failures still reshuffle the order.
    """
    if json_mode:
        task = "json"
    elif task == "auto" and prompt_chars >= 4500:
        task = "longform"
    default = TASK_DEFAULTS.get(task, TASK_DEFAULTS["auto"])
    return preferred_chain(default=default, path=path)


def prune_older_than(days: int = 7, path: Path | None = None) -> int:
    """Rewrite the ledger dropping entries older than `days`. Keeps the
    file bounded — daily call volume × 7 days ~ 50k rows ~ 4 MB."""
    p = path or STATS_LOG
    if not p.exists():
        return 0
    cutoff = time.time() - days * 86400
    keep: list[dict] = []
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (e.get("ts") or 0) >= cutoff:
                keep.append(e)
    except Exception:
        return 0
    tmp = p.with_suffix(p.suffix + ".tmp")
    with _write_lock:
        with tmp.open("w", encoding="utf-8") as fh:
            for e in keep:
                fh.write(json.dumps(e, ensure_ascii=False) + "\n")
        tmp.replace(p)
    return len(keep)
