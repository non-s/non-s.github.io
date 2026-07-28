"""Testes para scripts/cleanup_youtube.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import scripts.cleanup_youtube as cleanup_youtube


class TestParseIso8601Duration:
    def test_minutes_and_seconds(self):
        assert cleanup_youtube._parse_iso8601_duration("PT4M13S") == 4 * 60 + 13

    def test_hours_minutes_seconds(self):
        assert cleanup_youtube._parse_iso8601_duration("PT1H2M3S") == 3600 + 120 + 3

    def test_seconds_only(self):
        assert cleanup_youtube._parse_iso8601_duration("PT35S") == 35.0

    def test_empty_returns_zero(self):
        assert cleanup_youtube._parse_iso8601_duration("") == 0.0

    def test_malformed_returns_zero(self):
        assert cleanup_youtube._parse_iso8601_duration("not-a-duration") == 0.0


class TestClassifyVideo:
    def test_short_video_is_not_legacy(self):
        video = {"id": "v1", "contentDetails": {"duration": "PT35S"}}
        is_legacy, reason = cleanup_youtube.classify_video(video)
        assert is_legacy is False
        assert "v1" in reason

    def test_long_video_is_legacy(self):
        video = {"id": "v2", "contentDetails": {"duration": "PT5M0S"}}
        is_legacy, reason = cleanup_youtube.classify_video(video)
        assert is_legacy is True
        assert "horizontal/longform" in reason

    def test_live_streaming_details_is_legacy_even_if_short(self):
        video = {
            "id": "v3",
            "contentDetails": {"duration": "PT10S"},
            "liveStreamingDetails": {"actualStartTime": "2026-01-01T00:00:00Z"},
        }
        is_legacy, reason = cleanup_youtube.classify_video(video)
        assert is_legacy is True
        assert "liveStreamingDetails" in reason

    def test_boundary_at_max_seconds_is_not_legacy(self):
        video = {"id": "v4", "contentDetails": {"duration": f"PT{cleanup_youtube._SHORT_MAX_SECONDS}S"}}
        is_legacy, _ = cleanup_youtube.classify_video(video)
        assert is_legacy is False

    def test_just_above_max_seconds_is_legacy(self):
        video = {"id": "v5", "contentDetails": {"duration": f"PT{cleanup_youtube._SHORT_MAX_SECONDS + 1}S"}}
        is_legacy, _ = cleanup_youtube.classify_video(video)
        assert is_legacy is True


class TestFindLegacyVideos:
    def _service_with(self, video_items):
        service = MagicMock()
        service.channels().list().execute.return_value = {
            "items": [{"id": "chan1", "contentDetails": {"relatedPlaylists": {"uploads": "UU123"}}}]
        }
        service.playlistItems().list().execute.return_value = {
            "items": [{"snippet": {"resourceId": {"videoId": v["id"]}}} for v in video_items],
        }
        service.videos().list().execute.return_value = {"items": video_items}
        return service

    def test_returns_only_legacy_videos(self):
        videos = [
            {"id": "short1", "snippet": {"title": "Short"}, "contentDetails": {"duration": "PT35S"}},
            {"id": "horiz1", "snippet": {"title": "Horizontal"}, "contentDetails": {"duration": "PT5M0S"}},
        ]
        service = self._service_with(videos)
        legacy = cleanup_youtube.find_legacy_videos(service)
        assert [v["id"] for v in legacy] == ["horiz1"]

    def test_no_channel_returns_empty(self):
        service = MagicMock()
        service.channels().list().execute.return_value = {"items": []}
        assert cleanup_youtube.find_legacy_videos(service) == []

    def test_no_videos_returns_empty(self):
        service = self._service_with([])
        assert cleanup_youtube.find_legacy_videos(service) == []


class TestListAllVideoIds:
    def test_paginates_through_all_pages(self):
        service = MagicMock()
        page1 = {
            "items": [{"snippet": {"resourceId": {"videoId": "a"}}}],
            "nextPageToken": "tok2",
        }
        page2 = {
            "items": [{"snippet": {"resourceId": {"videoId": "b"}}}],
        }
        service.playlistItems().list().execute.side_effect = [page1, page2]
        ids = cleanup_youtube._list_all_video_ids(service, "UU123")
        assert ids == ["a", "b"]


class TestDeleteVideos:
    def test_dry_run_does_not_call_delete(self):
        service = MagicMock()
        videos = [{"id": "v1", "snippet": {"title": "Old horizontal"}}]
        deleted = cleanup_youtube.delete_videos(service, videos, dry_run=True)
        assert deleted == 0
        service.videos().delete.assert_not_called()

    def test_empty_list_returns_zero(self):
        service = MagicMock()
        assert cleanup_youtube.delete_videos(service, [], dry_run=False) == 0

    def test_real_run_deletes_and_counts(self):
        service = MagicMock()
        videos = [
            {"id": "v1", "snippet": {"title": "Old horizontal"}},
            {"id": "v2", "snippet": {"title": "Old live"}},
        ]
        with patch("scripts.cleanup_youtube.time.sleep"):
            deleted = cleanup_youtube.delete_videos(service, videos, dry_run=False)
        assert deleted == 2
        assert service.videos().delete.call_count == 2

    def test_continues_after_single_failure(self):
        service = MagicMock()
        videos = [{"id": "v1", "snippet": {}}, {"id": "v2", "snippet": {}}]
        with patch("scripts.cleanup_youtube.time.sleep"), \
             patch(
                 "scripts.cleanup_youtube._retry_youtube_call",
                 side_effect=[RuntimeError("api down"), {"id": "v2"}],
             ):
            deleted = cleanup_youtube.delete_videos(service, videos, dry_run=False)
        assert deleted == 1


class TestMain:
    def test_dry_run_writes_github_output(self, tmp_path, monkeypatch):
        out_file = tmp_path / "gh_output.txt"
        monkeypatch.setenv("GITHUB_OUTPUT", str(out_file))
        service = MagicMock()
        service.channels().list().execute.return_value = {"items": []}

        with patch("scripts.cleanup_youtube.get_youtube_service", return_value=service):
            code = cleanup_youtube.main(["--dry-run", "true"])

        assert code == 0
        content = out_file.read_text(encoding="utf-8")
        assert "candidates=0" in content
        assert "deleted=0" in content
        assert "dry_run=true" in content

    def test_execute_mode_deletes(self, tmp_path, monkeypatch):
        out_file = tmp_path / "gh_output.txt"
        monkeypatch.setenv("GITHUB_OUTPUT", str(out_file))
        service = MagicMock()
        service.channels().list().execute.return_value = {
            "items": [{"id": "chan1", "contentDetails": {"relatedPlaylists": {"uploads": "UU123"}}}]
        }
        service.playlistItems().list().execute.return_value = {
            "items": [{"snippet": {"resourceId": {"videoId": "horiz1"}}}]
        }
        service.videos().list().execute.return_value = {
            "items": [{"id": "horiz1", "snippet": {"title": "Old"}, "contentDetails": {"duration": "PT5M0S"}}]
        }

        with patch("scripts.cleanup_youtube.get_youtube_service", return_value=service), \
             patch("scripts.cleanup_youtube.time.sleep"):
            code = cleanup_youtube.main(["--dry-run", "false"])

        assert code == 0
        content = out_file.read_text(encoding="utf-8")
        assert "candidates=1" in content
        assert "deleted=1" in content
        assert "dry_run=false" in content
