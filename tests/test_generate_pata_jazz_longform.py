"""Testes para generate_pata_jazz_longform.py e longform_spec."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import generate_pata_jazz_longform as gen_longform
from utils.video_builder import longform_spec


class TestLongformSpec:
    def test_default_duration_is_1h(self):
        spec = longform_spec()
        assert spec.kind == "horizontal"
        assert spec.width == 1920
        assert spec.height == 1080
        assert spec.duration == 3600

    def test_duration_clamped_to_min(self):
        assert longform_spec(duration=60).duration == 3600

    def test_duration_clamped_to_max(self):
        assert longform_spec(duration=99999).duration == 36000

    def test_custom_duration_in_range(self):
        assert longform_spec(duration=7200).duration == 7200

    def test_fallback_description_mentions_long_form(self):
        assert "1 hour" in longform_spec().fallback_description

    def test_no_overlay_hook_means_horizontal_path(self):
        # longform reusa o caminho horizontal (kind=horizontal) que nao desenha
        # overlay de hook no video.
        spec = longform_spec()
        assert spec.kind == "horizontal"


class TestGenerateLongform:
    @patch("generate_pata_jazz_longform.scene_for_mood", return_value="sleepy cat")
    @patch("generate_pata_jazz_longform.mood_for_now", return_value="relax")
    @patch("generate_pata_jazz_longform.build_pata_jazz_video")
    @patch("generate_pata_jazz_longform.pool_stats", return_value={"videos": 50, "audio": 30})
    @patch("generate_pata_jazz_longform.audio_pool", return_value=[Path("a.mp3")] * 30)
    def test_generate_longform_dry_run(self, _audio, _stats, mock_build, _mood, _scene):
        mock_build.return_value = Path("fake.mp4")
        result = gen_longform._generate_longform(duration=3600, dry_run=True)

        assert result == Path("fake.mp4")
        args, kwargs = mock_build.call_args
        assert kwargs["dry_run"] is True
        assert kwargs["stem_prefix"] == "pata_jazz_longform"
        spec = kwargs["spec"]
        assert spec.duration == 3600
        assert spec.kind == "horizontal"

    @patch("generate_pata_jazz_longform.scene_for_mood", return_value="sleepy cat")
    @patch("generate_pata_jazz_longform.mood_for_now", return_value="relax")
    @patch("generate_pata_jazz_longform.build_pata_jazz_video")
    @patch("generate_pata_jazz_longform.pool_stats", return_value={"videos": 50, "audio": 30})
    @patch("generate_pata_jazz_longform.audio_pool", return_value=[Path("a.mp3")] * 30)
    def test_generate_longform_uses_mood(self, _audio, _stats, mock_build, mock_mood, _scene):
        mock_build.return_value = Path("fake.mp4")
        gen_longform._generate_longform(duration=7200)

        mock_mood.assert_called_once()
        spec = mock_build.call_args.kwargs["spec"]
        assert spec.duration == 7200


class TestMain:
    @patch("generate_pata_jazz_longform._generate_longform")
    @patch("generate_pata_jazz_longform.configure_logging")
    def test_dry_run_returns_zero(self, _log, mock_gen, monkeypatch):
        monkeypatch.setattr("sys.argv", ["gen", "--dry-run", "--duration", "3600"])
        assert gen_longform.main() == 0
        mock_gen.assert_called_once()
        assert mock_gen.call_args.kwargs["dry_run"] is True

    @patch("generate_pata_jazz_longform.log_exception_to_file")
    @patch("generate_pata_jazz_longform._generate_longform", side_effect=RuntimeError("boom"))
    @patch("generate_pata_jazz_longform.configure_logging")
    def test_exception_returns_one(self, _log, mock_gen, mock_log_exc, monkeypatch):
        monkeypatch.setattr("sys.argv", ["gen", "--duration", "3600"])
        assert gen_longform.main() == 1
        mock_log_exc.assert_called_once()

    @patch("generate_pata_jazz_longform.configure_logging")
    def test_invalid_duration_returns_one(self, _log, monkeypatch):
        monkeypatch.setattr("sys.argv", ["gen", "--duration", "60"])
        assert gen_longform.main() == 1

    @patch("generate_pata_jazz_longform._generate_longform")
    @patch("generate_pata_jazz_longform.configure_logging")
    def test_success_returns_zero(self, _log, mock_gen, monkeypatch):
        monkeypatch.setattr("sys.argv", ["gen", "--duration", "7200"])
        assert gen_longform.main() == 0
        assert mock_gen.call_args.kwargs["duration"] == 7200
