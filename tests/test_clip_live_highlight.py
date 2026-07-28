"""Testes para scripts/clip_live_highlight.py — recorte de Short vertical
a partir de uma gravacao de live, com deteccao automatica do pico de
espectadores em _data/live_viewer_history.json."""
import json
from unittest.mock import patch

import pytest

import scripts.clip_live_highlight as clip


@pytest.fixture(autouse=True)
def _isolate_paths(tmp_path, monkeypatch):
    """Isola OUTPUT_DIR e VIEWER_HISTORY_FILE para nao tocar em _data/ real."""
    monkeypatch.setattr(clip, "OUTPUT_DIR", tmp_path / "videos")
    monkeypatch.setattr(clip, "VIEWER_HISTORY_FILE", tmp_path / "live_viewer_history.json")


class TestPeakViewerMoment:
    def test_returns_none_when_history_missing(self, tmp_path):
        assert clip._peak_viewer_moment(tmp_path / "missing.json") is None

    def test_returns_none_when_history_empty(self, tmp_path):
        path = tmp_path / "h.json"
        path.write_text("[]", encoding="utf-8")
        assert clip._peak_viewer_moment(path) is None

    def test_returns_none_when_history_invalid_json(self, tmp_path):
        path = tmp_path / "h.json"
        path.write_text("not json", encoding="utf-8")
        assert clip._peak_viewer_moment(path) is None

    def test_picks_highest_concurrent_viewers(self, tmp_path):
        path = tmp_path / "h.json"
        path.write_text(json.dumps([
            {"collected_at": "2026-01-01T00:00:00+00:00", "concurrent_viewers": 5},
            {"collected_at": "2026-01-01T00:05:00+00:00", "concurrent_viewers": 42},
            {"collected_at": "2026-01-01T00:10:00+00:00", "concurrent_viewers": 20},
        ]), encoding="utf-8")
        result = clip._peak_viewer_moment(path)
        assert result == ("2026-01-01T00:05:00+00:00", 42)

    def test_skips_snapshots_without_viewers(self, tmp_path):
        path = tmp_path / "h.json"
        path.write_text(json.dumps([
            {"collected_at": "2026-01-01T00:00:00+00:00"},
            {"collected_at": "2026-01-01T00:05:00+00:00", "concurrent_viewers": 7},
        ]), encoding="utf-8")
        assert clip._peak_viewer_moment(path) == ("2026-01-01T00:05:00+00:00", 7)

    def test_handles_string_viewers(self, tmp_path):
        path = tmp_path / "h.json"
        path.write_text(json.dumps([
            {"collected_at": "2026-01-01T00:00:00+00:00", "concurrent_viewers": "15"},
        ]), encoding="utf-8")
        assert clip._peak_viewer_moment(path) == ("2026-01-01T00:00:00+00:00", 15)


class TestClipVerticalShort:
    def test_invokes_ffmpeg_with_vertical_crop_and_scale(self, tmp_path):
        input_path = tmp_path / "live.mp4"
        input_path.write_bytes(b"fake")
        with patch("scripts.clip_live_highlight.run_ffmpeg") as mock_run:
            out = clip.clip_vertical_short(input_path, start=30.0, duration=60.0)
        args = mock_run.call_args.args[0]
        assert mock_run.call_args.kwargs["timeout"] == 600
        assert "-ss" in args
        assert "30.000" in args
        assert "-t" in args
        assert "60.000" in args
        assert "scale=1080:1920" in "".join(args)
        assert str(out).endswith(".mp4")

    def test_uses_custom_output_path(self, tmp_path):
        input_path = tmp_path / "live.mp4"
        input_path.write_bytes(b"fake")
        custom = tmp_path / "custom.mp4"
        with patch("scripts.clip_live_highlight.run_ffmpeg"):
            out = clip.clip_vertical_short(input_path, start=0.0, duration=10.0, output_path=custom)
        assert out == custom


class TestArgParsing:
    def test_required_input(self):
        with pytest.raises(SystemExit):
            clip._parse_args([])

    def test_defaults_start_and_duration_none(self):
        args = clip._parse_args(["--input", "live.mp4"])
        assert args.input == "live.mp4"
        assert args.start is None
        assert args.duration is None
        assert args.output is None

    def test_explicit_start_duration(self):
        args = clip._parse_args(["--input", "x.mp4", "--start", "120", "--duration", "45"])
        assert args.start == 120.0
        assert args.duration == 45.0


class TestMain:
    def test_missing_input_returns_1(self):
        with patch("scripts.clip_live_highlight.configure_logging"):
            assert clip.main(["--input", "nope.mp4"]) == 1

    def test_explicit_start_clips_short(self, tmp_path):
        input_path = tmp_path / "live.mp4"
        input_path.write_bytes(b"fake")
        with patch("scripts.clip_live_highlight.configure_logging"), \
             patch("scripts.clip_live_highlight.run_ffmpeg") as mock_run:
            code = clip.main(["--input", str(input_path), "--start", "100", "--duration", "30"])
        assert code == 0
        mock_run.assert_called_once()

    def test_no_start_no_history_returns_1(self, tmp_path):
        input_path = tmp_path / "live.mp4"
        input_path.write_bytes(b"fake")
        with patch("scripts.clip_live_highlight.configure_logging"), \
             patch("scripts.clip_live_highlight._peak_viewer_moment", return_value=None):
            assert clip.main(["--input", str(input_path)]) == 1

    def test_peak_detected_but_no_mapping_returns_1_with_warning(self, tmp_path):
        """Deteccao do pico disponivel, mas a live e streamada - sem
        recording_start nao e possivel mapear timestamp ISO em offset de
        arquivo. O script loga o pico e exige --start explicito."""
        input_path = tmp_path / "live.mp4"
        input_path.write_bytes(b"fake")
        peak = ("2026-01-01T00:05:00+00:00", 42)
        with patch("scripts.clip_live_highlight.configure_logging"), \
             patch("scripts.clip_live_highlight._peak_viewer_moment", return_value=peak) as mock_peak, \
             patch("scripts.clip_live_highlight.run_ffmpeg") as mock_run:
            assert clip.main(["--input", str(input_path)]) == 1
        mock_peak.assert_called_once()
        mock_run.assert_not_called()

    def test_default_duration_is_2x_half_window(self, tmp_path):
        input_path = tmp_path / "live.mp4"
        input_path.write_bytes(b"fake")
        with patch("scripts.clip_live_highlight.configure_logging"), \
             patch("scripts.clip_live_highlight.run_ffmpeg") as mock_run:
            clip.main(["--input", str(input_path), "--start", "50"])
        args = mock_run.call_args.args[0]
        expected = float(2 * clip.PEAK_HALF_WINDOW_SECONDS)
        assert f"{expected:.3f}" in args

    def test_ffmpeg_failure_returns_1(self, tmp_path):
        input_path = tmp_path / "live.mp4"
        input_path.write_bytes(b"fake")
        with patch("scripts.clip_live_highlight.configure_logging"), \
             patch("scripts.clip_live_highlight.run_ffmpeg", side_effect=RuntimeError("boom")):
            assert clip.main(["--input", str(input_path), "--start", "0"]) == 1
