"""
utils/jamendo_cache.py — Disk cache for Jamendo search results.

Why this exists
---------------
scripts/sync_classical_music.py and scripts/sync_animal_jazz.py both hit
Jamendo's `/tracks` search with the same fuzzytags + offset + limit many
times per week. Re-scanning identical pages burns API quota for no new
candidates, because Jamendo's catalog rotates slowly. This cache lets a
subsequent run reuse the last successful result for a given query within a
configurable TTL (default 24 hours), only paying quota when the cache is
cold or stale.

Storage
-------
JSONL at `_data/jamendo_search_cache.jsonl`. Each entry is keyed by
sha256(tags + offset + limit). The latest entry for a key wins on load.
A daily prune step rewrites the file dropping entries older than the TTL.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any

try:
    import fcntl
except ImportError:  # pragma: no cover — Windows local dev only
    fcntl = None

log = logging.getLogger(__name__)

_DEFAULT_TTL_HOURS = float(os.environ.get("JAMENDO_CACHE_TTL_HOURS", "24"))
_DEFAULT_PATH = Path(os.environ.get("JAMENDO_CACHE_PATH", "_data/jamendo_search_cache.jsonl"))
_ENABLED = os.environ.get("JAMENDO_CACHE_ENABLED", "1") not in ("0", "false", "False")

_mem_lock = threading.Lock()
_mem: dict[str, dict] | None = None


def _key(tags: str, offset: int, limit: int) -> str:
    h = hashlib.sha256()
    h.update(str(tags).encode("utf-8", errors="replace"))
    h.update(b"\x00")
    h.update(str(offset).encode("utf-8"))
    h.update(b"\x00")
    h.update(str(limit).encode("utf-8"))
    return h.hexdigest()[:24]


def _now() -> float:
    return time.time()


def _load(path: Path = _DEFAULT_PATH) -> dict[str, dict]:
    if not path.exists():
        return {}
    out: dict[str, dict] = {}
    ttl_s = _DEFAULT_TTL_HOURS * 3600
    now = _now()
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            key = entry.get("k")
            ts = entry.get("ts", 0)
            if not key:
                continue
            if (now - ts) > ttl_s:
                continue
            out[key] = entry
    except Exception as exc:
        log.debug("jamendo_cache load failed: %s", exc)
        return {}
    return out


def _append(path: Path, entry: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(entry, ensure_ascii=False) + "\n"
    try:
        if fcntl is None:
            with path.open("a", encoding="utf-8") as fh:
                fh.write(payload)
            return
        with path.open("a", encoding="utf-8") as fh:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
                fh.write(payload)
            finally:
                try:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
                except Exception:
                    pass
    except Exception as exc:
        log.debug("jamendo_cache append failed: %s", exc)


def _ensure_loaded(path: Path = _DEFAULT_PATH) -> dict[str, dict]:
    global _mem
    with _mem_lock:
        if _mem is None:
            _mem = _load(path)
        return _mem


def reset_cache_for_tests() -> None:
    """Drop the in-memory cache. Used by tests to isolate fixtures."""
    global _mem
    with _mem_lock:
        _mem = None


def get(tags: str, offset: int, limit: int, path: Path = _DEFAULT_PATH) -> list[dict] | None:
    """Return cached results for this query if still fresh, else None."""
    if not _ENABLED:
        return None
    cache = _ensure_loaded(path)
    entry = cache.get(_key(tags, offset, limit))
    if not entry:
        return None
    value = entry.get("v")
    if not isinstance(value, list):
        return None
    return value


def put(tags: str, offset: int, limit: int, results: list[dict], path: Path = _DEFAULT_PATH) -> None:
    """Store `results` for this query. No-op if cache disabled or empty."""
    if not _ENABLED or not results:
        return
    key = _key(tags, offset, limit)
    entry = {"k": key, "ts": _now(), "v": results}
    cache = _ensure_loaded(path)
    cache[key] = entry
    _append(path, entry)


def cached_search(
    tags: str,
    offset: int,
    limit: int,
    fetcher: Any,
    path: Path = _DEFAULT_PATH,
) -> tuple[list[dict], bool]:
    """Return cached results if present and fresh; otherwise call
    `fetcher(tags, offset, limit)` and store the returned results.

    `fetcher` must return `(results, hard_failure)` in the same shape as
    the existing `_fetch_candidates_ex` helpers in the sync scripts.
    """
    cached = get(tags, offset, limit, path=path)
    if cached is not None:
        log.info("Jamendo cache hit for tags=%s offset=%s limit=%s", tags, offset, limit)
        return cached, False
    results, hard_failure = fetcher(tags, offset, limit)
    if not hard_failure and results:
        put(tags, offset, limit, results, path=path)
    return results, hard_failure


def prune(path: Path = _DEFAULT_PATH) -> int:
    """Rewrite the file dropping expired entries. Returns the number kept."""
    if not path.exists():
        return 0
    fresh = _load(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for entry in fresh.values():
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    tmp.replace(path)
    reset_cache_for_tests()
    return len(fresh)
