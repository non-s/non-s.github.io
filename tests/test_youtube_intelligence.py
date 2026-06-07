from utils.youtube_intelligence import (
    ANALYTICS_REPORTS,
    DATA_API_CAPABILITIES,
    build_payload,
    coverage_score,
    rows_to_dicts,
    summarise_channel,
    summarise_videos,
)


def test_youtube_intelligence_has_broad_api_matrix():
    ids = {item["id"] for item in DATA_API_CAPABILITIES}
    assert {"channel_profile", "uploaded_video_inventory", "video_metadata_statistics"} <= ids
    assert {"comment_threads", "video_upload", "thumbnail_upload"} <= ids
    report_ids = {item["id"] for item in ANALYTICS_REPORTS}
    assert {"video_core", "daily_channel", "country", "traffic_source", "device_type"} <= report_ids


def test_rows_to_dicts_uses_response_headers():
    rows = rows_to_dicts({
        "columnHeaders": [{"name": "video"}, {"name": "views"}],
        "rows": [["abc", 10]],
    })
    assert rows == [{"video": "abc", "views": 10}]


def test_summarise_channel_extracts_uploads_playlist():
    channel = summarise_channel({
        "id": "chan",
        "snippet": {"title": "Wild Brief"},
        "statistics": {"subscriberCount": "20", "viewCount": "1000", "videoCount": "5"},
        "contentDetails": {"relatedPlaylists": {"uploads": "UU123"}},
        "status": {"privacyStatus": "public"},
    })
    assert channel["uploads_playlist"] == "UU123"
    assert channel["subscriber_count"] == 20


def test_summarise_videos_ranks_public_stats():
    summary = summarise_videos([
        {"id": "a", "snippet": {"title": "A"}, "statistics": {"viewCount": "5", "likeCount": "1"}},
        {"id": "b", "snippet": {"title": "B"}, "statistics": {"viewCount": "10", "commentCount": "2"}},
    ])
    assert summary["videos_checked"] == 2
    assert summary["total_views"] == 15
    assert summary["top_public_videos"][0]["video_id"] == "b"


def test_build_payload_reports_coverage_and_issues():
    payload = build_payload(
        channel={},
        uploads=[],
        videos=[],
        reports=[{"id": "video_core", "status": "ok", "rows": 3}],
        issues=["youtube_token_missing"],
    )
    assert payload["coverage_score"] > 0
    assert payload["issues"] == ["youtube_token_missing"]
    assert coverage_score(payload["capabilities"], payload["analytics_reports"]) == payload["coverage_score"]
