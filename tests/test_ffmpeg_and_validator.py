"""Testes para utilitários de FFmpeg e validação de vídeo."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from utils import ffmpeg_helpers, video_validator
from utils.video_validator import VideoValidation, validate_generated_video, validate_video


def test_has_ffmpeg_detects_missing():
    with patch("utils.ffmpeg_helpers._has_binary", return_value=False):
        assert ffmpeg_helpers.has_ffmpeg() is False


def test_has_ffmpeg_detects_present():
    with patch("utils.ffmpeg_helpers._has_binary", return_value=True):
        assert ffmpeg_helpers.has_ffmpeg() is True


def test_has_ffprobe_detects_missing():
    with patch("utils.ffmpeg_helpers._has_binary", return_value=False):
        assert ffmpeg_helpers.has_ffprobe() is False


def test_has_ffprobe_detects_present():
    with patch("utils.ffmpeg_helpers._has_binary", return_value=True):
        assert ffmpeg_helpers.has_ffprobe() is True


def test_run_ffmpeg_raises_on_failure():
    with patch("subprocess.run", return_value=MagicMock(returncode=1, stderr="err", stdout="out")):
        with pytest.raises(Exception):
            ffmpeg_helpers.run_ffmpeg(["-i", "x.mp4", "out.mp4"])


def test_validate_video_missing_file():
    result = validate_video(Path("nao_existe.mp4"), 1920, 1080, 30)
    assert not result.ok
    assert "não encontrado" in result.errors[0].lower() or "not found" in result.errors[0].lower()


def test_validate_generated_video_bad_resolution():
    result = validate_generated_video(Path("x.mp4"), "abc", 30)
    assert not result.ok
    assert "resolução" in result.errors[0].lower() or "resolution" in result.errors[0].lower()


def test_video_validation_dataclass():
    v = VideoValidation(ok=True, errors=[], info={"width": 1920})
    assert v.ok is True


def test_extract_stream_info_video_only():
    probe = {
        "streams": [
            {"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080, "bit_rate": "2000000"},
        ]
    }
    info = video_validator._extract_stream_info(probe)
    assert info["has_video"]
    assert not info["has_audio"]
    assert info["video_codec"] == "h264"
    assert info["width"] == 1920


def test_extract_stream_info_with_audio():
    probe = {
        "streams": [
            {"codec_type": "video", "codec_name": "h264", "width": 1080, "height": 1920, "bit_rate": "1500000"},
            {"codec_type": "audio", "codec_name": "aac", "bit_rate": "192000"},
        ]
    }
    info = video_validator._extract_stream_info(probe)
    assert info["has_video"]
    assert info["has_audio"]
    assert info["audio_codec"] == "aac"
