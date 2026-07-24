"""
scripts/run_live.py — orquestra a live Pata Jazz no GitHub Actions.

Cria a transmissao no YouTube, constroi o loop de video e a playlist de audio,
e inicia o stream via FFmpeg. Ao finalizar (por SIGTERM ou duracao), encerra
a transmissao no YouTube.

create_live_stream() cria o broadcast com enableMonitorStream=False e
enableAutoStart=True: nessa configuracao a API do YouTube so aceita a
transicao ready -> live automaticamente assim que o stream vinculado comeca
a receber video, e rejeita qualquer chamada manual para 'testing' (essa
fase exige monitorStream habilitado). Por isso este script nao chama
liveBroadcasts.transition para 'testing' nem 'live' - apenas confirma que
o stream ficou ativo e deixa o YouTube promover o broadcast sozinho. So a
transicao final para 'complete' e manual (enableAutoStop=False).
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from generate_pata_jazz_live import (
    _build_looping_input,
    _save_live_meta,
    _start_ffmpeg_stream,
    _terminate_ffmpeg_stream,
    _wait_ffmpeg_stream,
)
from upload_youtube import create_live_stream, transition_broadcast, wait_for_stream_active
from utils.discord_webhook import notify_live_end, notify_live_start

log = logging.getLogger(__name__)


def _try_transition(broadcast_id: str, status: str) -> bool:
    """Transiciona o broadcast e retorna True se bem-sucedido."""
    try:
        transition_broadcast(broadcast_id, status)
        return True
    except Exception as exc:
        log.warning("Falha ao transicionar broadcast %s para %s: %s", broadcast_id, status, exc)
        return False


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    privacy = os.environ.get("YOUTUBE_PRIVACY", "public")
    resolution = os.environ.get("LIVE_RESOLUTION", "1920x1080")
    duration_minutes = int(os.environ.get("LIVE_DURATION_MINUTES", "0") or "0")

    w, h = (int(x) for x in resolution.split("x"))

    log.info("Criando live no YouTube...")
    meta = create_live_stream(
        privacy=privacy,
        resolution="1080p" if w >= 1920 else "720p",
    )
    if not meta:
        log.error("Falha ao criar live.")
        return 1

    stream_url = meta["ingestion_url"]
    broadcast_id = meta["broadcast_id"]
    title = meta["title"]

    output_stem = f"pata_jazz_live_{meta['stream_id']}"
    try:
        loop_input, audio_playlist = _build_looping_input(
            output_stem, target_resolution=(w, h), clip_duration=30
        )
    except Exception as exc:
        log.exception("Falha ao construir loop: %s", exc)
        _try_transition(broadcast_id, "complete")
        return 1

    _save_live_meta(
        title=title,
        stream_url=stream_url,
        loop_file=str(loop_input),
        audio_playlist=str(audio_playlist) if audio_playlist else None,
    )

    log.info("Iniciando stream para %s", stream_url)
    start_time = time.time()
    proc = _start_ffmpeg_stream(
        loop_input, stream_url, duration_minutes=duration_minutes, audio_playlist=audio_playlist
    )

    if not wait_for_stream_active(meta["stream_id"], timeout=90):
        log.error("Stream nao ficou ativo a tempo; abortando live.")
        _terminate_ffmpeg_stream(proc)
        _try_transition(broadcast_id, "complete")
        return 1

    # enableAutoStart=True: o proprio YouTube promove o broadcast para 'live'
    # assim que o stream fica ativo. Nao chamamos transition('testing') nem
    # transition('live') aqui - com enableMonitorStream=False a fase de
    # testing e sempre invalida (403 invalidTransition), e a chamada manual
    # para 'live' e desnecessaria e redundante com o auto-start.

    # Notifica início da live no Discord
    thumbnail = f"https://img.youtube.com/vi/{broadcast_id}/maxresdefault.jpg"
    notify_live_start(title=title, stream_url=f"https://youtube.com/watch?v={broadcast_id}", thumbnail=thumbnail)

    code = 1
    try:
        code = _wait_ffmpeg_stream(proc)
    finally:
        elapsed = (time.time() - start_time) / 60
        log.info("Stream encerrado com codigo %s (%.1f min). Finalizando live...", code, elapsed)
        _try_transition(broadcast_id, "complete")
        # Notifica fim da live no Discord
        notify_live_end(title=title, duration_minutes=int(elapsed))

    return 0 if code in (0, -15, 255) else code


if __name__ == "__main__":
    sys.exit(main())
