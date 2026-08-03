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


def test_to_int_handles_none_and_garbage():
    assert video_validator._to_int(None) is None
    assert video_validator._to_int("abc") is None
    assert video_validator._to_int("123") == 123


def _make_video_file(tmp_path: Path) -> Path:
    p = tmp_path / "fake.mp4"
    p.write_bytes(b"x" * 1024)
    return p


def _probe(width=1920, height=1080, vcodec="h264", acodec="aac", vbr="2000000", abr="192000", has_audio=True) -> dict:
    streams = [{"codec_type": "video", "codec_name": vcodec, "width": width, "height": height, "bit_rate": vbr}]
    if has_audio:
        streams.append({"codec_type": "audio", "codec_name": acodec, "bit_rate": abr})
    return {"streams": streams}


class TestValidateGeneratedVideo:
    def test_happy_path(self, tmp_path):
        p = _make_video_file(tmp_path)
        with (
            patch("utils.video_validator._run_ffprobe", return_value=_probe()),
            patch("utils.video_validator.get_video_duration", return_value=30.0),
        ):
            r = validate_generated_video(p, "1920x1080", 30, expect_audio=True)
        assert r.ok, r.errors
        assert r.info["video_codec"] == "h264"

    def test_missing_file(self, tmp_path):
        r = validate_generated_video(tmp_path / "nope.mp4", "1920x1080", 30)
        assert not r.ok
        assert any("não encontrado" in e.lower() or "not found" in e.lower() for e in r.errors)

    def test_bad_resolution(self, tmp_path):
        p = _make_video_file(tmp_path)
        with (
            patch("utils.video_validator._run_ffprobe", return_value=_probe(width=1280, height=720)),
            patch("utils.video_validator.get_video_duration", return_value=30.0),
        ):
            r = validate_generated_video(p, "1920x1080", 30)
        assert not r.ok
        assert any("Resolução" in e for e in r.errors)

    def test_bad_duration(self, tmp_path):
        p = _make_video_file(tmp_path)
        with (
            patch("utils.video_validator._run_ffprobe", return_value=_probe()),
            patch("utils.video_validator.get_video_duration", return_value=50.0),
        ):
            r = validate_generated_video(p, "1920x1080", 30)
        assert not r.ok
        assert any("Duração" in e for e in r.errors)

    def test_bad_codec(self, tmp_path):
        p = _make_video_file(tmp_path)
        with (
            patch("utils.video_validator._run_ffprobe", return_value=_probe(vcodec="hevc")),
            patch("utils.video_validator.get_video_duration", return_value=30.0),
        ):
            r = validate_generated_video(p, "1920x1080", 30)
        assert not r.ok
        assert any("Codec de vídeo" in e for e in r.errors)

    def test_audio_missing_when_expected(self, tmp_path):
        p = _make_video_file(tmp_path)
        with (
            patch("utils.video_validator._run_ffprobe", return_value=_probe(has_audio=False)),
            patch("utils.video_validator.get_video_duration", return_value=30.0),
        ):
            r = validate_generated_video(p, "1920x1080", 30, expect_audio=True)
        assert not r.ok
        assert any("áudio" in e.lower() for e in r.errors)

    def test_audio_missing_when_not_expected(self, tmp_path):
        p = _make_video_file(tmp_path)
        with (
            patch("utils.video_validator._run_ffprobe", return_value=_probe(has_audio=False)),
            patch("utils.video_validator.get_video_duration", return_value=30.0),
        ):
            r = validate_generated_video(p, "1920x1080", 30, expect_audio=False)
        assert r.ok, r.errors

    def test_ffprobe_failure(self, tmp_path):
        p = _make_video_file(tmp_path)
        with patch("utils.video_validator._run_ffprobe", side_effect=RuntimeError("ffprobe boom")):
            r = validate_generated_video(p, "1920x1080", 30)
        assert not r.ok
        assert any("ffprobe" in e for e in r.errors)

    def test_duration_zero(self, tmp_path):
        p = _make_video_file(tmp_path)
        with (
            patch("utils.video_validator._run_ffprobe", return_value=_probe()),
            patch("utils.video_validator.get_video_duration", return_value=0.0),
        ):
            r = validate_generated_video(p, "1920x1080", 30)
        assert not r.ok
        assert any("duração" in e.lower() for e in r.errors)

    def test_low_bitrate_estimated_from_filesize(self, tmp_path):
        p = _make_video_file(tmp_path)  # 8192 bits / 30s = ~273 bps
        probe = _probe()
        probe["streams"][0]["bit_rate"] = None  # força estimativa por filesize
        with (
            patch("utils.video_validator._run_ffprobe", return_value=probe),
            patch("utils.video_validator.get_video_duration", return_value=30.0),
        ):
            r = validate_generated_video(p, "1920x1080", 30)
        assert not r.ok
        assert any("Bitrate" in e for e in r.errors)

    def test_invalid_resolution_string(self, tmp_path):
        p = _make_video_file(tmp_path)
        r = validate_generated_video(p, "abc", 30)
        assert not r.ok
        assert any("Resolução" in e for e in r.errors)

    def test_no_video_stream(self, tmp_path):
        p = _make_video_file(tmp_path)
        with (
            patch("utils.video_validator._run_ffprobe", return_value={"streams": []}),
            patch("utils.video_validator.get_video_duration", return_value=30.0),
        ):
            r = validate_generated_video(p, "1920x1080", 30)
        assert not r.ok
        assert any("vídeo" in e.lower() for e in r.errors)


