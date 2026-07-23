"""Testes unitários para video_builder.py."""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import utils.video_builder as video_builder


class TestVideoBuilderUnits:
    """Testes unitários para video_builder."""
    
    @patch('utils.media_pool.video_pool')
    @patch('utils.media_pool.audio_pool')
    def test_validate_source_pools_success(self, mock_audio, mock_video):
        """Testa validação de pools com sucesso."""
        mock_video.return_value = [Path("video1.mp4")]
        mock_audio.return_value = [Path("audio1.mp3")]
        
        # Não deve levantar exceção
        video_builder._validate_source_pools()
    
    @patch('utils.media_pool.video_pool')
    def test_validate_source_pools_empty_video(self, mock_video):
        """Testa validação com pool de vídeo vazio."""
        mock_video.return_value = []
        
        with pytest.raises(RuntimeError, match="Pool de b-roll vazio"):
            video_builder._validate_source_pools()
    
    @patch('utils.media_pool.audio_pool')
    @patch('utils.media_pool.video_pool')
    def test_validate_source_pools_empty_audio(self, mock_video, mock_audio):
        """Testa validação com pool de áudio vazio."""
        mock_video.return_value = [Path("video1.mp4")]
        mock_audio.return_value = []
        
        # Não deve levantar exceção, apenas logar warning
        video_builder._validate_source_pools()
    
    def test_build_pata_jazz_video_invalid_spec(self):
        """Testa build com spec inválida."""
        spec_invalid = {"day": "Seg"}  # Falta type, mood, etc.
        
        with pytest.raises((KeyError, TypeError, RuntimeError)):
            video_builder.build_pata_jazz_video(
                spec=spec_invalid,
                output_dir=Path("test"),
                thumb_dir=Path("test"),
                stem_prefix="test"
            )
