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

Se o FFmpeg cair antes da duracao total (Broken pipe por instabilidade de
rede/CPU no runner gratuito), o main() reconecta automaticamente ao mesmo
broadcast/stream em vez de encerrar a live inteira - ver _MAX_RECONNECTS.
"""

from __future__ import annotations

import logging
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from generate_pata_jazz_live import (
    _build_looping_input,
    _register_signal_handlers,
    _save_live_meta,
    _start_ffmpeg_stream,
    _terminate_ffmpeg_stream,
    _wait_ffmpeg_stream,
)
from upload_youtube import create_live_stream, delete_broadcast, transition_broadcast, wait_for_stream_active
from utils.discord_webhook import notify_live_end, notify_live_start
from utils.log_config import configure_logging

log = logging.getLogger(__name__)

OUTPUT_DIR = ROOT / "_videos"
_MAX_RECONNECTS = 200
_RECONNECT_DELAY_SECONDS = 5
# Confirmado em producao (run 30178358662): o FFmpeg pode travar sem sair
# e sem respeitar seu proprio -t (write RTMP bloqueado por instabilidade
# de rede), rodando ate o job inteiro bater o timeout duro do GitHub
# Actions - que forca SIGKILL nos processos orfaos antes do finally poder
# chamar transition('complete'), deixando a broadcast presa "ao vivo"
# para sempre. Folga generosa (nao e um segmento CPU-bound, e so pra
# cobrir flush do muxer + latencia de rede na saida normal).
_SEGMENT_WATCHDOG_GRACE_SECONDS = 90
# 15 era baixo demais: uma run de teste de 20 min mediu FFmpeg quebrando
# (Broken pipe, encode caindo para ~0.43x tempo real) a cada ~2.8 min em
# media no runner gratuito de 2 vCPUs - ou seja, uma live de 350 min
# precisa de ~125 reconexoes so nesse ritmo. Com 200 tentativas (a 5s de
# espera cada) ha folga real; se cair mais rapido que isso o problema e
# outro (broadcast/stream invalido) e desistir ainda faz sentido.


def _try_transition(broadcast_id: str, status: str) -> bool:
    """Transiciona o broadcast e retorna True se bem-sucedido."""
    try:
        transition_broadcast(broadcast_id, status)
        return True
    except Exception as exc:
        log.warning("Falha ao transicionar broadcast %s para %s: %s", broadcast_id, status, exc)
        return False


def _end_broadcast(broadcast_id: str, went_active: bool) -> None:
    """Encerra o broadcast no YouTube, com fallback para nao deixar orfaos.

    transition(..., 'complete') so e valido a partir de 'testing'/'live'.
    Se o stream nunca chegou a ficar ativo (went_active=False), o broadcast
    provavelmente ainda esta em 'ready' e essa transicao pode falhar tambem
    (mesma classe de erro do antigo transition('testing') invalido) -
    nesse caso tenta apagar o broadcast em vez de deixa-lo "ready" parado
    no canal para sempre.
    """
    if _try_transition(broadcast_id, "complete"):
        return
    if not went_active:
        try:
            delete_broadcast(broadcast_id)
        except Exception as exc:
            log.error(
                "Nao foi possivel nem transicionar nem apagar o broadcast %s; "
                "pode ficar orfao no canal e precisar de limpeza manual: %s",
                broadcast_id, exc,
            )


def _cleanup_live_artifacts(output_stem: str) -> None:
    """Remove arquivos temporários da live (liveclip_*.mp4, *_concat.txt, *_audio_playlist.txt)."""
    patterns = [
        f"{output_stem}_liveclip_*.mp4",
        f"{output_stem}_concat.txt",
        f"{output_stem}_audio_playlist.txt",
    ]
    for pattern in patterns:
        for f in OUTPUT_DIR.glob(pattern):
            try:
                f.unlink(missing_ok=True)
            except Exception:
                pass


def main() -> int:
    configure_logging()
    # Sem isso, SIGTERM (cancelamento do job ou o hard limit de 360min dos
    # runners hospedados do GitHub - ver timeout-minutes no workflow) mata o
    # processo Python na hora, sem rodar o bloco finally abaixo: o broadcast
    # nunca recebe transition('complete') e fica preso "ao vivo" no canal
    # para sempre. Registrar o handler faz o SIGTERM soh marcar _shutdown
    # (checado em _wait_ffmpeg_stream) em vez de matar o processo.
    _register_signal_handlers()

    privacy = os.environ.get("YOUTUBE_PRIVACY", "public")
    resolution = os.environ.get("LIVE_RESOLUTION", "1280x720")
    duration_minutes = int(os.environ.get("LIVE_DURATION_MINUTES", "0") or "0")

    if not re.fullmatch(r"\d+x\d+", resolution):
        log.error("LIVE_RESOLUTION invalida '%s'. Use o formato WxH (ex: 1280x720).", resolution)
        return 1
    # 340 (nao 360): o hard limit de job do GitHub Actions hospedado E 360min
    # e nao pode ser aumentado (timeout-minutes acima disso e simplesmente
    # ignorado pela plataforma) - 340 deixa ~20min de folga para o preparo
    # (build do loop de clipes, sync de b-roll/jazz) e a limpeza final, que
    # NAO contam dentro de LIVE_DURATION_MINUTES mas contam no timeout do job.
    if not 0 <= duration_minutes <= 340:
        log.error("LIVE_DURATION_MINUTES invalido: %d (use 0 a 340).", duration_minutes)
        return 1

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
        _end_broadcast(broadcast_id, went_active=False)
        return 1

    _save_live_meta(
        title=title,
        stream_url=stream_url,
        loop_file=str(loop_input),
        audio_playlist=str(audio_playlist) if audio_playlist else None,
    )

    log.info("Iniciando stream para %s", stream_url)
    start_time = time.time()
    target_seconds = duration_minutes * 60 if duration_minutes > 0 else 0

    # Nao chamamos transition('testing') nem transition('live') aqui: com
    # enableMonitorStream=False a fase de testing e sempre invalida (403
    # invalidTransition), nao importa a ordem das chamadas - so existe fase
    # de testing quando o monitor stream esta habilitado. enableAutoStart=True
    # promove o broadcast de 'ready' para 'live' sozinho assim que o stream
    # vinculado comeca a receber video de verdade (confirmado por
    # wait_for_stream_active abaixo).
    stream_confirmed_active = False
    reconnect_count = 0
    consecutive_fast_failures = 0
    code = 1
    try:
        while True:
            elapsed = time.time() - start_time
            if target_seconds and elapsed >= target_seconds:
                code = 0
                break

            remaining_minutes = max(1, int((target_seconds - elapsed) / 60)) if target_seconds else 0
            segment_start = time.time()
            proc = _start_ffmpeg_stream(
                loop_input, stream_url, duration_minutes=remaining_minutes,
                audio_playlist=audio_playlist, resolution=(w, h),
            )

            if not stream_confirmed_active:
                if not wait_for_stream_active(meta["stream_id"], timeout=120):
                    log.error("Stream nao ficou ativo a tempo; abortando live.")
                    _terminate_ffmpeg_stream(proc)
                    _end_broadcast(broadcast_id, went_active=False)
                    return 1
                stream_confirmed_active = True
                thumbnail = f"https://img.youtube.com/vi/{broadcast_id}/maxresdefault.jpg"
                notify_live_start(title=title, stream_url=f"https://youtube.com/watch?v={broadcast_id}", thumbnail=thumbnail)

            segment_max_seconds = (
                remaining_minutes * 60 + _SEGMENT_WATCHDOG_GRACE_SECONDS if remaining_minutes else None
            )
            code = _wait_ffmpeg_stream(proc, max_seconds=segment_max_seconds)
            segment_seconds = time.time() - segment_start

            # 0 = -t atingido (segmento completo), -15 = SIGTERM (cancelamento
            # do GHA ou fim da duracao total) - nao reconectar nesses casos.
            if code in (0, -15):
                break

            reconnect_count += 1
            if reconnect_count > _MAX_RECONNECTS:
                log.error("FFmpeg falhou %d vezes seguidas; desistindo da live.", reconnect_count)
                break

            # Se varios segmentos seguidos caem quase na hora (bem menos que
            # o intervalo de ~2.8min medido para o CPU cair para tras), o
            # problema provavelmente nao e mais CPU - o broadcast pode ter
            # morrido do lado do YouTube (nao detectado por
            # wait_for_stream_active, que so roda uma vez por sessao) e
            # reconectar continuaria falhando ate esgotar as 200 tentativas
            # a toa. Desiste mais cedo nesse caso.
            if segment_seconds < 15:
                consecutive_fast_failures += 1
                if consecutive_fast_failures >= 5:
                    log.error(
                        "%d quedas seguidas em menos de 15s cada; o broadcast "
                        "provavelmente morreu do lado do YouTube. Desistindo "
                        "em vez de esgotar as %d tentativas de reconexao.",
                        consecutive_fast_failures, _MAX_RECONNECTS,
                    )
                    break
            else:
                consecutive_fast_failures = 0

            elapsed_min = (time.time() - start_time) / 60
            log.warning(
                "FFmpeg encerrou inesperadamente (codigo %s) apos %.1f min de execucao; "
                "reconectando ao mesmo broadcast (tentativa %d/%d)...",
                code, elapsed_min, reconnect_count, _MAX_RECONNECTS,
            )
            time.sleep(_RECONNECT_DELAY_SECONDS)
    finally:
        elapsed = (time.time() - start_time) / 60
        log.info(
            "Stream encerrado com codigo %s (%.1f min, %d reconexoes). Finalizando live...",
            code, elapsed, reconnect_count,
        )
        _end_broadcast(broadcast_id, went_active=stream_confirmed_active)
        # Notifica fim da live no Discord
        notify_live_end(title=title, duration_minutes=int(elapsed))
        # Limpa arquivos temporários da live
        _cleanup_live_artifacts(output_stem)

    # 0 = sucesso, -15 = SIGTERM (desligamento gracoso do GHA).
    return 0 if code in (0, -15) else code


if __name__ == "__main__":
    sys.exit(main())
