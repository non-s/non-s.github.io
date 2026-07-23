"""
Testes unitários para utils/media_pool.py
"""

import json
import random
from pathlib import Path
from unittest.mock import patch

import pytest

from utils.media_pool import (
    AUDIO_DIR,
    VIDEO_DIR,
    _cuteness_score,
    _load_video_metadata,
    available_audio_metadata,
    audio_pool,
    pick_audio,
    pick_videos,
    video_pool,
)


class TestMediaPool:
    """Testes para o módulo media_pool."""

    @patch("utils.media_pool.is_allowed_animal_text")
    @patch("utils.media_pool.VIDEO_DIR")
    def test_video_pool_with_allowed_videos(self, mock_video_dir, mock_is_allowed):
        """Testa pool de vídeos com arquivos permitidos."""
        mock_video1 = Path("/fake/path/video1.mp4")
        mock_video2 = Path("/fake/path/video2.mp4")
        mock_video_dir.glob.return_value = [mock_video1, mock_video2]
        mock_is_allowed.side_effect = lambda x: True

        result = video_pool()

        assert len(result) == 2
        mock_video_dir.glob.assert_called_once_with("*.mp4")
        mock_is_allowed.assert_called()

    @patch("utils.media_pool.is_allowed_animal_text")
    @patch("utils.media_pool.VIDEO_DIR")
    def test_video_pool_with_filtered_videos(self, mock_video_dir, mock_is_allowed):
        """Testa pool de vídeos com filtragem."""
        mock_video1 = Path("/fake/path/video1.mp4")
        mock_video2 = Path("/fake/path/video2.mp4")
        mock_video_dir.glob.return_value = [mock_video1, mock_video2]
        mock_is_allowed.side_effect = lambda x: x == "video1.mp4"

        result = video_pool()

        assert len(result) == 1
        assert result[0] == mock_video1

    @patch("utils.media_pool.AUDIO_DIR")
    def test_audio_pool(self, mock_audio_dir):
        """Testa pool de áudios."""
        mock_audio1 = Path("/fake/path/audio1.mp3")
        mock_audio2 = Path("/fake/path/audio2.mp3")
        mock_audio_dir.glob.return_value = [mock_audio2, mock_audio1]  # Desordenado

        result = audio_pool()

        assert len(result) == 2
        assert result[0] == mock_audio1  # Deve estar ordenado
        assert result[1] == mock_audio2
        mock_audio_dir.glob.assert_called_once_with("*.mp3")

    @patch("utils.media_pool.Path.exists")
    def test_load_video_metadata_exists(self, mock_exists):
        """Testa carregamento de metadados de vídeo existente."""
        mock_exists.return_value = True
        test_video = Path("/fake/path/video.mp4")
        test_meta = {"tags": "cute kitten", "likes": 100, "views": 1000}

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__ = lambda s: s
            mock_open.return_value.__exit__ = lambda s, *args: None
            mock_open.return_value.read.return_value = json.dumps(test_meta)

            # Precisa mockar o json.load também
            with patch("utils.media_pool.json.load", return_value=test_meta):
                result = _load_video_metadata(test_video)

        assert result == test_meta
        mock_exists.assert_called_once()

    @patch("utils.media_pool.Path.exists")
    def test_load_video_metadata_not_exists(self, mock_exists):
        """Testa carregamento de metadados de vídeo inexistente."""
        mock_exists.return_value = False
        test_video = Path("/fake/path/video.mp4")

        result = _load_video_metadata(test_video)

        assert result == {}
        mock_exists.assert_called_once()

    @patch("utils.media_pool.Path.exists")
    def test_load_video_metadata_invalid_json(self, mock_exists):
        """Testa carregamento de metadados com JSON inválido."""
        mock_exists.return_value = True
        test_video = Path("/fake/path/video.mp4")

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__ = lambda s: s
            mock_open.return_value.__exit__ = lambda s, *args: None
            # Simula JSON inválido
            with patch("utils.media_pool.json.load", side_effect=json.JSONDecodeError("test", "doc", 0)):
                result = _load_video_metadata(test_video)

        assert result == {}

    def test_cuteness_score_with_cute_tags(self):
        """Testa score de fofura com tags fofas."""
        test_video = Path("/fake/path/video.mp4")
        test_meta = {"tags": "cute kitten adorable baby", "likes": 100, "views": 5000}

        with patch("utils.media_pool._load_video_metadata", return_value=test_meta):
            score = _cuteness_score(test_video)

        # 3 tags fofas (cute, kitten, adorable, baby) = 40 + likes//20 (5) + views//1000 (5) = 50
        assert score >= 40  # Pelo menos o bonus das tags

    def test_cuteness_score_without_metadata(self):
        """Testa score de fofura sem metadados."""
        test_video = Path("/fake/path/video.mp4")

        with patch("utils.media_pool._load_video_metadata", return_value={}):
            score = _cuteness_score(test_video)

        assert score == 0

    def test_cuteness_score_with_zero_values(self):
        """Testa score de fofura com valores zero."""
        test_video = Path("/fake/path/video.mp4")
        test_meta = {"tags": "", "likes": 0, "views": 0}

        with patch("utils.media_pool._load_video_metadata", return_value=test_meta):
            score = _cuteness_score(test_video)

        assert score == 0

    @patch("utils.media_pool.video_pool")
    def test_pick_videos_empty_pool(self, mock_video_pool):
        """Testa seleção de vídeos com pool vazio."""
        mock_video_pool.return_value = []

        result = pick_videos()

        assert result == []
        mock_video_pool.assert_called_once()

    @patch("utils.media_pool.random.randint")
    @patch("utils.media_pool.video_pool")
    def test_pick_videos_single_video(self, mock_video_pool, mock_randint):
        """Testa seleção de único vídeo."""
        mock_video = Path("/fake/path/video.mp4")
        mock_video_pool.return_value = [mock_video]
        mock_randint.return_value = 1

        result = pick_videos(min_count=1, max_count=1)

        assert len(result) == 1
        assert result[0] == mock_video

    @patch("utils.media_pool.random.sample")
    @patch("utils.media_pool.video_pool")
    def test_pick_videos_multiple(self, mock_video_pool, mock_sample):
        """Testa seleção de múltiplos vídeos."""
        mock_videos = [Path(f"/fake/path/video{i}.mp4") for i in range(5)]
        mock_video_pool.return_value = mock_videos
        mock_sample.return_value = mock_videos[:3]

        result = pick_videos(min_count=3, max_count=3, cuteness_sort=False)

        assert len(result) == 3
        mock_sample.assert_called_once()

    @patch("utils.media_pool.random.sample")
    @patch("utils.media_pool.sorted")
    @patch("utils.media_pool.video_pool")
    def test_pick_videos_with_cuteness_sort(self, mock_video_pool, mock_sorted, mock_sample):
        """Testa seleção de vídeos com ordenação por fofura."""
        mock_videos = [Path(f"/fake/path/video{i}.mp4") for i in range(5)]
        mock_video_pool.return_value = mock_videos
        mock_sorted.return_value = mock_videos  # Já ordenados
        mock_sample.return_value = mock_videos[:3]

        result = pick_videos(min_count=3, max_count=3, cuteness_sort=True)

        assert len(result) == 3
        mock_sorted.assert_called_once()
        mock_sample.assert_called_once()

    @patch("utils.media_pool.audio_pool")
    def test_pick_audio_empty_pool(self, mock_audio_pool):
        """Testa seleção de áudio com pool vazio."""
        mock_audio_pool.return_value = []

        result = pick_audio()

        assert result is None
        mock_audio_pool.assert_called_once()

    @patch("utils.media_pool.random.choice")
    @patch("utils.media_pool.audio_pool")
    def test_pick_audio_with_options(self, mock_audio_pool, mock_choice):
        """Testa seleção de áudio com opções disponíveis."""
        mock_audio = Path("/fake/path/audio.mp3")
        mock_audio_pool.return_value = [mock_audio]
        mock_choice.return_value = mock_audio

        result = pick_audio()

        assert result == mock_audio
        mock_choice.assert_called_once_with([mock_audio])

    @patch("utils.media_pool.AUDIO_DIR")
    def test_available_audio_metadata(self, mock_audio_dir):
        """Testa obtenção de metadados de áudio disponíveis."""
        mock_json1 = Path("/fake/path/audio1.json")
        mock_json2 = Path("/fake/path/audio2.json")
        mock_audio_dir.glob.return_value = [mock_json1, mock_json2]

        test_meta1 = {"title": "Audio 1"}
        test_meta2 = {"title": "Audio 2"}

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__ = lambda s: s
            mock_open.return_value.__exit__ = lambda s, *args: None
            # Configura json.load para retornar metadados diferentes
            with patch("utils.media_pool.json.load") as mock_json_load:
                mock_json_load.side_effect = [test_meta1, test_meta2]
                result = list(available_audio_metadata())

        assert len(result) == 2
        assert result[0] == test_meta1
        assert result[1] == test_meta2
        mock_audio_dir.glob.assert_called_once_with("*.json")

    @patch("utils.media_pool.AUDIO_DIR")
    def test_available_audio_metadata_invalid_json(self, mock_audio_dir):
        """Testa obtenção de metadados com JSON inválido."""
        mock_json = Path("/fake/path/audio.json")
        mock_audio_dir.glob.return_value = [mock_json]

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__ = lambda s: s
            mock_open.return_value.__exit__ = lambda s, *args: None
            with patch("utils.media_pool.json.load", side_effect=json.JSONDecodeError("test", "doc", 0)):
                result = list(available_audio_metadata())

        assert len(result) == 0
