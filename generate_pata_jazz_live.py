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
import os
import random
import re
import signal
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from utils.animal_branding import ALL_SCENES, hook_for_scene, random_scene
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

    _write_current_track(valid_files[0])

    log.info(
        "Playlist de audio: %d faixas, ~%.0fs (~%.1fh)",
        len(valid_files),
        total_duration,
        total_duration / 3600,
    )
    return playlist_txt, total_duration


def _consume_next_scene() -> str | None:
    """Le (e apaga) _data/live_next_scene.json se existir e for uma cena valida.

    One-shot: comandos de chat !scene escrevem esse arquivo; o loop de clipes
    consome a primeira cena valida e apaga o arquivo para nao forcar a mesma
    cena em todos os ciclos seguintes.
    """
    path = LIVE_META_DIR / "live_next_scene.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning("live_next_scene.json corrompido, ignorando: %s", exc)
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass
        return None
    scene = str(data.get("scene", "")).lower().strip()
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass
    if scene and scene in ALL_SCENES:
        log.info("Cena forcada por comando de chat: %s", scene)
        return scene
    log.warning("Cena forcada invalida ignorada: %r", scene)
    return None


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

    scene = _consume_next_scene() or random_scene()
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


def _write_current_track(audio_path: str) -> None:
    """Escreve _data/live_current_track.json com a faixa atualmente na
    playlist, para o comando !song do chat. Le o .json de metadata do
    Jamendo ao lado do .mp3 quando disponivel."""
    LIVE_META_DIR.mkdir(parents=True, exist_ok=True)
    track_path = Path(audio_path)
    meta = {}
    sidecar = track_path.with_suffix(".json")
    if sidecar.exists():
        try:
            meta = json.loads(sidecar.read_text(encoding="utf-8"))
        except Exception:
            meta = {}
    payload = {
        "file": track_path.name,
        "title": meta.get("name") or meta.get("title") or track_path.stem,
        "artist": meta.get("artist") or meta.get("artist_name") or "",
        "updated_at": datetime.now(UTC).isoformat(),
    }
    try:
        (LIVE_META_DIR / "live_current_track.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception as exc:
        log.warning("Falha ao escrever live_current_track.json: %s", exc)


_UPTIME_OVERLAY_PATH = LIVE_META_DIR / "live_uptime.txt"
_CHAT_OVERLAY_PATH = LIVE_META_DIR / "live_chat_overlay.txt"

# Altura (px) da barra do visualizador de áudio no canto inferior da live.
# Sutil de propósito: não pode competir com o conteúdo principal.
_VISUALIZER_HEIGHT = 80
_VISUALIZER_ALPHA = 0.6


def _visualizer_enabled() -> bool:
    """Visualizador de áudio e opt-in via env var LIVE_VISUALIZER.

    Valores aceitos:
    - "1" ou "showcqt": espectrograma CQT (default, mesmo que "1" para
      backward compat com os testes existentes).
    - "showwaves": osciloscópio (mais leve, alternativa de baixo custo).
    - "avectorscope": vetorscope de áudio.

    Default OFF (qualquer outro valor, inclusive vazio) para não arriscar a
    CPU no runner gratuito em produção."""
    return _visualizer_mode() != ""


def _visualizer_mode() -> str:
    """Retorna o modo do visualizador normalizado, ou "" se desligado."""
    raw = os.environ.get("LIVE_VISUALIZER", "").strip().lower()
    if raw in ("1", "showcqt"):
        return "showcqt"
    if raw == "showwaves":
        return "showwaves"
    if raw == "avectorscope":
        return "avectorscope"
    return ""


def _build_visualizer_filter_chain(audio_input_index: int) -> str:
    """Monta a chain de filtro do visualizador de áudio reativo.

    Modo default: showcqt (espectro 2D), com timeclamp curto (0.5s) para
    que as barras pulsem visivelmente com o andamento do jazz, e count=32
    para manter o custo baixo.

    Modos alternativos:
    - showwaves: osciloscópio (forma de onda), mais leve que showcqt —
      alternativa de baixo custo para runners com pouca CPU.
    - avectorscope: vetorscope de áudio (Lissajous stereo), visual abstrato.

    A altura fica fixa em _VISUALIZER_HEIGHT e o resultado é sobreposto no
    canto inferior com alpha ~0.6 (sutil — não compete com o conteúdo
    principal).
    """
    mode = _visualizer_mode() or "showcqt"
    size = f"size={1280}x{_VISUALIZER_HEIGHT}"
    if mode == "showwaves":
        core = (
            f"[{audio_input_index}:a]"
            f"showwaves={size}:mode=line:rate=30:colors=white|white"
        )
    elif mode == "avectorscope":
        core = (
            f"[{audio_input_index}:a]"
            f"avectorscope={size}:m=lissajous:s=128x128:dc=1"
        )
    else:
        core = (
            f"[{audio_input_index}:a]"
            f"showcqt={size}:timeclamp=0.5:count=32"
        )
    return f"{core},format=rgba,colorchannelmixer=aa={_VISUALIZER_ALPHA}[viz]"


def _build_overlay_filter(resolution: tuple[int, int], audio_input_index: int | None = None) -> str:
    """Monta o filter graph com overlays de texto (uptime + chat) e,
    opcionalmente, o visualizador de áudio (showcqt) no canto inferior.

    Sem visualizador: usa a forma -vf antiga (uma única cadeia simples,
    sem filter_complex) — mantém o caminho de produção estável e o
    comando de teste existente intacto.

    Com visualizador: troca para -filter_complex — a entrada de áudio
    (audio_input_index) é consumida pelo showcqt e o vídeo resultante é
    sobreposto no canto inferior ([v][viz]overlay=0:H-h). O drawtext de
    uptime/chat é aplicado depois do overlay do visualizador para que o
    texto nunca seja coberto pelas barras.
    """
    _w, _h = resolution
    uptime_str = (
        f"drawtext="
        f"textfile='{_UPTIME_OVERLAY_PATH.as_posix()}':"
        f"reload=1:"
        f"fontcolor=white:fontsize=24:"
        f"x=20:y=20:"
        f"borderw=2:bordercolor=black"
    )
    chat_str = (
        f"drawtext="
        f"textfile='{_CHAT_OVERLAY_PATH.as_posix()}':"
        f"reload=1:"
        f"fontcolor=white:fontsize=24:"
        f"x=w-text_w-20:y=h-text_h-20:"
        f"borderw=2:bordercolor=black"
    )

    if audio_input_index is None or not _visualizer_enabled():
        return f"{uptime_str},{chat_str}"

    viz_chain = _build_visualizer_filter_chain(audio_input_index)
    # [v] = vídeo base; [viz] = espectro do showcqt; overlay no canto inferior
    # (x=0, y=H-h) e drawtext depois.
    return (
        f"{viz_chain};"
        f"[0:v]{uptime_str},{chat_str}[v];"
        f"[v][viz]overlay=0:H-h"
    )


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
    LIVE_META_DIR.mkdir(parents=True, exist_ok=True)
    # drawtext com textfile= falha (e derruba o encode) se o arquivo nao
    # existe no momento em que o filtro e avaliado. Inicializa vazios/placeholder
    # antes de subir o FFmpeg; a thread de uptime e o watcher de chat
    # reescrevem em seguida.
    if not _UPTIME_OVERLAY_PATH.exists():
        try:
            _UPTIME_OVERLAY_PATH.write_text("\U0001f534 LIVE 00:00:00", encoding="utf-8")
        except Exception:
            pass
    if not _CHAT_OVERLAY_PATH.exists():
        try:
            _CHAT_OVERLAY_PATH.write_text("", encoding="utf-8")
        except Exception:
            pass
    progress_path = OUTPUT_DIR / "live_progress.txt"
    # Trunca antes de comecar: _wait_ffmpeg_stream detecta stall pelo mtime
    # desse arquivo, e um arquivo do segmento anterior (mtime antigo) faria
    # o novo segmento parecer travado desde o primeiro instante.
    progress_path.write_text("", encoding="utf-8")

    # Visualizer opt-in (LIVE_VISUALIZER=1): só liga quando há playlist de
    # áudio (índice 1) para alimentar o showcqt. Sem áudio externo, cai no
    # caminho -vf simples (sem filter_complex) — mesmo comando de produção
    # estável que sempre rodou. Default OFF para não arriscar CPU no runner
    # gratuito em produção (ver _visualizer_enabled).
    visualizer_on = bool(audio_playlist and audio_playlist.exists()) and _visualizer_enabled()
    if visualizer_on:
        cmd += ["-filter_complex", _build_overlay_filter(resolution, audio_input_index=1)]
    else:
        cmd += ["-vf", _build_overlay_filter(resolution, audio_input_index=None)]

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
