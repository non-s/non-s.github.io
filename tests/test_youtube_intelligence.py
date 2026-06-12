import json

from utils.youtube_intelligence import (
    ANALYTICS_REPORTS,
    DATA_API_CAPABILITIES,
    build_payload,
    coverage_score,
    rows_to_dicts,
    summarise_channel,
    summarise_videos,
)
from utils.youtube_oauth import ANALYTICS_SCOPE, READONLY_SCOPE


def test_script_preserves_observed_snapshot_when_token_missing(monkeypatch, tmp_path):
    from scripts import youtube_intelligence as script

    out = tmp_path / "_data" / "youtube_intelligence.json"
    out.parent.mkdir()
    observed = build_payload(
        channel={"id": "chan", "snippet": {"title": "Wild Brief"}},
        uploads=[{"video_id": "abc", "title": "A"}],
        videos=[],
        reports=[{"id": "video_core", "status": "ok", "rows": 3}],
        issues=[],
    )
    out.write_text(json.dumps(observed, indent=2), encoding="utf-8")
    monkeypatch.setattr(script, "TOKEN_FILE", tmp_path / "missing-token.json")
    monkeypatch.setattr(script, "OUT", out)
    monkeypatch.delenv("YOUTUBE_TOKEN", raising=False)

    assert script.main() == 0

    assert json.loads(out.read_text(encoding="utf-8")) == observed


def test_script_accepts_env_token_without_token_file(monkeypatch, tmp_path):
    from scripts import youtube_intelligence as script

    out = tmp_path / "_data" / "youtube_intelligence.json"
    token = {
        "token": "access-secret",
        "refresh_token": "refresh-secret",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "client-id",
        "client_secret": "client-secret",
        "scopes": [READONLY_SCOPE, ANALYTICS_SCOPE],
    }
    seen_sources = []

    monkeypatch.setattr(script, "TOKEN_FILE", tmp_path / "missing-token.json")
    monkeypatch.setattr(script, "OUT", out)
    monkeypatch.setenv("YOUTUBE_TOKEN", json.dumps(token))
    monkeypatch.setattr(
        script, "_load_data_service", lambda info: seen_sources.append(("data", info.source)) or object()
    )
    monkeypatch.setattr(
        script,
        "_load_analytics_service",
        lambda info: seen_sources.append(("analytics", info.source)) or object(),
    )
    monkeypatch.setattr(script, "_fetch_channel", lambda youtube: {"id": "chan", "snippet": {"title": "Wild Brief"}})
    monkeypatch.setattr(script, "_fetch_uploads", lambda youtube, playlist_id: [])
    monkeypatch.setattr(script, "_fetch_videos", lambda youtube, ids: [])
    monkeypatch.setattr(script, "_run_reports", lambda analytics, unavailable_error="": [])

    assert script.main() == 0

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert seen_sources == [("data", "env"), ("analytics", "env")]
    assert "youtube_token_missing" not in payload["issues"]


def test_youtube_intelligence_has_broad_api_matrix():
    ids = {item["id"] for item in DATA_API_CAPABILITIES}
    assert {"channel_profile", "uploaded_video_inventory", "video_metadata_statistics"} <= ids
    assert {"comment_threads", "video_upload", "thumbnail_upload"} <= ids
    report_ids = {item["id"] for item in ANALYTICS_REPORTS}
    assert {"video_core", "daily_channel", "country", "traffic_source", "device_type"} <= report_ids


def test_rows_to_dicts_uses_response_headers():
    rows = rows_to_dicts(
        {
            "columnHeaders": [{"name": "video"}, {"name": "views"}],
            "rows": [["abc", 10]],
        }
    )
    assert rows == [{"video": "abc", "views": 10}]


def test_summarise_channel_extracts_uploads_playlist():
    channel = summarise_channel(
        {
            "id": "chan",
            "snippet": {"title": "Wild Brief"},
            "statistics": {"subscriberCount": "20", "viewCount": "1000", "videoCount": "5"},
            "contentDetails": {"relatedPlaylists": {"uploads": "UU123"}},
            "status": {"privacyStatus": "public"},
        }
    )
    assert channel["uploads_playlist"] == "UU123"
    assert channel["subscriber_count"] == 20


def test_summarise_videos_ranks_public_stats():
    summary = summarise_videos(
        [
            {"id": "a", "snippet": {"title": "A"}, "statistics": {"viewCount": "5", "likeCount": "1"}},
            {"id": "b", "snippet": {"title": "B"}, "statistics": {"viewCount": "10", "commentCount": "2"}},
        ]
    )
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
