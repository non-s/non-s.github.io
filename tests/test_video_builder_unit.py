"""Testes unitários para video_builder.py."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import utils.video_builder as video_builder
from utils.video_validator import VideoValidation


class TestBuildOverlayFilter:
    """Testes para o overlay de texto (hook) via drawtext."""

    def test_has_real_alpha_fade_not_just_hard_cutoff(self):
        result = video_builder._build_overlay_filter("hello", 1920)
        assert "alpha='if(lt(t," in result
        assert "enable='between(t,0," in result

    def test_uses_bundled_fontfile(self):
        """Agora usamos fontfile apontando para a fonte empacotada no repo,
        evitando depender de fontconfig ou do nome 'Arial:style=Bold' no
        runner."""
        result = video_builder._build_overlay_filter("hello", 1920)
        assert "fontfile=" in result
        assert "Roboto-Bold.ttf" in result

    def test_has_semi_transparent_box_for_legibility(self):
        result = video_builder._build_overlay_filter("hello", 1920)
        assert "box=1" in result
        assert "boxcolor=black@0.35" in result

    def test_audio_master_normalizes_and_fades_out(self):
        result = video_builder._audio_master_filter(35)
        assert "loudnorm=I=-16" in result
        assert "afade=t=in" in result
        assert "afade=t=out" in result

    def test_sanitizes_special_characters_in_hook(self):
        result = video_builder._build_overlay_filter("it's: cute", 1920)
        # FFmpeg drawtext nao aceita aspas simples dentro do valor. A sanitizacao
        # troca apostrofo por caractere tipografico e ':' por '\\:'.
        assert "it’s" in result
        assert "\\:" in result
        # Caracteres perigosos nao devem aparecer soltos.
        assert "'" not in result.split("text=")[1]

    def test_y_position_stays_within_jitter_range(self):
        for _ in range(30):
            result = video_builder._build_overlay_filter("hook", 1920)
            y_str = result.split(":y=")[1].split(":alpha=")[0]
            y = int(y_str)
            assert 1920 - 350 - 40 <= y <= 1920 - 350 + 40


class TestBuildEndcardFilter:
    """Testes para o end-card CTA (session/loop) via drawtext."""

    def test_uses_drawtext(self):
        result = video_builder._build_endcard_filter(1920, 30)
        assert result.startswith("drawtext=")

    def test_text_from_cta_rotation(self):
        result = video_builder._build_endcard_filter(1920, 30)
        assert any(f"text='{cta}'" in result for cta in video_builder._ENDCARD_CTAS)

    def test_enable_window_uses_last_seconds(self):
        result = video_builder._build_endcard_filter(1080, 60)
        # CTA aparece nos ultimos ~3.0s: enable gte(t, 57.0)
        assert "enable='gte(t,57.0" in result

    def test_uses_bundled_fontfile(self):
        result = video_builder._build_endcard_filter(1920, 30)
        assert "fontfile=" in result
        assert "Roboto-Bold.ttf" in result

    def test_has_background_box_for_legibility(self):
        result = video_builder._build_endcard_filter(1920, 30)
        assert "box=1" in result
        assert "boxcolor=black@0.35" in result

    def test_rejects_duration_shorter_than_cta(self):
        with pytest.raises(ValueError, match="End-card exige duração"):
            video_builder._build_endcard_filter(1920, 1)

    def test_any_cta_escaped_properly(self):
        for _ in range(50):
            result = video_builder._build_endcard_filter(1920, 30)
            # text='<cta>' fechado corretamente (sem caracteres que quebrem as aspas)
            assert "'\">" not in result
            assert "text='" in result

    def test_mood_specific_cta_is_used_when_mood_passed(self):
        """Passar mood='relax' seleciona um CTA da lista de relax em vez da
        lista legacy global - personalizacao por mood aumenta conversao de
        sessao."""
        for _ in range(30):
            result = video_builder._build_endcard_filter(1920, 30, mood="relax")
            assert any(f"text='{cta}'" in result for cta in video_builder._ENDCARD_CTAS_BY_MOOD["relax"])

    def test_diversao_mood_uses_diversao_ctas(self):
        for _ in range(20):
            result = video_builder._build_endcard_filter(1920, 30, mood="diversao")
            assert any(f"text='{cta}'" in result for cta in video_builder._ENDCARD_CTAS_BY_MOOD["diversao"])

    def test_anxiety_mood_uses_anxiety_ctas(self):
        for _ in range(20):
            result = video_builder._build_endcard_filter(1920, 30, mood="anxiety")
            assert any(f"text='{cta}'" in result for cta in video_builder._ENDCARD_CTAS_BY_MOOD["anxiety"])

    def test_unknown_mood_falls_back_to_legacy_list(self):
        """Mood nao mapeado (ex: 'xyz') cai na lista legacy _ENDCARD_CTAS
        para backward compat com callers que passam um mood nao catalogado."""
        for _ in range(20):
            result = video_builder._build_endcard_filter(1920, 30, mood="xyz")
            assert any(f"text='{cta}'" in result for cta in video_builder._ENDCARD_CTAS)

    def test_empty_mood_falls_back_to_legacy_list(self):
        for _ in range(20):
            result = video_builder._build_endcard_filter(1920, 30, mood="")
            assert any(f"text='{cta}'" in result for cta in video_builder._ENDCARD_CTAS)


class TestVideoBuilderUnits:
    """Testes unitários para video_builder."""

    @patch("utils.media_pool.video_pool")
    @patch("utils.media_pool.audio_pool")
    def test_validate_source_pools_success(self, mock_audio, mock_video):
        """Testa validação de pools com sucesso."""
        mock_video.return_value = [Path("video1.mp4")]
        mock_audio.return_value = [Path("audio1.mp3")]

        # Não deve levantar exceção
        video_builder._validate_source_pools()

    @patch("utils.media_pool.video_pool")
    def test_validate_source_pools_empty_video(self, mock_video):
        """Testa validação com pool de vídeo vazio."""
        mock_video.return_value = []

        with pytest.raises(RuntimeError, match="Pool de b-roll vazio"):
            video_builder._validate_source_pools()

    @patch("utils.media_pool.audio_pool")
    @patch("utils.media_pool.video_pool")
    def test_validate_source_pools_empty_audio(self, mock_video, mock_audio):
        """Testa validação com pool de áudio vazio."""
        mock_video.return_value = [Path("video1.mp4")]
        mock_audio.return_value = []

        # Não deve levantar exceção, apenas logar warning
        with pytest.raises(RuntimeError, match="Pool de jazz vazio"):
            video_builder._validate_source_pools()

    def test_build_pata_jazz_video_invalid_spec(self):
        """Testa build com spec inválida."""
        spec_invalid = {"day": "Seg"}  # Falta type, mood, etc.

        with pytest.raises(RuntimeError):
            video_builder.build_pata_jazz_video(
                spec=spec_invalid, output_dir=Path("test"), thumb_dir=Path("test"), stem_prefix="test"
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

        with (
            patch("utils.video_builder.ensure_dirs"),
            patch("utils.video_builder.pool_stats", return_value={"videos": 1, "audio": 1}),
            patch("utils.video_builder.random_scene", return_value="scene"),
            patch("utils.video_builder.hook_for_scene", return_value=("hook", "🐾")),
            patch("utils.video_builder.pick_videos", return_value=[Path("video.mp4")]),
            patch("utils.video_builder.pick_audio", return_value=Path("audio.mp3")),
            patch("utils.video_builder.music_attribution", return_value="Music: Track — Artist (via Jamendo)"),
            patch("utils.video_builder.run_ffmpeg", side_effect=fake_run_ffmpeg),
            patch("utils.video_builder.generate_metadata", return_value={"title": "t", "description": "d"}),
            patch(
                "utils.video_builder.validate_generated_video",
                return_value=VideoValidation(ok=True, errors=[], info={}),
            ),
        ):
            video_builder.build_pata_jazz_video(spec=spec, output_dir=tmp_path, thumb_dir=tmp_path, stem_prefix="test")

        cmd = captured["args"]
        map_values = [cmd[i + 1] for i, v in enumerate(cmd) if v == "-map"]
        assert map_values == ["0:v:0", "1:a:0"]

    def test_build_pata_jazz_video_requires_audio(self, tmp_path):
        """O vídeo só é aceito quando o pipeline fornece uma faixa de jazz."""
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

        with (
            patch("utils.video_builder.ensure_dirs"),
            patch("utils.video_builder.pool_stats", return_value={"videos": 1, "audio": 1}),
            patch("utils.video_builder.random_scene", return_value="scene"),
            patch("utils.video_builder.hook_for_scene", return_value=("hook", "🐾")),
            patch("utils.video_builder.pick_videos", return_value=[Path("video.mp4")]),
            patch("utils.video_builder.pick_audio", return_value=Path("jazz.mp3")),
            patch("utils.video_builder.run_ffmpeg"),
            patch("utils.video_builder.generate_metadata", return_value={"title": "t", "description": "d"}),
            patch("utils.video_builder.validate_generated_video", side_effect=fake_validate),
        ):
            video_builder.build_pata_jazz_video(spec=spec, output_dir=tmp_path, thumb_dir=tmp_path, stem_prefix="test")

        assert captured["kwargs"].get("expect_audio") is True

    def test_rejects_empty_jazz_pool(self):
        with patch("utils.video_builder.pool_stats", return_value={"videos": 1, "audio": 0}):
            with pytest.raises(RuntimeError, match="Pool de jazz vazio"):
                video_builder._validate_source_pools()

    def test_build_long_routes_to_loop_relax_builder(self, tmp_path):
        """Long-form (kind='long') usa o montador de loop com crossfade lento
        em vez do montador de Shorts."""
        spec = video_builder.long_spec(duration=600)
        with (
            patch("utils.video_builder.ensure_dirs"),
            patch("utils.video_builder._validate_source_pools"),
            patch("utils.video_builder.random_scene", return_value="scene"),
            patch("utils.video_builder.hook_for_scene", return_value=("hook", "🐾")),
            patch("utils.video_builder.pick_audio", return_value=Path("jazz.mp3")),
            patch("utils.video_builder.pick_videos", return_value=[Path("v1.mp4"), Path("v2.mp4")]),
            patch("utils.video_builder._build_loop_relax_video") as mock_loop,
            patch("utils.video_builder._build_multi_clip_short") as mock_short,
            patch("utils.video_builder.run_ffmpeg"),
            patch("utils.video_builder.generate_metadata", return_value={"title": "t", "description": "d"}),
            patch("utils.video_builder.make_long_thumbnail"),
            patch("utils.video_builder.winning_thumbnail_variant", return_value="A"),
            patch(
                "utils.video_builder.validate_generated_video",
                return_value=VideoValidation(ok=True, errors=[], info={}),
            ),
        ):
            video_builder.build_pata_jazz_video(spec=spec, output_dir=tmp_path, thumb_dir=tmp_path, stem_prefix="test")

        mock_loop.assert_called_once()
        mock_short.assert_not_called()

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

        with (
            patch("utils.video_builder.random", **{"sample.return_value": videos, "randint.return_value": 3}),
            patch("utils.video_builder.run_ffmpeg", side_effect=fake_run_ffmpeg),
        ):
            video_builder._build_multi_clip_short(
                spec,
                videos,
                audio_path=None,
                output=tmp_path / "out.mp4",
                hook="hook",
            )

        final_cmd = captured_cmds[-1]
        assert "-t" in final_cmd
        assert final_cmd[final_cmd.index("-t") + 1] == "35"

    def test_multi_clip_short_picks_transition_from_curated_list(self, tmp_path):
        """Cada video sorteia um estilo de transicao xfade (nao sempre
        'fade') de video_builder._XFADE_TRANSITIONS, aplicado a todos os
        cortes daquele video."""
        spec = video_builder.short_spec(duration=35)
        videos = [Path(f"video{i}.mp4") for i in range(3)]

        captured_cmds = []

        def fake_run_ffmpeg(args):
            captured_cmds.append(args)

        with (
            patch("utils.video_builder.random.sample", return_value=videos),
            patch("utils.video_builder.random.randint", return_value=3),
            patch("utils.video_builder.random.choice", return_value="circleopen") as mock_choice,
            patch("utils.video_builder.run_ffmpeg", side_effect=fake_run_ffmpeg),
        ):
            video_builder._build_multi_clip_short(
                spec,
                videos,
                audio_path=None,
                output=tmp_path / "out.mp4",
                hook="hook",
            )

        # O end-card CTA tambem sorteia via random.choice (a partir desta
        # feature) - o importante e que a transicao xfade tenha sido
        # sorteada da lista curada pelo menos uma vez.
        assert video_builder._XFADE_TRANSITIONS in [call.args[0] for call in mock_choice.call_args_list]
        final_cmd = captured_cmds[-1]
        filter_complex = final_cmd[final_cmd.index("-filter_complex") + 1]
        assert "xfade=transition=circleopen" in filter_complex
        assert "xfade=transition=fade" not in filter_complex

    def test_build_generates_both_thumbnail_variants_and_registers_list(self, tmp_path):
        """A/B/C testing: build_pata_jazz_video gera variante A, B e C da
        thumbnail e registra todas em meta['thumbnails'] (lista). Sem sinal
        de performance (winning_thumbnail_variant -> "A" default), a
        primaria enviada e a A."""
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

        with (
            patch("utils.video_builder.ensure_dirs"),
            patch("utils.video_builder.pool_stats", return_value={"videos": 1, "audio": 1}),
            patch("utils.video_builder.random_scene", return_value="scene"),
            patch("utils.video_builder.hook_for_scene", return_value=("hook", "🐾")),
            patch("utils.video_builder.pick_videos", return_value=[Path("video.mp4")]),
            patch("utils.video_builder.pick_audio", return_value=Path("audio.mp3")),
            patch("utils.video_builder.run_ffmpeg"),
            patch("utils.video_builder.generate_metadata", return_value={"title": "t", "description": "d"}),
            patch("utils.video_builder.music_attribution", return_value="Music: Track - Artist (via Jamendo)"),
            patch("utils.video_builder.winning_thumbnail_variant", return_value="A"),
            patch(
                "utils.video_builder.validate_generated_video",
                return_value=VideoValidation(ok=True, errors=[], info={}),
            ),
        ):
            video_builder.build_pata_jazz_video(spec=spec, output_dir=tmp_path, thumb_dir=tmp_path, stem_prefix="test")

        # thumbnail_maker chamado 3x: A, B e C.
        variants = [kw.get("variant", "A") for _, kw in calls]
        assert variants == ["A", "B", "C"]
        meta_path = tmp_path / "test_test.mp4"
        # build grava o .json ao lado do .mp4 (output stem).
        json_files = list(tmp_path.glob("*.json"))
        assert json_files, "meta JSON deve ser escrito"
        meta = json.loads(json_files[0].read_text(encoding="utf-8"))
        assert "thumbnails" in meta
        assert len(meta["thumbnails"]) == 3
        assert meta["thumbnails"][0].endswith("_thumb_a.png")
        assert meta["thumbnails"][1].endswith("_thumb_b.png")
        assert meta["thumbnails"][2].endswith("_thumb_c.png")
        assert meta["thumbnail"] == meta["thumbnails"][0]
        assert meta["thumbnail_variant"] == "A"
        assert meta["music_attribution"] == "Music: Track - Artist (via Jamendo)"
        assert meta["description"].endswith("Music: Track - Artist (via Jamendo)")

    def test_build_uploads_winning_variant_as_primary_thumbnail(self, tmp_path):
        """Feedback loop: quando winning_thumbnail_variant() aponta pra "B"
        (mais views historicamente), a thumbnail PRIMARIA enviada pro
        YouTube e a B, nao sempre A - fecha o loop entre performance e o
        proximo upload em vez de esperar a rotacao reativa de 7+ dias."""
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
        spec.thumbnail_maker.side_effect = lambda *a, **kw: None

        with (
            patch("utils.video_builder.ensure_dirs"),
            patch("utils.video_builder.pool_stats", return_value={"videos": 1, "audio": 1}),
            patch("utils.video_builder.random_scene", return_value="scene"),
            patch("utils.video_builder.hook_for_scene", return_value=("hook", "🐾")),
            patch("utils.video_builder.pick_videos", return_value=[Path("video.mp4")]),
            patch("utils.video_builder.pick_audio", return_value=Path("audio.mp3")),
            patch("utils.video_builder.run_ffmpeg"),
            patch("utils.video_builder.generate_metadata", return_value={"title": "t", "description": "d"}),
            patch("utils.video_builder.winning_thumbnail_variant", return_value="B"),
            patch(
                "utils.video_builder.validate_generated_video",
                return_value=VideoValidation(ok=True, errors=[], info={}),
            ),
        ):
            video_builder.build_pata_jazz_video(spec=spec, output_dir=tmp_path, thumb_dir=tmp_path, stem_prefix="test")

        json_files = list(tmp_path.glob("*.json"))
        meta = json.loads(json_files[0].read_text(encoding="utf-8"))
        assert meta["thumbnail_variant"] == "B"
        assert meta["thumbnail"].endswith("_thumb_b.png")
        assert meta["thumbnail"] == meta["thumbnails"][1]

    def test_build_falls_back_to_a_when_winning_variant_failed_to_render(self, tmp_path):
        """Se winning_thumbnail_variant() apontar pra uma variante que falhou
        ao renderizar (nao esta em `rendered`), cai pra A em vez de quebrar
        ou referenciar um arquivo inexistente."""
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

        def flaky_maker(*a, variant="A", **kw):
            if variant == "C":
                raise RuntimeError("falha simulada na variante C")

        spec.thumbnail_maker.side_effect = flaky_maker

        with (
            patch("utils.video_builder.ensure_dirs"),
            patch("utils.video_builder.pool_stats", return_value={"videos": 1, "audio": 1}),
            patch("utils.video_builder.random_scene", return_value="scene"),
            patch("utils.video_builder.hook_for_scene", return_value=("hook", "🐾")),
            patch("utils.video_builder.pick_videos", return_value=[Path("video.mp4")]),
            patch("utils.video_builder.pick_audio", return_value=Path("audio.mp3")),
            patch("utils.video_builder.run_ffmpeg"),
            patch("utils.video_builder.generate_metadata", return_value={"title": "t", "description": "d"}),
            patch("utils.video_builder.winning_thumbnail_variant", return_value="C"),
            patch(
                "utils.video_builder.validate_generated_video",
                return_value=VideoValidation(ok=True, errors=[], info={}),
            ),
        ):
            video_builder.build_pata_jazz_video(spec=spec, output_dir=tmp_path, thumb_dir=tmp_path, stem_prefix="test")

        json_files = list(tmp_path.glob("*.json"))
        meta = json.loads(json_files[0].read_text(encoding="utf-8"))
        assert meta["thumbnail_variant"] == "A"
        assert meta["thumbnail"].endswith("_thumb_a.png")

    def test_build_falls_back_to_single_thumbnail_when_variant_b_fails(self, tmp_path):
        """Se a variante B (ou C) falhar (fonte/paleta indisponivel, etc), build
        registra so as variantes que deram certo em thumbnails - publicacao
        nao pode quebrar porque a rotacao B/C e opcional."""
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
            if kw.get("variant") in ("B", "C"):
                raise RuntimeError("variant boom")

        spec.thumbnail_maker.side_effect = maker_side_effect

        with (
            patch("utils.video_builder.ensure_dirs"),
            patch("utils.video_builder.pool_stats", return_value={"videos": 1, "audio": 1}),
            patch("utils.video_builder.random_scene", return_value="scene"),
            patch("utils.video_builder.hook_for_scene", return_value=("hook", "🐾")),
            patch("utils.video_builder.pick_videos", return_value=[Path("video.mp4")]),
            patch("utils.video_builder.pick_audio", return_value=Path("audio.mp3")),
            patch("utils.video_builder.run_ffmpeg"),
            patch("utils.video_builder.generate_metadata", return_value={"title": "t", "description": "d"}),
            patch(
                "utils.video_builder.validate_generated_video",
                return_value=VideoValidation(ok=True, errors=[], info={}),
            ),
        ):
            video_builder.build_pata_jazz_video(spec=spec, output_dir=tmp_path, thumb_dir=tmp_path, stem_prefix="test")

        json_files = list(tmp_path.glob("*.json"))
        meta = json.loads(json_files[0].read_text(encoding="utf-8"))
        # So A foi gerada (B e C falharam).
        assert len(meta["thumbnails"]) == 1
        assert meta["thumbnails"][0].endswith("_thumb_a.png")
