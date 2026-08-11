"""Testes para collect_analytics.py."""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

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
            "items": [
                {
                    "id": "channel123",
                    "contentDetails": {"relatedPlaylists": {"uploads": "uploads_playlist"}},
                }
            ]
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
        stats, _channel = collect_analytics.collect_video_stats(service)
        assert len(stats) == 2
        assert stats[0]["video_id"] == "vid1"
        assert stats[0]["views"] == 100

    def test_collect_stats_handles_null_values(self):
        service = self._make_service()
        stats, _channel = collect_analytics.collect_video_stats(service)
        assert stats[1]["comments"] == 0

    def test_collect_stats_empty_channel(self):
        service = MagicMock()
        service.channels().list.return_value.execute.return_value = {"items": []}
        stats, _channel = collect_analytics.collect_video_stats(service)
        assert stats == []
        assert _channel == {}

    def test_pagination_follows_next_page_token_across_pages(self):
        """video_ids deve acumular de VARIAS paginas ate nextPageToken vazio,
        nao so da primeira - garante que o loop de paginacao (nao so o corpo
        de uma unica pagina) funciona de verdade."""
        service = MagicMock()
        service.channels().list.return_value.execute.return_value = {
            "items": [
                {
                    "id": "channel123",
                    "contentDetails": {"relatedPlaylists": {"uploads": "uploads_playlist"}},
                }
            ]
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
                {
                    "id": "vid1",
                    "snippet": {"title": "V1", "publishedAt": "2026-01-01"},
                    "contentDetails": {"duration": "PT1M"},
                    "statistics": {"viewCount": "1", "likeCount": "0", "commentCount": "0"},
                },
                {
                    "id": "vid2",
                    "snippet": {"title": "V2", "publishedAt": "2026-01-02"},
                    "contentDetails": {"duration": "PT1M"},
                    "statistics": {"viewCount": "2", "likeCount": "0", "commentCount": "0"},
                },
            ]
        }

        stats, _channel = collect_analytics.collect_video_stats(service)

        assert {s["video_id"] for s in stats} == {"vid1", "vid2"}
        assert service.playlistItems().list.return_value.execute.call_count == 2

    def test_pagination_stops_at_page_guard_even_without_empty_token(self):
        """Se a API nunca devolver nextPageToken vazio (resposta malformada
        ou bug do lado do YouTube), o guard `pages < 20` precisa impedir loop
        infinito."""
        service = MagicMock()
        service.channels().list.return_value.execute.return_value = {
            "items": [
                {
                    "id": "channel123",
                    "contentDetails": {"relatedPlaylists": {"uploads": "uploads_playlist"}},
                }
            ]
        }
        # Sempre retorna um item novo E sempre um nextPageToken nao-vazio -
        # so o guard de paginas (nao o token vazio) pode parar o loop.
        service.playlistItems().list.return_value.execute.side_effect = [
            {"items": [{"snippet": {"resourceId": {"videoId": f"vid{i}"}}}], "nextPageToken": "more"} for i in range(30)
        ]
        service.videos().list.return_value.execute.return_value = {"items": []}

        collect_analytics.collect_video_stats(service)

        assert service.playlistItems().list.return_value.execute.call_count == 20

    def test_empty_page_breaks_even_with_next_page_token(self):
        """Uma pagina vazia (items == []) com nextPageToken presente deve
        quebrar imediatamente - nao continuar paginando."""
        service = MagicMock()
        service.channels().list.return_value.execute.return_value = {
            "items": [
                {
                    "id": "channel123",
                    "contentDetails": {"relatedPlaylists": {"uploads": "uploads_playlist"}},
                }
            ]
        }
        service.playlistItems().list.return_value.execute.side_effect = [
            {"items": [], "nextPageToken": "page2"},
            {"items": [{"snippet": {"resourceId": {"videoId": "vid1"}}}], "nextPageToken": ""},
        ]
        service.videos().list.return_value.execute.return_value = {"items": []}

        stats, _channel = collect_analytics.collect_video_stats(service)

        assert stats == []
        assert service.playlistItems().list.return_value.execute.call_count == 1


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
        # Com Wilson normalizado pra media 1.0, o peso maximo possivel com K
        # keys e ~K (quando so uma tem lower>0 e as demais ~0). Precisamos de
        # 3+ keys pra ultrapassar o cap de 2.5 e exercita-lo de verdade.
        stats = self._stats(cat_views=[1_000_000] * 3, dog_views=[1] * 30)
        stats += [{"video_id": f"bird{i}", "views": 1} for i in range(30)]
        tags = self._tags(cat_count=3, dog_count=30)
        tags.update({f"bird{i}": {"scene": "bird"} for i in range(30)})

        weights = collect_analytics._compute_scene_performance(stats, tags)

        assert weights["cat"] == collect_analytics._MAX_SCENE_WEIGHT
        assert weights["dog"] == collect_analytics._MIN_SCENE_WEIGHT

    def test_all_zero_views_returns_empty(self):
        stats = self._stats(cat_views=[0, 0, 0], dog_views=[0, 0, 0])
        tags = self._tags(cat_count=3, dog_count=3)

        assert collect_analytics._compute_scene_performance(stats, tags) == {}


