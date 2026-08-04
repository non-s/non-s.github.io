"""Testes para o long-form Loop & Relax (utils/video_builder.long_spec +
_build_loop_relax_video)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

import utils.video_builder as video_builder
from utils.thumbnail_engine import make_long_thumbnail


class TestLongSpec:
    def test_defaults_are_landscape_16_9(self):
        spec = video_builder.long_spec()
        assert spec.kind == "long"
        assert (spec.width, spec.height) == (1920, 1080)
        assert "16/9" in spec.crop_filter
        assert spec.default_duration == 600
        assert spec.thumbnail_maker is make_long_thumbnail

    def test_duration_passed_through(self):
        spec = video_builder.long_spec(duration=900)
        assert spec.duration == 900

    def test_rejects_below_10_min(self):
        with pytest.raises(ValueError, match="600"):
            video_builder.long_spec(duration=300)

    def test_rejects_above_45_min(self):
        with pytest.raises(ValueError, match="2700"):
            video_builder.long_spec(duration=3600)


class TestBuildLoopRelaxVideo:
    def _run(self, tmp_path, spec, videos, audio_path=None):
        captured = []
        with (
            patch(
                "utils.video_builder.random",
                **{
                    "sample.return_value": videos,
                    "randint.return_value": len(videos),
                    "choice.return_value": video_builder._ENDCARD_CTAS[0],
                },
            ),
            patch("utils.video_builder.run_ffmpeg", side_effect=lambda args: captured.append(args)),
        ):
            video_builder._build_loop_relax_video(
                spec,
                videos,
                audio_path,
                tmp_path / "out.mp4",
                hook="hook",
            )
        return captured

    def test_single_command_with_stream_loops(self, tmp_path):
        spec = video_builder.long_spec(duration=600)
        videos = [Path(f"video{i}.mp4") for i in range(3)]
        captured = self._run(tmp_path, spec, videos)

        assert len(captured) == 1
        cmd = captured[0]
        # Cada clipe entra com -stream_loop -1
        assert cmd.count("-stream_loop") >= len(videos)
        assert "-1" in cmd
        # Duracao total do output
        assert cmd[cmd.index("-t") + 1] == "600"
        # Per-segmento implicito no xfade
        assert "duration=2.0" in cmd[cmd.index("-filter_complex") + 1]

    def test_final_output_uses_total_duration_and_slow_xfade(self, tmp_path):
        spec = video_builder.long_spec(duration=600)
        videos = [Path(f"video{i}.mp4") for i in range(3)]
        captured = self._run(tmp_path, spec, videos)

        final_cmd = captured[-1]
        assert "-t" in final_cmd
        assert final_cmd[final_cmd.index("-t") + 1] == "600"
        assert "duration=2.0" in final_cmd[final_cmd.index("-filter_complex") + 1]
        # offset do primeiro xfade = per_clip - xfade = 200 - 2 = 198
        assert "offset=198" in final_cmd[final_cmd.index("-filter_complex") + 1]

    def test_adds_hook_and_endcard(self, tmp_path):
        spec = video_builder.long_spec(duration=600)
        videos = [Path(f"video{i}.mp4") for i in range(2)]
        captured = self._run(tmp_path, spec, videos)

        filter_complex = captured[-1][captured[-1].index("-filter_complex") + 1]
        assert "drawtext=text='hook'" in filter_complex
        assert any(f"text='{cta}'" in filter_complex for cta in video_builder._ENDCARD_CTAS)

    def test_single_clip_still_builds_one_pass(self, tmp_path):
        spec = video_builder.long_spec(duration=600)
        videos = [Path("video0.mp4")]
        captured = self._run(tmp_path, spec, videos)

        assert len(captured) == 1
        cmd = captured[0]
        assert "-stream_loop" in cmd
        assert cmd[cmd.index("-t") + 1] == "600"
        assert "xfade" not in " ".join(cmd)

    def test_ffmpeg_error_bubbles_without_temp_clips(self, tmp_path):
        spec = video_builder.long_spec(duration=600)
        videos = [Path(f"video{i}.mp4") for i in range(3)]

        def fail_on_filter(args):
            if "-filter_complex" in args:
                raise RuntimeError("filter boom")

        with (
            patch(
                "utils.video_builder.random",
                **{"sample.return_value": videos, "randint.return_value": 3},
            ),
            patch("utils.video_builder.run_ffmpeg", side_effect=fail_on_filter),
            pytest.raises(RuntimeError, match="filter boom"),
        ):
            video_builder._build_loop_relax_video(
                spec,
                videos,
                None,
                tmp_path / "out.mp4",
                hook="hook",
            )

        # Sem arquivos temporarios *_clip_*.mp4 com a nova arquitetura.
        leftovers = list(tmp_path.glob("out_*_clip_*.mp4"))
        assert leftovers == []

    def test_maps_jazz_audio_as_loop(self, tmp_path):
        spec = video_builder.long_spec(duration=600)
        videos = [Path(f"video{i}.mp4") for i in range(2)]
        captured = self._run(tmp_path, spec, videos, audio_path=Path("audio.mp3"))

        final_cmd = captured[-1]
        assert "-stream_loop" in final_cmd
        assert "audio.mp3" in final_cmd
        map_values = [final_cmd[i + 1] for i, v in enumerate(final_cmd) if v == "-map"]
        # 2 clipes (indices 0..1) -> audio mapeado em 2:a:0
        assert "2:a:0" in map_values
