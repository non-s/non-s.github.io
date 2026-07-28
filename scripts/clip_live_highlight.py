"""
scripts/clip_live_highlight.py — recorta um Short vertical a partir da
gravacao de uma live, com deteccao automatica do pico de espectadores.

A live do Pata Jazz e streamada (nao gravada localmente); este script e um
scaffolding: dado um arquivo de gravacao em _videos/ e um instante inicial,
clippa um Short vertical (1080x1920) com FFmpeg. Se --start/--duration nao
forem passados, le _data/live_viewer_history.json para localizar o pico de
concurrentViewers e clippa ±30s em torno dele — mas apenas se o arquivo de
gravacao for passado via --input, ja que o pico sozinho nao serve sem o video
de origem.

Uso:
    python scripts/clip_live_highlight.py --input _videos/live.mp4 \\
        --start 120 --duration 60
    python scripts/clip_live_highlight.py --input _videos/live.mp4  # deteccao auto
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.ffmpeg_helpers import run_ffmpeg
from utils.log_config import configure_logging
from utils.paths import data_dir

log = logging.getLogger(__name__)

OUTPUT_DIR = ROOT / "_videos"
VIEWER_HISTORY_FILE = data_dir() / "live_viewer_history.json"
PEAK_HALF_WINDOW_SECONDS = 30
SHORT_WIDTH = 1080
SHORT_HEIGHT = 1920


def _peak_viewer_moment(history_path: Path) -> tuple[str, int] | None:
    """Encontra o snapshot com maior concurrent_viewers no historico.

    Retorna (collected_at_iso, concurrent_viewers) ou None se vazio/invalido.
    """
    if not history_path.exists():
        return None
    try:
        history = json.loads(history_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(history, list) or not history:
        return None
    best = None
    for snap in history:
        viewers = snap.get("concurrent_viewers")
        if viewers is None:
            continue
        try:
            viewers = int(viewers)
        except (TypeError, ValueError):
            continue
        collected_at = snap.get("collected_at", "")
        if best is None or viewers > best[1]:
            best = (collected_at, viewers)
    return best


def _collected_at_to_offset_seconds(collected_at: str, recording_start: datetime | None) -> float | None:
    """Converte o timestamp ISO do snapshot em um offset em segundos desde o
    inicio da gravacao (recording_start). Retorna None se nao for possivel
    converter (timestamp ausente ou invalido)."""
    if not collected_at or recording_start is None:
        return None
    try:
        snap_dt = datetime.fromisoformat(collected_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    delta = (snap_dt - recording_start).total_seconds()
    return max(0.0, delta) if delta >= 0 else None


def clip_vertical_short(
    input_path: Path,
    start: float,
    duration: float,
    output_path: Path | None = None,
) -> Path:
    """Recorta um Short vertical (1080x1920) de input_path começando em
    ``start`` com a ``duration`` dada (segundos). Aplica crop central + scale
    vertical. Retorna o caminho do arquivo gerado."""
    if output_path is None:
        stem = input_path.stem
        output_path = OUTPUT_DIR / f"{stem}_short_{int(start)}s.mp4"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # crop=1080:1920 centralizado sobre o frame original, depois scale para
    # garantir saida exata 1080x1920 (mesmo se o source tenha dimensoes
    # diferentes). -ss antes de -i para seek rapido (keyframe-aware).
    args = [
        "-ss", f"{start:.3f}",
        "-i", str(input_path),
        "-t", f"{duration:.3f}",
        "-vf", f"crop=min(iw\\,ih*{SHORT_WIDTH}/{SHORT_HEIGHT}):ih,"
               f"scale={SHORT_WIDTH}:{SHORT_HEIGHT}:flags=lanczos",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        str(output_path),
    ]
    run_ffmpeg(args, timeout=600)
    log.info("Short gerado: %s", output_path)
    return output_path


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recorta um Short vertical de uma gravacao de live.")
    parser.add_argument("--input", required=True, help="Caminho do arquivo de gravacao (mp4).")
    parser.add_argument("--start", type=float, default=None,
                        help="Tempo inicial em segundos (default: deteccao automatica via pico de viewers).")
    parser.add_argument("--duration", type=float, default=None,
                        help="Duracao em segundos (default: 60, ou 2x30s em torno do pico).")
    parser.add_argument("--output", default=None, help="Caminho de saida (default: _videos/<stem>_short_<start>s.mp4).")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    args = _parse_args(argv)
    input_path = Path(args.input)
    if not input_path.exists():
        log.error("Arquivo de gravacao nao encontrado: %s", input_path)
        return 1

    start = args.start
    duration = args.duration

    if start is None:
        peak = _peak_viewer_moment(VIEWER_HISTORY_FILE)
        if peak is None:
            log.error(
                "Sem --start e sem pico de viewers em %s; passando --start explicitamente.",
                VIEWER_HISTORY_FILE,
            )
            return 1
        collected_at, viewers = peak
        log.info(
            "Pico de viewers detectado: %d espectadores em %s. Recortando ±%ds em torno do pico.",
            viewers, collected_at, PEAK_HALF_WINDOW_SECONDS,
        )
        # Sem recording_start conhecido (live streamada), nao e possivel
        # converter o timestamp ISO em offset de arquivo - loga e requer
        # --start explicito do operador, que conhece o ponto do arquivo.
        log.warning(
            "Deteccao do pico disponivel, mas a live e streamada: o timestamp do "
            "pico nao mapeia diretamente para o offset do arquivo de gravacao. "
            "Passe --start <segundos> explicitamente (offset no arquivo)."
        )
        return 1

    if duration is None:
        duration = float(2 * PEAK_HALF_WINDOW_SECONDS)

    output_path = Path(args.output) if args.output else None
    try:
        clip_vertical_short(input_path, start=start, duration=duration, output_path=output_path)
    except Exception as exc:
        log.exception("Falha ao recortar Short: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
