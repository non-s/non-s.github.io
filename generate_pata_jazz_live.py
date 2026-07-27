"""
generate_pata_jazz_live.py — prepara e executa live stream em loop infinito.

Gera um feed contínuo de clipes de gatos e cachorros com uma playlist de jazz
real (~150 faixas ou o maximo disponivel) e transmite para o YouTube Live.
O processo aceita SIGTERM (cancelamento do GitHub Actions) e finaliza a
transmissao de forma limpa.
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import re
import signal
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from utils.animal_branding import hook_for_scene, random_scene
from utils.ffmpeg_helpers import build_concat_demuxer, get_video_duration, run_ffmpeg
from utils.log_config import configure_logging, log_exception_to_file
from utils.media_pool import audio_pool, ensure_dirs, pick_videos, pool_stats

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "_videos"
LIVE_META_DIR = ROOT / "_data"

log = logging.getLogger(__name__)

_shutdown = False


def _register_signal_handlers() -> None:
    """Registra handlers de SIGTERM/SIGINT; deve ser chamado apenas dentro de main()."""
    global _shutdown
    _shutdown = False
    signal.signal(signal.SIGTERM, _handle_sigterm)
    signal.signal(signal.SIGINT, _handle_sigterm)


def _handle_sigterm(signum, frame) -> None:
    global _shutdown
    log.info("SIGTERM recebido; iniciando desligamento gracioso da live...")
    _shutdown = True


def _load_live_title() -> str:
    """Le titulo gerado por upload_youtube.py do estado da live, se existir."""
    state = LIVE_META_DIR / "live_state.json"
    if state.exists():
        try:
            data = json.loads(state.read_text(encoding="utf-8"))
            return str(data.get("title", ""))[:100]
        except Exception as exc:
            log.warning("live_state.json invalido, usando titulo default: %s", exc)
    return "Pata Jazz 🐾🎷 | Gatinhos e Cachorrinhos Fofos ao Vivo"


def _build_audio_playlist(output_stem: str) -> tuple[Path | None, float]:
    """Cria arquivo de playlist com todas as musicas jazz disponiveis.

    Faixas com duracao 0 (corrompidas ou ilegiveis pelo ffprobe) sao
    ignoradas para nao subestimar o tempo total e evitar que o demuxer
    concat engasgue em arquivos vazios.
    """
    all_files = sorted([str(p) for p in audio_pool()])
    if not all_files:
        return None, 0.0

    total_duration = 0.0
    valid_files: list[str] = []
    for p in all_files:
        d = get_video_duration(p)
        if d > 0:
            total_duration += d
            valid_files.append(p)
        else:
            log.warning("Faixa com duracao invalida (0s), ignorando: %s", p)
    if not valid_files:
        return None, 0.0

    random.shuffle(valid_files)
    playlist_txt = OUTPUT_DIR / f"{output_stem}_audio_playlist.txt"
    build_concat_demuxer(valid_files, str(playlist_txt))

    log.info(
        "Playlist de audio: %d faixas, ~%.0fs (~%.1fh)",
        len(valid_files),
        total_duration,
        total_duration / 3600,
    )
    return playlist_txt, total_duration


def _build_looping_input(
    output_stem: str,
    target_resolution: tuple[int, int] = (1920, 1080),
    clip_duration: int = 45,
    video_count: int = 90,
) -> tuple[Path, Path | None]:
    """Pre-processa clips fofos e monta a playlist (concat demuxer) usada no loop da live.

    Cada clip e normalizado individualmente (resolucao/codec) para que o
    demuxer concat funcione bem quando transmitido com -stream_loop -1
    diretamente pelo FFmpeg (ver _start_ffmpeg_stream), sem um passo extra de
    "rebake" num unico arquivo grande: rebake exigia um re-encode completo
    (minutos de espera so pra gerar poucos minutos de video) e cada reinicio
    do loop obrigava o FFmpeg a reabrir um unico arquivo de video inteiro,
    causando travamentos visiveis na live a cada ciclo. Usar bem mais clips
    (ate 90, ~45min de ciclo) reduz bastante a frequencia desses reinicios.
    """
    ensure_dirs()
    stats = pool_stats()
    if stats["videos"] == 0:
        raise RuntimeError("Pool de b-roll vazio")

    scene = random_scene()
    hook, emoji = hook_for_scene(scene)
    # Live horizontal: usa muitos clips fofos para um ciclo de loop longo.
    videos = pick_videos(
        min_count=min(60, stats["videos"]),
        max_count=min(video_count, stats["videos"]),
        cuteness_sort=True,
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    processed: list[Path] = []
    for i, v in enumerate(videos):
        proc = OUTPUT_DIR / f"{output_stem}_liveclip_{i}.mp4"
        run_ffmpeg(
            [
                "-i",
                str(v),
                "-vf",
                f"scale={target_resolution[0]}:{target_resolution[1]}:force_original_aspect_ratio=decrease,"
                f"pad={target_resolution[0]}:{target_resolution[1]}:(ow-iw)/2:(oh-ih)/2:black",
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "23",
                "-an",
                "-t",
                str(clip_duration),
                str(proc),
            ]
        )
        processed.append(proc)

    # concat_txt e os clips referenciados por ele precisam sobreviver a live
    # inteira: o FFmpeg de streaming reabre esse playlist a cada volta do
    # -stream_loop -1, entao nao apagamos nada aqui.
    concat_txt = OUTPUT_DIR / f"{output_stem}_concat.txt"
    build_concat_demuxer([str(p) for p in processed], str(concat_txt))

    total_loop_duration = clip_duration * len(videos)
    playlist_txt, _ = _build_audio_playlist(output_stem)

    log.info(
        "Playlist de loop da live gerada: %s (ciclo: %ss, clips: %d, audio playlist: %s)",
        concat_txt,
        total_loop_duration,
        len(videos),
        playlist_txt,
    )
    return concat_txt, playlist_txt


def _start_ffmpeg_stream(
    input_path: Path,
    stream_url: str,
    duration_minutes: int = 0,
    audio_playlist: Path | None = None,
    resolution: tuple[int, int] = (1920, 1080),
) -> subprocess.Popen:
    """Inicia o processo FFmpeg em modo stream e retorna imediatamente.

    Separado de _wait_ffmpeg_stream para permitir que o chamador comece a
    enviar dados ao YouTube e depois confirme o stream ficando ativo (ver
    upload_youtube.wait_for_stream_active) antes de notificar o inicio da
    live. Nao ha transicao manual para "testing" nesse fluxo - broadcasts
    criados com enableMonitorStream=False sempre rejeitam essa fase (403
    invalidTransition) independente do timing; enableAutoStart=True promove
    o broadcast para "live" sozinho assim que o stream fica ativo.

    input_path e um playlist do demuxer concat (gerado por
    _build_looping_input), nao um unico arquivo de video ja "baked" - isso
    evita o FFmpeg ter que reabrir um arquivo de video inteiro a cada volta
    do -stream_loop -1, que causava travamentos visiveis na live.

    -re e aplicado nos DOIS inputs (video e audio). Sem -re no audio, o
    FFmpeg le e decodifica a playlist de audio o mais rapido possivel (sem
    limitar a 1x tempo real), disputando CPU com a codificacao de video em
    tempo real no runner de 2 vCPUs do GitHub Actions - isso fazia o encode
    ir ficando pra tras (speed caindo de ~1x para ~0.5x, frames acumulando
    e sendo dropados) ate a conexao RTMP quebrar (Broken pipe).

    Mesmo com -preset ultrafast, 1080p30 continua caindo pra tras nesse
    runner (testado: speed cai a ~0.43x e quebra em menos de 1min). Em
    720p o encode tem ~2.25x menos pixels por frame, o que da folga real
    de CPU em vez de so trocar preset. O bitrate e escalado junto pra nao
    desperdicar banda/qualidade num frame menor.

    Mesmo em 720p30 o runner ainda cai pra tras periodicamente (medido:
    Broken pipe a cada ~2.8min em media, speed caindo a ~0.43x pouco antes
    - ver run_live._MAX_RECONNECTS, que reconecta quando isso acontece em
    vez de derrubar a live inteira). -r 24 (em vez de 30) reduz ~20% do
    trabalho de encode por segundo para tornar essas quebras mais raras;
    -g 48 mantem o GOP em ~2s (48 frames a 24fps) como antes (60 a 30fps).

    O stderr do FFmpeg e redirecionado para um arquivo de log em _videos/
    em vez de PIPE: o FFmpeg produz muito stderr (logs de progresso
    continuos) e se o buffer da pipe (~64KB) encher sem ninguem drenar, o
    processo bloqueia em write e o stream RTMP congela. Redirecionar para
    arquivo evita o deadlock e permite inspecao posterior.
    """
    video_bitrate_kbps = 2500 if resolution[0] >= 1920 else 1800
    cmd = [
        "ffmpeg",
        "-re",
        "-fflags",
        "+genpts",
        "-stream_loop",
        "-1",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(input_path),
    ]
    if audio_playlist and audio_playlist.exists():
        cmd += [
            "-re",
            "-stream_loop",
            "-1",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(audio_playlist),
        ]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    progress_path = OUTPUT_DIR / "live_progress.txt"
    # Trunca antes de comecar: _wait_ffmpeg_stream detecta stall pelo mtime
    # desse arquivo, e um arquivo do segmento anterior (mtime antigo) faria
    # o novo segmento parecer travado desde o primeiro instante.
    progress_path.write_text("", encoding="utf-8")

    cmd += [
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-b:v",
        f"{video_bitrate_kbps}k",
        "-maxrate",
        f"{video_bitrate_kbps}k",
        "-bufsize",
        f"{video_bitrate_kbps * 2}k",
        "-g",
        "48",
        "-r",
        "24",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-ar",
        "44100",
        # -progress escreve key=value (frame=, out_time_ms=, speed=...)
        # periodicamente nesse arquivo enquanto o encode avanca de verdade -
        # _wait_ffmpeg_stream usa o mtime dele pra detectar um travamento em
        # ~1-2min em vez de esperar o resto da sessao (max_seconds cobre a
        # duracao inteira do segmento, que pode ser horas logo no inicio).
        "-progress",
        str(progress_path),
        "-f",
        "flv",
        stream_url,
    ]
    if duration_minutes > 0:
        # Insere -t logo antes da URL de saida (ultimo elemento).
        cmd = cmd[:-1] + ["-t", str(duration_minutes * 60)] + cmd[-1:]

    log.info("Iniciando stream: %s", " ".join(cmd))
    log_path = OUTPUT_DIR / "live_ffmpeg.log"
    # Abre o arquivo de log e mantem o handle aberto pelo tempo de vida do processo.
    # Usamos stdout=DEVNULL (FFmpeg so escreve progresso em stderr) e stderr para o arquivo.
    log_handle = open(log_path, "ab", buffering=0)  # noqa: SIM115 - mantido aberto pelo processo
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=log_handle)
    # Anexa o handle ao proc para que seja fechado no termino.
    proc._log_handle = log_handle  # type: ignore[attr-defined]
    proc._progress_path = progress_path  # type: ignore[attr-defined]
    return proc


_STALL_GRACE_SECONDS = 75  # folga generosa acima do intervalo normal de -progress (frequente, sub-segundo)


def _wait_ffmpeg_stream(proc: subprocess.Popen, max_seconds: float | None = None) -> int:
    """Aguarda o processo FFmpeg iniciado por _start_ffmpeg_stream terminar.

    O stderr do FFmpeg ja esta redirecionado para um arquivo de log (sem
    risco de deadlock de pipe). Aqui apenas fazemos poll do processo e
    lidamos com o desligamento gracoso via SIGTERM.

    Dois watchdogs, dois papeis:
    - stall (mtime de _progress_path, escrito por -progress): detecta um
      FFmpeg que parou de progredir de verdade em ~_STALL_GRACE_SECONDS.
      max_seconds sozinho so cobre esse caso perto do FIM do segmento -
      um travamento logo no INICIO de uma sessao de ~320min ficaria sem
      deteccao ate quase esse tanto de tempo todo, ja que max_seconds e
      calculado a partir do tempo RESTANTE da sessao inteira.
    - max_seconds: confirmado em producao que o FFmpeg pode travar (parar
      de progredir sem crashar nem respeitar seu proprio -t, provavelmente
      um write RTMP bloqueado por instabilidade de rede) por dezenas de
      minutos sem sair sozinho. Continua como backstop absoluto (cobre
      qualquer cenario onde o arquivo de progresso nao existe/nao e
      escrito por algum motivo) - sem ele o processo so seria derrubado
      quando o job inteiro batesse o timeout duro do GitHub Actions
      (SIGKILL forcado nos processos orfaos, sem chance do codigo chamar
      transition('complete') - broadcast fica preso "ao vivo" para sempre).

    Em qualquer um dos dois casos, mata o FFmpeg e devolve o controle para
    o loop de reconexao em run_live.py, que ja lida com FFmpeg morrendo
    antes da duracao pedida.
    """
    start = time.time()
    progress_path = getattr(proc, "_progress_path", None)
    if not isinstance(progress_path, Path):
        # getattr(..., None) nao basta: um MagicMock (proc de teste, ou
        # qualquer objeto que nao passou por _start_ffmpeg_stream) auto-cria
        # o atributo em vez de levantar AttributeError, entao progress_path
        # viraria outro MagicMock em vez de None e o stat()/mtime abaixo
        # quebraria com TypeError silenciosamente capturado la embaixo.
        progress_path = None
    try:
        while proc.poll() is None:
            if _shutdown:
                log.info("Enviando SIGTERM para FFmpeg...")
                proc.terminate()
                try:
                    proc.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=10)
                break

            stalled = False
            if progress_path is not None:
                try:
                    idle_seconds = time.time() - progress_path.stat().st_mtime
                    if idle_seconds > _STALL_GRACE_SECONDS:
                        stalled = True
                        log.warning(
                            "FFmpeg parece travado (sem progresso ha %.0fs, limite %.0fs); forcando encerramento.",
                            idle_seconds, _STALL_GRACE_SECONDS,
                        )
                except OSError:
                    pass  # arquivo ainda nao existe (ffmpeg nao iniciou a escrever) - nada a checar ainda

            if stalled or (max_seconds and (time.time() - start) > max_seconds):
                if not stalled:
                    log.warning(
                        "FFmpeg parece travado (sem sair apos %.0fs, esperado ~%.0fs); forcando encerramento.",
                        time.time() - start, max_seconds,
                    )
                proc.kill()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    pass
                break
            time.sleep(5)
    except Exception:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()

    # Fecha o handle do log aberto em _start_ffmpeg_stream.
    log_handle = getattr(proc, "_log_handle", None)
    if log_handle:
        try:
            log_handle.close()
        except Exception:
            pass

    code = proc.returncode
    # Le as ultimas linhas do arquivo de log para diagnostico.
    log_path = OUTPUT_DIR / "live_ffmpeg.log"
    try:
        stderr_tail = log_path.read_bytes()[-8000:].decode("utf-8", errors="replace") if log_path.exists() else ""
    except Exception:
        stderr_tail = ""
    if stderr_tail:
        error_lines = [
            line for line in stderr_tail.splitlines()
            if any(kw in line.lower() for kw in ("error", "failed", "invalid", "broken pipe", "connection reset"))
        ]
        if error_lines:
            log.error("FFmpeg linhas de erro detectadas:\n%s", "\n".join(error_lines[-30:]))
        log.info("FFmpeg log (ultimos 6000 chars): %s", stderr_tail[-6000:])
    return code if code is not None else 1


def _terminate_ffmpeg_stream(proc: subprocess.Popen) -> None:
    """Encerra a forca um processo FFmpeg ja iniciado (usado em caminhos de erro)."""
    proc.terminate()
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
    log_handle = getattr(proc, "_log_handle", None)
    if log_handle:
        try:
            log_handle.close()
        except Exception:
            pass


def _run_ffmpeg_stream(
    input_path: Path,
    stream_url: str,
    duration_minutes: int = 0,
    audio_playlist: Path | None = None,
    resolution: tuple[int, int] = (1920, 1080),
) -> int:
    """Executa FFmpeg em modo stream do inicio ao fim. Retorna codigo de saida."""
    proc = _start_ffmpeg_stream(
        input_path,
        stream_url,
        duration_minutes=duration_minutes,
        audio_playlist=audio_playlist,
        resolution=resolution,
    )
    return _wait_ffmpeg_stream(proc)


def _save_live_meta(**kwargs) -> None:
    """Atualiza _data/live_state.json, mesclando com o conteudo ja existente.

    upload_youtube.create_live_stream() grava broadcast_id/stream_id/
    ingestion_url nesse mesmo arquivo logo antes desta funcao ser chamada
    (ver run_live.py) - sobrescrever tudo aqui apagava exatamente os campos
    que upload_youtube._try_resume_existing_broadcast precisa pra
    reaproveitar o broadcast na proxima sessao em vez de criar um novo.
    """
    LIVE_META_DIR.mkdir(parents=True, exist_ok=True)
    path = LIVE_META_DIR / "live_state.json"
    try:
        existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except Exception:
        existing = {}
    data = {**existing, **kwargs}
    data["updated_at"] = datetime.now(UTC).isoformat()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    """CLI standalone para teste manual/local - NAO e usado em producao.

    O workflow .github/workflows/pata-jazz-youtube-live.yml roda
    `python scripts/run_live.py`, que importa as funcoes deste modulo
    (_build_looping_input, _start_ffmpeg_stream etc.) mas tem seu proprio
    main() com todo o ciclo de vida do broadcast (criar, aguardar stream
    ficar ativo, reconectar, encerrar). Corrigir um bug de streaming aqui
    (fluxo abaixo) NAO afeta a live de verdade - edite scripts/run_live.py.
    """
    parser = argparse.ArgumentParser(description="Live Pata Jazz em loop infinito")
    parser.add_argument(
        "--duration",
        type=int,
        default=0,
        help="Duracao maxima em minutos (0 = ate processo ser encerrado).",
    )
    parser.add_argument("--stream-url", type=str, default="", help="URL RTMP de ingestao do YouTube")
    parser.add_argument("--resolution", type=str, default="1280x720", help="Ex: 1920x1080 ou 1280x720")
    args = parser.parse_args()

    configure_logging()

    if not args.stream_url:
        log.error("URL de ingestao nao fornecida. Use --stream-url.")
        return 1

    if not re.fullmatch(r"\d+x\d+", args.resolution):
        log.error("Resolucao invalida '%s'. Use o formato WxH (ex: 1280x720).", args.resolution)
        return 1

    if not 0 <= args.duration <= 360:
        log.error("Duracao invalida: %d minutos (use 0 a 360).", args.duration)
        return 1

    _register_signal_handlers()

    w, h = (int(x) for x in args.resolution.split("x"))
    if w >= 1920:
        log.warning("Resolucao %sx%s nao e suportada no runner gratuito do GitHub Actions "
                    "(encode nao acompanha o tempo real). Usando 1280x720.", w, h)
        w, h = 1280, 720
    output_stem = f"pata_jazz_live_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"

    try:
        loop_input, audio_playlist = _build_looping_input(output_stem, target_resolution=(w, h), clip_duration=30)
    except Exception as exc:
        log.exception("Falha ao construir loop: %s", exc)
        log_exception_to_file(exc, OUTPUT_DIR)
        return 1

    title = _load_live_title()
    _save_live_meta(
        title=title,
        stream_url=args.stream_url,
        loop_file=str(loop_input),
        audio_playlist=str(audio_playlist) if audio_playlist else None,
    )

    log.info("Titulo da live: %s", title)
    log.info("Iniciando stream infinito para %s", args.stream_url)

    code = _run_ffmpeg_stream(
        loop_input, args.stream_url, duration_minutes=args.duration, audio_playlist=audio_playlist, resolution=(w, h)
    )
    log.info("Stream encerrado com codigo %s", code)
    # 0 = sucesso, -15 = SIGTERM (desligamento gracoso solicitado pelo GHA).
    return 0 if code in (0, -15) else code


if __name__ == "__main__":
    sys.exit(main())