class TestComputeWeightedPerformanceWilson:
    """_compute_weighted_performance usa Wilson score interval (lower bound)
    sobre a proporcao de videos acima da mediana geral - mais conservador
    que media simples com amostras pequenas."""

    def _stats_tags(self, scene_specs: dict[str, list[int]]):
        stats: list[dict] = []
        tags: dict = {}
        for scene, views_list in scene_specs.items():
            for i, v in enumerate(views_list):
                vid = f"{scene}{i}"
                stats.append({"video_id": vid, "views": v})
                tags[vid] = {"scene": scene}
        return stats, tags

    def test_consistent_above_median_beats_inconsistent(self):
        # Cena A: 3 videos todos acima da mediana (p=1.0).
        # Cena B: 3 videos 1 acima 2 abaixo (p=0.33).
        stats, tags = self._stats_tags(
            {
                "a": [2000, 2000, 2000],
                "b": [1000, 100, 50],
            }
        )

        weights = collect_analytics._compute_scene_performance(stats, tags)

        assert weights["a"] > weights["b"]
        assert weights["a"] > 1.0
        assert weights["b"] < 1.0

    def test_viral_inconsistent_penalized_vs_consistent(self):
        # Cena viral: 1 viral + 2 baixos (p=0.33 mas views altas).
        # Cena consistente: 2 acima 1 abaixo (p=0.66, views medias).
        stats, tags = self._stats_tags(
            {
                "viral": [100000, 100, 100],
                "consistent": [1000, 1000, 100],
            }
        )

        weights = collect_analytics._compute_scene_performance(stats, tags)

        assert weights["consistent"] > weights["viral"]

    def test_below_min_samples_is_neutral(self):
        stats, tags = self._stats_tags(
            {
                "small": [1000, 1000],
                "ok": [1000, 1000, 1000],
            }
        )

        weights = collect_analytics._compute_scene_performance(stats, tags)

        assert "small" not in weights
        assert "ok" in weights

    def test_newer_video_velocity_beats_older_accumulated_views(self):
        now = datetime.now(UTC)
        stats = []
        tags = {}
        for i in range(3):
            cat_id = f"cat{i}"
            dog_id = f"dog{i}"
            stats.extend(
                [
                    {"video_id": cat_id, "views": 20, "published_at": (now - timedelta(days=1)).isoformat()},
                    {"video_id": dog_id, "views": 100, "published_at": (now - timedelta(days=30)).isoformat()},
                ]
            )
            tags[cat_id] = {"scene": "cat"}
            tags[dog_id] = {"scene": "dog"}

        weights = collect_analytics._compute_scene_performance(stats, tags)

        assert weights["cat"] > weights["dog"]

    def test_retention_improves_equally_timed_video_signal(self):
        now = datetime.now(UTC)
        high_retention = {
            "views": 100,
            "published_at": (now - timedelta(days=2)).isoformat(),
            "averageViewPercentage": 90,
        }
        low_retention = {**high_retention, "averageViewPercentage": 20}

        assert collect_analytics._performance_signal(high_retention, now) > collect_analytics._performance_signal(
            low_retention, now
        )


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


class TestComputeTitlePatternPerformance:
    """_compute_title_pattern_performance: mesmo mecanismo de
    _compute_scene_performance (generalizado em _compute_weighted_performance),
    so que cruzando views com o padrao de titulo (title_pattern em
    video_tags.json) em vez da cena - title_pattern ja era gravado no
    upload mas nunca fechava o loop de volta."""

    def _stats(self, *, a_views, b_views):
        stats = [{"video_id": f"a{i}", "views": v} for i, v in enumerate(a_views)]
        stats += [{"video_id": f"b{i}", "views": v} for i, v in enumerate(b_views)]
        return stats

    def _tags(self, *, a_count, b_count):
        tags = {f"a{i}": {"title_pattern": "pattern-a"} for i in range(a_count)}
        tags.update({f"b{i}": {"title_pattern": "pattern-b"} for i in range(b_count)})
        return tags

    def test_no_tagged_videos_returns_empty(self):
        stats = [{"video_id": "untagged1", "views": 100}]
        assert collect_analytics._compute_title_pattern_performance(stats, {}) == {}

    def test_pattern_with_too_few_samples_is_skipped(self):
        stats = self._stats(a_views=[100, 100], b_views=[10, 10, 10])
        tags = self._tags(a_count=2, b_count=3)

        weights = collect_analytics._compute_title_pattern_performance(stats, tags)

        assert "pattern-a" not in weights
        assert "pattern-b" in weights

    def test_above_average_pattern_gets_weight_above_one(self):
        stats = self._stats(a_views=[1000, 1000, 1000], b_views=[10, 10, 10])
        tags = self._tags(a_count=3, b_count=3)

        weights = collect_analytics._compute_title_pattern_performance(stats, tags)

        assert weights["pattern-a"] > 1.0
        assert weights["pattern-b"] < 1.0

    def test_weight_is_capped_at_max(self):
        stats = self._stats(a_views=[1_000_000] * 3, b_views=[1] * 30)
        stats += [{"video_id": f"c{i}", "views": 1} for i in range(30)]
        tags = self._tags(a_count=3, b_count=30)
        tags.update({f"c{i}": {"title_pattern": "pattern-c"} for i in range(30)})

        weights = collect_analytics._compute_title_pattern_performance(stats, tags)

        assert weights["pattern-a"] == collect_analytics._MAX_TITLE_PATTERN_WEIGHT
        assert weights["pattern-b"] == collect_analytics._MIN_TITLE_PATTERN_WEIGHT


class TestUpdateTitlePatternPerformance:
    """_update_title_pattern_performance mescla por cima do arquivo
    existente em vez de sobrescrever - mesmo raciocinio de
    _update_scene_performance."""

    def test_writes_new_file_when_none_exists(self, tmp_path, monkeypatch):
        perf_file = tmp_path / "title_pattern_performance.json"
        monkeypatch.setattr(collect_analytics, "TITLE_PATTERN_PERFORMANCE_FILE", perf_file)

        collect_analytics._update_title_pattern_performance({"pattern-a": 1.8})

        assert json.loads(perf_file.read_text(encoding="utf-8")) == {"pattern-a": 1.8}

    def test_preserves_pattern_missing_from_fresh_weights(self, tmp_path, monkeypatch):
        perf_file = tmp_path / "title_pattern_performance.json"
        perf_file.write_text(json.dumps({"pattern-a": 1.5, "pattern-b": 2.1}), encoding="utf-8")
        monkeypatch.setattr(collect_analytics, "TITLE_PATTERN_PERFORMANCE_FILE", perf_file)

        collect_analytics._update_title_pattern_performance({"pattern-a": 1.2})

        result = json.loads(perf_file.read_text(encoding="utf-8"))
        assert result["pattern-a"] == 1.2
        assert result["pattern-b"] == 2.1


