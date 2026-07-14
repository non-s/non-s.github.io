"""YouTube API coverage and intelligence aggregation helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

DATA_API_CAPABILITIES = [
    {
        "id": "channel_profile",
        "api": "youtube.data",
        "method": "channels.list",
        "coverage": "implemented",
        "use": "Channel identity, uploads playlist, subscriber/view/video totals, branding/status audit.",
        "risk": "read_only",
    },
    {
        "id": "uploaded_video_inventory",
        "api": "youtube.data",
        "method": "playlistItems.list",
        "coverage": "implemented",
        "use": "Compare YouTube uploads against local .done markers and detect missing local memory.",
        "risk": "read_only",
    },
    {
        "id": "video_metadata_statistics",
        "api": "youtube.data",
        "method": "videos.list",
        "coverage": "implemented",
        "use": "Public stats, title/description/tag/status/duration audit for every tracked Short.",
        "risk": "read_only",
    },
    {
        "id": "comment_threads",
        "api": "youtube.data",
        "method": "commentThreads.list",
        "coverage": "implemented_elsewhere",
        "use": "Audience questions, requested animals, sentiment and sequel prompts.",
        "risk": "read_only",
    },
    {
        "id": "video_upload",
        "api": "youtube.data",
        "method": "videos.insert",
        "coverage": "implemented_elsewhere",
        "use": "Publish generated Shorts.",
        "risk": "write_high_quota",
    },
    {
        "id": "thumbnail_upload",
        "api": "youtube.data",
        "method": "thumbnails.set",
        "coverage": "implemented_elsewhere",
        "use": "Upload custom thumbnail when YouTube permits it for the video type/account.",
        "risk": "write_medium_quota",
    },
    {
        "id": "playlist_management",
        "api": "youtube.data",
        "method": "playlists.list,playlistItems.insert",
        "coverage": "planned_manual_gate",
        "use": "Series packaging after winners are proven.",
        "risk": "write_requires_review",
    },
    {
        "id": "comment_replies_moderation",
        "api": "youtube.data",
        "method": "comments.insert,comments.setModerationStatus,comments.delete",
        "coverage": "blocked_by_human_review",
        "use": "Reply/moderate comments only after explicit operator approval.",
        "risk": "write_sensitive",
    },
    {
        "id": "channel_branding_update",
        "api": "youtube.data",
        "method": "channels.update",
        "coverage": "blocked_by_human_review",
        "use": "Branding changes are too sensitive for unattended automation.",
        "risk": "write_sensitive",
    },
]


ANALYTICS_REPORTS = [
    {
        "id": "video_core",
        "dimensions": "video",
        "metrics": "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,likes,comments,shares,subscribersGained",
        "sort": "-views",
        "use": "Rank videos by growth, engagement, retention and subscriber conversion.",
    },
    {
        "id": "daily_channel",
        "dimensions": "day",
        "metrics": "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,subscribersGained",
        "sort": "day",
        "use": "Daily pacing and anomaly detection.",
    },
    {
        "id": "country",
        "dimensions": "country",
        "metrics": "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,subscribersGained",
        "sort": "-views",
        "use": "Geo demand and publish timing hints.",
    },
    {
        "id": "traffic_source",
        "dimensions": "insightTrafficSourceType",
        "metrics": "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage",
        "sort": "-views",
        "use": "Detect whether Shorts feed, search, browse, external or channel surfaces are driving growth.",
    },
    {
        "id": "device_type",
        "dimensions": "deviceType",
        "metrics": "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage",
        "sort": "-views",
        "use": "Tune caption size, pacing and visual density for device mix.",
    },
    {
        "id": "subscriber_status",
        "dimensions": "subscribedStatus",
        "metrics": "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage",
        "sort": "-views",
        "use": "Separate existing subscriber behavior from discovery behavior.",
    },
]


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_window(days: int = 28) -> tuple[str, str]:
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=max(1, days - 1))
    return start.isoformat(), end.isoformat()


def rows_to_dicts(response: dict) -> list[dict]:
    headers = [item.get("name", "") for item in response.get("columnHeaders", [])]
    rows = []
    for raw in response.get("rows", []) or []:
        rows.append(dict(zip(headers, raw)))
    return rows


def summarise_channel(channel: dict | None) -> dict:
    channel = channel or {}
    snippet = channel.get("snippet") or {}
    stats = channel.get("statistics") or {}
    content = channel.get("contentDetails") or {}
    status = channel.get("status") or {}
    return {
        "id": channel.get("id", ""),
        "title": snippet.get("title", ""),
        "custom_url": snippet.get("customUrl", ""),
        "published_at": snippet.get("publishedAt", ""),
        "uploads_playlist": ((content.get("relatedPlaylists") or {}).get("uploads") or ""),
        "subscriber_count": int(stats.get("subscriberCount", 0) or 0),
        "view_count": int(stats.get("viewCount", 0) or 0),
        "video_count": int(stats.get("videoCount", 0) or 0),
        "privacy_status": status.get("privacyStatus", ""),
        "made_for_kids": bool(status.get("madeForKids", False)),
        "self_declared_made_for_kids": bool(status.get("selfDeclaredMadeForKids", False)),
    }


def summarise_videos(videos: list[dict]) -> dict:
    total_views = total_likes = total_comments = 0
    private_or_unlisted = 0
    shorts_like = 0
    top = []
    for item in videos:
        stats = item.get("statistics") or {}
        snippet = item.get("snippet") or {}
        status = item.get("status") or {}
        views = int(stats.get("viewCount", 0) or 0)
        likes = int(stats.get("likeCount", 0) or 0)
        comments = int(stats.get("commentCount", 0) or 0)
        total_views += views
        total_likes += likes
        total_comments += comments
        if status.get("privacyStatus") in {"private", "unlisted"}:
            private_or_unlisted += 1
        title = str(snippet.get("title") or "")
        if "#shorts" in str(snippet.get("description") or "").lower() or len(title) <= 100:
            shorts_like += 1
        top.append(
            {
                "video_id": item.get("id", ""),
                "title": title,
                "views": views,
                "likes": likes,
                "comments": comments,
                "privacy_status": status.get("privacyStatus", ""),
                "published_at": snippet.get("publishedAt", ""),
            }
        )
    top.sort(key=lambda row: (row["views"], row["likes"], row["comments"]), reverse=True)
    return {
        "videos_checked": len(videos),
        "total_views": total_views,
        "total_likes": total_likes,
        "total_comments": total_comments,
        "private_or_unlisted": private_or_unlisted,
        "shorts_like": shorts_like,
        "top_public_videos": top[:10],
    }


def coverage_score(capabilities: list[dict], reports: list[dict]) -> int:
    possible = len(capabilities) + len(reports)
    if not possible:
        return 0
    done = sum(1 for item in capabilities if str(item.get("coverage", "")).startswith("implemented"))
    done += sum(1 for item in reports if item.get("status") == "ok")
    return round(done * 100 / possible)


def build_payload(
    *, channel: dict | None, uploads: list[dict], videos: list[dict], reports: list[dict], issues: list[str]
) -> dict:
    capabilities = [dict(item) for item in DATA_API_CAPABILITIES]
    for item in capabilities:
        if item["id"] in {"channel_profile", "uploaded_video_inventory", "video_metadata_statistics"}:
            item["last_run"] = "ok" if not issues else "attempted"
    report_status = []
    report_by_id = {item.get("id"): item for item in reports}
    for spec in ANALYTICS_REPORTS:
        row = dict(spec)
        found = report_by_id.get(spec["id"]) or {}
        row["status"] = found.get("status", "not_run")
        row["rows"] = found.get("rows", 0)
        row["error"] = found.get("error", "")
        report_status.append(row)
    return {
        "generated_at": iso_now(),
        "window": dict(zip(("start_date", "end_date"), default_window())),
        "coverage_score": coverage_score(capabilities, report_status),
        "quota_strategy": [
            "Batch videos.list in groups of 50.",
            "Avoid search.list for routine automation because it is expensive and trend discovery already uses cheaper public sources.",
            "Run write operations only in publishing workflows; keep intelligence refresh read-only.",
            "Fail open for unavailable Analytics reports and record the exact missing capability.",
        ],
        "channel": summarise_channel(channel),
        "uploads_inventory": {
            "uploads_checked": len(uploads),
            "latest_uploads": uploads[:25],
        },
        "video_audit": summarise_videos(videos),
        "capabilities": capabilities,
        "analytics_reports": report_status,
        "issues": issues,
    }
