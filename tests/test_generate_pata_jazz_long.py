"""Testes para scripts/generate_pata_jazz_long.py."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

import scripts.generate_pata_jazz_long as gen_long


class TestGenerateLong:
    @patch("scripts.generate_pata_jazz_long.scene_for_mood", return_value="sleepy cat")
    @patch("scripts.generate_pata_jazz_long.build_pata_jazz_video")
    def test_generate_long_dry_run(self, mock_build, _scene):
        mock_build.return_value = Path("fake.mp4")
        result = gen_long._generate_long(duration=600, dry_run=True)

        assert result == Path("fake.mp4")
        kwargs = mock_build.call_args.kwargs
        assert kwargs["dry_run"] is True
        assert kwargs["stem_prefix"] == "pata_jazz_long"
        assert kwargs["spec"].kind == "long"

    @patch("scripts.generate_pata_jazz_long.scene_for_mood", return_value="sleepy cat")
    @patch("scripts.generate_pata_jazz_long.build_pata_jazz_video")
    def test_generate_long_always_uses_relax_mood(self, mock_build, mock_scene):
        mock_build.return_value = Path("fake.mp4")
        gen_long._generate_long(duration=600)

        mock_scene.assert_called_once_with("relax")
        assert mock_build.call_args.kwargs["spec"].mood == "relax"

    @patch("scripts.generate_pata_jazz_long.scene_for_mood")
    @patch("scripts.generate_pata_jazz_long.build_pata_jazz_video")
    def test_generate_long_rejects_out_of_range_duration(self, mock_build, _scene):
        with pytest.raises(ValueError, match="2700"):
            gen_long._generate_long(duration=3600)
        mock_build.assert_not_called()


class TestMain:
    @patch("scripts.generate_pata_jazz_long._generate_long")
    @patch("scripts.generate_pata_jazz_long.configure_logging")
    def test_dry_run_returns_zero(self, _log, mock_gen, monkeypatch):
        monkeypatch.setattr("sys.argv", ["gen", "--dry-run"])
        assert gen_long.main() == 0
        mock_gen.assert_called_once()
        assert mock_gen.call_args.kwargs["dry_run"] is True

    @patch("scripts.generate_pata_jazz_long.log_exception_to_file")
    @patch("scripts.generate_pata_jazz_long._generate_long", side_effect=RuntimeError("boom"))
    @patch("scripts.generate_pata_jazz_long.configure_logging")
    def test_exception_returns_one(self, _log, mock_gen, mock_log_exc, monkeypatch):
        monkeypatch.setattr("sys.argv", ["gen"])
        assert gen_long.main() == 1
        mock_log_exc.assert_called_once()

    @patch("scripts.generate_pata_jazz_long._generate_long")
    @patch("scripts.generate_pata_jazz_long.configure_logging")
    def test_success_returns_zero_with_duration(self, _log, mock_gen, monkeypatch):
        monkeypatch.setattr("sys.argv", ["gen", "--duration", "900"])
        assert gen_long.main() == 0
        assert mock_gen.call_args.kwargs["duration"] == 900