class TestMaybeRotateThumbnail:
    """maybe_rotate_thumbnail: rotaciona a thumbnail pela sequencia A->B->C
    quando o video performa abaixo de _THUMBNAIL_ROTATION_THRESHOLD x a
    mediana apos _THUMBNAIL_ROTATION_DAYS dias (ou apos a ultima rotacao,
    para B->C). A YouTube Data API thumbnails.set so aceita 1 thumbnail por
    chamada (nao suporta A/B nativamente); esta rotacao e a alternativa
    pratica."""

    def _entry(self, *, uploaded_at, views, thumbnails, variant="A", rotated_at=None):
        entry = {
            "scene": "cat",
            "thumbnails": thumbnails,
            "thumbnail_variant": variant,
            "uploaded_at": uploaded_at,
            "views": views,
        }
        if rotated_at is not None:
            entry["rotated_at"] = rotated_at
        return entry

    def _thumb_paths(self, tmp_path):
        a = tmp_path / "thumb_a.png"
        b = tmp_path / "thumb_b.png"
        c = tmp_path / "thumb_c.png"
        a.write_bytes(b"png-a")
        b.write_bytes(b"png-b")
        c.write_bytes(b"png-c")
        return str(a), str(b), str(c)

    def test_rotates_a_to_b_when_below_median_and_old_enough(self, tmp_path):
        a, b, c = self._thumb_paths(tmp_path)
        now = datetime.now(UTC)
        uploaded = (now - timedelta(days=10)).isoformat()
        entry = self._entry(uploaded_at=uploaded, views=10, thumbnails=[a, b, c])
        service = MagicMock()

        with patch("scripts.collect_analytics._retry_youtube_call", side_effect=lambda f: f()):
            rotated = collect_analytics.maybe_rotate_thumbnail(service, "vid1", entry, median_views=1000, now=now)

        assert rotated is True
        assert entry["thumbnail_variant"] == "B"
        assert "rotated_at" in entry
        service.thumbnails().set.assert_called_once()

    def test_rotates_b_to_c_when_below_median_after_rotation_age(self, tmp_path):
        """B->C: precisa estar abaixo da mediana apos _THUMBNAIL_ROTATION_DAYS
        desde a ULTIMA rotacao (rotated_at), nao desde uploaded_at."""
        a, b, c = self._thumb_paths(tmp_path)
        now = datetime.now(UTC)
        # Upload ha 20 dias; rotacao A->B ha 3 dias (ainda dentro do prazo) â€”
        # nao deve rotacionar.
        uploaded = (now - timedelta(days=20)).isoformat()
        rotated_recent = (now - timedelta(days=3)).isoformat()
        entry = self._entry(
            uploaded_at=uploaded,
            views=1,
            thumbnails=[a, b, c],
            variant="B",
            rotated_at=rotated_recent,
        )
        service = MagicMock()
        rotated = collect_analytics.maybe_rotate_thumbnail(service, "vid1", entry, median_views=1000, now=now)
        assert rotated is False
        service.thumbnails().set.assert_not_called()

        # Agora rotated_at ha 10 dias (fora do prazo) â€” deve rotacionar B->C.
        rotated_old = (now - timedelta(days=10)).isoformat()
        entry = self._entry(
            uploaded_at=uploaded,
            views=1,
            thumbnails=[a, b, c],
            variant="B",
            rotated_at=rotated_old,
        )
        with patch("scripts.collect_analytics._retry_youtube_call", side_effect=lambda f: f()):
            rotated = collect_analytics.maybe_rotate_thumbnail(service, "vid1", entry, median_views=1000, now=now)
        assert rotated is True
        assert entry["thumbnail_variant"] == "C"

    def test_no_rotation_when_already_variant_c(self, tmp_path):
        a, b, c = self._thumb_paths(tmp_path)
        now = datetime.now(UTC)
        uploaded = (now - timedelta(days=30)).isoformat()
        entry = self._entry(uploaded_at=uploaded, views=1, thumbnails=[a, b, c], variant="C")
        service = MagicMock()

        rotated = collect_analytics.maybe_rotate_thumbnail(service, "vid1", entry, median_views=1000, now=now)

        assert rotated is False
        service.thumbnails().set.assert_not_called()

    def test_no_rotation_when_only_one_thumbnail(self, tmp_path):
        a, _, _ = self._thumb_paths(tmp_path)
        now = datetime.now(UTC)
        uploaded = (now - timedelta(days=30)).isoformat()
        entry = self._entry(uploaded_at=uploaded, views=1, thumbnails=[a])
        service = MagicMock()

        rotated = collect_analytics.maybe_rotate_thumbnail(service, "vid1", entry, median_views=1000, now=now)

        assert rotated is False
        service.thumbnails().set.assert_not_called()

    def test_no_rotation_when_two_thumbnails_and_already_b(self, tmp_path):
        """Apenas 2 variantes (A, B) e ja e B: nao ha C para rotacionar."""
        a, b, _ = self._thumb_paths(tmp_path)
        now = datetime.now(UTC)
        uploaded = (now - timedelta(days=30)).isoformat()
        rotated_old = (now - timedelta(days=30)).isoformat()
        entry = self._entry(
            uploaded_at=uploaded,
            views=1,
            thumbnails=[a, b],
            variant="B",
            rotated_at=rotated_old,
        )
        service = MagicMock()

        rotated = collect_analytics.maybe_rotate_thumbnail(service, "vid1", entry, median_views=1000, now=now)

        assert rotated is False
        service.thumbnails().set.assert_not_called()

    def test_no_rotation_when_younger_than_min_days(self, tmp_path):
        a, b, c = self._thumb_paths(tmp_path)
        now = datetime.now(UTC)
        uploaded = (now - timedelta(days=2)).isoformat()
        entry = self._entry(uploaded_at=uploaded, views=1, thumbnails=[a, b, c])
        service = MagicMock()

        rotated = collect_analytics.maybe_rotate_thumbnail(service, "vid1", entry, median_views=1000, now=now)

        assert rotated is False
        service.thumbnails().set.assert_not_called()

    def test_no_rotation_when_views_above_threshold(self, tmp_path):
        """views >= median * threshold (50%) -> ainda performando bem, nao troca."""
        a, b, c = self._thumb_paths(tmp_path)
        now = datetime.now(UTC)
        uploaded = (now - timedelta(days=30)).isoformat()
        entry = self._entry(uploaded_at=uploaded, views=600, thumbnails=[a, b, c])
        service = MagicMock()

        rotated = collect_analytics.maybe_rotate_thumbnail(service, "vid1", entry, median_views=1000, now=now)

        assert rotated is False
        service.thumbnails().set.assert_not_called()

    def test_no_rotation_when_median_is_zero(self, tmp_path):
        a, b, c = self._thumb_paths(tmp_path)
        now = datetime.now(UTC)
        uploaded = (now - timedelta(days=30)).isoformat()
        entry = self._entry(uploaded_at=uploaded, views=10, thumbnails=[a, b, c])
        service = MagicMock()

        rotated = collect_analytics.maybe_rotate_thumbnail(service, "vid1", entry, median_views=0, now=now)

        assert rotated is False
        service.thumbnails().set.assert_not_called()

    def test_rotation_failure_is_not_fatal(self, tmp_path):
        a, b, c = self._thumb_paths(tmp_path)
        now = datetime.now(UTC)
        uploaded = (now - timedelta(days=10)).isoformat()
        entry = self._entry(uploaded_at=uploaded, views=1, thumbnails=[a, b, c])
        service = MagicMock()

        with patch("scripts.collect_analytics._retry_youtube_call", side_effect=RuntimeError("api down")):
            rotated = collect_analytics.maybe_rotate_thumbnail(service, "vid1", entry, median_views=1000, now=now)

        assert rotated is False
        assert entry["thumbnail_variant"] == "A"

    def test_no_rotation_when_next_variant_file_missing(self, tmp_path):
        a = tmp_path / "thumb_a.png"
        a.write_bytes(b"png-a")
        # thumb_b aponta pra caminho inexistente; thumb_c tambem.
        missing_b = str(tmp_path / "missing_b.png")
        missing_c = str(tmp_path / "missing_c.png")
        now = datetime.now(UTC)
        uploaded = (now - timedelta(days=30)).isoformat()
        entry = self._entry(uploaded_at=uploaded, views=1, thumbnails=[str(a), missing_b, missing_c])
        service = MagicMock()

        rotated = collect_analytics.maybe_rotate_thumbnail(service, "vid1", entry, median_views=1000, now=now)

        assert rotated is False
        service.thumbnails().set.assert_not_called()


