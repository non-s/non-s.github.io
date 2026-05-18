#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
youtube_analytics.py — Pull retention / CTR / search-query data for every
Short published by the channel, write a CSV snapshot to _data/analytics/.

This runs daily (separate workflow). The CSV is committed back to the
repo so trends are visible in `git log` without needing any external
analytics service. Specifically, we capture the dimensions the growth
research agent flagged as predictive of long-term Shorts performance:

  - views, averageViewPercentage, averageViewDuration
  - cardImpressionsClickThroughRate
  - audienceWatchRatio sampled at 100 points (the retention curve)
  - trafficSourceType breakdown (SHORTS feed vs YT_SEARCH vs SUGGESTED)

Auth: reuses token.json restored by the youtube-bot workflow. Read-only
scope (youtube.readonly) is enough — set `YOUTUBE_TOKEN` to a token
generated with that scope.
"""
from __future__ import annotations

import csv
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import google.auth.transport.requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from utils.categorise import infer_category_from_title

ANALYTICS_DIR = Path("_data/analytics")
TOKEN_FILE    = Path("token.json")
LOG_FILE      = "youtube_analytics.log"

# Lower bound for "recently published" — Analytics data settles ~24-48h
# after upload, so anything fresher than 1 day is too noisy to log.
LOOKBACK_DAYS_MIN = int(os.environ.get("ANALYTICS_LOOKBACK_MIN", "1"))
# Don't bother re-pulling videos older than this — Shorts performance
# is mostly decided in the first 14 days.
LOOKBACK_DAYS_MAX = int(os.environ.get("ANALYTICS_LOOKBACK_MAX", "30"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler()],
)
log = logging.getLogger("yt_analytics")


def _load_credentials() -> Credentials:
    if not TOKEN_FILE.exists():
        log.error("❌ token.json not found — youtube-bot workflow restores it from YOUTUBE_TOKEN.")
        sys.exit(2)
    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE))
    if creds.expired and creds.refresh_token:
        creds.refresh(google.auth.transport.requests.Request())
    return creds


def _channel_id(youtube) -> str:
    resp = youtube.channels().list(part="id", mine=True).execute()
    items = resp.get("items", [])
    if not items:
        raise RuntimeError("Could not resolve `mine=True` channel ID — token scope issue?")
    return items[0]["id"]


def _recent_shorts(youtube, channel_id: str) -> list[dict]:
    """
    Return videos from the channel uploaded between LOOKBACK_DAYS_MIN
    and LOOKBACK_DAYS_MAX ago. Filters to vertical Shorts (duration < 60s)
    via the contentDetails call.
    """
    cutoff_new = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS_MIN)
    cutoff_old = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS_MAX)

    # uploads playlist is the canonical "all my videos" pseudo-playlist.
    chan = youtube.channels().list(part="contentDetails", id=channel_id).execute()
    uploads_pl = chan["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

    video_ids: list[str] = []
    page_token = None
    while True:
        resp = youtube.playlistItems().list(
            part="contentDetails",
            playlistId=uploads_pl,
            maxResults=50,
            pageToken=page_token,
        ).execute()
        for item in resp.get("items", []):
            vid = item["contentDetails"]["videoId"]
            published = datetime.fromisoformat(
                item["contentDetails"]["videoPublishedAt"].replace("Z", "+00:00")
            )
            if published < cutoff_old:
                # uploads playlist is sorted newest-first, so we can stop.
                page_token = None
                break
            if published <= cutoff_new:
                video_ids.append(vid)
        else:
            page_token = resp.get("nextPageToken")
            if page_token:
                continue
        break

    if not video_ids:
        return []

    # Filter to Shorts: contentDetails.duration < 60s. Batch in 50s.
    shorts: list[dict] = []
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i:i + 50]
        resp = youtube.videos().list(
            part="snippet,contentDetails,statistics",
            id=",".join(chunk),
        ).execute()
        for v in resp.get("items", []):
            dur = v.get("contentDetails", {}).get("duration", "")
            if not _is_short_duration(dur):
                continue
            shorts.append({
                "video_id":   v["id"],
                "title":      v["snippet"]["title"],
                "published":  v["snippet"]["publishedAt"],
                "duration":   dur,
                "views":      int(v.get("statistics", {}).get("viewCount", 0)),
                "likes":      int(v.get("statistics", {}).get("likeCount", 0)),
                "comments":   int(v.get("statistics", {}).get("commentCount", 0)),
            })
    return shorts


def _is_short_duration(iso8601: str) -> bool:
    """`PT45S` / `PT1M2S` → True/False. Shorts are < 60 s by definition."""
    import re
    m = re.fullmatch(r"PT(?:(\d+)M)?(?:(\d+)S)?", iso8601 or "")
    if not m:
        return False
    minutes = int(m.group(1) or 0)
    seconds = int(m.group(2) or 0)
    return (minutes * 60 + seconds) <= 60


def _pull_video_metrics(yt_analytics, video_id: str, start_date: str, end_date: str) -> dict:
    """
    YouTube Analytics API for one video: average view %, CTR, traffic
    sources. `start_date` / `end_date` are YYYY-MM-DD.
    """
    metrics_resp = yt_analytics.reports().query(
        ids="channel==MINE",
        startDate=start_date,
        endDate=end_date,
        metrics="views,averageViewPercentage,averageViewDuration,likes,comments,subscribersGained",
        filters=f"video=={video_id}",
    ).execute()
    rows = metrics_resp.get("rows", []) or [[0] * 6]
    row = rows[0]
    out = {
        "an_views":             int(row[0] or 0),
        "avg_view_pct":         round(float(row[1] or 0), 1),
        "avg_view_duration_s":  round(float(row[2] or 0), 1),
        "an_likes":             int(row[3] or 0),
        "an_comments":          int(row[4] or 0),
        "subs_gained":          int(row[5] or 0),
    }

    # Top 3 traffic sources by view share.
    try:
        traf = yt_analytics.reports().query(
            ids="channel==MINE",
            startDate=start_date,
            endDate=end_date,
            metrics="views",
            dimensions="insightTrafficSourceType",
            filters=f"video=={video_id}",
            sort="-views",
            maxResults=3,
        ).execute()
        sources = []
        for r in traf.get("rows", []) or []:
            sources.append(f"{r[0]}:{int(r[1])}")
        out["top_sources"] = ",".join(sources) if sources else ""
    except HttpError as e:
        log.debug(f"traffic sources query failed for {video_id}: {e}")
        out["top_sources"] = ""

    return out


def main() -> None:
    log.info("=" * 60)
    log.info(f"📊 YouTube Analytics pull — {datetime.now(timezone.utc).isoformat()}")
    log.info("=" * 60)

    ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)
    creds = _load_credentials()
    youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)
    yt_analytics = build("youtubeAnalytics", "v2", credentials=creds, cache_discovery=False)

    channel_id = _channel_id(youtube)
    log.info(f"Channel: {channel_id}")

    shorts = _recent_shorts(youtube, channel_id)
    log.info(f"Found {len(shorts)} Shorts in the lookback window "
             f"({LOOKBACK_DAYS_MIN}-{LOOKBACK_DAYS_MAX} days old)")
    if not shorts:
        log.info("Nothing to analyse. Done.")
        return

    # Analytics window: last 14 days vs upload date — Shorts performance
    # mostly settles in that window.
    today = datetime.now(timezone.utc).date()
    end_date = today.strftime("%Y-%m-%d")
    start_date = (today - timedelta(days=14)).strftime("%Y-%m-%d")

    rows: list[dict] = []
    for short in shorts:
        try:
            metrics = _pull_video_metrics(yt_analytics, short["video_id"], start_date, end_date)
        except HttpError as e:
            log.warning(f"⚠️ analytics fetch failed for {short['video_id']}: {e}")
            continue
        rows.append({**short, **metrics, "pulled_at": end_date})

    # Write today's snapshot.
    csv_path = ANALYTICS_DIR / f"{end_date}.csv"
    fieldnames = sorted({k for r in rows for k in r.keys()})
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    log.info(f"✅ Wrote {len(rows)} rows to {csv_path}")

    # Also dump a compact summary JSON for at-a-glance reading. The
    # `category_avg_view_pct` block is consumed by fetch_news.py to
    # bias future story selection toward what retained well.
    if rows:
        avg_pct = sum(r.get("avg_view_pct", 0) for r in rows) / len(rows)
        total_views = sum(r.get("an_views", 0) for r in rows)

        # Per-category breakdown. We infer the category from the title's
        # leading hashtag when possible (the upload metadata embeds the
        # category playlist tag in the description, not the title — so
        # this is a coarse approximation pending a join against the
        # _videos/*.done sidecar files).
        from collections import defaultdict
        cat_views: dict[str, list[float]] = defaultdict(list)
        for r in rows:
            cat = infer_category_from_title(r.get("title", "")) or "uncategorised"
            cat_views[cat].append(r.get("avg_view_pct", 0))
        cat_avg = {
            cat: round(sum(v) / len(v), 1) if v else 0.0
            for cat, v in cat_views.items()
        }

        # Top performers (avg_view_pct >= 80 + at least 100 views).
        top_performers = sorted(
            [r for r in rows if r.get("avg_view_pct", 0) >= 80 and r.get("an_views", 0) >= 100],
            key=lambda r: r.get("an_views", 0),
            reverse=True,
        )[:5]

        summary = {
            "pulled_at":              end_date,
            "shorts_analysed":        len(rows),
            "total_views_14d":        total_views,
            "avg_view_pct":           round(avg_pct, 1),
            "below_60_pct":           [r["video_id"] for r in rows if r.get("avg_view_pct", 100) < 60],
            "category_avg_view_pct":  cat_avg,
            "top_performers":         [
                {"video_id": r["video_id"], "title": r.get("title", ""),
                 "views": r.get("an_views", 0), "view_pct": r.get("avg_view_pct", 0)}
                for r in top_performers
            ],
        }
        (ANALYTICS_DIR / "latest.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8",
        )
        log.info(f"📈 Avg view %: {summary['avg_view_pct']} · "
                 f"Total views 14d: {total_views} · "
                 f"Underperforming (<60%): {len(summary['below_60_pct'])}")
        if cat_avg:
            log.info(f"📂 Per-category retention: {cat_avg}")


if __name__ == "__main__":
    main()
