#!/usr/bin/env python3
"""
submit_urls.py — Submit newly published URLs to Bing Webmaster and IndexNow.

Reads new post filenames from git diff HEAD~1, builds their permalinks,
and submits them to Bing and/or IndexNow APIs.

Env vars:
  BING_API_KEY  — Bing Webmaster API subscription key (optional)
  INDEXNOW_KEY  — IndexNow key (optional)
  SITE_URL      — Base URL (default: https://non-s.github.io)
"""
import logging
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

POSTS_DIR = Path(__file__).parent / "_posts"
SITE_URL  = os.environ.get("SITE_URL", "https://non-s.github.io").rstrip("/")
BING_KEY  = os.environ.get("BING_API_KEY", "").strip()
INOW_KEY  = os.environ.get("INDEXNOW_KEY", "").strip()
MAX_URLS  = 20


def get_new_post_files() -> list[Path]:
    """Returns list of _posts/*.md files added in the last git commit."""
    try:
        proc = subprocess.run(
            ["git", "diff", "HEAD~1", "--name-only", "--diff-filter=A"],
            cwd=str(POSTS_DIR.parent),
            capture_output=True, text=True, timeout=15,
        )
        if proc.returncode != 0:
            return []
        files = []
        for line in proc.stdout.strip().splitlines():
            if line.startswith("_posts/") and line.endswith(".md"):
                p = POSTS_DIR.parent / line
                if p.exists():
                    files.append(p)
        return files[:MAX_URLS]
    except Exception as exc:
        log.warning("git diff failed: %s", exc)
        return []


def build_url(path: Path) -> str | None:
    """Build permalink from post filename and frontmatter categories."""
    stem = path.stem
    parts = stem.split("-", 3)
    if len(parts) < 4:
        return None
    year, month, day, slug = parts
    if not (year.isdigit() and month.isdigit() and day.isdigit()):
        return None
    # Read category from frontmatter
    category = "news"
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("categories:"):
                m = re.search(r'\[([^\]]+)\]', line)
                if m:
                    cats = [c.strip().strip('"').strip("'") for c in m.group(1).split(",")]
                    if cats:
                        category = cats[0]
                break
    except Exception:
        pass
    return f"{SITE_URL}/{category}/{year}/{month}/{day}/{slug}/"


def retry_post(url: str, **kwargs) -> requests.Response | None:
    """POST with up to 3 retries on transient errors."""
    for attempt in range(3):
        try:
            resp = requests.post(url, timeout=20, **kwargs)
            if resp.status_code in (429, 503):
                wait = int(resp.headers.get("Retry-After", 15))
                log.warning("Rate limited (%s) — waiting %ds", resp.status_code, wait)
                time.sleep(wait)
                continue
            return resp
        except requests.exceptions.RequestException as exc:
            log.warning("Request failed (attempt %d/3): %s", attempt + 1, exc)
            if attempt < 2:
                time.sleep(5 * (attempt + 1))
    return None


def submit_bing(urls: list[str]) -> bool:
    if not BING_KEY:
        log.info("BING_API_KEY not set — skipping Bing submission")
        return False
    payload = {"siteUrl": SITE_URL, "urlList": urls}
    resp = retry_post(
        "https://ssl.bing.com/webmaster/api.svc/json/SubmitUrlbatch",
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Ocp-Apim-Subscription-Key": BING_KEY,
        },
        json=payload,
    )
    if resp and resp.status_code == 200:
        log.info("✅ Bing: submitted %d URL(s)", len(urls))
        return True
    log.warning("Bing submission failed: %s", resp.text[:200] if resp else "no response")
    return False


def submit_indexnow(urls: list[str], host: str = "non-s.github.io") -> bool:
    if not INOW_KEY:
        log.info("INDEXNOW_KEY not set — skipping IndexNow submission")
        return False
    payload = {
        "host":        host,
        "key":         INOW_KEY,
        "keyLocation": f"https://{host}/{INOW_KEY}.txt",
        "urlList":     urls,
    }
    ok = True
    for endpoint in ["https://api.indexnow.org/indexnow", "https://yandex.com/indexnow"]:
        resp = retry_post(
            endpoint,
            headers={"Content-Type": "application/json; charset=utf-8"},
            json=payload,
        )
        if resp and resp.status_code in (200, 202):
            log.info("✅ IndexNow (%s): submitted %d URL(s)", endpoint, len(urls))
        else:
            log.warning("IndexNow (%s) failed: %s", endpoint, resp.text[:100] if resp else "no response")
            ok = False
    return ok


def main() -> None:
    post_files = get_new_post_files()
    if not post_files:
        log.info("No new posts found — nothing to submit.")
        return

    urls = [u for f in post_files if (u := build_url(f))]
    if not urls:
        log.info("Could not build URLs for any new posts.")
        return

    log.info("Submitting %d URL(s): %s", len(urls), urls)

    submit_bing(urls)
    submit_indexnow(urls)


if __name__ == "__main__":
    main()
