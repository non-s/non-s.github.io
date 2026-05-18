"""
utils/crosspost_reddit.py — Free Reddit cross-post for Shorts.

Reddit's public OAuth API is free and doesn't require an app review.
The script app type uses a username + password (NOT the regular login
password — a separate one generated under preferences → apps) so we
can post programmatically without browser flow.

Posting strategy
----------------
For each YouTube Short we publish, we attempt one self-post (link
type) to a subreddit chosen by category — `world` → r/worldnews,
`technology` → r/technology, `business` → r/Economics, etc. The
post title is the SEO title; body is the AI-authored description.

Reddit moderates aggressively, so:

  - We post to ONE sub per Short (no spammy multi-sub crosspost)
  - We don't post the same URL twice (Reddit returns an error, we log
    and move on)
  - We don't auto-comment / vote / DM — only the single self-post

Operator should:
  - Sign up a dedicated bot account (e.g. `u/GlobalBRNews_bot`)
  - Mark it as "I am a bot, blah blah" in the profile description
  - Subscribe to the target subs so account isn't 0-karma cold
  - Avoid posting more than 1/hour to any single sub

Auth
----
Three env vars:
  REDDIT_USER_AGENT      "Mozilla/5.0 (GlobalBR News bot by /u/<handle>)"
  REDDIT_USERNAME        the bot account
  REDDIT_PASSWORD        the bot account password (NOT TOTP)
  REDDIT_CLIENT_ID       "script" app client_id from prefs/apps
  REDDIT_CLIENT_SECRET   "script" app secret

Without all five the function no-ops and logs why.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

import requests

log = logging.getLogger(__name__)

_TIMEOUT = 30


# Per-category subreddit map. Conservative — every sub here allows
# news links from established accounts. Extend with caution; banned-
# from-sub responses won't break the pipeline but waste an attempt.
SUBREDDIT_BY_CATEGORY: dict[str, str] = {
    "world":         "worldnews",
    "politics":      "politics",
    "technology":    "technology",
    "ai":            "MachineLearning",
    "business":      "Economics",
    "science":       "science",
    "health":        "health",
    "environment":   "environment",
    "security":      "cybersecurity",
    "sports":        "sports",
    "entertainment": "Entertainment",
}


def _auth_token() -> tuple[str, str] | None:
    """Return (access_token, user_agent) or None if env is incomplete."""
    user_agent = os.environ.get("REDDIT_USER_AGENT", "").strip()
    username   = os.environ.get("REDDIT_USERNAME", "").strip()
    password   = os.environ.get("REDDIT_PASSWORD", "").strip()
    client_id  = os.environ.get("REDDIT_CLIENT_ID", "").strip()
    client_sec = os.environ.get("REDDIT_CLIENT_SECRET", "").strip()
    if not all([user_agent, username, password, client_id, client_sec]):
        log.info("Reddit cross-post skipped — REDDIT_* env vars not all set")
        return None
    try:
        r = requests.post(
            "https://www.reddit.com/api/v1/access_token",
            auth=(client_id, client_sec),
            data={"grant_type": "password",
                  "username":   username,
                  "password":   password},
            headers={"User-Agent": user_agent},
            timeout=_TIMEOUT,
        )
        if r.status_code != 200:
            log.warning("Reddit auth %d: %s", r.status_code, r.text[:200])
            return None
        token = r.json().get("access_token")
        if not token:
            return None
        return token, user_agent
    except Exception as exc:
        log.warning("Reddit auth failed: %s", exc)
        return None


def crosspost_link(youtube_url: str, title: str, *,
                    category: str = "world",
                    subreddit_override: str = "") -> str | None:
    """Post a single link to the category-appropriate subreddit.

    Returns the post URL or None. Best-effort: any failure logs and
    swallows so the upload pipeline isn't blocked.
    """
    if not youtube_url:
        return None
    auth = _auth_token()
    if not auth:
        return None
    token, user_agent = auth

    sub = (subreddit_override or
           SUBREDDIT_BY_CATEGORY.get((category or "").lower(), "worldnews"))
    safe_title = (title or "").strip()[:300]
    if not safe_title:
        log.info("Reddit cross-post skipped — empty title")
        return None

    try:
        r = requests.post(
            "https://oauth.reddit.com/api/submit",
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent":    user_agent,
            },
            data={
                "sr":     sub,
                "kind":   "link",
                "title":  safe_title,
                "url":    youtube_url,
                "resubmit": "false",  # decline if URL is already posted
                "sendreplies": "false",
                "api_type": "json",
            },
            timeout=_TIMEOUT,
        )
        if r.status_code != 200:
            log.warning("Reddit submit %d: %s", r.status_code, r.text[:200])
            return None
        data = r.json().get("json", {}) or {}
        errors = data.get("errors") or []
        if errors:
            log.warning("Reddit submit returned errors: %s", errors)
            return None
        url = (data.get("data") or {}).get("url", "")
        if url:
            log.info("👽 Reddit cross-posted to r/%s: %s", sub, url)
            return url
    except Exception as exc:
        log.warning("Reddit submit failed: %s", exc)
    return None
