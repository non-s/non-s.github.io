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

    def test_pagination_follows_next_page_token_across_pages(self):
        """video_ids deve acumular de VARIAS paginas ate nextPageToken vazio,
        nao so da primeira - garante que o loop de paginacao (nao so o corpo
        de uma unica pagina) funciona de verdade."""
        service = MagicMock()
        service.channels().list.return_value.execute.return_value = {
            "items": [{
                "id": "channel123",
                "contentDetails": {"relatedPlaylists": {"uploads": "uploads_playlist"}},
            }]
        }
        page1 = {
            "items": [{"snippet": {"resourceId": {"videoId": "vid1"}}}],
            "nextPageToken": "page2",
        }
        page2 = {
            "items": [{"snippet": {"resourceId": {"videoId": "vid2"}}}],
            "nextPageToken": "",
        }
        service.playlistItems().list.return_value.execute.side_effect = [page1, page2]
        service.videos().list.return_value.execute.return_value = {
            "items": [
                {"id": "vid1", "snippet": {"title": "V1", "publishedAt": "2026-01-01"},
                 "contentDetails": {"duration": "PT1M"},
                 "statistics": {"viewCount": "1", "likeCount": "0", "commentCount": "0"}},
                {"id": "vid2", "snippet": {"title": "V2", "publishedAt": "2026-01-02"},
                 "contentDetails": {"duration": "PT1M"},
                 "statistics": {"viewCount": "2", "likeCount": "0", "commentCount": "0"}},
            ]
        }

        stats = collect_analytics.collect_video_stats(service)

        assert {s["video_id"] for s in stats} == {"vid1", "vid2"}
        assert service.playlistItems().list.return_value.execute.call_count == 2

    def test_pagination_stops_at_page_guard_even_without_empty_token(self):
        """Se a API nunca devolver nextPageToken vazio (resposta malformada
        ou bug do lado do YouTube), o guard `pages < 20` precisa impedir loop
        infinito."""
        service = MagicMock()
        service.channels().list.return_value.execute.return_value = {
            "items": [{
                "id": "channel123",
                "contentDetails": {"relatedPlaylists": {"uploads": "uploads_playlist"}},
            }]
        }
        # Sempre retorna um item novo E sempre um nextPageToken nao-vazio -
        # so o guard de paginas (nao o token vazio) pode parar o loop.
        service.playlistItems().list.return_value.execute.side_effect = [
            {"items": [{"snippet": {"resourceId": {"videoId": f"vid{i}"}}}], "nextPageToken": "more"}
            for i in range(30)
        ]
        service.videos().list.return_value.execute.return_value = {"items": []}

        collect_analytics.collect_video_stats(service)

        assert service.playlistItems().list.return_value.execute.call_count == 20
