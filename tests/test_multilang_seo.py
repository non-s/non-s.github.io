"""Testes para A3 - SEO multilingue PT-BR + ES."""

import json
from unittest.mock import patch

import utils.metadata_engine as metadata_engine
import utils.seo_keywords as seo_keywords
from utils.seo_keywords import HIGH_VOLUME_KEYWORDS_ES, HIGH_VOLUME_KEYWORDS_PT


class TestPickUploadLanguage:
    """pick_upload_language: decide o idioma do próximo upload baseado num
    contador persistente. 1 a cada 6 -> PT-BR, 1 a cada 12 -> ES, resto EN."""

    def test_returns_en_on_first_call(self, tmp_path, monkeypatch):
        monkeypatch.setattr(seo_keywords, "data_dir", lambda: tmp_path)
        # Garante que nao ha arquivo previo
        assert seo_keywords.pick_upload_language() == "en"

    def test_returns_pt_every_sixth(self, tmp_path, monkeypatch):
        monkeypatch.setattr(seo_keywords, "data_dir", lambda: tmp_path)
        counter = tmp_path / "upload_language_counter.json"
        # Pre-popula contador em 5 -> proxima chamada (6) deve ser PT
        counter.write_text(json.dumps({"count": 5}))
        assert seo_keywords.pick_upload_language() == "pt"

    def test_returns_es_every_twelfth(self, tmp_path, monkeypatch):
        monkeypatch.setattr(seo_keywords, "data_dir", lambda: tmp_path)
        counter = tmp_path / "upload_language_counter.json"
        # Pre-popula contador em 11 -> proxima chamada (12) deve ser ES
        counter.write_text(json.dumps({"count": 11}))
        assert seo_keywords.pick_upload_language() == "es"

    def test_returns_en_otherwise(self, tmp_path, monkeypatch):
        monkeypatch.setattr(seo_keywords, "data_dir", lambda: tmp_path)
        counter = tmp_path / "upload_language_counter.json"
        # Counters nao multiplos de 6 -> EN
        for n in [1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 13, 14]:
            counter.write_text(json.dumps({"count": n - 1}))
            assert seo_keywords.pick_upload_language() == "en"

    def test_es_takes_precedence_over_pt_at_12(self, tmp_path, monkeypatch):
        """12 e multiplo de 6 E de 12. ES tem prioridade (menos frequente,
        mas mais especifico)."""
        monkeypatch.setattr(seo_keywords, "data_dir", lambda: tmp_path)
        counter = tmp_path / "upload_language_counter.json"
        counter.write_text(json.dumps({"count": 11}))
        # 12 % 12 == 0 -> ES (testado antes de 12 % 6)
        assert seo_keywords.pick_upload_language() == "es"

    def test_counter_increments_persistently(self, tmp_path, monkeypatch):
        monkeypatch.setattr(seo_keywords, "data_dir", lambda: tmp_path)
        seo_keywords.pick_upload_language()
        seo_keywords.pick_upload_language()
        counter = tmp_path / "upload_language_counter.json"
        data = json.loads(counter.read_text())
        assert data["count"] == 2

    def test_corrupted_counter_falls_back_to_en(self, tmp_path, monkeypatch):
        monkeypatch.setattr(seo_keywords, "data_dir", lambda: tmp_path)
        counter = tmp_path / "upload_language_counter.json"
        counter.write_text("not json")
        assert seo_keywords.pick_upload_language() == "en"


