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
from utils.experiments import compute_winners, write_winners

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


_VIDEO_DIRS = (Path("_videos"), Path("_videos_pt-BR"),
               Path("_videos_es-ES"), Path("_videos_fr-FR"))

# Map ISO 3166 codes to (city, UTC offset hours). Just the codes that
# show up frequently in the wild — extend as the channel grows. Offsets
# are non-DST baselines; the recommender only needs hour-resolution.
_COUNTRY_OFFSETS: dict[str, int] = {
    "US": -5,   # ET — biggest single market, EST
    "GB": 0,
    "BR": -3,
    "IN": 5,    # rounded down from 5.5h
    "MX": -6,
    "CA": -5,
    "AU": 10,
    "DE": 1,
    "FR": 1,
    "ES": 1,
    "IT": 1,
    "JP": 9,
    "KR": 9,
    "PH": 8,
    "NG": 1,
    "ZA": 2,
    "AR": -3,
    "CL": -4,
    "CO": -5,
    "EG": 2,
    "TR": 3,
    "ID": 7,
    "PT": 0,
    "PL": 1,
    "NL": 1,
    "SE": 1,
    "RU": 3,
}


def _cohort_optimal_utc_hours(geo_views: dict[str, dict[str, int]]) -> dict:
    """Aggregate views by country, return suggested UTC posting hours.

    Strategy: for each top country, the local evening peak is 18:00.
    Convert that to UTC. Final output recommends the three best
    posting slots (one per top-3 country market, deduplicated).
    """
    totals: dict[str, int] = {}
    for video_geo in geo_views.values():
        for country, views in video_geo.items():
            totals[country] = totals.get(country, 0) + int(views or 0)
    if not totals:
        return {"top_countries": [], "recommended_utc_hours": []}
    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:10]
    suggestions: list[dict] = []
    hours_seen: set[int] = set()
    for country, views in ranked:
        offset = _COUNTRY_OFFSETS.get(country)
        if offset is None:
            continue
        # Local 18:00 in UTC.
        local_target = 18
        utc_hour = (local_target - offset) % 24
        if utc_hour in hours_seen:
            continue
        hours_seen.add(utc_hour)
        suggestions.append({
            "country":         country,
            "views":           views,
            "local_offset_h":  offset,
            "utc_hour":        utc_hour,
        })
        if len(suggestions) >= 3:
            break
    return {
        "top_countries":          [{"country": c, "views": v}
                                    for c, v in ranked[:5]],
        "recommended_utc_hours":  suggestions,
    }


def _write_anomaly_check() -> None:
    """Compare today's CSV total views against the 7-day baseline.

    Writes `_data/analytics/anomaly.json` with `{flagged, today_total,
    baseline_mean, drop_pct, reason}`. The daily digest reads it.
    """
    import csv as _csv
    today = datetime.now(timezone.utc).date()
    today_path = ANALYTICS_DIR / f"{today.strftime('%Y-%m-%d')}.csv"
    if not today_path.exists():
        return
    def _total(path: Path) -> int:
        try:
            with path.open(encoding="utf-8") as fh:
                reader = _csv.DictReader(fh)
                return sum(int(r.get("an_views", 0) or 0) for r in reader)
        except Exception:
            return 0

    today_total = _total(today_path)
    baseline: list[int] = []
    for d in range(1, 8):
        prev = ANALYTICS_DIR / f"{(today - timedelta(days=d)).strftime('%Y-%m-%d')}.csv"
        if prev.exists():
            t = _total(prev)
            if t > 0:
                baseline.append(t)
    if len(baseline) < 3:
        return  # not enough baseline; skip silently
    baseline_mean = sum(baseline) / len(baseline)
    drop_pct = round((1 - today_total / baseline_mean) * 100, 1) if baseline_mean else 0.0
    flagged = today_total > 0 and drop_pct >= 50.0
    payload = {
        "checked_at":     datetime.now(timezone.utc).isoformat(),
        "today_total":    today_total,
        "baseline_mean":  round(baseline_mean, 1),
        "drop_pct":       drop_pct,
        "flagged":        flagged,
        "reason":         (f"today's {today_total} views vs 7-day baseline "
                            f"{baseline_mean:.0f} = {drop_pct} % drop"
                            if flagged else "within normal range"),
    }
    (ANALYTICS_DIR / "anomaly.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8",
    )
    if flagged:
        log.warning("🚨 ANOMALY: %s", payload["reason"])


def _write_cohort_timing(row_geo: dict[str, dict[str, int]]) -> None:
    """Compute + persist `_data/analytics/cohort_timing.json`."""
    payload = _cohort_optimal_utc_hours(row_geo)
    out = ANALYTICS_DIR / "cohort_timing.json"
    try:
        out.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                        encoding="utf-8")
        if payload.get("recommended_utc_hours"):
            log.info("⏰ Audience cohort timing:")
            for s in payload["recommended_utc_hours"]:
                log.info("   %s (%d views) → %02d:00 UTC",
                         s["country"], s["views"], s["utc_hour"])
    except Exception as exc:
        log.warning("cohort timing write failed: %s", exc)


