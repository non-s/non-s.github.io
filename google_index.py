#!/usr/bin/env python3
"""
google_index.py
Submits new post URLs to Google Search Console Indexing API for immediate indexing.

Reads _posts/ for files modified in the last 2 hours, builds their permalink,
and POSTs each URL to the Google Indexing API using a service account.

Env vars required:
  GOOGLE_INDEXING_CREDENTIALS — JSON string of the Google service account key
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

from utils.frontmatter import parse as _parse_fm, get_str, get_list
from utils.retry import retry_call

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("google_index.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
POSTS_DIR = Path(__file__).parent / "_posts"
SITE_BASE_URL = "https://non-s.github.io"
INDEXING_ENDPOINT = "https://indexing.googleapis.com/v3/urlNotifications:publish"
MAX_URLS_PER_RUN = 10
LOOKBACK_HOURS = 2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def build_post_url(filename: str, frontmatter: dict) -> str:
    """
    Build the full permalink for a post.
    Pattern: /{category}/{year}/{month}/{day}/{slug}/
    """
    stem = filename.removesuffix(".md")          # 2026-05-13-some-slug
    parts = stem.split("-", 3)                   # ['2026', '05', '13', 'some-slug']
    if len(parts) < 4:
        return f"{SITE_BASE_URL}/"
    year, month, day, slug = parts[0], parts[1], parts[2], parts[3]
    cats     = get_list(frontmatter, "categories")
    category = (cats[0] if cats else "news").strip()
    return f"{SITE_BASE_URL}/{category}/{year}/{month}/{day}/{slug}/"


def find_new_posts() -> list[tuple[str, str]]:
    """
    Return (filename, url) for posts whose file mtime is within the last LOOKBACK_HOURS.
    Limited to MAX_URLS_PER_RUN entries.
    """
    cutoff = time.time() - LOOKBACK_HOURS * 3600
    results = []
    for path in sorted(POSTS_DIR.glob("*.md"), reverse=True):
        if path.stat().st_mtime < cutoff:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        fm   = _parse_fm(text)
        url = build_post_url(path.name, fm)
        results.append((path.name, url))
        if len(results) >= MAX_URLS_PER_RUN:
            break
    return results


# ---------------------------------------------------------------------------
# Google Auth
# ---------------------------------------------------------------------------

def get_auth_headers(credentials_json: str) -> dict:
    """
    Build Authorization headers using a Google service account JSON string.
    Requires the google-auth library.
    """
    try:
        from google.oauth2 import service_account
        import google.auth.transport.requests
    except ImportError:
        log.error(
            "google-auth is not installed. Run: pip install google-auth"
        )
        sys.exit(1)

    creds = service_account.Credentials.from_service_account_info(
        json.loads(credentials_json),
        scopes=["https://www.googleapis.com/auth/indexing"],
    )
    auth_req = google.auth.transport.requests.Request()
    creds.refresh(auth_req)
    return {
        "Authorization": f"Bearer {creds.token}",
        "Content-Type": "application/json",
    }


# ---------------------------------------------------------------------------
# Indexing API
# ---------------------------------------------------------------------------

def submit_url(url: str, headers: dict) -> bool:
    """Submit a single URL to the Google Indexing API with retry. Returns True on success."""
    payload = {"url": url, "type": "URL_UPDATED"}

    def _do_submit() -> bool:
        resp = requests.post(
            INDEXING_ENDPOINT,
            headers=headers,
            data=json.dumps(payload),
            timeout=30,
        )
        if resp.status_code == 200:
            log.info("Indexed — %s", url)
            return True
        if resp.status_code == 403:
            log.warning(
                "403 Forbidden — service account not verified as owner. "
                "Fix via search.google.com/search-console → Settings → Users → Add owner."
            )
            return False
        if resp.status_code == 429:
            log.warning("Google Indexing rate limited (429) for %s", url)
            raise requests.HTTPError("429", response=resp)
        log.warning("Failed to index %s — HTTP %s: %s", url, resp.status_code, resp.text[:200])
        return False

    result = retry_call(_do_submit, max_attempts=3, base_delay=5.0, default=False)
    return bool(result)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    credentials_json = os.environ.get("GOOGLE_INDEXING_CREDENTIALS", "").strip()

    if not credentials_json:
        log.warning("GOOGLE_INDEXING_CREDENTIALS not set — skipping Google indexing.")
        sys.exit(0)

    log.info(
        "Scanning %s for posts modified in the last %d hour(s)…",
        POSTS_DIR,
        LOOKBACK_HOURS,
    )

    new_posts = find_new_posts()

    if not new_posts:
        log.info("No new posts found — nothing to submit.")
        sys.exit(0)

    log.info("Found %d new post(s) to submit (max %d):", len(new_posts), MAX_URLS_PER_RUN)
    for filename, url in new_posts:
        log.info("  • %s → %s", filename, url)

    try:
        headers = get_auth_headers(credentials_json)
    except Exception as exc:
        log.error("Failed to obtain Google auth token: %s", exc)
        sys.exit(1)

    success_count = 0
    for filename, url in new_posts:
        if submit_url(url, headers):
            success_count += 1

    log.info(
        "Done — %d/%d URL(s) submitted successfully.",
        success_count,
        len(new_posts),
    )


if __name__ == "__main__":
    main()
