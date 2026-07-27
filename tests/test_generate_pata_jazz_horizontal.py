"""Testes para generate_pata_jazz_horizontal.py."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import generate_pata_jazz_horizontal as gen_horizontal


class TestGenerateHorizontal:
    @patch("generate_pata_jazz_horizontal.scene_for_mood", return_value="sleepy cat")
    @patch("generate_pata_jazz_horizontal.mood_for_now", return_value="relax")
    @patch("generate_pata_jazz_horizontal.build_pata_jazz_video")
    def test_generate_horizontal_dry_run(self, mock_build, _mood, _scene):
        mock_build.return_value = Path("fake.mp4")
        result = gen_horizontal._generate_horizontal(duration=240, dry_run=True)

        assert result == Path("fake.mp4")
        args, kwargs = mock_build.call_args
        assert kwargs["dry_run"] is True
        assert kwargs["stem_prefix"] == "pata_jazz_horizontal"

    @patch("generate_pata_jazz_horizontal.scene_for_mood", return_value="sleepy cat")
    @patch("generate_pata_jazz_horizontal.mood_for_now", return_value="relax")
    @patch("generate_pata_jazz_horizontal.build_pata_jazz_video")
    def test_generate_horizontal_uses_mood(self, mock_build, mock_mood, _scene):
        mock_build.return_value = Path("fake.mp4")
        gen_horizontal._generate_horizontal(duration=120)

        mock_mood.assert_called_once()


class TestMain:
    @patch("generate_pata_jazz_horizontal._generate_horizontal")
    @patch("generate_pata_jazz_horizontal.configure_logging")
    def test_dry_run_returns_zero(self, _log, mock_gen, monkeypatch):
        monkeypatch.setattr("sys.argv", ["gen", "--dry-run"])
        assert gen_horizontal.main() == 0
        mock_gen.assert_called_once()
        assert mock_gen.call_args.kwargs["dry_run"] is True

    @patch("generate_pata_jazz_horizontal.log_exception_to_file")
    @patch("generate_pata_jazz_horizontal._generate_horizontal", side_effect=RuntimeError("boom"))
    @patch("generate_pata_jazz_horizontal.configure_logging")
    def test_exception_returns_one(self, _log, mock_gen, mock_log_exc, monkeypatch):
        monkeypatch.setattr("sys.argv", ["gen"])
        assert gen_horizontal.main() == 1
        mock_log_exc.assert_called_once()

    @patch("generate_pata_jazz_horizontal._generate_horizontal")
    @patch("generate_pata_jazz_horizontal.configure_logging")
    def test_success_returns_zero(self, _log, mock_gen, monkeypatch):
        monkeypatch.setattr("sys.argv", ["gen", "--duration", "300"])
        assert gen_horizontal.main() == 0
        assert mock_gen.call_args.kwargs["duration"] == 300
