"""Testes para o pool de assets e o novo builder centralizado de vídeos."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from utils import media_pool, video_builder
from utils.media_pool import VIDEO_DIR, AUDIO_DIR, pick_audio, pick_videos, pool_stats, video_pool, audio_pool
from utils.video_builder import VideoSpec, horizontal_spec, inspect_video, short_spec


def test_video_pool_returns_list():
    with patch("utils.media_pool.VIDEO_DIR", new_callable=Path) as mock_dir:
        with patch.object(Path, "glob", return_value=[]) as _glob:
            assert video_pool() == []


def test_audio_pool_returns_list():
    with patch("utils.media_pool.AUDIO_DIR", new_callable=Path) as mock_dir:
        with patch.object(Path, "glob", return_value=[]) as _glob:
            assert audio_pool() == []


def test_pick_videos_returns_empty_without_pool():
    with patch("utils.media_pool.video_pool", return_value=[]):
        assert pick_videos() == []


def test_pick_audio_returns_none_without_pool():
    with patch("utils.media_pool.audio_pool", return_value=[]):
        assert pick_audio() is None


def test_pool_stats_keys():
    with patch("utils.media_pool.video_pool", return_value=[Path("a.mp4")]), \
         patch("utils.media_pool.audio_pool", return_value=[Path("a.mp3")]):
        stats = pool_stats()
        assert stats["videos"] == 1
        assert stats["audio"] == 1


def test_short_spec_is_vertical():
    spec = short_spec()
    assert spec.width == 1080
    assert spec.height == 1920
    assert "crop" in spec.crop_filter


def test_horizontal_spec_is_horizontal():
    spec = horizontal_spec()
    assert spec.width == 1920
    assert spec.height == 1080
    assert "crop" in spec.crop_filter


def test_video_spec_has_required_fields():
    spec = VideoSpec(
        kind="test",
        width=1280,
        height=720,
        duration=30,
        default_duration=30,
        crop_filter="crop=1280:720",
        thumbnail_maker=None,
        fallback_description="desc",
    )
    assert spec.duration == 30


def test_inspect_video_missing_file():
    info = inspect_video(Path("nao_existe.mp4"))
    assert info.get("duration") == 0.0
    assert "path" in info
