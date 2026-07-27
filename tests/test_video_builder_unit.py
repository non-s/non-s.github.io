"""Testes unitários para video_builder.py."""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

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

        with pytest.raises(RuntimeError):
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

    def test_build_pata_jazz_video_does_not_require_audio_when_pool_empty(self, tmp_path):
        """Sem musica de jazz disponivel (pool vazio), pick_audio() retorna
        None e o video e gerado sem trilha - a validacao nao pode continuar
        exigindo audio nesse caso, senao toda geracao falha sempre que o
        pool de jazz estiver vazio, mesmo o video em si estando correto."""
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

        def fake_validate(*args, **kwargs):
            captured["kwargs"] = kwargs
            captured["args"] = args
            return VideoValidation(ok=True, errors=[], info={})

        with patch("utils.video_builder.ensure_dirs"), \
             patch("utils.video_builder.pool_stats", return_value={"videos": 1, "audio": 0}), \
             patch("utils.video_builder.random_scene", return_value="scene"), \
             patch("utils.video_builder.hook_for_scene", return_value=("hook", "🐾")), \
             patch("utils.video_builder.pick_videos", return_value=[Path("video.mp4")]), \
             patch("utils.video_builder.pick_audio", return_value=None), \
             patch("utils.video_builder.run_ffmpeg"), \
             patch("utils.video_builder.generate_metadata", return_value={"title": "t", "description": "d"}), \
             patch("utils.video_builder.validate_generated_video", side_effect=fake_validate):
            video_builder.build_pata_jazz_video(
                spec=spec, output_dir=tmp_path, thumb_dir=tmp_path, stem_prefix="test"
            )

        assert captured["kwargs"].get("expect_audio") is False

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

    def test_build_generates_both_thumbnail_variants_and_registers_list(self, tmp_path):
        """A/B testing: build_pata_jazz_video gera variante A e B da thumbnail
        e registra ambas em meta['thumbnails'] (lista), mantendo
        meta['thumbnail'] (legado) apontando para A pra backward compat."""
        spec = video_builder.VideoSpec(
            kind="test",
            width=100,
            height=100,
            duration=5,
            default_duration=5,
            crop_filter="crop=100:100",
            thumbnail_maker=MagicMock(),
            fallback_description="desc",
        )
        calls: list = []
        spec.thumbnail_maker.side_effect = lambda *a, **kw: calls.append((a, kw))

        with patch("utils.video_builder.ensure_dirs"), \
             patch("utils.video_builder.pool_stats", return_value={"videos": 1, "audio": 1}), \
             patch("utils.video_builder.random_scene", return_value="scene"), \
             patch("utils.video_builder.hook_for_scene", return_value=("hook", "🐾")), \
             patch("utils.video_builder.pick_videos", return_value=[Path("video.mp4")]), \
             patch("utils.video_builder.pick_audio", return_value=Path("audio.mp3")), \
             patch("utils.video_builder.run_ffmpeg"), \
             patch("utils.video_builder.generate_metadata", return_value={"title": "t", "description": "d"}), \
             patch("utils.video_builder.validate_generated_video",
                   return_value=VideoValidation(ok=True, errors=[], info={})):
            video_builder.build_pata_jazz_video(
                spec=spec, output_dir=tmp_path, thumb_dir=tmp_path, stem_prefix="test"
            )

        # thumbnail_maker chamado 2x: A e B.
        variants = [kw.get("variant", "A") for _, kw in calls]
        assert variants == ["A", "B"]
        meta_path = tmp_path / "test_test.mp4"
        # build grava o .json ao lado do .mp4 (output stem).
        json_files = list(tmp_path.glob("*.json"))
        assert json_files, "meta JSON deve ser escrito"
        meta = json.loads(json_files[0].read_text(encoding="utf-8"))
        assert "thumbnails" in meta
        assert len(meta["thumbnails"]) == 2
        assert meta["thumbnails"][0].endswith("_thumb_a.png")
        assert meta["thumbnails"][1].endswith("_thumb_b.png")
        # Backward compat: thumbnail (legado) aponta pra variante A.
        assert meta["thumbnail"] == meta["thumbnails"][0]

    def test_build_falls_back_to_single_thumbnail_when_variant_b_fails(self, tmp_path):
        """Se a variante B falhar (fonte/paleta indisponivel, etc), build
        registra so a variante A em thumbnails - publicacao nao pode quebrar
        porque a rotacao B e opcional."""
        spec = video_builder.VideoSpec(
            kind="test",
            width=100,
            height=100,
            duration=5,
            default_duration=5,
            crop_filter="crop=100:100",
            thumbnail_maker=MagicMock(),
            fallback_description="desc",
        )

        def maker_side_effect(*a, **kw):
            if kw.get("variant") == "B":
                raise RuntimeError("variant B boom")

        spec.thumbnail_maker.side_effect = maker_side_effect

        with patch("utils.video_builder.ensure_dirs"), \
             patch("utils.video_builder.pool_stats", return_value={"videos": 1, "audio": 1}), \
             patch("utils.video_builder.random_scene", return_value="scene"), \
             patch("utils.video_builder.hook_for_scene", return_value=("hook", "🐾")), \
             patch("utils.video_builder.pick_videos", return_value=[Path("video.mp4")]), \
             patch("utils.video_builder.pick_audio", return_value=Path("audio.mp3")), \
             patch("utils.video_builder.run_ffmpeg"), \
             patch("utils.video_builder.generate_metadata", return_value={"title": "t", "description": "d"}), \
             patch("utils.video_builder.validate_generated_video",
                   return_value=VideoValidation(ok=True, errors=[], info={})):
            video_builder.build_pata_jazz_video(
                spec=spec, output_dir=tmp_path, thumb_dir=tmp_path, stem_prefix="test"
            )

        json_files = list(tmp_path.glob("*.json"))
        meta = json.loads(json_files[0].read_text(encoding="utf-8"))
        assert len(meta["thumbnails"]) == 1
        assert meta["thumbnails"][0].endswith("_thumb_a.png")
