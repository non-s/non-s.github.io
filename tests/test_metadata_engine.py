"""Testes para metadata_engine.py."""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import utils.metadata_engine as metadata_engine
import json


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
        assert metadata["title"] == "Título Fofo"
        assert "Descrição incrível" in metadata["description"]
        assert "#gato" in metadata["hashtags"]
        assert "#jazz" in metadata["hashtags"]
    
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
        # Título default deve conter o hook
        assert "Gato dançante" in metadata["title"]
