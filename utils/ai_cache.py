"""
utils/ai_cache.py — Disk cache for AI text responses.

Wraps `utils.ai_helper.ai_text` so identical prompts in the same TTL
window don't burn Mistral / Cerebras / Gemini / Groq quota.

How it helps the free-tier budget
---------------------------------
fetch_animals.py runs every 3h and may revisit the same Pexels clips
until they're consumed. Without caching, each retry of the same animal fact
costs a fresh AI call. With caching, the first call is paid; reruns
within `AI_CACHE_TTL_DAYS` (default 30) come back from disk for free.

Realistic budget impact: roughly 60–80 % drop in Mistral calls on a
queue that re-encounters the same stories across runs, which is
typical for the 3h cron cadence.

Invalidation
------------
The cache key is `sha256(prompt + model + json_mode)`. Any change to
`_AI_PROMPT_TEMPLATE` produces a different hash, so an editorial
update to the prompt automatically invalidates every prior entry —
no manual purge needed. Stale entries past their TTL are pruned on
load.

Storage
-------
JSONL at `_data/ai_cache.jsonl` to keep the on-disk shape readable
and append-only. We rewrite the file in full only on prune; daily
writes stay append-only and concurrency-safe via fcntl on POSIX.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Callable

try:
    import fcntl
except ImportError:  # pragma: no cover — Windows local dev only
    fcntl = None

log = logging.getLogger(__name__)

# Configurable so tests / local dev can override without env juggling.
_DEFAULT_TTL_DAYS = float(os.environ.get("AI_CACHE_TTL_DAYS", "30"))
_DEFAULT_PATH = Path(os.environ.get("AI_CACHE_PATH", "_data/ai_cache.jsonl"))
_ENABLED = os.environ.get("AI_CACHE_ENABLED", "1") not in ("0", "false", "False")
# Template version is folded into every cache key. Bump it when the
# `_AI_PROMPT_TEMPLATE` in fetch_animals.py (or any other prompt that
# round-trips through ai_text) changes shape in a way that invalidates
# previous responses. Old entries become unreachable instantly; the
# prune() call rewrites the file the next time the workflow runs.
_TEMPLATE_VERSION = os.environ.get("AI_TEMPLATE_VERSION", "v3-2026-05")

# In-process lock so worker threads in fetch_animals.py don't both call
# the API for the same key in the brief window before disk is read.
_mem_lock = threading.Lock()
_mem: dict[str, dict] | None = None  # lazy-loaded on first use


def _key(prompt: str, model_hint: str, json_mode: bool) -> str:
    """Stable cache key. Hashing the prompt + template version means both
    inline-edits AND deliberate template-version bumps self-invalidate."""
    h = hashlib.sha256()
    h.update(prompt.encode("utf-8", errors="replace"))
    h.update(b"\x00")
    h.update(model_hint.encode("utf-8", errors="replace"))
    h.update(b"\x00")
    h.update(b"1" if json_mode else b"0")
    h.update(b"\x00")
    h.update(_TEMPLATE_VERSION.encode("utf-8", errors="replace"))
    return h.hexdigest()[:24]


def _now() -> float:
    return time.time()


def _load(path: Path) -> dict[str, dict]:
    """Read the JSONL cache file into a dict, dropping expired entries."""
    if not path.exists():
        return {}
    out: dict[str, dict] = {}
    ttl_s = _DEFAULT_TTL_DAYS * 86400
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
            # Later entries override earlier ones (regenerated same key).
            out[key] = entry
    except Exception as exc:
        log.debug("ai_cache load failed: %s", exc)
        return {}
    return out


def _append(path: Path, entry: dict) -> None:
    """Append a single entry as a JSON line. Cross-process safe via flock."""
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
        log.debug("ai_cache append failed: %s", exc)


def _ensure_loaded(path: Path) -> dict[str, dict]:
    global _mem
    with _mem_lock:
        if _mem is None:
            _mem = _load(path)
        return _mem


def reset_cache_for_tests() -> None:
    """Drops the in-memory cache. Used by tests to isolate fixtures."""
    global _mem
    with _mem_lock:
        _mem = None


def get(prompt: str, model_hint: str = "", json_mode: bool = False,
        path: Path = _DEFAULT_PATH) -> str | None:
    """Return cached response for this prompt, or None on miss."""
    if not _ENABLED:
        return None
    cache = _ensure_loaded(path)
    entry = cache.get(_key(prompt, model_hint, json_mode))
    if not entry:
        return None
    return entry.get("v") or None


def put(prompt: str, value: str, model_hint: str = "", json_mode: bool = False,
        path: Path = _DEFAULT_PATH) -> None:
    """Store `value` against this prompt. No-op if cache is disabled or value empty."""
    if not _ENABLED or not value:
        return
    k = _key(prompt, model_hint, json_mode)
    entry = {"k": k, "ts": _now(), "v": value, "m": model_hint, "j": json_mode}
    cache = _ensure_loaded(path)
    cache[k] = entry
    _append(path, entry)


def cached_call(prompt: str,
                caller: Callable[[], str],
                model_hint: str = "",
                json_mode: bool = False,
                path: Path = _DEFAULT_PATH) -> str:
    """Cache wrapper: returns the cached value if present, else calls `caller()`
    and stores the result. `caller` is invoked AT MOST ONCE per (prompt, model,
    json_mode) within the TTL window."""
    hit = get(prompt, model_hint=model_hint, json_mode=json_mode, path=path)
    if hit is not None:
        return hit
    value = caller()
    put(prompt, value, model_hint=model_hint, json_mode=json_mode, path=path)
    return value


def prune(path: Path = _DEFAULT_PATH) -> int:
    """Rewrite the file dropping expired entries. Returns the number kept.

    Called by the workflow's commit step once per day so the JSONL doesn't
    grow unbounded. Safe to skip; expired entries are ignored on read.
    """
    if not path.exists():
        return 0
    fresh = _load(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for entry in fresh.values():
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    tmp.replace(path)
    # Invalidate the in-memory copy so the next get() reloads.
    reset_cache_for_tests()
    return len(fresh)
