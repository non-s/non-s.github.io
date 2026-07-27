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

import pytest

import upload_youtube

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("YOUTUBE_TEST_TOKEN"),
        reason="YOUTUBE_TEST_TOKEN ausente: teste de upload real requer token de canal de teste.",
    ),
]


def _make_test_video(out_dir: Path) -> tuple[Path, dict]:
    """Gera um MP4 de 1s (frame preto + silencio) e a metadata minima."""
    video = out_dir / "test_integration_upload.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "color=c=black:s=320x240:d=1",
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-t", "1",
        "-c:a", "aac", "-shortest",
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
