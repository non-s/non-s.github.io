"""
utils/crosspost_bluesky.py — Free vertical-video cross-post to Bluesky.

Bluesky launched a vertical-video feed in Jan 2025 and the network is
now ~42M MAUs. Cross-posting the same 1080x1920 MP4 we ship to YouTube
yields measurable additional reach with zero cost — Bluesky's AT Protocol
is free, doesn't require a card, and uses app-passwords (no OAuth dance).

Auth
----
Set two env vars / repo secrets:

  BLUESKY_HANDLE      e.g. "globalbrnews.bsky.social"
  BLUESKY_APP_PASSWORD generated at https://bsky.app/settings/app-passwords
                       (NOT your main account password)

Without either, `crosspost_video()` no-ops and logs an info line. The
youtube-bot workflow can call this best-effort after every upload.

What we post
------------
- Video: the same MP4 we just shipped to YouTube
- Alt text: the SEO title (≤ 1000 chars per ATProto)
- Caption: hook + a "🎬 Watch on YouTube → URL" line

Limits
------
Bluesky caps video at 60s @ 1080p, ~50 MB. Shorts are smaller; fits.
ATProto uses chunked upload for large blobs but a single PUT is fine
under ~50 MB. We give up cleanly on any 4xx — the YouTube upload
already shipped, this is purely additive.
"""
from __future__ import annotations

import json
import logging
import mimetypes
import os
from pathlib import Path

import requests

log = logging.getLogger(__name__)

_ATP_HOST = os.environ.get("BLUESKY_PDS", "https://bsky.social")
_TIMEOUT = 60


# ── Session login ────────────────────────────────────────────────

def _login(handle: str, app_password: str) -> dict | None:
    """Create an ATProto session. Returns the session dict or None."""
    try:
        r = requests.post(
            f"{_ATP_HOST}/xrpc/com.atproto.server.createSession",
            json={"identifier": handle, "password": app_password},
            timeout=_TIMEOUT,
            headers={"Content-Type": "application/json"},
        )
        if r.status_code != 200:
            log.warning("Bluesky login %d: %s", r.status_code, r.text[:200])
            return None
        return r.json()
    except Exception as exc:
        log.warning("Bluesky login failed: %s", exc)
        return None


# ── Blob upload ──────────────────────────────────────────────────

def _upload_blob(jwt: str, path: Path, mime: str) -> dict | None:
    """Upload a single blob (image or video). Returns the blob ref dict."""
    try:
        with path.open("rb") as fh:
            r = requests.post(
                f"{_ATP_HOST}/xrpc/com.atproto.repo.uploadBlob",
                data=fh.read(),
                headers={
                    "Authorization": f"Bearer {jwt}",
                    "Content-Type":  mime,
                },
                timeout=_TIMEOUT * 3,  # large video uploads take a moment
            )
        if r.status_code != 200:
            log.warning("Bluesky uploadBlob %d: %s", r.status_code, r.text[:200])
            return None
        return r.json().get("blob")
    except Exception as exc:
        log.warning("Bluesky blob upload failed: %s", exc)
        return None


# ── Post creation ────────────────────────────────────────────────

def _create_post(jwt: str, did: str, text: str,
                 video_blob: dict | None,
                 alt_text: str = "") -> dict | None:
    """Create an app.bsky.feed.post record. Returns the record ref."""
    record: dict = {
        "$type": "app.bsky.feed.post",
        "text":  text[:300],         # ATProto cap: 300 graphemes; we cap chars
        "createdAt": _iso_now(),
        "langs": ["en"],
    }
    if video_blob:
        record["embed"] = {
            "$type": "app.bsky.embed.video",
            "video": video_blob,
            "alt": alt_text[:1000],
        }
    try:
        r = requests.post(
            f"{_ATP_HOST}/xrpc/com.atproto.repo.createRecord",
            headers={
                "Authorization": f"Bearer {jwt}",
                "Content-Type":  "application/json",
            },
            json={
                "repo":       did,
                "collection": "app.bsky.feed.post",
                "record":     record,
            },
            timeout=_TIMEOUT,
        )
        if r.status_code != 200:
            log.warning("Bluesky createRecord %d: %s", r.status_code, r.text[:300])
            return None
        return r.json()
    except Exception as exc:
        log.warning("Bluesky createRecord failed: %s", exc)
        return None


def _iso_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# ── Public API ───────────────────────────────────────────────────

def crosspost_video(video_path: Path,
                    caption: str = "",
                    alt_text: str = "",
                    youtube_url: str = "") -> str | None:
    """Cross-post `video_path` to Bluesky. Returns the post URI or None.

    Best-effort: any failure is logged and swallowed. Caller MUST treat
    this as additive — the YouTube upload always wins.
    """
    handle = os.environ.get("BLUESKY_HANDLE", "").strip()
    pw     = os.environ.get("BLUESKY_APP_PASSWORD", "").strip()
    if not handle or not pw:
        log.info("Bluesky cross-post skipped — BLUESKY_HANDLE / BLUESKY_APP_PASSWORD not set")
        return None
    if not video_path.exists():
        log.warning("Bluesky cross-post: video not found: %s", video_path)
        return None
    # Bluesky video limit is ~50 MB.
    size_mb = video_path.stat().st_size / (1024 * 1024)
    if size_mb > 48:
        log.info("Bluesky cross-post: video too large (%.1f MB > 48 MB)", size_mb)
        return None

    session = _login(handle, pw)
    if not session:
        return None
    jwt = session["accessJwt"]
    did = session["did"]

    mime = mimetypes.guess_type(str(video_path))[0] or "video/mp4"
    blob = _upload_blob(jwt, video_path, mime)
    if not blob:
        return None

    text = caption.strip()[:240] or "Latest world news on @globalbrnews."
    if youtube_url:
        text = f"{text}\n\n🎬 Watch on YouTube → {youtube_url}"[:300]

    rec = _create_post(jwt, did, text, video_blob=blob, alt_text=alt_text)
    if not rec:
        return None
    uri = rec.get("uri", "")
    log.info("🦋 Bluesky cross-posted: %s", uri)
    return uri
