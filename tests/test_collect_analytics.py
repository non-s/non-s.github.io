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


class TestLoadVideoTags:
    def test_missing_file_returns_empty_dict(self, tmp_path, monkeypatch):
        monkeypatch.setattr(collect_analytics, "VIDEO_TAGS_FILE", tmp_path / "video_tags.json")
        assert collect_analytics._load_video_tags() == {}

    def test_reads_existing_file(self, tmp_path, monkeypatch):
        tags_file = tmp_path / "video_tags.json"
        tags_file.write_text(json.dumps({"vid1": {"scene": "cat"}}), encoding="utf-8")
        monkeypatch.setattr(collect_analytics, "VIDEO_TAGS_FILE", tags_file)

        assert collect_analytics._load_video_tags() == {"vid1": {"scene": "cat"}}

    def test_corrupted_file_returns_empty_dict(self, tmp_path, monkeypatch):
        tags_file = tmp_path / "video_tags.json"
        tags_file.write_text("not json", encoding="utf-8")
        monkeypatch.setattr(collect_analytics, "VIDEO_TAGS_FILE", tags_file)

        assert collect_analytics._load_video_tags() == {}


class TestComputeScenePerformance:
    """_compute_scene_performance: cruza views (stats) com a cena que gerou
    cada video (video_tags) pra calcular um peso relativo por cena."""

    def _stats(self, *, cat_views, dog_views):
        stats = [{"video_id": f"cat{i}", "views": v} for i, v in enumerate(cat_views)]
        stats += [{"video_id": f"dog{i}", "views": v} for i, v in enumerate(dog_views)]
        return stats

    def _tags(self, *, cat_count, dog_count):
        tags = {f"cat{i}": {"scene": "cat"} for i in range(cat_count)}
        tags.update({f"dog{i}": {"scene": "dog"} for i in range(dog_count)})
        return tags

    def test_no_tagged_videos_returns_empty(self):
        stats = [{"video_id": "untagged1", "views": 100}]
        assert collect_analytics._compute_scene_performance(stats, {}) == {}

    def test_scene_with_too_few_samples_is_skipped(self):
        """_MIN_SCENE_SAMPLES = 3: uma ou duas amostras e ruido demais pra
        confiar num peso - fica de fora do resultado (peso neutro implicito)."""
        stats = self._stats(cat_views=[100, 100], dog_views=[10, 10, 10])
        tags = self._tags(cat_count=2, dog_count=3)

        weights = collect_analytics._compute_scene_performance(stats, tags)

        assert "cat" not in weights
        assert "dog" in weights

    def test_above_average_scene_gets_weight_above_one(self):
        stats = self._stats(cat_views=[1000, 1000, 1000], dog_views=[10, 10, 10])
        tags = self._tags(cat_count=3, dog_count=3)

        weights = collect_analytics._compute_scene_performance(stats, tags)

        assert weights["cat"] > 1.0
        assert weights["dog"] < 1.0

    def test_weight_is_capped_at_max(self):
        # Grupos com contagens desiguais (3 vs 30) pra puxar a media geral bem
        # abaixo da media do cat - com grupos do mesmo tamanho o peso maximo
        # possivel tende a 2.0 (nunca alcancaria o cap de 2.5).
        stats = self._stats(cat_views=[1_000_000] * 3, dog_views=[1] * 30)
        tags = self._tags(cat_count=3, dog_count=30)

        weights = collect_analytics._compute_scene_performance(stats, tags)

        assert weights["cat"] == collect_analytics._MAX_SCENE_WEIGHT
        assert weights["dog"] == collect_analytics._MIN_SCENE_WEIGHT

    def test_all_zero_views_returns_empty(self):
        stats = self._stats(cat_views=[0, 0, 0], dog_views=[0, 0, 0])
        tags = self._tags(cat_count=3, dog_count=3)

        assert collect_analytics._compute_scene_performance(stats, tags) == {}


class TestLoadScenePerformance:
    def test_missing_file_returns_empty_dict(self, tmp_path, monkeypatch):
        monkeypatch.setattr(collect_analytics, "SCENE_PERFORMANCE_FILE", tmp_path / "scene_performance.json")
        assert collect_analytics._load_scene_performance() == {}

    def test_reads_existing_file(self, tmp_path, monkeypatch):
        perf_file = tmp_path / "scene_performance.json"
        perf_file.write_text(json.dumps({"cat": 1.5}), encoding="utf-8")
        monkeypatch.setattr(collect_analytics, "SCENE_PERFORMANCE_FILE", perf_file)

        assert collect_analytics._load_scene_performance() == {"cat": 1.5}

    def test_corrupted_file_returns_empty_dict(self, tmp_path, monkeypatch):
        perf_file = tmp_path / "scene_performance.json"
        perf_file.write_text("not json", encoding="utf-8")
        monkeypatch.setattr(collect_analytics, "SCENE_PERFORMANCE_FILE", perf_file)

        assert collect_analytics._load_scene_performance() == {}


class TestUpdateScenePerformance:
    """_update_scene_performance mescla por cima do arquivo existente em vez
    de sobrescrever - uma cena que caiu abaixo de _MIN_SCENE_SAMPLES nesta
    semana (e por isso ausente do scene_weights recem-calculado) nao pode
    perder o peso ja conhecido de uma semana anterior."""

    def test_writes_new_file_when_none_exists(self, tmp_path, monkeypatch):
        perf_file = tmp_path / "scene_performance.json"
        monkeypatch.setattr(collect_analytics, "SCENE_PERFORMANCE_FILE", perf_file)

        collect_analytics._update_scene_performance({"cat": 1.8})

        assert json.loads(perf_file.read_text(encoding="utf-8")) == {"cat": 1.8}

    def test_preserves_scene_missing_from_fresh_weights(self, tmp_path, monkeypatch):
        perf_file = tmp_path / "scene_performance.json"
        perf_file.write_text(json.dumps({"cat": 1.5, "sleepy cat": 2.1}), encoding="utf-8")
        monkeypatch.setattr(collect_analytics, "SCENE_PERFORMANCE_FILE", perf_file)

        # Esta semana so "cat" teve amostras suficientes; "sleepy cat" nao
        # aparece no resultado fresco, mas deve sobreviver no arquivo.
        collect_analytics._update_scene_performance({"cat": 1.2})

        result = json.loads(perf_file.read_text(encoding="utf-8"))
        assert result["cat"] == 1.2
        assert result["sleepy cat"] == 2.1

    def test_fresh_weight_overrides_stale_one(self, tmp_path, monkeypatch):
        perf_file = tmp_path / "scene_performance.json"
        perf_file.write_text(json.dumps({"cat": 0.5}), encoding="utf-8")
        monkeypatch.setattr(collect_analytics, "SCENE_PERFORMANCE_FILE", perf_file)

        collect_analytics._update_scene_performance({"cat": 2.0})

        assert json.loads(perf_file.read_text(encoding="utf-8"))["cat"] == 2.0
