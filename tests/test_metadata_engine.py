"""Testes para metadata_engine.py."""
import json
import re
from unittest.mock import patch

import utils.metadata_engine as metadata_engine


class TestMetadataEngine:
    """Testes para metadata_engine."""

    @patch('utils.metadata_engine.ai_text')
    def test_generate_metadata_full(self, mock_ai_text):
        """Testa geração completa de metadados."""
        mock_ai_text.return_value = json.dumps({
            "title": "Título Fofo",
            "description": "Descrição incrível",
            "hashtags": ["#gato", "#jazz"]
        })

        metadata = metadata_engine.generate_metadata(
            hook="Gato dançante",
            scene="gato",
            duration=25,
            kind="short",
            emoji="🐱"
        )

        assert "title" in metadata
        assert "description" in metadata
        assert "hashtags" in metadata
        # SEO 2.0 gera títulos otimizados dinamicamente
        assert len(metadata["title"]) > 0
        assert len(metadata["title"]) <= 100  # Limite YouTube
        assert "Descrição incrível" in metadata["description"]
        assert "#gato" in metadata["hashtags"] or "#cat" in metadata["hashtags"]
        assert "#jazz" in metadata["hashtags"] or "#music" in metadata["hashtags"]

    @patch('utils.metadata_engine.ai_text')
    def test_generate_metadata_does_not_duplicate_hashtags(self, mock_ai_text):
        """generate_description ja inclui as hashtags no fim; o check de
        'ja tem hashtag' precisa reconhecer isso e nao duplicar (regressao:
        um \\b antes do '#' nunca batia, entao duplicava sempre)."""
        mock_ai_text.return_value = ""  # forca fallback local (sem AI)

        metadata = metadata_engine.generate_metadata(
            hook="Gato dançante",
            scene="cat",
            duration=25,
            kind="short",
            emoji="🐱",
        )

        # Conta ocorrencias por palavra inteira (\b apos a tag), nao por
        # substring crua: hashtags como "#Cute" e "#CutePets" convivem no
        # mesmo conjunto, e "#CutePets".count("#Cute") mentiria "2" mesmo
        # com cada hashtag aparecendo exatamente uma vez de verdade.
        for tag in metadata["hashtags"]:
            occurrences = len(re.findall(rf"{re.escape(tag)}\b", metadata["description"]))
            assert occurrences == 1, (
                f"hashtag {tag} duplicada na descricao: {metadata['description']!r}"
            )

    @patch('utils.metadata_engine.ai_text')
    def test_generate_metadata_ai_failure(self, mock_ai_text):
        """Testa fallback quando AI falha (retorna string vazia)."""
        mock_ai_text.return_value = ""

        metadata = metadata_engine.generate_metadata(
            hook="Gato dançante",
            scene="gato",
            duration=20,
            kind="short",
            emoji="🐱"
        )

        # Deve retornar metadata com valores default
        assert metadata is not None
        assert isinstance(metadata, dict)
        # Verifica se tem fallbacks
        assert "title" in metadata
        assert "description" in metadata
        assert "hashtags" in metadata
        # SEO 2.0 deve gerar título válido mesmo sem AI
        assert len(metadata["title"]) > 0
        assert len(metadata["title"]) <= 100  # Limite YouTube
