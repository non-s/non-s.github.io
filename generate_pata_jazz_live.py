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
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
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


# REMOVIDO: signal.signal() no import time. Use _register_signal_handlers() em main().
# signal.signal(signal.SIGTERM, _handle_sigterm)
# signal.signal(signal.SIGINT, _handle_sigterm)


def _load_live_title() -> str:
    """Le titulo gerado por upload_youtube.py do estado da live, se existir."""
    state = LIVE_META_DIR / "live_state.json"
    if state.exists():
        try:
            data = json.loads(state.read_text(encoding="utf-8"))
            return str(data.get("title", ""))[:100]
        except Exception:
            pass
    return "Pata Jazz 🐾🎷 | Gatinhos e Cachorrinhos Fofos ao Vivo"


def _build_audio_playlist(output_stem: str) -> tuple[Path | None, float]:
    """Cria arquivo de playlist com todas as musicas jazz disponiveis."""
    audio_files = sorted([str(p) for p in audio_pool()])
    if not audio_files:
        return None, 0.0

    random.shuffle(audio_files)
    playlist_txt = OUTPUT_DIR / f"{output_stem}_audio_playlist.txt"
    build_concat_demuxer(audio_files, str(playlist_txt))

    total_duration = sum(get_video_duration(p) for p in audio_files)
    log.info(
        "Playlist de audio: %d faixas, ~%.0fs (~%.1fh)",
        len(audio_files),
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
    enviar dados ao YouTube antes de transicionar o broadcast: a API do
    YouTube rejeita a transicao para "testing" com 403 invalidTransition
    ate que o stream vinculado esteja com status.streamStatus == "active",
    o que so acontece depois que o FFmpeg comeca a enviar video de verdade.

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
        "60",
        "-r",
        "30",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-ar",
        "44100",
        "-f",
        "flv",
        stream_url,
    ]
    if duration_minutes > 0:
        # Insere -t logo antes da URL de saida (ultimo elemento).
        cmd = cmd[:-1] + ["-t", str(duration_minutes * 60)] + cmd[-1:]

    log.info("Iniciando stream: %s", " ".join(cmd))
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def _wait_ffmpeg_stream(proc: subprocess.Popen) -> int:
    """Aguarda o processo FFmpeg iniciado por _start_ffmpeg_stream terminar."""
    try:
        while proc.poll() is None:
            if _shutdown:
                log.info("Enviando SIGTERM para FFmpeg...")
                proc.terminate()
                try:
                    proc.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    proc.kill()
                break
            time.sleep(5)
    except Exception:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()

    stdout, stderr = proc.communicate()
    if stderr:
        # A causa raiz de uma falha costuma aparecer no meio do stderr, nao
        # no final (que geralmente e so o resumo de estatisticas do libx264).
        # Um tail curto escondia esses erros; aqui destacamos linhas que
        # parecem erro em qualquer ponto do output, alem de um tail maior.
        error_lines = [
            line for line in stderr.splitlines()
            if any(kw in line.lower() for kw in ("error", "failed", "invalid", "broken pipe", "connection reset"))
        ]
        if error_lines:
            log.error("FFmpeg linhas de erro detectadas:\n%s", "\n".join(error_lines[-30:]))
        log.info("FFmpeg stderr (ultimos 6000 chars): %s", stderr[-6000:])
    return proc.returncode


def _terminate_ffmpeg_stream(proc: subprocess.Popen) -> None:
    """Encerra a forca um processo FFmpeg ja iniciado (usado em caminhos de erro)."""
    proc.terminate()
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()


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
    LIVE_META_DIR.mkdir(parents=True, exist_ok=True)
    path = LIVE_META_DIR / "live_state.json"
    data = kwargs.copy()
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
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

    _register_signal_handlers()

    w, h = (int(x) for x in args.resolution.split("x"))
    if w >= 1920:
        log.warning("Resolucao %sx%s nao e suportada no runner gratuito do GitHub Actions "
                    "(encode nao acompanha o tempo real). Usando 1280x720.", w, h)
        w, h = 1280, 720
    output_stem = f"pata_jazz_live_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

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
    return 0 if code in (0, -15, 255) else code


if __name__ == "__main__":
    sys.exit(main())
