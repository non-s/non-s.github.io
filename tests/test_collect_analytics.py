"""Testes para collect_analytics.py."""
import json
from unittest.mock import MagicMock

import scripts.collect_analytics as collect_analytics


class TestAppendHistory:
    def _report(self, collected_at="2026-01-01T00:00:00+00:00", views=100):
        return {
            "collected_at": collected_at,
            "total_videos": 5,
            "total_views": views,
            "total_likes": 1,
            "total_comments": 0,
            "avg_views": views // 5,
            "top_10": [],
            "bottom_10": [],
            "all_videos": [{"video_id": "x"}],
        }

    def test_creates_history_file_with_one_snapshot(self, tmp_path, monkeypatch):
        monkeypatch.setattr(collect_analytics, "HISTORY_FILE", tmp_path / "history.json")

        collect_analytics._append_history(self._report())

        history = json.loads((tmp_path / "history.json").read_text())
        assert len(history) == 1
        assert history[0]["total_views"] == 100
        # Snapshot e compacto - nao carrega all_videos/top_10/bottom_10.
        assert "all_videos" not in history[0]

    def test_appends_to_existing_history(self, tmp_path, monkeypatch):
        history_path = tmp_path / "history.json"
        monkeypatch.setattr(collect_analytics, "HISTORY_FILE", history_path)
        history_path.write_text(json.dumps([{"collected_at": "2025-01-01", "total_views": 10}]))

        collect_analytics._append_history(self._report(views=200))

        history = json.loads(history_path.read_text())
        assert len(history) == 2
        assert history[-1]["total_views"] == 200

    def test_caps_history_at_max_entries(self, tmp_path, monkeypatch):
        history_path = tmp_path / "history.json"
        monkeypatch.setattr(collect_analytics, "HISTORY_FILE", history_path)
        monkeypatch.setattr(collect_analytics, "MAX_HISTORY_ENTRIES", 3)
        history_path.write_text(json.dumps([{"total_views": i} for i in range(3)]))

        collect_analytics._append_history(self._report(views=999))

        history = json.loads(history_path.read_text())
        assert len(history) == 3
        assert history[-1]["total_views"] == 999

    def test_corrupted_history_file_does_not_crash(self, tmp_path, monkeypatch):
        history_path = tmp_path / "history.json"
        monkeypatch.setattr(collect_analytics, "HISTORY_FILE", history_path)
        history_path.write_text("not valid json{{{")

        collect_analytics._append_history(self._report())

        history = json.loads(history_path.read_text())
        assert len(history) == 1


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
