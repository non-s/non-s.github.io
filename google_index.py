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

def parse_frontmatter(text: str) -> dict:
    """Minimal YAML frontmatter parser — no external deps."""
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    raw = parts[1]
    data: dict = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if val.startswith("[") and val.endswith("]"):
            items = [v.strip().strip('"').strip("'") for v in val[1:-1].split(",")]
            data[key] = items
        else:
            data[key] = val
    return data


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
    cats = frontmatter.get("categories", [])
    category = (cats[0] if isinstance(cats, list) and cats else "news").strip()
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
        fm = parse_frontmatter(text)
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
    """
    Submit a single URL to the Google Indexing API.
    Returns True on success, False on failure.
    """
    payload = {"url": url, "type": "URL_UPDATED"}
    try:
        resp = requests.post(
            INDEXING_ENDPOINT,
            headers=headers,
            data=json.dumps(payload),
            timeout=30,
        )
        if resp.status_code == 200:
            log.info("Indexed — %s", url)
            return True
        elif resp.status_code == 403:
            log.warning(
                "403 Forbidden — service account not verified as owner of this site. "
                "Fix: go to search.google.com/search-console → Settings → Users and permissions "
                "→ Add user → %s (Owner). Skipping URL submission.",
                "globalbr-news@techbr-youtube-bot.iam.gserviceaccount.com",
            )
            return False
        else:
            log.warning(
                "Failed to index %s — HTTP %s: %s",
                url,
                resp.status_code,
                resp.text[:200],
            )
            return False
    except requests.RequestException as exc:
        log.error("Request error for %s: %s", url, exc)
        return False


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
