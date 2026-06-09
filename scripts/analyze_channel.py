#!/usr/bin/env python3
"""Refresh free public performance metrics for uploaded Wild Brief Shorts."""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from utils.experiments import compute_winners, write_winners
from utils.growth_studio import (
    build_performance_matrix,
    remake_candidates,
    weekly_brief,
    winners_and_losers,
)
from utils.story_intelligence import classify_format, postmortem

TOKEN_FILE = ROOT / "youtube_token.json"
VIDEOS_DIR = ROOT / "_videos"
ANALYTICS_DIR = ROOT / "_data" / "analytics"
UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
READONLY_SCOPE = "https://www.googleapis.com/auth/youtube.readonly"
ANALYTICS_SCOPE = "https://www.googleapis.com/auth/yt-analytics.readonly"
FULL_YOUTUBE_SCOPE = "https://www.googleapis.com/auth/youtube"
SCOPES = [UPLOAD_SCOPE, READONLY_SCOPE]


def _load_markers(videos_dir: Path = VIDEOS_DIR) -> list[dict]:
    rows: list[dict] = []
    if not videos_dir.exists():
        return rows
    for path in sorted(videos_dir.glob("*.done")):
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(item, dict) and item.get("video_id"):
            item["_marker"] = path.name
            rows.append(item)
    return rows


def _token_grants(data: dict, *accepted_scopes: str) -> bool:
    granted = set(data.get("scopes") or [])
    return bool(granted.intersection(accepted_scopes))


def _load_service(token_file: Path = TOKEN_FILE):
    data = json.loads(token_file.read_text(encoding="utf-8"))
    if not _token_grants(data, READONLY_SCOPE, FULL_YOUTUBE_SCOPE):
        print("analytics: token lacks youtube.readonly; skipping public-stat refresh")
        return None
    creds = Credentials.from_authorized_user_info(data, SCOPES)
    if not creds.valid and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def _load_analytics_service(token_file: Path = TOKEN_FILE):
    data = json.loads(token_file.read_text(encoding="utf-8"))
    if not _token_grants(data, ANALYTICS_SCOPE, FULL_YOUTUBE_SCOPE):
        print("analytics: token lacks yt-analytics.readonly; skipping retention refresh")
        return None
    scopes = [ANALYTICS_SCOPE]
    if _token_grants(data, READONLY_SCOPE, FULL_YOUTUBE_SCOPE):
        scopes.append(READONLY_SCOPE)
    creds = Credentials.from_authorized_user_info(data, scopes)
    if not creds.valid and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build("youtubeAnalytics", "v2", credentials=creds, cache_discovery=False)


def _fetch_retention(analytics, ids: list[str]) -> dict[str, dict]:
    """Fetch retention and subscriber conversion when Analytics OAuth is available."""
    if analytics is None or not ids:
        return {}
    today = datetime.now(timezone.utc).date()
    response = analytics.reports().query(
        ids="channel==MINE",
        startDate="2005-01-01",
        endDate=today.isoformat(),
        metrics="views,averageViewDuration,averageViewPercentage,subscribersGained",
        dimensions="video",
        filters="video==" + ",".join(ids),
        maxResults=min(200, len(ids)),
    ).execute()
    headers = [item["name"] for item in response.get("columnHeaders", [])]
    return {str(row[0]): dict(zip(headers, row)) for row in response.get("rows", []) if row}


