#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tiktok_analytics.py — Pull view/like/comment/share metrics for every
Short published by the channel, write a CSV snapshot under
`_data/analytics/`.

This runs daily (separate workflow). The CSV is committed back to the
repo so trends are visible in `git log` without any external service.

TikTok's Display API surfaces a SHORTER list of metrics than YouTube's
Analytics API exposed — but it covers the dimensions the growth
research flagged as most predictive of long-term Shorts performance on
the For You feed:

  - view_count, like_count, comment_count, share_count
  - title (caption) so we can back-classify category
  - create_time so we can window properly

Endpoint: POST /v2/video/list/ (own videos) + /v2/video/query/ (by id).

Auth: reuses tiktok_token.json restored by the tiktok-bot workflow.
"""
from __future__ import annotations

import csv
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from utils.categorise import infer_category_from_title
from utils.experiments import compute_winners, write_winners

ANALYTICS_DIR = Path("_data/analytics")
TOKEN_FILE    = Path("tiktok_token.json")
LOG_FILE      = "tiktok_analytics.log"

# Lower bound: TikTok metrics settle within minutes (vs. YouTube's
# ~24h), but we keep a 1-day floor to align with the daily-digest run.
LOOKBACK_DAYS_MIN = int(os.environ.get("ANALYTICS_LOOKBACK_MIN", "1"))
LOOKBACK_DAYS_MAX = int(os.environ.get("ANALYTICS_LOOKBACK_MAX", "30"))

API_BASE       = "https://open.tiktokapis.com"
USER_INFO_URL  = f"{API_BASE}/v2/user/info/"
VIDEO_LIST_URL = f"{API_BASE}/v2/video/list/"

# Fields we ask for from TikTok. `cover_image_url` we don't need; keep
# the list tight to stay under the documented field-bytes ceiling.
VIDEO_FIELDS = (
    "id,title,create_time,duration,share_url,"
    "view_count,like_count,comment_count,share_count"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler()],
)
log = logging.getLogger("tiktok_analytics")


# ── Auth + token refresh ────────────────────────────────────────────

def _load_access_token() -> str:
    """Read tiktok_token.json (refresh if expired) and return access_token."""
    if not TOKEN_FILE.exists():
        log.error("❌ tiktok_token.json not found — tiktok-bot workflow "
                  "restores it from TIKTOK_TOKEN.")
        sys.exit(2)
    # Reuse upload_tiktok.get_access_token so the refresh logic lives
    # in exactly one place.
    from upload_tiktok import get_access_token
    access_token, _ = get_access_token()
    return access_token


# ── API helpers ──────────────────────────────────────────────────────

def _post_json(url: str, access_token: str, body: dict | None = None,
                params: dict | None = None) -> dict:
    resp = requests.post(
        url,
        params=params,
        json=body or {},
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type":  "application/json; charset=UTF-8",
        },
        timeout=30,
    )
    try:
        payload = resp.json()
    except Exception:
        payload = {"raw": resp.text[:500]}
    if resp.status_code >= 400:
        raise RuntimeError(
            f"TikTok API {url} → HTTP {resp.status_code}: {payload}"
        )
    err = (payload.get("error") or {})
    if err and err.get("code") and err["code"] not in ("ok", ""):
        raise RuntimeError(f"TikTok API {url} → error {err}")
    return payload


def _list_user_videos(access_token: str,
                       cutoff_old: datetime) -> list[dict]:
    """Page through /v2/video/list/ until videos older than cutoff appear."""
    videos: list[dict] = []
    cursor: int = 0
    has_more = True
    while has_more:
        body = {"max_count": 20}
        if cursor:
            body["cursor"] = cursor
        payload = _post_json(
            VIDEO_LIST_URL, access_token, body=body,
            params={"fields": VIDEO_FIELDS},
        )
        data = payload.get("data") or {}
        for v in data.get("videos") or []:
            ts = v.get("create_time")
            try:
                created = datetime.fromtimestamp(int(ts or 0), tz=timezone.utc)
            except Exception:
                continue
            if created < cutoff_old:
                has_more = False
                break
            videos.append(v)
        cursor = int(data.get("cursor") or 0)
        has_more = has_more and bool(data.get("has_more")) and cursor > 0
    return videos


# ── Local sidecar joins (experiments, category) ─────────────────────

_VIDEO_DIRS = (Path("_videos"), Path("_videos_pt-BR"),
               Path("_videos_es-ES"), Path("_videos_fr-FR"))


def _experiments_for_video(video_id: str) -> dict[str, str]:
    """Look up the variant assignments for `video_id` from .done sidecars.

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


# ── Anomaly + summary writers (shared shape with previous design) ────