class TestThumbnailRotationSequence:
    """Sequencia completa A->B->C: cobre os 3 saltos (e o limite em C) num
    unico grupo de testes focado na transicao, reusando os helpers de
    TestMaybeRotateThumbnail (que cobre os casos de borda individuais)."""

    def _entry(self, *, uploaded_at, views, thumbnails, variant="A", rotated_at=None):
        entry = {
            "scene": "cat",
            "thumbnails": thumbnails,
            "thumbnail_variant": variant,
            "uploaded_at": uploaded_at,
            "views": views,
        }
        if rotated_at is not None:
            entry["rotated_at"] = rotated_at
        return entry

    def _thumb_paths(self, tmp_path, *, count=3):
        paths = []
        for label in ("a", "b", "c", "d")[:count]:
            p = tmp_path / f"thumb_{label}.png"
            p.write_bytes(f"png-{label}".encode())
            paths.append(str(p))
        return paths

    def test_a_to_b_when_below_median_and_old_enough(self, tmp_path):
        a, b, c = self._thumb_paths(tmp_path)
        now = datetime.now(UTC)
        uploaded = (now - timedelta(days=7)).isoformat()
        entry = self._entry(uploaded_at=uploaded, views=10, thumbnails=[a, b, c])
        service = MagicMock()

        with patch("scripts.collect_analytics._retry_youtube_call", side_effect=lambda f: f()):
            rotated = collect_analytics.maybe_rotate_thumbnail(service, "vid1", entry, median_views=1000, now=now)

        assert rotated is True
        assert entry["thumbnail_variant"] == "B"
        assert "rotated_at" in entry
        service.thumbnails().set.assert_called_once()

    def test_b_to_c_when_below_median_after_rotation_age(self, tmp_path):
        a, b, c = self._thumb_paths(tmp_path)
        now = datetime.now(UTC)
        uploaded = (now - timedelta(days=20)).isoformat()
        rotated_old = (now - timedelta(days=7)).isoformat()
        entry = self._entry(
            uploaded_at=uploaded,
            views=1,
            thumbnails=[a, b, c],
            variant="B",
            rotated_at=rotated_old,
        )
        service = MagicMock()

        with patch("scripts.collect_analytics._retry_youtube_call", side_effect=lambda f: f()):
            rotated = collect_analytics.maybe_rotate_thumbnail(service, "vid1", entry, median_views=1000, now=now)

        assert rotated is True
        assert entry["thumbnail_variant"] == "C"

    def test_c_stays_at_c_when_below_median(self, tmp_path):
        a, b, c = self._thumb_paths(tmp_path)
        now = datetime.now(UTC)
        uploaded = (now - timedelta(days=30)).isoformat()
        rotated_old = (now - timedelta(days=30)).isoformat()
        entry = self._entry(
            uploaded_at=uploaded,
            views=1,
            thumbnails=[a, b, c],
            variant="C",
            rotated_at=rotated_old,
        )
        service = MagicMock()

        rotated = collect_analytics.maybe_rotate_thumbnail(service, "vid1", entry, median_views=1000, now=now)

        assert rotated is False
        assert entry["thumbnail_variant"] == "C"
        service.thumbnails().set.assert_not_called()

    def test_no_rotation_when_above_median(self, tmp_path):
        a, b, c = self._thumb_paths(tmp_path)
        now = datetime.now(UTC)
        uploaded = (now - timedelta(days=30)).isoformat()
        entry = self._entry(uploaded_at=uploaded, views=600, thumbnails=[a, b, c])
        service = MagicMock()

        rotated = collect_analytics.maybe_rotate_thumbnail(service, "vid1", entry, median_views=1000, now=now)

        assert rotated is False
        assert entry["thumbnail_variant"] == "A"
        service.thumbnails().set.assert_not_called()

    def test_no_rotation_when_only_one_thumbnail_variant(self, tmp_path):
        a = self._thumb_paths(tmp_path, count=1)
        now = datetime.now(UTC)
        uploaded = (now - timedelta(days=30)).isoformat()
        entry = self._entry(uploaded_at=uploaded, views=1, thumbnails=a)
        service = MagicMock()

        rotated = collect_analytics.maybe_rotate_thumbnail(service, "vid1", entry, median_views=1000, now=now)

        assert rotated is False
        service.thumbnails().set.assert_not_called()

    def test_uses_uploaded_at_age_when_no_rotation_timestamp(self, tmp_path):
        """Sem rotated_at (primeira rotacao A->B), a idade conta desde
        uploaded_at; um video com 7+ dias deve rotacionar."""
        a, b, c = self._thumb_paths(tmp_path)
        now = datetime.now(UTC)
        uploaded = (now - timedelta(days=8)).isoformat()
        entry = self._entry(uploaded_at=uploaded, views=1, thumbnails=[a, b, c])
        service = MagicMock()

        with patch("scripts.collect_analytics._retry_youtube_call", side_effect=lambda f: f()):
            rotated = collect_analytics.maybe_rotate_thumbnail(service, "vid1", entry, median_views=1000, now=now)

        assert rotated is True
        assert entry["thumbnail_variant"] == "B"

    def test_does_not_rotate_when_uploaded_at_too_recent_and_no_rotated_at(self, tmp_path):
        """Complementar do anterior: sem rotated_at e uploaded_at < 7 dias,
        nao rotaciona (confirma que uploaded_at e o anchor usado)."""
        a, b, c = self._thumb_paths(tmp_path)
        now = datetime.now(UTC)
        uploaded = (now - timedelta(days=2)).isoformat()
        entry = self._entry(uploaded_at=uploaded, views=1, thumbnails=[a, b, c])
        service = MagicMock()

        rotated = collect_analytics.maybe_rotate_thumbnail(service, "vid1", entry, median_views=1000, now=now)

        assert rotated is False
        service.thumbnails().set.assert_not_called()