def _experiments_for_video(video_id: str) -> dict[str, str]:
    """Look up the variant assignments for `video_id` from the .done sidecars.

    Returns {} if the sidecar is missing or doesn't carry experiments
    (older Shorts that predate the A/B framework).
    """
    if not video_id:
        return {}
    for d in _VIDEO_DIRS:
        if not d.exists():
            continue
        for done_path in d.glob("*.done"):
            try:
                data = json.loads(done_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if data.get("video_id") == video_id:
                exps = data.get("experiments") or {}
                if isinstance(exps, dict):
                    return {str(k): str(v) for k, v in exps.items()}
    return {}


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


def _pull_geo_breakdown(yt_analytics, video_id: str,
                        start_date: str, end_date: str) -> dict[str, int]:
    """Top 5 countries by views for a single video.

    Returns `{ISO-3166-1: views}`. Used by the audience cohort timing
    recommender — knowing where viewers are tells us when to post.
    """
    try:
        r = yt_analytics.reports().query(
            ids="channel==MINE",
            startDate=start_date,
            endDate=end_date,
            metrics="views",
            dimensions="country",
            filters=f"video=={video_id}",
            sort="-views",
            maxResults=5,
        ).execute()
        return {row[0]: int(row[1] or 0) for row in r.get("rows", []) or []}
    except HttpError:
        return {}


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

    # CTR + impressions. cardImpressionsClickThroughRate covers in-card
    # CTR; the more relevant Shorts impression metric is
    # `cardClickRate` / `cardImpressions` and (separately)
    # `impressionsToViewRatio` for non-Shorts. We pull both and let
    # the analyser pick the one with non-zero data per row.
    try:
        ctr_resp = yt_analytics.reports().query(
            ids="channel==MINE",
            startDate=start_date,
            endDate=end_date,
            metrics="cardImpressions,cardClickRate",
            filters=f"video=={video_id}",
        ).execute()
        ctr_rows = ctr_resp.get("rows", []) or [[0, 0]]
        out["impressions"]      = int(ctr_rows[0][0] or 0)
        out["impression_ctr"]   = round(float(ctr_rows[0][1] or 0), 3)
    except HttpError as e:
        log.debug(f"CTR query failed for {video_id}: {e}")
        out["impressions"]    = 0
        out["impression_ctr"] = 0.0

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
    row_geo: dict[str, dict[str, int]] = {}
    for short in shorts:
        try:
            metrics = _pull_video_metrics(yt_analytics, short["video_id"], start_date, end_date)
        except HttpError as e:
            log.warning(f"⚠️ analytics fetch failed for {short['video_id']}: {e}")
            continue
        # Join with experiment tags from the .done sidecar so we can
        # correlate variant ↔ retention. The sidecars live in either
        # _videos/ or _videos_<lang>/; we scan both.
        experiments = _experiments_for_video(short["video_id"])
        geo_views = _pull_geo_breakdown(yt_analytics, short["video_id"],
                                          start_date, end_date)
        rows.append({**short, **metrics, "pulled_at": end_date,
                     "experiments": experiments,
                     "geo_top5":   ",".join(f"{k}:{v}" for k, v in geo_views.items())})
        # Stash geo breakdown for the cohort-timing analyser below.
        row_geo[short["video_id"]] = geo_views

    # Write today's snapshot.
    csv_path = ANALYTICS_DIR / f"{end_date}.csv"
    fieldnames = sorted({k for r in rows for k in r.keys()})
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    log.info(f"✅ Wrote {len(rows)} rows to {csv_path}")

    # Also dump a compact summary JSON for at-a-glance reading. The
    # `category_avg_view_pct` block is consumed by fetch_animals.py to
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

    # ── Audience cohort timing recommender ────────────────────────
    # Aggregate views by country across all recent Shorts, then map
    # each top country to a recommended posting hour-in-UTC (the
    # local 18:00-20:00 window for that country = "evening peak").
    # The daily-digest workflow surfaces this in the Issue body.
    _write_cohort_timing(row_geo)

    # ── Anomaly detection on view volume ──────────────────────────
    # Compare today's total against the trailing 7-day mean. A sudden
    # > 50 % drop flags as anomaly so the daily-digest issue surfaces
    # it the next morning. Could be: channel strike, API quota hit,
    # workflow misfire, or external (slow news day) — operator's job
    # to investigate.
    _write_anomaly_check()

    # ── A/B winner computation ─────────────────────────────────────
    # Build observations from the rows that have experiments + a score.
    # `score_metric` decides what we optimise. By default we use a
    # 60/40 blend of retention (avg_view_pct) and CTR — the two stages
    # of the Shorts funnel — so a thumbnail variant that lifts CTR
    # by 10 % but tanks retention by 30 % still loses.
    def _blend(r: dict) -> float:
        retention = float(r.get("avg_view_pct", 0) or 0)
        # CTR comes back as a fraction in [0, 1]. Scale to 0-100 so it
        # weighs comparably with avg_view_pct.
        ctr_pct = float(r.get("impression_ctr", 0) or 0) * 100
        return 0.6 * retention + 0.4 * ctr_pct

    observations = [
        {"experiments": r.get("experiments") or {},
         "score":       _blend(r)}
        for r in rows
        if isinstance(r.get("experiments"), dict)
        and (r.get("experiments") or {})
        and r.get("avg_view_pct") is not None
    ]
    if observations:
        winners_payload = compute_winners(observations)
        write_winners(winners_payload)
        winners = winners_payload.get("winners") or {}
        if winners:
            log.info("🏆 Experiment winners: %s",
                     ", ".join(f"{k}={v}" for k, v in winners.items()))
        else:
            stats_by_axis = winners_payload.get("axis_stats") or {}
            n_total = sum(d["n"] for v in stats_by_axis.values() for d in v.values())
            log.info("⏳ A/B framework still warming up — %d observations "
                     "across %d axes (need ≥ %d per variant per axis)",
                     n_total, len(stats_by_axis),
                     winners_payload.get("min_samples", 8))


if __name__ == "__main__":
    main()