def _fetch_statistics(youtube, ids: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for start in range(0, len(ids), 50):
        response = youtube.videos().list(
            part="statistics,snippet",
            id=",".join(ids[start:start + 50]),
        ).execute()
        for item in response.get("items", []):
            out[str(item.get("id", ""))] = item
    return out


def _engagement_score(stats: dict) -> float:
    views = max(1, int(stats.get("viewCount", 0) or 0))
    likes = int(stats.get("likeCount", 0) or 0)
    comments = int(stats.get("commentCount", 0) or 0)
    return round((likes + comments * 2) * 100 / views, 3)


def _parse_dt(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def _views_per_hour(views: int, uploaded_at: str) -> float:
    uploaded = _parse_dt(uploaded_at)
    if not uploaded:
        return 0.0
    age_hours = max(1.0, (datetime.now(timezone.utc) - uploaded).total_seconds() / 3600)
    return round(views / age_hours, 3)


def _growth_score(*, views: int, views_per_hour: float, engagement_score: float,
                  average_view_percentage: float,
                  subscribers_gained: int) -> float:
    retention_bonus = average_view_percentage * 0.9 if average_view_percentage else 0.0
    subscriber_bonus = subscribers_gained * 20
    velocity_bonus = min(500.0, views_per_hour * 6)
    view_bonus = min(300.0, views / 20)
    return round(view_bonus + velocity_bonus + retention_bonus + engagement_score + subscriber_bonus, 3)


def _retention_tier(value: float) -> str:
    if value >= 80:
        return "excellent"
    if value >= 60:
        return "solid"
    if value > 0:
        return "weak"
    return "unknown"


def _keywords_from_titles(items: list[dict], limit: int = 12) -> list[str]:
    stop = {
        "about", "after", "animal", "animals", "brief", "their", "there",
        "these", "thing", "things", "watch", "where", "which", "while",
        "wild", "with", "without", "really", "secret", "secrets",
    }
    out: list[str] = []
    for item in items:
        for token in str(item.get("title") or "").lower().split():
            clean = "".join(ch for ch in token if ch.isalnum())
            if len(clean) < 5 or clean in stop or clean in out:
                continue
            out.append(clean)
            if len(out) >= limit:
                return out
    return out


def _learning_profile(top: list[dict], observations: list[dict],
                      category_growth: dict[str, float],
                      format_growth: dict[str, float]) -> dict:
    retention_tiers: dict[str, int] = defaultdict(int)
    for item in top:
        retention_tiers[_retention_tier(float(item.get("view_pct", 0) or 0))] += 1
    winners = [item for item in top if item.get("growth_score", 0) > 0][:5]
    weak = [
        item for item in top
        if 0 < float(item.get("view_pct", 0) or 0) < 60
    ]
    label_scores: dict[str, list[float]] = defaultdict(list)
    for item in observations:
        label_scores[str(item.get("humanity_label") or "unknown")].append(
            float(item.get("growth_score", 0) or 0)
        )
    avg = lambda values: round(sum(values) / len(values), 3) if values else 0.0
    return {
        "retention_tiers": dict(sorted(retention_tiers.items())),
        "winning_categories": [
            key for key, _ in sorted(category_growth.items(), key=lambda kv: kv[1], reverse=True)[:5]
        ],
        "winning_formats": [
            key for key, _ in sorted(format_growth.items(), key=lambda kv: kv[1], reverse=True)[:5]
        ],
        "winning_humanity_labels": [
            key for key, _ in sorted(
                ((key, avg(values)) for key, values in label_scores.items()),
                key=lambda kv: kv[1],
                reverse=True,
            )[:3]
        ],
        "winning_title_keywords": _keywords_from_titles(winners),
        "avoid_repeating_video_ids": [str(item.get("video_id")) for item in weak[:8]],
        "rules": [
            "Open with the animal and the surprising outcome in the first sentence.",
            "Prefer one visible animal, one concrete body detail, one because/that-is-why payoff.",
            "Repeat winning categories and formats only with a new subject angle.",
            "Do not repeat subjects from weak-retention videos until the hook shape changes.",
        ],
    }


def build_snapshot(markers: list[dict], statistics: dict[str, dict],
                   retention: dict[str, dict] | None = None) -> tuple[dict, list[dict]]:
    retention = retention or {}
    observations: list[dict] = []
    category: dict[str, list[float]] = defaultdict(list)
    category_retention: dict[str, list[float]] = defaultdict(list)
    category_growth: dict[str, list[float]] = defaultdict(list)
    format_growth: dict[str, list[float]] = defaultdict(list)
    series: dict[str, list[float]] = defaultdict(list)
    humanity_scores: list[float] = []
    humanity_by_label: dict[str, int] = defaultdict(int)
    studio_polished_count = 0
    studio_state_counts: dict[str, int] = defaultdict(int)
    top: list[dict] = []
    total_views = 0
    total_subscribers_gained = 0
    retention_percentages: list[float] = []
    for marker in markers:
        video_id = str(marker.get("video_id", ""))
        resource = statistics.get(video_id, {})
        stats = resource.get("statistics") or {}
        views = int(stats.get("viewCount", 0) or 0)
        score = _engagement_score(stats)
        title = str(marker.get("title", ""))
        hook = str(marker.get("hook", ""))
        story_format = str(marker.get("story_format") or classify_format(f"{title} {hook}"))
        humanity = marker.get("humanity") or (marker.get("editorial") or {}).get("humanity") or {}
        try:
            humanity_score = float(humanity.get("score", 0) or 0)
        except Exception:
            humanity_score = 0.0
        humanity_label = str(humanity.get("label") or "unknown")
        if humanity_score:
            humanity_scores.append(humanity_score)
            humanity_by_label[humanity_label] += 1
        studio_polish = marker.get("studio_polish") or {}
        studio_polished = bool(studio_polish.get("applied"))
        if studio_polished:
            studio_polished_count += 1
        studio_state = str(marker.get("studio_state") or (marker.get("editorial") or {}).get("state") or "unknown")
        studio_state_counts[studio_state] += 1
        analytics = retention.get(video_id, {})
        subscribers_gained = int(analytics.get("subscribersGained", 0) or 0)
        average_view_percentage = float(analytics.get("averageViewPercentage", 0) or 0)
        average_view_duration = float(analytics.get("averageViewDuration", 0) or 0)
        vph = _views_per_hour(views, str(marker.get("uploaded_at") or ""))
        growth_score = _growth_score(
            views=views,
            views_per_hour=vph,
            engagement_score=score,
            average_view_percentage=average_view_percentage,
            subscribers_gained=subscribers_gained,
        )
        total_subscribers_gained += subscribers_gained
        if average_view_percentage:
            retention_percentages.append(average_view_percentage)
            category_retention[str(marker.get("category") or "unknown")].append(average_view_percentage)
        total_views += views
        cat_key = str(marker.get("category") or "unknown")
        category[cat_key].append(score)
        category_growth[cat_key].append(growth_score)
        format_growth[story_format].append(growth_score)
        series[str(marker.get("series") or "Unassigned")].append(score)
        observations.append({
            "video_id": video_id,
            "title": title,
            "category": cat_key,
            "series": str(marker.get("series") or "Unassigned"),
            "score": growth_score or average_view_percentage or score,
            "engagement_score": score,
            "experiments": marker.get("experiments") or {},
            "average_view_percentage": average_view_percentage,
            "subscribers_gained": subscribers_gained,
            "views_per_hour": vph,
            "growth_score": growth_score,
            "story_format": story_format,
            "narrator_voice": str(marker.get("narrator_voice") or ""),
            "humanity_score": humanity_score,
            "humanity_label": humanity_label,
            "studio_polished": studio_polished,
            "studio_state": studio_state,
            "retention_tier": _retention_tier(average_view_percentage),
        })
        top.append({
            "video_id": video_id,
            "title": title,
            "views": views,
            "engagement_score": score,
            "growth_score": growth_score,
            "views_per_hour": vph,
            "share_url": marker.get("url", ""),
            "category": cat_key,
            "story_format": story_format,
            "humanity_score": round(humanity_score, 3),
            "humanity_label": humanity_label,
            "studio_polished": studio_polished,
            "studio_state": studio_state,
            "average_view_percentage": round(average_view_percentage, 3),
            "view_pct": round(average_view_percentage, 3),
            "average_view_duration": round(average_view_duration, 3),
            "subscribers_gained": subscribers_gained,
            "postmortem": postmortem(
                title=title,
                hook=hook,
                views=views,
                views_per_hour=vph,
                average_view_percentage=average_view_percentage,
                growth_score=growth_score,
            ),
        })
    top.sort(key=lambda item: (item["growth_score"], item["views"], item["engagement_score"]), reverse=True)
    average = lambda values: round(sum(values) / len(values), 3) if values else 0.0
    category_avg_growth = {k: average(v) for k, v in sorted(category_growth.items())}
    format_avg_growth = {k: average(v) for k, v in sorted(format_growth.items())}
    ranked_categories = sorted(category_avg_growth.items(), key=lambda kv: kv[1], reverse=True)
    ranked_formats = sorted(format_avg_growth.items(), key=lambda kv: kv[1], reverse=True)
    best = ranked_categories[0][1] if ranked_categories else 0.0
    category_weights = {
        key: round(1.0 + min(0.8, (score / best) * 0.8), 3) if best else 1.0
        for key, score in ranked_categories
    }
    for key, score_value in ranked_categories[-2:]:
        if best and score_value < best * 0.35:
            category_weights[key] = 0.75
    format_best = ranked_formats[0][1] if ranked_formats else 0.0
    format_weights = {
        key: round(1.0 + min(0.6, (score / format_best) * 0.6), 3) if format_best else 1.0
        for key, score in ranked_formats
    }
    exploit_keywords: list[str] = []
    for item in top[:5]:
        for token in str(item.get("title", "")).lower().split():
            clean = "".join(ch for ch in token if ch.isalnum())
            if len(clean) >= 5 and clean not in exploit_keywords:
                exploit_keywords.append(clean)
            if len(exploit_keywords) >= 12:
                break
        if len(exploit_keywords) >= 12:
            break
    learning_profile = _learning_profile(
        top,
        observations,
        category_avg_growth,
        format_avg_growth,
    )
    performance_matrix = build_performance_matrix(observations)
    win_loss = winners_and_losers(performance_matrix)
    remakes = remake_candidates(top)
    brief_seed = {
        "total_views": total_views,
        "avg_view_pct": average(retention_percentages),
        "avg_view_percentage": average(retention_percentages),
        "subscribers_gained": total_subscribers_gained,
    }
    brief = weekly_brief(brief_seed, observations, performance_matrix, remakes)
    snapshot = {
        "pulled_at": datetime.now(timezone.utc).isoformat(),
        "metric_scope": "youtube_analytics_and_public_statistics" if retention else "public_video_statistics",
        "total_views": total_views,
        "shorts_tracked": len(markers),
        "avg_engagement_score": average([o["engagement_score"] for o in observations]),
        "avg_humanity_score": average(humanity_scores),
        "humanity_label_counts": dict(sorted(humanity_by_label.items())),
        "studio_polished_count": studio_polished_count,
        "studio_state_counts": dict(sorted(studio_state_counts.items())),
        "avg_view_percentage": average(retention_percentages),
        "avg_view_pct": average(retention_percentages),
        "subscribers_gained": total_subscribers_gained,
        "below_60_pct": sorted([
            video_id for video_id, item in retention.items()
            if float(item.get("averageViewPercentage", 0) or 0) < 60
        ]),
        "below_62_pct": sorted([
            video_id for video_id, item in retention.items()
            if float(item.get("averageViewPercentage", 0) or 0) < 62
        ]),
        "category_avg_view_pct": {
            key: average(values) for key, values in sorted(category_retention.items())
        },
        "category_avg_engagement": {k: average(v) for k, v in sorted(category.items())},
        "category_avg_growth_score": category_avg_growth,
        "format_avg_growth_score": format_avg_growth,
        "series_avg_engagement": {k: average(v) for k, v in sorted(series.items())},
        "top_performers": top[:10],
        "learning_profile": learning_profile,
        "performance_matrix": performance_matrix,
        "winner_loser_map": win_loss,
        "remake_candidates": remakes,
        "weekly_brief": brief,
        "production_recommendations": {
            "hot_categories": [key for key, _ in ranked_categories[:3]],
            "slow_categories": [key for key, _ in ranked_categories[-3:]] if len(ranked_categories) >= 3 else [],
            "hot_formats": [key for key, _ in ranked_formats[:3]],
            "category_weights": category_weights,
            "format_weights": format_weights,
            "exploit_mode": bool(top and top[0].get("growth_score", 0) >= 120),
            "exploit_keywords": exploit_keywords,
            "learning_profile": learning_profile,
            "performance_matrix": performance_matrix,
            "winner_loser_map": win_loss,
            "remake_candidates": remakes,
            "production_mix": brief.get("production_mix", {}),
            "double_down_titles": [
                item["title"] for item in top[:5]
                if item.get("views", 0) > 0
            ],
            "next_actions": [
                "Favor categories with the highest growth score for the next production day.",
                "Keep Shorts tight: one strong hook, one animal, one payoff.",
                "Prefer stories with a high humanity score: host presence, visible detail, tension, payoff.",
                "Review any Short below 62 percent average view percentage before repeating its subject.",
                "Use the learning profile before fetch: winning keywords/categories are the next discovery bias.",
            ],
        },
    }
    return snapshot, observations


def main() -> int:
    markers = _load_markers()
    if not markers:
        print("analytics: no uploaded markers yet")
        return 0
    if not TOKEN_FILE.exists():
        print("analytics: youtube_token.json missing; keeping existing snapshots")
        return 0
    youtube = _load_service()
    if youtube is None:
        return 0
    try:
        stats = _fetch_statistics(youtube, [m["video_id"] for m in markers])
    except Exception as exc:
        print(f"analytics: public-stat refresh skipped: {exc}")
        return 0
    retention: dict[str, dict] = {}
    try:
        retention = _fetch_retention(_load_analytics_service(), [m["video_id"] for m in markers])
    except Exception as exc:
        print(f"analytics: retention refresh skipped: {exc}")
    snapshot, observations = build_snapshot(markers, stats, retention)
    ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)
    (ANALYTICS_DIR / "latest.json").write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8",
    )
    write_winners(compute_winners(observations), ANALYTICS_DIR / "experiments.json")
    print(f"analytics: refreshed {snapshot['shorts_tracked']} Shorts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