class TestMedianViews:
    def test_empty_stats_returns_zero(self):
        assert collect_analytics._median_views([]) == 0.0

    def test_odd_count_returns_middle(self):
        stats = [{"views": v} for v in [10, 5, 20]]
        assert collect_analytics._median_views(stats) == 10.0

    def test_even_count_returns_average_of_middles(self):
        stats = [{"views": v} for v in [1, 2, 3, 4]]
        assert collect_analytics._median_views(stats) == 2.5


class TestDetectViralVideos:
    """detect_viral_videos: um video e viral se suas views excedem
    _VIRAL_THRESHOLD (10x) a mediana do conjunto coletado. Devolve sinais
    com video_id/scene/title_pattern/views/viral_factor/detected_at."""

    def _stats(self, views_list):
        return [{"video_id": f"vid{i}", "views": v} for i, v in enumerate(views_list)]

    def _tags(self, mapping):
        return {vid: {"scene": s, "title_pattern": p} for vid, s, p in mapping}

    def test_no_virals_when_all_views_below_threshold(self):
        stats = self._stats([10, 20, 30, 40, 50])  # mediana 30
        tags = self._tags([("vid0", "cat", "p1")])

        virals = collect_analytics.detect_viral_videos(stats, tags)

        assert virals == []

    def test_detects_video_above_10x_median(self):
        # mediana = 30; 500 > 8*30 = 240 -> viral (factor ~16.67).
        stats = self._stats([10, 20, 30, 40, 500])
        tags = self._tags([("vid4", "cat", "p1")])

        virals = collect_analytics.detect_viral_videos(stats, tags)

        assert len(virals) == 1
        v = virals[0]
        assert v["video_id"] == "vid4"
        assert v["scene"] == "cat"
        assert v["title_pattern"] == "p1"
        assert v["views"] == 500
        assert v["viral_factor"] == round(500 / 30.0, 3)
        assert "detected_at" in v

    def test_detected_signal_includes_ctr_and_avp(self):
        stats = self._stats([10, 20, 30, 40, 500])
        stats[-1]["ctr"] = 0.12
        stats[-1]["averageViewPercentage"] = 0.78
        tags = self._tags([("vid4", "cat", "p1")])

        virals = collect_analytics.detect_viral_videos(stats, tags)

        assert virals[0]["ctr"] == 0.12
        assert virals[0]["avp"] == 0.78

    def test_untagged_viral_is_detected_with_empty_scene(self):
        """Um viral sem entrada em video_tags ainda e detectado, mas com
        scene/title_pattern vazios - o boost de cena so se aplica quando a
        tag existe."""
        stats = self._stats([10, 20, 30, 40, 500])
        virals = collect_analytics.detect_viral_videos(stats, {})

        assert len(virals) == 1
        assert virals[0]["scene"] == ""
        assert virals[0]["title_pattern"] == ""

    def test_zero_median_returns_empty(self):
        stats = self._stats([0, 0, 0])
        assert collect_analytics.detect_viral_videos(stats, {}) == []

    def test_custom_threshold_respected(self):
        stats = self._stats([10, 20, 30, 40, 100])  # mediana 30; 100 = 3.33x
        tags = self._tags([("vid4", "cat", "p1")])

        # threshold 3x -> 100/30 = 3.33 > 3 -> viral.
        virals = collect_analytics.detect_viral_videos(stats, tags, threshold=3.0)
        assert len(virals) == 1

        # threshold 5x -> 3.33 < 5 -> nao viral.
        virals = collect_analytics.detect_viral_videos(stats, tags, threshold=5.0)
        assert virals == []

    def test_detected_at_is_iso_now(self):
        stats = self._stats([10, 20, 30, 40, 500])
        fixed = datetime(2026, 7, 27, 6, 0, 0, tzinfo=UTC)

        virals = collect_analytics.detect_viral_videos(stats, {}, now=fixed)

        assert virals[0]["detected_at"] == fixed.isoformat()