def _write_anomaly_check() -> None:
    """Compare today's CSV total views against the 7-day baseline.

    Writes `_data/analytics/anomaly.json` with `{flagged, today_total,
    baseline_mean, drop_pct, reason}`. The daily digest reads it.
    """
    today = datetime.now(timezone.utc).date()
    today_path = ANALYTICS_DIR / f"{today.strftime('%Y-%m-%d')}.csv"
    if not today_path.exists():
        return

    def _total(path: Path) -> int:
        try:
            with path.open(encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
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
        return
    baseline_mean = sum(baseline) / len(baseline)
    drop_pct = round((1 - today_total / baseline_mean) * 100, 1) if baseline_mean else 0.0
    flagged = today_total > 0 and drop_pct >= 50.0
    payload = {
        "checked_at":    datetime.now(timezone.utc).isoformat(),
        "today_total":   today_total,
        "baseline_mean": round(baseline_mean, 1),
        "drop_pct":      drop_pct,
        "flagged":       flagged,
        "reason":        (f"today's {today_total} views vs 7-day baseline "
                          f"{baseline_mean:.0f} = {drop_pct} % drop"
                          if flagged else "within normal range"),
    }
    (ANALYTICS_DIR / "anomaly.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8",
    )
    if flagged:
        log.warning("🚨 ANOMALY: %s", payload["reason"])


# ── Main driver ─────────────────────────────────────────────────────

def _row_from_video(v: dict, end_date: str) -> dict:
    """Project the TikTok API response into the analytics CSV row shape.

    We keep the same column names the rest of the pipeline already
    expects (`an_views`, `avg_view_pct`, etc.) so dashboards + the
    digest don't have to change. TikTok doesn't expose
    `averageViewPercentage` on the Display API, so we leave it 0;
    operators who care can paste it in manually from the TikTok
    Studio dashboard.
    """
    vid = str(v.get("id", ""))
    views    = int(v.get("view_count")    or 0)
    likes    = int(v.get("like_count")    or 0)
    comments = int(v.get("comment_count") or 0)
    shares   = int(v.get("share_count")   or 0)
    title    = (v.get("title") or "").strip()
    create_ts = int(v.get("create_time") or 0)
    create_iso = (datetime.fromtimestamp(create_ts, tz=timezone.utc).isoformat()
                  if create_ts else "")
    return {
        "video_id":         vid,
        "title":            title,
        "published":        create_iso,
        "duration":         int(v.get("duration") or 0),
        "views":            views,
        "likes":            likes,
        "comments":         comments,
        "shares":           shares,
        # Legacy column names the dashboard reads.
        "an_views":         views,
        "an_likes":         likes,
        "an_comments":      comments,
        "an_shares":        shares,
        # Not exposed by TikTok Display API.
        "avg_view_pct":         0.0,
        "avg_view_duration_s":  0.0,
        "subs_gained":          0,
        "impressions":          0,
        "impression_ctr":       0.0,
        "top_sources":          "",
        "geo_top5":             "",
        "pulled_at":            end_date,
        "share_url":            v.get("share_url") or "",
        "experiments":          _experiments_for_video(vid),
    }


def main() -> None:
    log.info("=" * 60)
    log.info("📊 TikTok Analytics pull — %s",
             datetime.now(timezone.utc).isoformat())
    log.info("=" * 60)

    ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)
    access_token = _load_access_token()

    cutoff_old = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS_MAX)

    videos = _list_user_videos(access_token, cutoff_old)
    log.info("Found %d videos in the lookback window (≤ %d days old)",
             len(videos), LOOKBACK_DAYS_MAX)
    if not videos:
        log.info("Nothing to analyse. Done.")
        return

    today = datetime.now(timezone.utc).date()
    end_date = today.strftime("%Y-%m-%d")

    rows = [_row_from_video(v, end_date) for v in videos]

    # Write today's CSV snapshot.
    csv_path = ANALYTICS_DIR / f"{end_date}.csv"
    fieldnames = sorted({k for r in rows for k in r.keys()})
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in fieldnames})
    log.info("✅ Wrote %d rows to %s", len(rows), csv_path)

    # Summary JSON for at-a-glance reading. Categories are inferred from
    # title text since TikTok doesn't carry our hashtag-derived category
    # field on the platform side.
    if rows:
        total_views = sum(r["views"] for r in rows)
        total_likes = sum(r["likes"] for r in rows)
        total_comments = sum(r["comments"] for r in rows)
        total_shares = sum(r["shares"] for r in rows)
        engagement_rates = [
            (r["likes"] + r["comments"] + r["shares"]) / r["views"]
            for r in rows if r["views"] > 0
        ]
        avg_engagement_pct = (
            round(100 * sum(engagement_rates) / len(engagement_rates), 2)
            if engagement_rates else 0.0
        )

        from collections import defaultdict
        cat_views: dict[str, list[int]] = defaultdict(list)
        for r in rows:
            cat = infer_category_from_title(r.get("title", "")) or "uncategorised"
            cat_views[cat].append(r["views"])
        cat_avg = {
            cat: round(sum(v) / len(v), 1) if v else 0.0
            for cat, v in cat_views.items()
        }

        top_performers = sorted(
            rows, key=lambda r: r["views"], reverse=True
        )[:5]

        summary = {
            "pulled_at":              end_date,
            "shorts_analysed":        len(rows),
            "total_views_14d":        total_views,
            "total_likes":            total_likes,
            "total_comments":         total_comments,
            "total_shares":           total_shares,
            "avg_engagement_pct":     avg_engagement_pct,
            # Kept for dashboard backwards-compat (avg_view_pct doesn't
            # exist on TikTok). We surface engagement rate instead.
            "avg_view_pct":           avg_engagement_pct,
            "below_60_pct":           [],
            "category_avg_view_pct":  cat_avg,
            "top_performers":         [
                {"video_id": r["video_id"], "title": r["title"],
                 "views":    r["views"],    "view_pct": 0,
                 "share_url": r["share_url"]}
                for r in top_performers
            ],
        }
        (ANALYTICS_DIR / "latest.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8",
        )
        log.info("📈 Total views: %d · likes: %d · comments: %d · shares: %d "
                 "· engagement: %.2f%%",
                 total_views, total_likes, total_comments, total_shares,
                 avg_engagement_pct)
        if cat_avg:
            log.info("📂 Per-category mean views: %s", cat_avg)

    _write_anomaly_check()

    # ── A/B winner computation (engagement-blended score) ────────────
    def _engagement_score(r: dict) -> float:
        v = r.get("views") or 0
        if not v:
            return 0.0
        return 100.0 * (r["likes"] + r["comments"] + r["shares"]) / v

    observations = [
        {"experiments": r.get("experiments") or {},
         "score":       _engagement_score(r)}
        for r in rows
        if isinstance(r.get("experiments"), dict)
        and r.get("experiments")
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
