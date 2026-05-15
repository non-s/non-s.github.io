#!/usr/bin/env python3
"""Check source URLs in recent posts for broken links. Caches results across runs."""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import date, timedelta
from pathlib import Path

import requests

from utils.retry import retry_call

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

POSTS_DIR   = Path("_posts")
DATA_DIR    = Path("_data")
REPORT_FILE = DATA_DIR / "link_report.json"
CACHE_FILE  = DATA_DIR / "link_cache.json"
LOOKBACK_DAYS = 14   # check posts up to 2 weeks old
MAX_POSTS     = 100
TIMEOUT       = 12

_USER_AGENTS = [
    "Mozilla/5.0 (compatible; GlobalBRNews/1.0; +https://non-s.github.io)",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15",
]


def _load_cache() -> dict[str, dict]:
    """Load previously checked URLs. Keys are URLs, values are {status, date}."""
    try:
        if CACHE_FILE.exists():
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_cache(cache: dict[str, dict]) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    try:
        CACHE_FILE.write_text(json.dumps(cache, indent=2), encoding="utf-8")
    except Exception as e:
        log.warning("Could not save link cache: %s", e)


def _check_url(url: str, attempt_num: int = 0) -> int:
    """HEAD request → status code, or 0 on error."""
    ua = _USER_AGENTS[attempt_num % len(_USER_AGENTS)]

    def _do_head() -> int:
        r = requests.head(
            url, timeout=TIMEOUT, allow_redirects=True,
            headers={"User-Agent": ua},
        )
        return r.status_code

    result = retry_call(_do_head, max_attempts=2, base_delay=3.0, default=0)
    return result or 0


def main() -> None:
    cutoff = date.today() - timedelta(days=LOOKBACK_DAYS)
    cache = _load_cache()
    today_str = date.today().isoformat()

    broken, ok, skipped, cached_ok = [], [], [], []

    posts = sorted(POSTS_DIR.glob("*.md"), reverse=True)[:MAX_POSTS]
    for post_path in posts:
        fname = post_path.name
        try:
            date_str = "-".join(fname.split("-")[:3])
            if date.fromisoformat(date_str) < cutoff:
                break
        except Exception:
            continue

        try:
            content = post_path.read_text(encoding="utf-8", errors="replace")
            m = re.search(r"^source_url:\s*(.+)$", content, re.MULTILINE)
            if not m:
                continue
            url = m.group(1).strip().strip('"').strip("'")
            if not url.startswith("http"):
                continue

            # Cache hit — skip re-check if checked today and was OK
            if url in cache:
                cached = cache[url]
                if cached.get("date") == today_str and cached.get("status", 0) < 400:
                    cached_ok.append({"file": fname, "url": url, "status": cached["status"]})
                    continue

            status = _check_url(url)
            cache[url] = {"status": status, "date": today_str}

            if status == 0:
                skipped.append({"file": fname, "url": url, "error": "no response"})
            elif status < 400:
                ok.append({"file": fname, "url": url, "status": status})
            else:
                broken.append({"file": fname, "url": url, "status": status})
                log.warning("Broken: %s (%d)", url, status)

        except Exception as e:
            log.warning("Error reading %s: %s", post_path, e)

    _save_cache(cache)

    report = {
        "date": today_str,
        "checked": len(ok) + len(broken),
        "cached_ok": len(cached_ok),
        "ok": len(ok),
        "broken": len(broken),
        "broken_list": broken,
        "skipped": len(skipped),
    }

    DATA_DIR.mkdir(exist_ok=True)
    REPORT_FILE.write_text(json.dumps(report, indent=2), encoding="utf-8")
    log.info(
        "Done: %d OK, %d cached-ok, %d broken, %d skipped",
        len(ok), len(cached_ok), len(broken), len(skipped),
    )


if __name__ == "__main__":
    main()
