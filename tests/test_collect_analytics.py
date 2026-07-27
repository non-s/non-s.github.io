"""Testes para collect_analytics.py."""
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

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

    def test_empty_page_breaks_even_with_next_page_token(self):
        """Uma pagina vazia (items == []) com nextPageToken presente deve
        quebrar imediatamente - nao continuar paginando."""
        service = MagicMock()
        service.channels().list.return_value.execute.return_value = {
            "items": [{
                "id": "channel123",
                "contentDetails": {"relatedPlaylists": {"uploads": "uploads_playlist"}},
            }]
        }
        service.playlistItems().list.return_value.execute.side_effect = [
            {"items": [], "nextPageToken": "page2"},
            {"items": [{"snippet": {"resourceId": {"videoId": "vid1"}}}], "nextPageToken": ""},
        ]
        service.videos().list.return_value.execute.return_value = {"items": []}

        stats = collect_analytics.collect_video_stats(service)

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
        stats, tags = self._stats_tags({
            "a": [2000, 2000, 2000],
            "b": [1000, 100, 50],
        })

        weights = collect_analytics._compute_scene_performance(stats, tags)

        assert weights["a"] > weights["b"]
        assert weights["a"] > 1.0
        assert weights["b"] < 1.0

    def test_viral_inconsistent_penalized_vs_consistent(self):
        # Cena viral: 1 viral + 2 baixos (p=0.33 mas views altas).
        # Cena consistente: 2 acima 1 abaixo (p=0.66, views medias).
        stats, tags = self._stats_tags({
            "viral": [100000, 100, 100],
            "consistent": [1000, 1000, 100],
        })

        weights = collect_analytics._compute_scene_performance(stats, tags)

        assert weights["consistent"] > weights["viral"]

    def test_below_min_samples_is_neutral(self):
        stats, tags = self._stats_tags({
            "small": [1000, 1000],
            "ok": [1000, 1000, 1000],
        })

        weights = collect_analytics._compute_scene_performance(stats, tags)

        assert "small" not in weights
        assert "ok" in weights


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
            rotated = collect_analytics.maybe_rotate_thumbnail(
                service, "vid1", entry, median_views=1000, now=now
            )

        assert rotated is True
        assert entry["thumbnail_variant"] == "B"
        assert "rotated_at" in entry
        service.thumbnails().set.assert_called_once()

    def test_rotates_b_to_c_when_below_median_after_rotation_age(self, tmp_path):
        """B->C: precisa estar abaixo da mediana apos _THUMBNAIL_ROTATION_DAYS
        desde a ULTIMA rotacao (rotated_at), nao desde uploaded_at."""
        a, b, c = self._thumb_paths(tmp_path)
        now = datetime.now(UTC)
        # Upload ha 20 dias; rotacao A->B ha 3 dias (ainda dentro do prazo) —
        # nao deve rotacionar.
        uploaded = (now - timedelta(days=20)).isoformat()
        rotated_recent = (now - timedelta(days=3)).isoformat()
        entry = self._entry(
            uploaded_at=uploaded, views=1, thumbnails=[a, b, c],
            variant="B", rotated_at=rotated_recent,
        )
        service = MagicMock()
        rotated = collect_analytics.maybe_rotate_thumbnail(
            service, "vid1", entry, median_views=1000, now=now
        )
        assert rotated is False
        service.thumbnails().set.assert_not_called()

        # Agora rotated_at ha 10 dias (fora do prazo) — deve rotacionar B->C.
        rotated_old = (now - timedelta(days=10)).isoformat()
        entry = self._entry(
            uploaded_at=uploaded, views=1, thumbnails=[a, b, c],
            variant="B", rotated_at=rotated_old,
        )
        with patch("scripts.collect_analytics._retry_youtube_call", side_effect=lambda f: f()):
            rotated = collect_analytics.maybe_rotate_thumbnail(
                service, "vid1", entry, median_views=1000, now=now
            )
        assert rotated is True
        assert entry["thumbnail_variant"] == "C"

    def test_no_rotation_when_already_variant_c(self, tmp_path):
        a, b, c = self._thumb_paths(tmp_path)
        now = datetime.now(UTC)
        uploaded = (now - timedelta(days=30)).isoformat()
        entry = self._entry(
            uploaded_at=uploaded, views=1, thumbnails=[a, b, c], variant="C"
        )
        service = MagicMock()

        rotated = collect_analytics.maybe_rotate_thumbnail(
            service, "vid1", entry, median_views=1000, now=now
        )

        assert rotated is False
        service.thumbnails().set.assert_not_called()

    def test_no_rotation_when_only_one_thumbnail(self, tmp_path):
        a, _, _ = self._thumb_paths(tmp_path)
        now = datetime.now(UTC)
        uploaded = (now - timedelta(days=30)).isoformat()
        entry = self._entry(uploaded_at=uploaded, views=1, thumbnails=[a])
        service = MagicMock()

        rotated = collect_analytics.maybe_rotate_thumbnail(
            service, "vid1", entry, median_views=1000, now=now
        )

        assert rotated is False
        service.thumbnails().set.assert_not_called()

    def test_no_rotation_when_two_thumbnails_and_already_b(self, tmp_path):
        """Apenas 2 variantes (A, B) e ja e B: nao ha C para rotacionar."""
        a, b, _ = self._thumb_paths(tmp_path)
        now = datetime.now(UTC)
        uploaded = (now - timedelta(days=30)).isoformat()
        rotated_old = (now - timedelta(days=30)).isoformat()
        entry = self._entry(
            uploaded_at=uploaded, views=1, thumbnails=[a, b],
            variant="B", rotated_at=rotated_old,
        )
        service = MagicMock()

        rotated = collect_analytics.maybe_rotate_thumbnail(
            service, "vid1", entry, median_views=1000, now=now
        )

        assert rotated is False
        service.thumbnails().set.assert_not_called()

    def test_no_rotation_when_younger_than_min_days(self, tmp_path):
        a, b, c = self._thumb_paths(tmp_path)
        now = datetime.now(UTC)
        uploaded = (now - timedelta(days=2)).isoformat()
        entry = self._entry(uploaded_at=uploaded, views=1, thumbnails=[a, b, c])
        service = MagicMock()

        rotated = collect_analytics.maybe_rotate_thumbnail(
            service, "vid1", entry, median_views=1000, now=now
        )

        assert rotated is False
        service.thumbnails().set.assert_not_called()

    def test_no_rotation_when_views_above_threshold(self, tmp_path):
        """views >= median * threshold (50%) -> ainda performando bem, nao troca."""
        a, b, c = self._thumb_paths(tmp_path)
        now = datetime.now(UTC)
        uploaded = (now - timedelta(days=30)).isoformat()
        entry = self._entry(uploaded_at=uploaded, views=600, thumbnails=[a, b, c])
        service = MagicMock()

        rotated = collect_analytics.maybe_rotate_thumbnail(
            service, "vid1", entry, median_views=1000, now=now
        )

        assert rotated is False
        service.thumbnails().set.assert_not_called()

    def test_no_rotation_when_median_is_zero(self, tmp_path):
        a, b, c = self._thumb_paths(tmp_path)
        now = datetime.now(UTC)
        uploaded = (now - timedelta(days=30)).isoformat()
        entry = self._entry(uploaded_at=uploaded, views=10, thumbnails=[a, b, c])
        service = MagicMock()

        rotated = collect_analytics.maybe_rotate_thumbnail(
            service, "vid1", entry, median_views=0, now=now
        )

        assert rotated is False
        service.thumbnails().set.assert_not_called()

    def test_rotation_failure_is_not_fatal(self, tmp_path):
        a, b, c = self._thumb_paths(tmp_path)
        now = datetime.now(UTC)
        uploaded = (now - timedelta(days=10)).isoformat()
        entry = self._entry(uploaded_at=uploaded, views=1, thumbnails=[a, b, c])
        service = MagicMock()

        with patch("scripts.collect_analytics._retry_youtube_call", side_effect=RuntimeError("api down")):
            rotated = collect_analytics.maybe_rotate_thumbnail(
                service, "vid1", entry, median_views=1000, now=now
            )

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
        entry = self._entry(
            uploaded_at=uploaded, views=1, thumbnails=[str(a), missing_b, missing_c]
        )
        service = MagicMock()

        rotated = collect_analytics.maybe_rotate_thumbnail(
            service, "vid1", entry, median_views=1000, now=now
        )

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
