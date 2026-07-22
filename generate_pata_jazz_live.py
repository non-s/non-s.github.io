"""
generate_pata_jazz_live.py — prepara e executa live stream em loop infinito.

Gera um feed contínuo de clipes de gatos e cachorros com jazz real e transmite
para o YouTube Live usando FFmpeg. O script aceita SIGTERM (cancelamento do
GitHub Actions) e finaliza a transmissão de forma limpa.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from utils.animal_branding import hook_for_scene, random_scene
from utils.ffmpeg_helpers import build_concat_demuxer, run_ffmpeg
from utils.media_pool import ensure_dirs, pick_audio, pick_videos, pool_stats

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "_videos"
LIVE_META_DIR = ROOT / "_data"

log = logging.getLogger(__name__)

# Sinalizador para desligamento gracioso
_shutdown = False


def _handle_sigterm(signum, frame) -> None:
    global _shutdown
    log.info("SIGTERM recebido; iniciando desligamento gracioso da live...")
    _shutdown = True


signal.signal(signal.SIGTERM, _handle_sigterm)
signal.signal(signal.SIGINT, _handle_sigterm)


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


def _build_looping_input(
    output_stem: str,
    target_resolution: tuple[int, int] = (1920, 1080),
    clip_duration: int = 30,
) -> tuple[Path, Path | None]:
    """Constroi arquivo unico de entrada para a live (loop interno via concat)."""
    ensure_dirs()
    stats = pool_stats()
    if stats["videos"] == 0:
        raise RuntimeError("Pool de b-roll vazio")

    scene = random_scene()
    hook, emoji = hook_for_scene(scene)
    videos = pick_videos(min_count=2, max_count=min(10, stats["videos"]))
    audio_path = pick_audio()

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

    concat_txt = OUTPUT_DIR / f"{output_stem}_concat.txt"
    build_concat_demuxer([str(p) for p in processed], str(concat_txt))

    loop_input = OUTPUT_DIR / f"{output_stem}_loop.mp4"
    audio_args: list[str] = []
    if audio_path:
        audio_args = [
            "-stream_loop",
            "-1",
            "-i",
            str(audio_path),
            "-shortest",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
        ]

    total_loop_duration = clip_duration * len(videos)
    run_ffmpeg(
        ["-stream_loop", "-1", "-f", "concat", "-safe", "0", "-i", str(concat_txt)]
        + audio_args
        + [
            "-t",
            str(total_loop_duration),
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(loop_input),
        ]
    )

    for p in processed:
        p.unlink(missing_ok=True)
    concat_txt.unlink(missing_ok=True)

    log.info("Arquivo de loop gerado: %s (duracao do ciclo: %ss)", loop_input, total_loop_duration)
    return loop_input, audio_path


def _run_ffmpeg_stream(input_path: Path, stream_url: str, duration_minutes: int = 0) -> int:
    """Executa FFmpeg em modo stream. Retorna codigo de saida."""
    cmd = [
        "ffmpeg",
        "-re",
        "-stream_loop",
        "-1",
        "-i",
        str(input_path),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-b:v",
        "2500k",
        "-maxrate",
        "2500k",
        "-bufsize",
        "5000k",
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
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

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
        log.info("FFmpeg stderr final: %s", stderr[-1000:])
    return proc.returncode


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
    parser.add_argument("--resolution", type=str, default="1920x1080", help="Ex: 1920x1080 ou 1280x720")
    parser.add_argument("--dry-run", action="store_true", help="Nao chama APIs externas")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.dry_run:
        os.environ.setdefault("GEMINI_API_KEY", "dry-run")

    if not args.stream_url:
        log.error("URL de ingestao nao fornecida. Use --stream-url.")
        return 1

    w, h = (int(x) for x in args.resolution.split("x"))
    output_stem = f"pata_jazz_live_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

    try:
        loop_input, audio = _build_looping_input(output_stem, target_resolution=(w, h), clip_duration=30)
    except Exception as exc:
        log.exception("Falha ao construir loop: %s", exc)
        return 1

    title = _load_live_title()
    _save_live_meta(title=title, stream_url=args.stream_url, loop_file=str(loop_input), audio=str(audio))

    log.info("Titulo da live: %s", title)
    log.info("Iniciando stream infinito para %s", args.stream_url)

    code = _run_ffmpeg_stream(loop_input, args.stream_url, duration_minutes=args.duration)
    log.info("Stream encerrado com codigo %s", code)
    return 0 if code in (0, -15, 255) else code


if __name__ == "__main__":
    sys.exit(main())