class TestFfmpegHelpers:
    def test_run_ffmpeg_success(self):
        ok = MagicMock(returncode=0, stdout="ok", stderr="")
        with patch("subprocess.run", return_value=ok) as mock_run:
            res = ffmpeg_helpers.run_ffmpeg(["-i", "x", "out.mp4"])
        assert res.returncode == 0
        assert mock_run.call_args.args[0][0] == "ffmpeg"
        assert "-y" in mock_run.call_args.args[0]

    def test_run_ffmpeg_timeout(self):
        import subprocess

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="ffmpeg", timeout=5)):
            with pytest.raises(subprocess.TimeoutExpired):
                ffmpeg_helpers.run_ffmpeg(["-i", "x"], timeout=5)

    def test_get_video_duration_ok(self):
        with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="42.5\n")):
            assert ffmpeg_helpers.get_video_duration("x.mp4") == 42.5

    def test_get_video_duration_zero(self):
        with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="0\n")):
            assert ffmpeg_helpers.get_video_duration("x.mp4") == 0.0

    def test_get_video_duration_bad_returncode(self):
        with patch("subprocess.run", return_value=MagicMock(returncode=1, stdout="")):
            assert ffmpeg_helpers.get_video_duration("x.mp4") == 0.0

    def test_get_video_duration_oserror(self):
        with patch("subprocess.run", side_effect=OSError("nope")):
            assert ffmpeg_helpers.get_video_duration("x.mp4") == 0.0

    def test_build_concat_demuxer(self, tmp_path):
        out = tmp_path / "concat.txt"
        ffmpeg_helpers.build_concat_demuxer([str(tmp_path / "a.mp4"), str(tmp_path / "b.mp4")], str(out))
        content = out.read_text(encoding="utf-8")
        assert "file " in content
        assert content.count("file ") == 2

    def test_run_ffmpeg_nonzero_returncode_raises(self):
        """returncode != 0 deve levantar subprocess.CalledProcessError."""
        import subprocess

        with patch("subprocess.run", return_value=MagicMock(returncode=2, stderr="boom", stdout="")):
            with pytest.raises(subprocess.CalledProcessError):
                ffmpeg_helpers.run_ffmpeg(["-i", "x", "out.mp4"])

    def test_get_video_duration_timeout_returns_zero(self):
        """TimeoutExpired no ffprobe -> retorna 0.0 (nao propaga)."""
        import subprocess

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="ffprobe", timeout=15)):
            assert ffmpeg_helpers.get_video_duration("x.mp4") == 0.0

    def test_get_video_duration_value_error_returns_zero(self):
        """stdout nao-numerico -> ValueError capturado -> 0.0."""
        with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="not-a-number\n")):
            assert ffmpeg_helpers.get_video_duration("x.mp4") == 0.0


class TestVideoValidatorBranches:
    """Cobertura dos branches de erro de ffprobe em video_validator.py."""

    def test_run_ffprobe_raises_on_subprocess_failure(self, tmp_path):
        """_run_ffprobe encapsula qualquer excecao do subprocess em RuntimeError."""
        p = tmp_path / "v.mp4"
        p.write_bytes(b"x")
        with patch("subprocess.run", side_effect=OSError("ffprobe missing")):
            with pytest.raises(RuntimeError, match="ffprobe falhou"):
                video_validator._run_ffprobe(p)

    def test_extract_stream_info_video_without_codec_name(self):
        """Stream de video sem codec_name -> info['video_codec'] e None."""
        probe = {
            "streams": [
                {"codec_type": "video", "width": 1920, "height": 1080},
            ]
        }
        info = video_validator._extract_stream_info(probe)
        assert info["has_video"]
        assert info["video_codec"] is None
        assert info["video_bit_rate"] is None

    def test_validate_video_audio_missing_when_expected(self, tmp_path):
        """expect_audio=True e sem stream de audio -> erro de audio ausente."""
        p = tmp_path / "fake.mp4"
        p.write_bytes(b"x" * 1024)
        probe = {
            "streams": [
                {"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080, "bit_rate": "2000000"},
            ]
        }
        with (
            patch("utils.video_validator._run_ffprobe", return_value=probe),
            patch("utils.video_validator.get_video_duration", return_value=30.0),
        ):
            r = validate_video(p, 1920, 1080, 30, expect_audio=True)
        assert not r.ok
        assert any("áudio" in e.lower() for e in r.errors)

    def test_validate_video_missing_bitrate_uses_filesize_estimate(self, tmp_path):
        """video_bit_rate ausente e duration > 0 -> estima do tamanho do arquivo."""
        p = tmp_path / "tiny.mp4"
        p.write_bytes(b"x" * 100)  # 800 bits / 30s = ~26 bps
        probe = {
            "streams": [
                {"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080},
                {"codec_type": "audio", "codec_name": "aac"},
            ]
        }
        with (
            patch("utils.video_validator._run_ffprobe", return_value=probe),
            patch("utils.video_validator.get_video_duration", return_value=30.0),
        ):
            r = validate_video(p, 1920, 1080, 30, expect_audio=True, min_video_bitrate_kbps=100)
        assert not r.ok
        assert any("Bitrate" in e for e in r.errors)

    def test_run_ffprobe_wraps_json_error(self, tmp_path):
        """_run_ffprobe levanta RuntimeError se json.loads falhar."""
        p = tmp_path / "v.mp4"
        p.write_bytes(b"x")
        with patch("subprocess.run", return_value=MagicMock(stdout="not json", returncode=0)):
            with pytest.raises(RuntimeError, match="ffprobe falhou"):
                video_validator._run_ffprobe(p)
