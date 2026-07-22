"""
scripts/run_live.py — orquestra a live Pata Jazz no GitHub Actions.

Cria a transmissao no YouTube, constroi o loop de video e a playlist de audio,
e inicia o stream via FFmpeg. Ao finalizar (por SIGTERM ou duracao), encerra
a transmissao no YouTube.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from generate_pata_jazz_live import _build_looping_input, _run_ffmpeg_stream, _save_live_meta
from upload_youtube import create_live_stream, transition_broadcast

log = logging.getLogger(__name__)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    privacy = os.environ.get("YOUTUBE_PRIVACY", "public")
    resolution = os.environ.get("LIVE_RESOLUTION", "1920x1080")
    duration_minutes = int(os.environ.get("LIVE_DURATION_MINUTES", "0") or "0")

    w, h = (int(x) for x in resolution.split("x"))

    log.info("Criando live no YouTube...")
    meta = create_live_stream(privacy=privacy, resolution="1080p" if w >= 1920 else "720p")
    if not meta:
        log.error("Falha ao criar live.")
        return 1

    stream_url = meta["ingestion_url"]
    broadcast_id = meta["broadcast_id"]
    title = meta["title"]

    output_stem = f"pata_jazz_live_{meta['stream_id']}"
    try:
        loop_input, audio_playlist = _build_looping_input(output_stem, target_resolution=(w, h), clip_duration=30)
    except Exception as exc:
        log.exception("Falha ao construir loop: %s", exc)
        transition_broadcast(broadcast_id, "complete")
        return 1

    _save_live_meta(
        title=title,
        stream_url=stream_url,
        loop_file=str(loop_input),
        audio_playlist=str(audio_playlist) if audio_playlist else None,
    )

    log.info("Iniciando stream infinito para %s", stream_url)
    code = _run_ffmpeg_stream(loop_input, stream_url, duration_minutes=duration_minutes, audio_playlist=audio_playlist)
    log.info("Stream encerrado com codigo %s", code)

    log.info("Encerrando live no YouTube...")
    try:
        transition_broadcast(broadcast_id, "complete")
    except Exception as exc:
        log.warning("Erro ao finalizar live: %s", exc)

    return 0 if code in (0, -15, 255) else code


if __name__ == "__main__":
    sys.exit(main())
