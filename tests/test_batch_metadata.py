"""Testes para B1 - Gemini batching (ai_batch_metadata).

ai_batch_metadata faz uma unica chamada Gemini que gera todos os textos
do vídeo (título, descrição, hashtags, legendas) de uma vez, reduzindo
4-5 chamadas para 1. Economia de ~75% de quota/latencia Gemini.
"""

import json
from unittest.mock import patch

import utils.ai_helper as ai_helper
import utils.metadata_engine as metadata_engine


class TestAiBatchMetadata:
    """ai_batch_metadata: chamada unica que retorna dict com todos os textos."""

    @patch("utils.ai_helper.ai_text")
    def test_returns_parsed_dict_when_valid_json(self, mock_ai_text):
        mock_ai_text.return_value = json.dumps(
            {
                "title": "Cute Cat Video",
                "title_alt": "Adorable Kitten Moment",
                "description": "A cute cat video with jazz.",
                "hashtags": ["#cats", "#jazz"],
                "caption_en": "1\n00:00:00,000 --> 00:00:03,000\nCute cat",
                "caption_pt": "1\n00:00:00,000 --> 00:00:03,000\nGato fofo",
            }
        )
        result = ai_helper.ai_batch_metadata("test prompt")
        assert result is not None
        assert result["title"] == "Cute Cat Video"
        assert result["title_alt"] == "Adorable Kitten Moment"
        assert result["caption_pt"] is not None

    @patch("utils.ai_helper.ai_text")
    def test_returns_none_when_ai_text_fails(self, mock_ai_text):
        mock_ai_text.return_value = ""
        result = ai_helper.ai_batch_metadata("test prompt")
        assert result is None

    @patch("utils.ai_helper.ai_text")
    def test_returns_none_when_invalid_json(self, mock_ai_text):
        mock_ai_text.return_value = "not json at all"
        result = ai_helper.ai_batch_metadata("test prompt")
        assert result is None

    @patch("utils.ai_helper.ai_text")
    def test_returns_none_when_not_dict(self, mock_ai_text):
        mock_ai_text.return_value = json.dumps(["not", "a", "dict"])
        result = ai_helper.ai_batch_metadata("test prompt")
        assert result is None


class TestTryBatchMetadata:
    """try_batch_metadata: wrapper em metadata_engine que valida o resultado."""

    @patch("utils.metadata_engine.ai_batch_metadata")
    def test_returns_dict_when_title_present_and_safe(self, mock_batch):
        mock_batch.return_value = {
            "title": "Cute Cat Sleeping | Soft Jazz",
            "title_alt": "Kitten Nap Time | Jazz Moment",
            "description": "A cute cat sleeping with jazz.",
            "hashtags": ["#cats", "#jazz"],
        }
        result = metadata_engine.try_batch_metadata("hook", "cat", 30, "short", "🐱")
        assert result is not None
        assert result["title"] == "Cute Cat Sleeping | Soft Jazz"

    @patch("utils.metadata_engine.ai_batch_metadata")
    def test_returns_none_when_title_empty(self, mock_batch):
        mock_batch.return_value = {"title": "", "description": "desc"}
        result = metadata_engine.try_batch_metadata("hook", "cat", 30, "short", "🐱")
        assert result is None

    @patch("utils.metadata_engine.ai_batch_metadata")
    def test_returns_none_when_title_suspicious(self, mock_batch):
        mock_batch.return_value = {"title": "Click https://scam.com now"}
        result = metadata_engine.try_batch_metadata("hook", "cat", 30, "short", "🐱")
        assert result is None

    @patch("utils.metadata_engine.ai_batch_metadata")
    def test_returns_none_when_batch_fails(self, mock_batch):
        mock_batch.return_value = None
        result = metadata_engine.try_batch_metadata("hook", "cat", 30, "short", "🐱")
        assert result is None


class TestBatchIntegrationInGenerateMetadata:
    """generate_metadata usa batch quando disponivel, cai para fluxo
    individual quando falha."""

    @patch("utils.metadata_engine.ai_batch_metadata")
    @patch("utils.metadata_engine.ai_text")
    def test_batch_success_uses_batch_title(self, mock_ai_text, mock_batch):
        """Quando o batch funciona, o título vem do batch (nao do fluxo individual)."""
        mock_batch.return_value = {
            "title": "Cozy Cat | Soft Jazz",
            "title_alt": "Sleepy Kitten | Jazz Moment",
            "description": "A cozy cat by the window with soft jazz for a quiet little moment.",
            "hashtags": ["#batch", "#cats"],
        }
        # ai_text individual nao deve ser chamado quando batch funciona
        metadata = metadata_engine.generate_metadata(
            hook="Cute cat", scene="cat", duration=30, kind="short", emoji="🐱", lang="pt"
        )
        assert "Cozy Cat" in metadata["title"]
        assert mock_ai_text.called is False or mock_ai_text.call_count == 0

    @patch("utils.metadata_engine.ai_batch_metadata")
    def test_batch_failure_falls_back_to_local(self, mock_batch):
        """Quando o batch falha (None), cai no fluxo local (SEO Zeus)."""
        mock_batch.return_value = None
        metadata = metadata_engine.generate_metadata(
            hook="Cute cat", scene="cat", duration=30, kind="short", emoji="🐱", lang="pt"
        )
        assert metadata["title"].startswith("Pata Jazz |")
        assert len(metadata["title"]) <= 100
        assert "title_alt" in metadata
