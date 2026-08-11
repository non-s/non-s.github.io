"""
Testes unitários para utils/media_pool.py
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

import utils.media_pool as media_pool
from utils.media_pool import (
    _cuteness_score,
    _filter_by_mood,
    _load_video_metadata,
    audio_pool,
    available_audio_metadata,
    pick_audio,
    pick_videos,
    video_pool,
)


@pytest.fixture(autouse=True)
def _isolate_recent_media_file(tmp_path, monkeypatch):
    """pick_videos()/pick_audio() persistem historico em _recent_file() (path
    real do repo) - sem isolar, testes escrevem no disco de verdade e o
    historico de uma run vaza pra proxima (nomes de mock se repetem entre
    testes deste arquivo)."""
    recent_file = tmp_path / "recent_media.json"
    monkeypatch.setattr(media_pool, "_recent_file", lambda: recent_file)


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


class TestAvoidRecent:
    """pick_videos()/pick_audio() evitam repetir os itens usados mais recentemente."""

    def test_pick_audio_avoids_last_used_track(self):
        import random as _random

        _random.seed(42)
        pool = [Path(f"/fake/audio{i}.mp3") for i in range(3)]
        with patch("utils.media_pool.audio_pool", return_value=pool):
            first = pick_audio()
            second = pick_audio()

        assert first is not None and second is not None
        assert first != second

    def test_pick_audio_falls_back_when_pool_too_small(self):
        """So 1 faixa no pool: precisa poder repetir em vez de travar."""
        pool = [Path("/fake/only.mp3")]
        with patch("utils.media_pool.audio_pool", return_value=pool):
            first = pick_audio()
            second = pick_audio()

        assert first == pool[0]
        assert second == pool[0]

    @patch("utils.media_pool.random.sample")
    @patch("utils.media_pool.random.randint")
    @patch("utils.media_pool.video_pool")
    def test_pick_videos_excludes_recently_used_names(self, mock_video_pool, mock_randint, mock_sample):
        mock_videos = [Path(f"/fake/path/video{i}.mp4") for i in range(5)]
        mock_video_pool.return_value = mock_videos
        mock_randint.return_value = 2
        mock_sample.return_value = mock_videos[:2]

        pick_videos(min_count=2, max_count=2, cuteness_sort=False)
        # Primeira chamada: nada no historico ainda, pool completo (5 videos).
        assert len(mock_sample.call_args_list[0].args[0]) == 5

        pick_videos(min_count=2, max_count=2, cuteness_sort=False)
        # Segunda chamada: os 2 usados na primeira devem estar fora do pool.
        second_pool = mock_sample.call_args_list[1].args[0]
        assert len(second_pool) == 3
        assert not (set(p.name for p in second_pool) & {"video0.mp4", "video1.mp4"})


class TestFilterByAnimal:
    """pick_videos(animal=...) restringe o b-roll ao animal do scene, pra
    nao mostrar cachorro num video cujo titulo/hook fala de gato."""

    def test_pick_videos_with_cat_filter_excludes_dog_clips(self):
        pool = [
            Path("/fake/real_cat_00_aaa.mp4"),
            Path("/fake/cute_kitten_real_01_bbb.mp4"),
            Path("/fake/real_dog_00_ccc.mp4"),
            Path("/fake/real_puppy_00_ddd.mp4"),
        ]
        with patch("utils.media_pool.video_pool", return_value=pool):
            result = pick_videos(min_count=1, max_count=2, cuteness_sort=False, animal="cat")

        assert all("cat" in p.name or "kitten" in p.name for p in result)

    def test_pick_videos_with_dog_filter_excludes_cat_clips(self):
        pool = [
            Path("/fake/real_cat_00_aaa.mp4"),
            Path("/fake/real_dog_00_ccc.mp4"),
            Path("/fake/real_puppy_00_ddd.mp4"),
        ]
        with patch("utils.media_pool.video_pool", return_value=pool):
            result = pick_videos(min_count=1, max_count=2, cuteness_sort=False, animal="dog")

        assert all("cat" not in p.name for p in result)

    def test_rejects_pool_when_requested_animal_is_missing(self):
        """Sem cachorro disponível, não pode usar gato como substituto."""
        pool = [Path("/fake/real_cat_00_aaa.mp4"), Path("/fake/real_cat_01_bbb.mp4")]
        with patch("utils.media_pool.video_pool", return_value=pool):
            result = pick_videos(min_count=2, max_count=2, cuteness_sort=False, animal="dog")

        assert result == []

    def test_no_animal_filter_keeps_old_behavior(self):
        pool = [Path("/fake/real_cat_00_aaa.mp4"), Path("/fake/real_dog_00_ccc.mp4")]
        with patch("utils.media_pool.video_pool", return_value=pool):
            result = pick_videos(min_count=2, max_count=2, cuteness_sort=False)

        assert len(result) == 2


def _write_audio_meta(tmp_path, name: str, genres: list[str], tags: str = "") -> Path:
    audio = tmp_path / name
    audio.write_bytes(b"")
    meta = audio.with_suffix(".json")
    meta.write_text(
        json.dumps({"musicinfo": {"tags": {"genres": genres}}, "tags": tags}),
        encoding="utf-8",
    )
    return audio


class TestPickAudioByMood:
    """pick_audio(mood=...) filtra faixas por genero da metadata do Jamendo."""

    def test_fofura_filters_by_genres(self, tmp_path):
        bossa = _write_audio_meta(tmp_path, "a1.mp3", ["bossa nova"])
        swing = _write_audio_meta(tmp_path, "a2.mp3", ["swing"])
        with patch("utils.media_pool.audio_pool", return_value=[bossa, swing]):
            with patch("utils.media_pool.random.choice", side_effect=lambda p: p[0]):
                result = pick_audio(mood="fofura")
        assert result == bossa

    def test_relax_filters_by_genres(self, tmp_path):
        smooth = _write_audio_meta(tmp_path, "a1.mp3", ["smooth jazz"])
        swing = _write_audio_meta(tmp_path, "a2.mp3", ["swing"])
        with patch("utils.media_pool.audio_pool", return_value=[smooth, swing]):
            with patch("utils.media_pool.random.choice", side_effect=lambda p: p[0]):
                result = pick_audio(mood="relax")
        assert result == smooth

    def test_no_mood_match_falls_back_to_full_pool(self, tmp_path):
        swing = _write_audio_meta(tmp_path, "a1.mp3", ["swing"])
        rock = _write_audio_meta(tmp_path, "a2.mp3", ["rock"])
        with patch("utils.media_pool.audio_pool", return_value=[swing, rock]):
            with patch("utils.media_pool.random.choice", side_effect=lambda p: p[0]):
                result = pick_audio(mood="fofura")
        assert result == swing

    def test_empty_mood_keeps_old_behavior(self, tmp_path):
        a1 = _write_audio_meta(tmp_path, "a1.mp3", ["bossa nova"])
        a2 = _write_audio_meta(tmp_path, "a2.mp3", ["swing"])
        with patch("utils.media_pool.audio_pool", return_value=[a1, a2]):
            with patch("utils.media_pool.random.choice", side_effect=lambda p: p[0]):
                result = pick_audio()
        assert result == a1

    def test_filter_by_mood_helper_returns_pool_when_too_narrow(self):
        pool = [Path("/fake/x1.mp3"), Path("/fake/x2.mp3")]
        with patch("utils.media_pool._load_audio_metadata", return_value={}):
            result = _filter_by_mood(pool, "fofura", min_needed=1)
        assert result == pool


class TestMusicAttribution:
    def test_includes_track_artist_and_license(self, tmp_path):
        audio = tmp_path / "track.mp3"
        audio.write_bytes(b"")
        audio.with_suffix(".json").write_text(
            json.dumps(
                {
                    "name": "Midnight Jazz",
                    "artist_name": "The Quartet",
                    "license_ccurl": "https://creativecommons.org/licenses/by/4.0/",
                }
            ),
            encoding="utf-8",
        )

        credit = media_pool.music_attribution(audio)

        assert credit == (
            "Music: Midnight Jazz — The Quartet (via Jamendo)\n"
            "License: https://creativecommons.org/licenses/by/4.0/"
        )

    def test_uses_source_when_license_url_is_unavailable(self, tmp_path):
        audio = tmp_path / "track.mp3"
        audio.write_bytes(b"")
        audio.with_suffix(".json").write_text(
            json.dumps({"name": "Quiet Walk", "artist_name": "Artist", "shorturl": "https://jamen.do/t/1"}),
            encoding="utf-8",
        )

        assert "Source: https://jamen.do/t/1" in media_pool.music_attribution(audio)