class TestSaveViralSignals:
    def test_writes_json_list_to_file(self, tmp_path, monkeypatch):
        out = tmp_path / "viral_signals.json"
        monkeypatch.setattr(collect_analytics, "VIRAL_SIGNALS_FILE", out)
        virals = [{"video_id": "v1", "scene": "cat", "views": 500, "viral_factor": 16.5}]

        collect_analytics._save_viral_signals(virals, path=out)

        data = json.loads(out.read_text(encoding="utf-8"))
        assert data == virals

    def test_creates_parent_dir(self, tmp_path, monkeypatch):
        out = tmp_path / "nested" / "viral_signals.json"
        monkeypatch.setattr(collect_analytics, "VIRAL_SIGNALS_FILE", out)

        collect_analytics._save_viral_signals([], path=out)

        assert out.exists()
        assert json.loads(out.read_text(encoding="utf-8")) == []

    def test_overwrites_previous_content(self, tmp_path, monkeypatch):
        out = tmp_path / "viral_signals.json"
        monkeypatch.setattr(collect_analytics, "VIRAL_SIGNALS_FILE", out)
        out.write_text(json.dumps([{"old": "stale"}]), encoding="utf-8")

        collect_analytics._save_viral_signals([{"video_id": "v1"}], path=out)

        data = json.loads(out.read_text(encoding="utf-8"))
        assert data == [{"video_id": "v1"}]


class TestRecordThumbnailVariantInStats:
    """_record_thumbnail_variant_in_stats: mescla thumbnail_variant de
    video_tags.json em cada stat dict, pra fechar o loop de feedback de
    variante de thumbnail (qual variante estava ativa quando as views foram
    coletadas)."""

    def test_adds_variant_from_video_tags(self):
        stats = [{"video_id": "v1", "views": 100}, {"video_id": "v2", "views": 200}]
        tags = {"v1": {"thumbnail_variant": "B"}, "v2": {"thumbnail_variant": "C"}}

        enriched = collect_analytics._record_thumbnail_variant_in_stats(stats, tags)

        assert enriched[0]["thumbnail_variant"] == "B"
        assert enriched[1]["thumbnail_variant"] == "C"

    def test_defaults_to_a_when_tag_missing(self):
        stats = [{"video_id": "v1", "views": 100}]
        enriched = collect_analytics._record_thumbnail_variant_in_stats(stats, {})
        assert enriched[0]["thumbnail_variant"] == "A"

    def test_defaults_to_a_when_variant_field_absent(self):
        stats = [{"video_id": "v1", "views": 100}]
        tags = {"v1": {"scene": "cat"}}  # sem thumbnail_variant
        enriched = collect_analytics._record_thumbnail_variant_in_stats(stats, tags)
        assert enriched[0]["thumbnail_variant"] == "A"

    def test_does_not_mutate_original_stats(self):
        stats = [{"video_id": "v1", "views": 100}]
        tags = {"v1": {"thumbnail_variant": "B"}}

        collect_analytics._record_thumbnail_variant_in_stats(stats, tags)

        assert "thumbnail_variant" not in stats[0]

    def test_preserves_other_fields(self):
        stats = [{"video_id": "v1", "views": 100, "likes": 5, "title": "T"}]
        enriched = collect_analytics._record_thumbnail_variant_in_stats(stats, {"v1": {"thumbnail_variant": "C"}})
        assert enriched[0]["likes"] == 5
        assert enriched[0]["title"] == "T"


