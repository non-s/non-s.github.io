"""Testes para A2 - Trending topics do YouTube (scripts/sync_trending.py)."""

import json
from unittest.mock import MagicMock, patch

import scripts.sync_trending as sync_trending
import utils.seo_keywords as seo_keywords


class TestExtractKeywordsFromTitle:
    def test_extracts_individual_words(self):
        kws = sync_trending._extract_keywords_from_title("Cute Cat Relaxing with Jazz Music")
        assert "cute" in kws
        assert "cat" in kws
        assert "relaxing" in kws

    def test_extracts_bigrams(self):
        kws = sync_trending._extract_keywords_from_title("Pet Anxiety Relief Calm")
        # Bigrams de palavras adjacentes que nao sao stop words
        assert "pet anxiety" in kws
        assert "anxiety relief" in kws

    def test_filters_stop_words(self):
        kws = sync_trending._extract_keywords_from_title("The Best Cat Video for You")
        assert "the" not in kws
        assert "best" not in kws
        assert "for" not in kws
        assert "you" not in kws

    def test_filters_short_words(self):
        kws = sync_trending._extract_keywords_from_title("Cat 4K HD Video")
        # "4k" e "hd" tem 2 chars, sao filtrados
        assert "4k" not in kws
        assert "hd" not in kws
        assert "cat" in kws

    def test_filters_niche_stop_words(self):
        kws = sync_trending._extract_keywords_from_title("Pata Jazz Music Video")
        assert "pata" not in kws
        assert "jazz" not in kws
        assert "music" not in kws
        assert "video" not in kws

    def test_empty_title_returns_empty(self):
        assert sync_trending._extract_keywords_from_title("") == []

    def test_normalizes_to_lowercase(self):
        kws = sync_trending._extract_keywords_from_title("CUTE CAT")
        assert "cute" in kws
        assert "cat" in kws


class TestComputeTrendingKeywords:
    def test_returns_top_keywords_by_frequency(self):
        videos = [
            {"title": "Pet Anxiety Music for Dogs"},
            {"title": "Pet Anxiety Relief Calm"},
            {"title": "Cat Sleeping Music"},
            {"title": "Dog Anxiety Music Calm"},
        ]
        trending = sync_trending._compute_trending_keywords(videos)
        # "anxiety" aparece 3x, "pet" 2x, "calm" 2x
        assert "anxiety" in trending
        assert "pet anxiety" in trending

    def test_filters_low_frequency_keywords(self):
        videos = [{"title": "Unique Rare Keyword Once"}]
        trending = sync_trending._compute_trending_keywords(videos)
        # _MIN_FREQUENCY = 2, entao keywords que aparecem so 1x sao filtradas
        assert "unique" not in trending

    def test_respects_max_keywords_limit(self):
        # Gerar muitas keywords com frequencia alta
        videos = []
        for i in range(30):
            videos.append({"title": f"keyword{i} keyword{i} common"})
        trending = sync_trending._compute_trending_keywords(videos)
        assert len(trending) <= sync_trending._MAX_TRENDING_KEYWORDS

    def test_empty_videos_returns_empty(self):
        assert sync_trending._compute_trending_keywords([]) == []


class TestSaveLoadTrendingKeywords:
    def test_save_and_load_roundtrip(self, tmp_path, monkeypatch):
        out = tmp_path / "trending_keywords.json"
        monkeypatch.setattr(sync_trending, "TRENDING_FILE", out)
        keywords = ["pet anxiety", "calming music", "dog sleep"]
        sync_trending.save_trending_keywords(keywords)
        assert out.exists()
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["keywords"] == keywords
        assert "collected_at" in data

    def test_load_returns_keywords_list(self, tmp_path, monkeypatch):
        out = tmp_path / "trending_keywords.json"
        monkeypatch.setattr(sync_trending, "TRENDING_FILE", out)
        out.write_text(json.dumps({"keywords": ["k1", "k2"], "collected_at": "2026-01-01"}))
        assert sync_trending.load_trending_keywords() == ["k1", "k2"]

    def test_load_missing_file_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sync_trending, "TRENDING_FILE", tmp_path / "missing.json")
        assert sync_trending.load_trending_keywords() == []

    def test_load_corrupted_file_returns_empty(self, tmp_path, monkeypatch):
        out = tmp_path / "trending_keywords.json"
        monkeypatch.setattr(sync_trending, "TRENDING_FILE", out)
        out.write_text("not json")
        assert sync_trending.load_trending_keywords() == []


class TestSeoKeywordsTrendingIntegration:
    """seo_keywords.trending_keywords() mescla trending estatico com
    dinamico do _data/trending_keywords.json."""

    def test_returns_static_when_no_dynamic_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(seo_keywords, "data_dir", lambda: tmp_path)
        result = seo_keywords.trending_keywords()
        # Pelo menos as estaticas (thunderstorm/fireworks/etc) devem aparecer
        assert len(result) > 0
        assert "thunderstorm music for dogs" in result

    def test_dynamic_prepended_to_static(self, tmp_path, monkeypatch):
        monkeypatch.setattr(seo_keywords, "data_dir", lambda: tmp_path)
        trending_file = tmp_path / "trending_keywords.json"
        trending_file.write_text(json.dumps({"keywords": ["custom trending 1", "custom trending 2"]}))
        result = seo_keywords.trending_keywords()
        assert "custom trending 1" in result
        assert "custom trending 2" in result
        # Estaticas ainda presentes
        assert "thunderstorm music for dogs" in result

    def test_dynamic_appears_first(self, tmp_path, monkeypatch):
        monkeypatch.setattr(seo_keywords, "data_dir", lambda: tmp_path)
        trending_file = tmp_path / "trending_keywords.json"
        trending_file.write_text(json.dumps({"keywords": ["dynamic_first"]}))
        result = seo_keywords.trending_keywords()
        assert result[0] == "dynamic_first"

    def test_no_duplicates(self, tmp_path, monkeypatch):
        monkeypatch.setattr(seo_keywords, "data_dir", lambda: tmp_path)
        trending_file = tmp_path / "trending_keywords.json"
        # "thunderstorm music for dogs" ja esta no estatico; nao duplica
        trending_file.write_text(
            json.dumps({"keywords": ["thunderstorm music for dogs", "new keyword"]})
        )
        result = seo_keywords.trending_keywords()
        assert result.count("thunderstorm music for dogs") == 1


class TestSearchYoutube:
    def test_returns_items_with_titles(self):
        service = MagicMock()
        service.search().list.return_value.execute.return_value = {
            "items": [
                {"snippet": {"title": "Cute Cat Video"}},
                {"snippet": {"title": "Dog Relaxing Music"}},
            ]
        }
        with patch("utils.youtube_retry.retry_youtube_call", side_effect=lambda f: f()):
            videos = sync_trending._search_youtube(service, "cat", "2026-01-01T00:00:00Z", 25)
        assert len(videos) == 2
        assert videos[0]["title"] == "Cute Cat Video"

    def test_returns_empty_on_error(self):
        service = MagicMock()
        with patch("utils.youtube_retry.retry_youtube_call", side_effect=RuntimeError("api down")):
            videos = sync_trending._search_youtube(service, "cat", "2026-01-01T00:00:00Z", 25)
        assert videos == []
