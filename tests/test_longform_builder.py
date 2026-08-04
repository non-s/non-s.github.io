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

    def test_pre_renders_segments_with_stream_loops(self, tmp_path):
        spec = video_builder.long_spec(duration=600)
        videos = [Path(f"video{i}.mp4") for i in range(3)]
        captured = self._run(tmp_path, spec, videos)

        # 3 clipes intermediarios + 1 comando final de xfade
        assert len(captured) == 4
        for cmd in captured[:3]:
            assert "-stream_loop" in cmd
            assert cmd[cmd.index("-t") + 1] == "200"  # 600 / 3
        final = captured[-1]
        assert final[final.index("-t") + 1] == "600"
        assert "duration=2.0" in final[final.index("-filter_complex") + 1]

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
        # Inputs do final sao os clipes processados, nao os originais
        assert any(str(tmp_path) in arg and "_clip_" in arg for arg in final_cmd)

    def test_adds_hook_and_endcard(self, tmp_path):
        spec = video_builder.long_spec(duration=600)
        videos = [Path(f"video{i}.mp4") for i in range(2)]
        captured = self._run(tmp_path, spec, videos)

        filter_complex = captured[-1][captured[-1].index("-filter_complex") + 1]
        assert "drawtext=text='hook'" in filter_complex
        assert any(f"text='{cta}'" in filter_complex for cta in video_builder._ENDCARD_CTAS)

    def test_single_clip_renders_segment_and_copy(self, tmp_path):
        spec = video_builder.long_spec(duration=600)
        videos = [Path("video0.mp4")]
        captured = self._run(tmp_path, spec, videos)

        # 1 segmento + 1 copy
        assert len(captured) == 2
        assert captured[-1][-3:-1] == ["-c", "copy"]

    def test_ffmpeg_error_bubbles_and_cleans_temp_clips(self, tmp_path):
        spec = video_builder.long_spec(duration=600)
        videos = [Path(f"video{i}.mp4") for i in range(3)]

        call_count = 0
        def fail_on_second(args):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("segment boom")

        with (
            patch(
                "utils.video_builder.random",
                **{"sample.return_value": videos, "randint.return_value": 3},
            ),
            patch("utils.video_builder.run_ffmpeg", side_effect=fail_on_second),
            pytest.raises(RuntimeError, match="segment boom"),
        ):
            video_builder._build_loop_relax_video(
                spec,
                videos,
                None,
                tmp_path / "out.mp4",
                hook="hook",
            )

        # run_ffmpeg e mockado, entao nao cria arquivos; a logica de cleanup
        # do finally continua funcionando.
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