class TestParseIso8601Duration:
    """_parse_iso8601_duration: converte duracao ISO 8601 do YouTube em segundos."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("PT1M", 60.0),
            ("PT2M", 120.0),
            ("PT1M30S", 90.0),
            ("PT30S", 30.0),
            ("PT2H", 7200.0),
            ("PT1H2M3S", 3723.0),
            ("", 0.0),
            ("garbage", 0.0),
            (None, 0.0),
        ],
    )
    def test_parse(self, raw, expected):
        assert collect_analytics._parse_iso8601_duration(raw) == expected


class TestYppEligibility:
    """_ypp_eligibility: estima watch time real a partir da duracao dos videos."""

    def test_uses_real_duration_not_hardcoded_30s(self):
        # 2 videos de 60s, 100 views total -> 100 * 60s = 6000s = ~1.6h
        stats = [
            {"duration": "PT1M", "views": 50},
            {"duration": "PT1M", "views": 50},
        ]
        result = collect_analytics._ypp_eligibility({"subscriber_count": 0, "total_views": 100}, stats)
        assert result["watch_hours_estimate"] == 1  # 6000s / 3600 = 1.66 -> int 1

    def test_empty_stats_gives_zero_watch_hours(self):
        result = collect_analytics._ypp_eligibility({"subscriber_count": 0, "total_views": 100}, [])
        assert result["watch_hours_estimate"] == 0

    def test_eligible_when_subs_and_watch_hours_met(self):
        # 1000 subs + 4000h: 1000 views * 14400s (4h) = 4M s = 1111h... use
        # 4000h via 4000 views de 3600s cada.
        stats = [{"duration": "PT1H", "views": 4000}]
        result = collect_analytics._ypp_eligibility(
            {"subscriber_count": 1000, "total_views": 4000}, stats
        )
        assert result["eligible"] is True


class TestCollectRetentionMetrics:
    """_collect_retention_metrics: chama o YouTube Analytics API
    (youtubeAnalytics.reports().query) por video para buscar
    averageViewDuration, averageViewPercentage (retention) e ctr.

    A Analytics API pode nao estar disponivel para todos os canais (403,
    canal novo sem dados, scope ausente) - qualquer erro e tratado como
    nao-fatal: loga warning e segue (retorna {} ou o subset que deu)."""

    def _analytics_service(
        self, rows_by_video: dict[str, list[list]] | None = None, raise_on_query: Exception | None = None
    ):
        service = MagicMock()
        reports_mock = MagicMock()
        query_mock = MagicMock()
        service.reports.return_value = reports_mock
        reports_mock.query.return_value = query_mock
        if raise_on_query is not None:
            query_mock.execute.side_effect = raise_on_query
        else:

            def _execute():
                call_args = reports_mock.query.call_args
                filters = call_args.kwargs.get("filters", "") if call_args else ""
                vid = filters.split("==", 1)[1] if "==" in filters else ""
                rows = (rows_by_video or {}).get(vid, [])
                return {"rows": rows}

            query_mock.execute.side_effect = _execute
        return service

    def test_returns_metrics_for_each_video(self):
        # Ordem das metricas: averageViewDuration, averageViewPercentage,
        # subscribersGained, likes, comments, estimatedMinutesWatched
        rows = {
            "vid1": [[120.0, 55.5, 2.0, 5.0, 1.0, 600.0]],
            "vid2": [[200.0, 70.0, 3.0, 10.0, 2.0, 1000.0]],
        }
        service = self._analytics_service(rows_by_video=rows)

        result = collect_analytics._collect_retention_metrics(service, ["vid1", "vid2"])

        assert result["vid1"] == {
            "averageViewDuration": 120.0,
            "averageViewPercentage": 55.5,
            "subscribersGained": 2.0,
            "likes": 5.0,
            "comments": 1.0,
            "estimatedMinutesWatched": 600.0,
        }
        assert result["vid2"]["averageViewDuration"] == 200.0
        assert result["vid2"]["subscribersGained"] == 3.0
        assert result["vid2"]["estimatedMinutesWatched"] == 1000.0

    def test_empty_video_ids_returns_empty(self):
        service = self._analytics_service()
        assert collect_analytics._collect_retention_metrics(service, []) == {}
        service.reports().query.assert_not_called()

    def test_video_without_rows_is_skipped(self):
        rows = {"vid1": [[100.0, 50.0, 2.0, 5.0, 1.0, 500.0]]}  # vid2 sem rows
        service = self._analytics_service(rows_by_video=rows)

        result = collect_analytics._collect_retention_metrics(service, ["vid1", "vid2"])

        assert "vid1" in result
        assert "vid2" not in result

    def test_api_error_returns_empty_and_does_not_crash(self):
        service = self._analytics_service(raise_on_query=RuntimeError("403 Forbidden"))

        result = collect_analytics._collect_retention_metrics(service, ["vid1", "vid2"])

        assert result == {}

    def test_partial_failure_returns_subset(self):
        """Se a API falha para alguns videos mas nao todos, o subset que deu
        certo ainda e retornado (nao aborta no primeiro erro)."""
        service = MagicMock()
        reports_mock = MagicMock()
        query_mock = MagicMock()
        service.reports.return_value = reports_mock
        reports_mock.query.return_value = query_mock
        call_count = {"n": 0}

        def _execute():
            call_count["n"] += 1
            if call_count["n"] == 1:
                return {"rows": [[100.0, 50.0, 2.0, 5.0, 1.0, 500.0]]}
            raise RuntimeError("403 Forbidden")

        query_mock.execute.side_effect = _execute

        result = collect_analytics._collect_retention_metrics(service, ["vid1", "vid2"])

        assert "vid1" in result
        assert "vid2" not in result

    def test_query_uses_channel_mine_and_metrics(self):
        service = self._analytics_service(rows_by_video={"vid1": [[1.0, 1.0, 1.0, 1.0, 1.0, 1.0]]})

        collect_analytics._collect_retention_metrics(service, ["vid1"])

        kwargs = service.reports.return_value.query.call_args.kwargs
        assert kwargs["ids"] == "channel==mine"
        assert kwargs["metrics"] == (
            "averageViewDuration,averageViewPercentage,"
            "subscribersGained,likes,comments,estimatedMinutesWatched"
        )
        assert kwargs["filters"] == "video==vid1"
        assert "startDate" in kwargs and "endDate" in kwargs


class TestSnapshotOnlyFlag:
    """--snapshot-only: modo leve diario que so coleta stats + historico,
    pulando computacao pesada de cena/title_pattern, virais e rotacao."""

    def _patch_run(self, monkeypatch, tmp_path):
        """Patcha dependencias externas de main() pra um run em memoria."""
        monkeypatch.setattr(collect_analytics, "DATA_DIR", tmp_path)
        monkeypatch.setattr(collect_analytics, "HISTORY_FILE", tmp_path / "analytics_history.json")
        monkeypatch.setattr(collect_analytics, "VIDEO_TAGS_FILE", tmp_path / "video_tags.json")
        monkeypatch.setattr(collect_analytics, "SCENE_PERFORMANCE_FILE", tmp_path / "scene_perf.json")
        monkeypatch.setattr(collect_analytics, "TITLE_PATTERN_PERFORMANCE_FILE", tmp_path / "tp_perf.json")
        monkeypatch.setattr(collect_analytics, "VIRAL_SIGNALS_FILE", tmp_path / "viral.json")
        monkeypatch.setattr(collect_analytics, "get_youtube_service", lambda: MagicMock())
        monkeypatch.setattr(collect_analytics, "get_youtube_analytics_service", lambda: MagicMock())
        stats = [
            {
                "video_id": "v1",
                "views": 100,
                "likes": 1,
                "comments": 0,
                "title": "t",
                "published_at": "2026-01-01",
                "duration": "PT1M",
            }
        ]
        monkeypatch.setattr(collect_analytics, "collect_video_stats", lambda service: (stats, {"subscriber_count": 10}))
        return stats

    def test_snapshot_only_skips_scene_performance_file(self, tmp_path, monkeypatch):
        self._patch_run(monkeypatch, tmp_path)
        perf_file = tmp_path / "scene_perf.json"

        collect_analytics.main(["--snapshot-only"])

        assert not perf_file.exists()

    def test_snapshot_only_skips_viral_signals_file(self, tmp_path, monkeypatch):
        self._patch_run(monkeypatch, tmp_path)
        viral_file = tmp_path / "viral.json"

        collect_analytics.main(["--snapshot-only"])

        assert not viral_file.exists()

    def test_snapshot_only_still_writes_history(self, tmp_path, monkeypatch):
        self._patch_run(monkeypatch, tmp_path)

        collect_analytics.main(["--snapshot-only"])

        history = json.loads((tmp_path / "analytics_history.json").read_text())
        assert len(history) == 1
        assert history[0]["total_views"] == 100

    def test_full_run_writes_scene_performance(self, tmp_path, monkeypatch):
        self._patch_run(monkeypatch, tmp_path)
        # 3 videos tagueados com a mesma cena pra passar _MIN_SCENE_SAMPLES.
        stats = [
            {
                "video_id": f"v{i}",
                "views": v,
                "likes": 0,
                "comments": 0,
                "title": "t",
                "published_at": "2026-01-01",
                "duration": "PT1M",
            }
            for i, v in enumerate([100, 100, 100])
        ]
        monkeypatch.setattr(collect_analytics, "collect_video_stats", lambda service: (stats, {"subscriber_count": 10}))
        (tmp_path / "video_tags.json").write_text(
            json.dumps({f"v{i}": {"scene": "cat", "title_pattern": "p"} for i in range(3)}),
            encoding="utf-8",
        )

        collect_analytics.main([])

        assert (tmp_path / "scene_perf.json").exists()
        assert (tmp_path / "viral.json").exists()

    def test_snapshot_only_skips_retention_metrics(self, tmp_path, monkeypatch):
        self._patch_run(monkeypatch, tmp_path)
        called = {"n": 0}
        monkeypatch.setattr(
            collect_analytics,
            "get_youtube_analytics_service",
            lambda: called.__setitem__("n", called["n"] + 1) or MagicMock(),
        )

        collect_analytics.main(["--snapshot-only"])

        # snapshot-only nao tenta construir o Analytics service.
        assert called["n"] == 0
        analytics = json.loads((tmp_path / "analytics.json").read_text())
        assert "retention_metrics" not in analytics

    def test_full_run_collects_retention_metrics(self, tmp_path, monkeypatch):
        self._patch_run(monkeypatch, tmp_path)
        stats = [
            {
                "video_id": f"v{i}",
                "views": 100,
                "likes": 0,
                "comments": 0,
                "title": "t",
                "published_at": "2026-01-01",
                "duration": "PT1M",
            }
            for i in range(3)
        ]
        monkeypatch.setattr(collect_analytics, "collect_video_stats", lambda service: (stats, {"subscriber_count": 10}))
        (tmp_path / "video_tags.json").write_text(
            json.dumps({f"v{i}": {"scene": "cat", "title_pattern": "p"} for i in range(3)}),
            encoding="utf-8",
        )
        monkeypatch.setattr(collect_analytics, "get_youtube_analytics_service", lambda: MagicMock())
        captured = {"ids": []}

        def _spy(service, video_ids):
            captured["ids"] = video_ids
            return {"v0": {"averageViewDuration": 60.0, "averageViewPercentage": 50.0, "subscribersGained": 2.0}}

        monkeypatch.setattr(collect_analytics, "_collect_retention_metrics", _spy)

        collect_analytics.main([])

        assert captured["ids"] == ["v0", "v1", "v2"]
        analytics = json.loads((tmp_path / "analytics.json").read_text())
        assert "retention_metrics" in analytics
        assert analytics["retention_metrics"]["v0"]["averageViewDuration"] == 60.0

    def test_full_run_without_analytics_service_still_succeeds(self, tmp_path, monkeypatch):
        self._patch_run(monkeypatch, tmp_path)
        stats = [
            {
                "video_id": f"v{i}",
                "views": 100,
                "likes": 0,
                "comments": 0,
                "title": "t",
                "published_at": "2026-01-01",
                "duration": "PT1M",
            }
            for i in range(3)
        ]
        monkeypatch.setattr(collect_analytics, "collect_video_stats", lambda service: (stats, {"subscriber_count": 10}))
        (tmp_path / "video_tags.json").write_text(
            json.dumps({f"v{i}": {"scene": "cat", "title_pattern": "p"} for i in range(3)}),
            encoding="utf-8",
        )

        def _raise():
            raise RuntimeError("analytics unavailable")

        monkeypatch.setattr(collect_analytics, "get_youtube_analytics_service", _raise)

        assert collect_analytics.main([]) == 0
        analytics = json.loads((tmp_path / "analytics.json").read_text())
        assert "retention_metrics" not in analytics
