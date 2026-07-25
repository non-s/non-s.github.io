"""Testes unitários para video_builder.py."""
from pathlib import Path
from unittest.mock import patch

import pytest

import utils.video_builder as video_builder
from utils.video_validator import VideoValidation


class TestVideoBuilderUnits:
    """Testes unitários para video_builder."""

    @patch('utils.media_pool.video_pool')
    @patch('utils.media_pool.audio_pool')
    def test_validate_source_pools_success(self, mock_audio, mock_video):
        """Testa validação de pools com sucesso."""
        mock_video.return_value = [Path("video1.mp4")]
        mock_audio.return_value = [Path("audio1.mp3")]

        # Não deve levantar exceção
        video_builder._validate_source_pools()

    @patch('utils.media_pool.video_pool')
    def test_validate_source_pools_empty_video(self, mock_video):
        """Testa validação com pool de vídeo vazio."""
        mock_video.return_value = []

        with pytest.raises(RuntimeError, match="Pool de b-roll vazio"):
            video_builder._validate_source_pools()

    @patch('utils.media_pool.audio_pool')
    @patch('utils.media_pool.video_pool')
    def test_validate_source_pools_empty_audio(self, mock_video, mock_audio):
        """Testa validação com pool de áudio vazio."""
        mock_video.return_value = [Path("video1.mp4")]
        mock_audio.return_value = []

        # Não deve levantar exceção, apenas logar warning
        video_builder._validate_source_pools()

    def test_build_pata_jazz_video_invalid_spec(self):
        """Testa build com spec inválida."""
        spec_invalid = {"day": "Seg"}  # Falta type, mood, etc.

        with pytest.raises((KeyError, TypeError, RuntimeError)):
            video_builder.build_pata_jazz_video(
                spec=spec_invalid,
                output_dir=Path("test"),
                thumb_dir=Path("test"),
                stem_prefix="test"
            )

    def test_build_pata_jazz_video_maps_music_explicitly(self, tmp_path):
        """A trilha de jazz (input 1) precisa ser mapeada explicitamente como
        audio de saida; sem -map, a selecao automatica do FFmpeg pode pegar o
        audio embutido no clipe de b-roll (input 0) em vez da musica."""
        spec = video_builder.VideoSpec(
            kind="test",
            width=100,
            height=100,
            duration=5,
            default_duration=5,
            crop_filter="crop=100:100",
            thumbnail_maker=lambda *a, **kw: None,
            fallback_description="desc",
        )

        captured = {}

        def fake_run_ffmpeg(args):
            captured["args"] = args

        with patch("utils.video_builder.ensure_dirs"), \
             patch("utils.video_builder.pool_stats", return_value={"videos": 1, "audio": 1}), \
             patch("utils.video_builder.random_scene", return_value="scene"), \
             patch("utils.video_builder.hook_for_scene", return_value=("hook", "🐾")), \
             patch("utils.video_builder.pick_videos", return_value=[Path("video.mp4")]), \
             patch("utils.video_builder.pick_audio", return_value=Path("audio.mp3")), \
             patch("utils.video_builder.run_ffmpeg", side_effect=fake_run_ffmpeg), \
             patch("utils.video_builder.generate_metadata", return_value={"title": "t", "description": "d"}), \
             patch("utils.video_builder.validate_generated_video",
                   return_value=VideoValidation(ok=True, errors=[], info={})):
            video_builder.build_pata_jazz_video(
                spec=spec, output_dir=tmp_path, thumb_dir=tmp_path, stem_prefix="test"
            )

        cmd = captured["args"]
        map_values = [cmd[i + 1] for i, v in enumerate(cmd) if v == "-map"]
        assert map_values == ["0:v:0", "1:a:0"]

    def test_multi_clip_short_caps_duration_without_audio(self, tmp_path):
        """Sem audio (pool de jazz vazio), o xfade final ainda precisa de -t:
        sum(per_clip) - (n_clips-1)*xfade_duration fica abaixo de spec.duration
        por causa do truncamento inteiro de per_clip, o que sem -t produziria
        um video curto demais e reprovaria em video_validator (tolerancia de
        1.5s)."""
        spec = video_builder.short_spec(duration=35)
        videos = [Path(f"video{i}.mp4") for i in range(3)]

        captured_cmds = []

        def fake_run_ffmpeg(args):
            captured_cmds.append(args)

        with patch("utils.video_builder.random", **{"sample.return_value": videos, "randint.return_value": 3}), \
             patch("utils.video_builder.run_ffmpeg", side_effect=fake_run_ffmpeg):
            video_builder._build_multi_clip_short(
                spec, videos, audio_path=None, output=tmp_path / "out.mp4", hook="hook",
            )

        final_cmd = captured_cmds[-1]
        assert "-t" in final_cmd
        assert final_cmd[final_cmd.index("-t") + 1] == "35"
