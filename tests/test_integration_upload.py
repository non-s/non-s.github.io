"""Teste de integracao (I/O real) do upload de um video curto para o YouTube.

Skipped por padrao: so roda com `pytest -m integration` explicito E a env var
YOUTUBE_TEST_TOKEN setada (token OAuth de um canal de teste, NUNCA o do
canal de producao). O video e criado com FFmpeg (1s, frame preto + silencio),
subido como private (prefix="test_" para nao colidir com o prefixo de
producao "pata_jazz_"), e apagado logo apos para nao deixar sujo no canal.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import upload_youtube


def _make_test_video(out_dir: Path) -> tuple[Path, dict]:
    """Gera um MP4 de 1s (frame preto + silencio) e a metadata minima."""
    video = out_dir / "test_integration_upload.mp4"
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "color=c=black:s=320x240:d=1",
        "-f",
        "lavfi",
        "-i",
        "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-t",
        "1",
        "-c:a",
        "aac",
        "-shortest",
        str(video),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    meta = {
        "title": "Pata Jazz | Teste Integracao (apagar)",
        "description": "Video gerado por teste de integracao; sera apagado.",
        "scene": "cat",
        "hashtags": ["test"],
        "kind": "short",
        "mood": "relax",
        "thumbnail": "",
        "caption": "",
    }
    meta_path = video.with_suffix(".json")
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    return video, meta


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("YOUTUBE_TEST_TOKEN"),
    reason="YOUTUBE_TEST_TOKEN ausente: teste de upload real requer token de canal de teste.",
)
def test_upload_and_delete_real_video(monkeypatch, tmp_path):
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg nao encontrado no PATH")

    monkeypatch.setattr(upload_youtube, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(upload_youtube, "_VIDEO_TAGS_FILE", tmp_path / "video_tags.json")

    video, _meta = _make_test_video(tmp_path)

    video_id = upload_youtube.upload_video(privacy="private", prefix="test_")
    assert video_id is not None, "upload_video retornou None; o upload falhou."

    try:
        from utils.youtube_oauth import get_youtube_service

        service = get_youtube_service()
        service.videos().delete(id=video_id).execute()
    except Exception:
        pytest.fail(f"Nao foi possivel apagar o video de teste {video_id}; apague manualmente.")
    finally:
        video.unlink(missing_ok=True)


def _fake_subprocess_run(cmd, *args, **kwargs):
    """Mock de subprocess.run que cobre ffmpeg e ffprobe do pipeline.

    - ffmpeg: cria o arquivo de saida (ultimo arg .mp4) e retorna returncode=0,
      para que validate_generated_video encontre o arquivo e o proximo passo do
      pipeline (thumbnail/legenda) tenha um path valido.
    - ffprobe (duration): retorna a duracao esperada como stdout.
    - ffprobe (streams): retorna JSON com codec/width/height/duration validos
      para que validate_video nao reproche por resolucao/codec/bitrate.
    """
    bin_name = Path(cmd[0]).name if cmd else ""
    if bin_name == "ffmpeg":
        out = cmd[-1]
        if isinstance(out, str) and out.endswith(".mp4"):
            Path(out).write_bytes(b"fake mp4 bytes")
        return subprocess.CompletedProcess(cmd, 0, "", "")
    if bin_name == "ffprobe":
        entries = " ".join(cmd)
        stdout = "0\n"
        if "stream=" in entries:
            streams = [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1080,
                    "height": 1920,
                    "bit_rate": 500000,
                    "duration": "35.0",
                },
                {
                    "codec_type": "audio",
                    "codec_name": "aac",
                    "bit_rate": 192000,
                    "duration": "35.0",
                },
            ]
            stdout = json.dumps({"streams": streams})
        elif "format=duration" in entries:
            stdout = "35.0\n"
        return subprocess.CompletedProcess(cmd, 0, stdout, "")
    return subprocess.CompletedProcess(cmd, 0, "", "")


class TestFullPipelineShort:
    """Pipeline ponta-a-ponta de geracao de Short: _generate_short (selecao de
    spec, dry_run) -> build_pata_jazz_video (FFmpeg mockado) -> validate.

    Mocka subprocess.run (FFmpeg + ffprobe) e a YouTube API (MagicMock service)
    para que o teste rode em CI sem binarios reais nem credenciais. Verifica que
    o .json de metadata gerado pelo build contem todos os campos esperados.
    """

    def test_metadata_json_has_all_expected_fields(self, tmp_path, monkeypatch):
        import generate_pata_jazz_short as gen_short
        from utils.video_builder import build_pata_jazz_video, short_spec

        monkeypatch.setattr(gen_short, "OUTPUT_DIR", tmp_path)
        thumb_dir = tmp_path / "thumbs"
        monkeypatch.setattr(gen_short, "THUMB_DIR", thumb_dir)

        service = MagicMock()
        service.videos().insert().execute.return_value = {
            "id": "vid-pipeline",
            "status": {"privacyStatus": "public"},
        }

        with (
            patch("generate_pata_jazz_short.mood_for_now", return_value="relax"),
            patch("generate_pata_jazz_short.scene_for_mood", return_value="sleepy cat"),
            patch("generate_pata_jazz_short.optimized_scene_and_pattern", return_value=("sleepy cat", "")),
            patch("generate_pata_jazz_short.build_pata_jazz_video") as mock_build_dry,
        ):
            mock_build_dry.return_value = Path("fake-dry.mp4")
            dry_path = gen_short._generate_short(duration=35, dry_run=True)
            assert dry_path == Path("fake-dry.mp4")

        with (
            patch("utils.ffmpeg_helpers.subprocess.run", side_effect=_fake_subprocess_run),
            patch("utils.video_validator.subprocess.run", side_effect=_fake_subprocess_run),
            patch("utils.thumbnail_engine.subprocess.run", side_effect=_fake_subprocess_run),
            patch("utils.video_builder.ensure_dirs"),
            patch("utils.video_builder.pool_stats", return_value={"videos": 3, "audio": 2}),
            patch("utils.video_builder.pick_videos", return_value=[Path("v0.mp4"), Path("v1.mp4"), Path("v2.mp4")]),
            patch("utils.video_builder.pick_audio", return_value=Path("audio.mp3")),
        ):
            spec = short_spec(duration=35, scene="sleepy cat", mood="relax")
            output = build_pata_jazz_video(
                spec=spec,
                output_dir=tmp_path,
                thumb_dir=thumb_dir,
                stem_prefix="pata_jazz_short",
                dry_run=False,
            )

        assert output.exists()
        meta_path = output.with_suffix(".json")
        assert meta_path.exists()
        meta = json.loads(meta_path.read_text(encoding="utf-8"))

        for field in (
            "title",
            "description",
            "hashtags",
            "scene",
            "hook",
            "kind",
            "thumbnail",
            "caption",
            "caption_pt",
            "chapters",
            "cta",
        ):
            assert field in meta, f"campo '{field}' ausente da metadata"
        assert meta["scene"] == "sleepy cat"
        assert meta["kind"] == "short"
        assert meta["title"].startswith("Pata Jazz")
        assert isinstance(meta["hashtags"], list) and meta["hashtags"]
        assert meta["thumbnail"].endswith("_thumb_a.png")
        assert meta["caption"].endswith(".ass")
        assert meta["caption_pt"].endswith(".pt.srt")
        assert "Intro" in meta["chapters"]
        assert meta["cta"]

        with (
            patch("utils.ffmpeg_helpers.subprocess.run", side_effect=_fake_subprocess_run),
            patch("utils.video_validator.subprocess.run", side_effect=_fake_subprocess_run),
        ):
            from utils.video_validator import validate_generated_video

            validation = validate_generated_video(
                output,
                meta["resolution"],
                spec.duration,
                expect_audio=True,
            )
        assert validation.ok, f"validacao falhou: {validation.errors}"
