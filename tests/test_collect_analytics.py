"""Testes para collect_analytics.py."""
from unittest.mock import MagicMock

import scripts.collect_analytics as collect_analytics


class TestCollectVideoStats:
    def _make_service(self, videos_stats=None):
        service = MagicMock()
        channels_resp = {
            "items": [{
                "id": "channel123",
                "contentDetails": {"relatedPlaylists": {"uploads": "uploads_playlist"}},
            }]
        }
        playlist_resp = {
            "items": [
                {"snippet": {"resourceId": {"videoId": "vid1"}}},
                {"snippet": {"resourceId": {"videoId": "vid2"}}},
            ],
            "nextPageToken": "",
        }
        videos_resp = {
            "items": [
                {
                    "id": "vid1",
                    "snippet": {"title": "Video 1", "publishedAt": "2026-01-01"},
                    "contentDetails": {"duration": "PT1M"},
                    "statistics": {"viewCount": "100", "likeCount": "10", "commentCount": "2"},
                },
                {
                    "id": "vid2",
                    "snippet": {"title": "Video 2", "publishedAt": "2026-01-02"},
                    "contentDetails": {"duration": "PT2M"},
                    "statistics": {"viewCount": "200", "likeCount": "20", "commentCount": None},
                },
            ]
        }
        service.channels().list.return_value.execute.return_value = channels_resp
        service.playlistItems().list.return_value.execute.return_value = playlist_resp
        service.videos().list.return_value.execute.return_value = videos_resp
        return service

    def test_collect_stats_returns_list(self):
        service = self._make_service()
        stats = collect_analytics.collect_video_stats(service)
        assert len(stats) == 2
        assert stats[0]["video_id"] == "vid1"
        assert stats[0]["views"] == 100

    def test_collect_stats_handles_null_values(self):
        service = self._make_service()
        stats = collect_analytics.collect_video_stats(service)
        assert stats[1]["comments"] == 0

    def test_collect_stats_empty_channel(self):
        service = MagicMock()
        service.channels().list.return_value.execute.return_value = {"items": []}
        stats = collect_analytics.collect_video_stats(service)
        assert stats == []