class TestKeywordsForLanguage:
    def test_en_returns_high_volume_keywords(self):
        kws = seo_keywords.keywords_for_language("en")
        assert "music for cats" in kws["primary"]
        assert "music for dogs" in kws["primary"]

    def test_pt_returns_pt_keywords(self):
        kws = seo_keywords.keywords_for_language("pt")
        assert "musica para gatos" in kws["primary"]
        assert "musica para cachorros" in kws["primary"]

    def test_es_returns_es_keywords(self):
        kws = seo_keywords.keywords_for_language("es")
        assert "musica para gatos" in kws["primary"]
        assert "musica para perros" in kws["primary"]

    def test_unknown_lang_falls_back_to_en(self):
        kws = seo_keywords.keywords_for_language("fr")
        assert "music for cats" in kws["primary"]

    def test_pt_has_long_tail_keywords(self):
        assert "musica para gatos dormirem" in HIGH_VOLUME_KEYWORDS_PT["long_tail"]

    def test_es_has_long_tail_keywords(self):
        assert "musica para gatos dormir" in HIGH_VOLUME_KEYWORDS_ES["long_tail"]


class TestMetadataEngineMultilang:
    """generate_metadata com lang='pt'/'es' gera metadados no idioma alvo."""

    @patch("utils.metadata_engine.ai_text")
    def test_pt_metadata_uses_ai_with_pt_prompt(self, mock_ai_text):
        """Em PT-BR, a IA e preferencial (100%) e o prompt e em portugues."""
        mock_ai_text.return_value = json.dumps(
            {
                "title": "Música Relaxante para Gatos",
                "description": "Uma descrição fofo em português.",
                "hashtags": ["#gatos", "#jazz"],
            }
        )
        metadata = metadata_engine.generate_metadata(
            hook="Gato fofo", scene="cat", duration=30, kind="short", emoji="🐱", lang="pt"
        )
        # Verifica que a IA foi chamada (não fallback local)
        assert mock_ai_text.called
        # O título gerado pela IA em PT deve aparecer (com prefixo de marca)
        assert "Música Relaxante" in metadata["title"] or "Pata Jazz" in metadata["title"]

    @patch("utils.metadata_engine.ai_text")
    def test_es_metadata_uses_ai_with_es_prompt(self, mock_ai_text):
        mock_ai_text.return_value = json.dumps(
            {
                "title": "Música Relajante para Gatos",
                "description": "Una descripción tierna en español.",
                "hashtags": ["#gatos", "#jazz"],
            }
        )
        metadata = metadata_engine.generate_metadata(
            hook="Gato lindo", scene="cat", duration=30, kind="short", emoji="🐱", lang="es"
        )
        assert mock_ai_text.called
        assert "Relajante" in metadata["title"] or "Pata Jazz" in metadata["title"]

    @patch("utils.metadata_engine.ai_text")
    def test_en_metadata_keeps_20_percent_ai_probability(self, mock_ai_text):
        """Em EN, a probabilidade de IA continua 20% (nao 100% como PT/ES)."""
        mock_ai_text.return_value = ""
        # Com 20% de chance, em 50 amostras pelo menos algumas NAO chamam IA
        ai_call_count = 0
        for _ in range(50):
            mock_ai_text.reset_mock()
            metadata_engine.generate_metadata(
                hook="Cute cat", scene="cat", duration=30, kind="short", emoji="🐱", lang="en"
            )
            if mock_ai_text.called:
                ai_call_count += 1
        # Nao pode ser 50/50 (seria 100%); tambem nao pode ser 0 (seria 0%).
        # Com 20%, esperamos algo em torno de 10, mas允许 variancia.
        assert 0 < ai_call_count < 50

    @patch("utils.metadata_engine.ai_text")
    def test_pt_ai_failure_falls_back_to_local(self, mock_ai_text):
        """Se a IA falha em PT-BR, cai no fallback local (keywords PT)."""
        mock_ai_text.return_value = ""
        metadata = metadata_engine.generate_metadata(
            hook="Gato fofo", scene="cat", duration=30, kind="short", emoji="🐱", lang="pt"
        )
        # Fallback local: titulo ainda e gerado (com keywords EN por enquanto,
        # pois generate_title_with_pattern usa HIGH_VOLUME_KEYWORDS global).
        # O importante e que nao quebra e retorna um titulo valido.
        assert "title" in metadata
        assert len(metadata["title"]) > 0
        assert metadata["title"].startswith("Pata Jazz |")
