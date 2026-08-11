"""
utils/video_builder.py — lógica de construção dos vídeos do canal ativo.

Reúne o pipeline completo:
- seleção de assets
- montagem FFmpeg (multi-clipe com crossfade)
- validação do arquivo de saída
- escrita de metadados
- geração de thumbnail (A/B/C)
"""

from __future__ import annotations

import json
import logging
import random
import subprocess
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Protocol

from utils.animal_branding import best_hook_for_scene, detect_animal, hook_for_scene, random_scene
from utils.caption_engine import generate_ass, save_ass
from utils.channel_config import active_channel
from utils.editorial_brief import build_editorial_brief
from utils.ffmpeg_helpers import get_video_duration, run_ffmpeg
from utils.font_config import font_path
from utils.format_strategy import format_strategy
from utils.media_pool import ensure_dirs, music_attribution, pick_audio, pick_videos, pool_stats
from utils.media_usage import commit_reservation, release_reservation, reserve_media
from utils.metadata_engine import clean_title, generate_metadata
from utils.story_engine import choose_story_card, record_story_card
from utils.thumbnail_engine import make_long_thumbnail, make_short_thumbnail, winning_thumbnail_variant
from utils.video_validator import validate_generated_video
from utils.viewer_experience import assess_viewer_experience
from utils.visual_intelligence import analyze_image, analyze_video, creative_quality_flags

log = logging.getLogger(__name__)


class _ThumbnailMaker(Protocol):
    """Assinatura real de make_short_thumbnail - um Callable[[str, str,
    Path], None] simples nao cobria o kwarg video_path usado em
    _build_video (linha ~286), nem o kwarg variant usado na geracao das
    tres variantes para A/B/C testing."""

    def __call__(
        self,
        hook: str,
        emoji: str,
        output: Path,
        *,
        video_path: Path | None = None,
        variant: str = "A",
    ) -> None: ...


@dataclass(frozen=True)
class VideoSpec:
    """Especificação de um vídeo a ser gerado."""

    kind: Literal["short", "long"]
    width: int
    height: int
    duration: int
    default_duration: int
    crop_filter: str
    thumbnail_maker: _ThumbnailMaker
    fallback_description: str
    scene: str = ""
    mood: str = ""
    # Hint de padrao de titulo otimizado por previsao (utils/slot_optimizer).
    # Vazio = generate_metadata usa o comportamento legado (sortear/IA).
    title_pattern_hint: str = ""
    # Idioma do metadata (A3): "en" (default), "pt" ou "es". Define em qual
    # idioma o título/descrição/hashtags sao gerados. O pipeline visual
    # (video, legendas) nao muda - so o texto do upload.
    lang: str = "en"


_HOOK_ENABLE_SECONDS = 5.0
_HOOK_FADE_SECONDS = 0.4


def _audio_master_filter(duration: int) -> str:
    """Normaliza volume entre faixas e evita cortes secos no inicio/fim."""
    fade_duration = min(0.8, max(0.2, duration / 10))
    fade_out_start = max(0.0, duration - fade_duration)
    return (
        "loudnorm=I=-16:LRA=11:TP=-1.5,"
        f"afade=t=in:st=0:d={fade_duration:.2f},"
        f"afade=t=out:st={fade_out_start:.2f}:d={fade_duration:.2f}"
    )


def _build_video_filter(spec: VideoSpec) -> str:
    """Constrói a cadeia de filtros FFmpeg para o aspecto-alvo."""
    w, h = spec.width, spec.height
    return (
        f"{spec.crop_filter},"
        f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,"
        f"setsar=1/1"
    )


# #9: Cache de clipes normalizados em _assets/normalized/. O cache e
# indexado por (nome_do_arquivo, width, height) - se o mesmo clipe for
# usado em outro video com a mesma resolucao, reusa o normalizado sem
# re-crop/re-scale. Limitado a MAX_NORMALIZED_FILES para nao crescer
# indefinidamente; evicts mais antigos por mtime quando cheio.
_NORMALIZED_DIR = Path(__file__).resolve().parent.parent / "_assets" / "normalized"
MAX_NORMALIZED_FILES = 60


def _normalized_cache_path(video: Path, spec: VideoSpec) -> Path:
    """Caminho do clipe normalizado no cache."""
    stem = video.stem
    return _NORMALIZED_DIR / f"{stem}_{spec.width}x{spec.height}.mp4"


def _get_or_cache_normalized(video: Path, spec: VideoSpec) -> Path | None:
    """#9: retorna clipe normalizado do cache, ou cria e cacheia.

    Normaliza o clipe (crop+scale+pad para o aspecto-alvo) UMA VEZ e
    guarda em _assets/normalized/. Se o cache ja existe, retorna direto
    (pulando o crop/scale caro). Retorna None se falhar (caller cai no
    fluxo legado de normalizar do zero).
    """
    cache_path = _normalized_cache_path(video, spec)
    if cache_path.exists():
        return cache_path
    try:
        _NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)
        # Evict mais antigos se cache cheio
        cached_files = sorted(_NORMALIZED_DIR.glob("*.mp4"), key=lambda p: p.stat().st_mtime)
        while len(cached_files) >= MAX_NORMALIZED_FILES:
            cached_files[0].unlink(missing_ok=True)
            cached_files.pop(0)
        run_ffmpeg(
            [
                "-i", str(video),
                "-vf", _build_video_filter(spec),
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "23",
                "-r", "30",
                "-pix_fmt", "yuv420p",
                "-an",
                str(cache_path),
            ]
        )
        return cache_path
    except Exception as exc:
        log.debug("Cache de clipe normalizado falhou (%s): %s", video.name, exc)
        if cache_path.exists():
            cache_path.unlink(missing_ok=True)
        return None


def _build_overlay_filter(hook: str, height: int) -> str:
    """Constrói filtro drawtext para mostrar o hook nos primeiros segundos.

    Fonte bold empacotada, caixa semi-transparente atras do texto
    (legibilidade sobre qualquer fundo) e fade in/out real via alpha animado.
    """
    # O valor do texto fica entre aspas simples. Dois caracteres problematicos
    # sao normalizados ANTES de envolver em aspas:
    # - apostofo ASCII (') vira apostrofo tipografico (’), evitando a
    #   sequencia de escape `\'` que e instavel em algumas builds do FFmpeg;
    # - dois-pontos (:) e escapado como `\:` porque o parser de opcoes do
    #   FFmpeg o splita mesmo dentro de aspas simples quando fontfile= e usado.
    safe_hook = hook.replace("'", "’").replace(":", "\\:")
    fade = _HOOK_FADE_SECONDS
    hold_end = _HOOK_ENABLE_SECONDS - fade
    alpha_expr = (
        f"if(lt(t,{fade}),t/{fade},"
        f"if(lt(t,{hold_end}),1,"
        f"if(lt(t,{_HOOK_ENABLE_SECONDS}),({_HOOK_ENABLE_SECONDS}-t)/{fade},0)))"
    )
    # Pequena variacao de posicao entre videos (nao sempre o mesmo pixel),
    # mantendo a faixa segura acima da UI do player de Shorts.
    y_pos = height - 350 + random.randint(-40, 40)
    return (
        f"drawtext=text='{safe_hook}'"
        f":fontfile='{font_path()}'"
        f":fontsize=56"
        f":fontcolor=white"
        f":shadowcolor=black:shadowx=2:shadowy=2"
        f":box=1:boxcolor=black@0.35:boxborderw=18"
        f":x=(w-text_w)/2:y={y_pos}"
        f":alpha='{alpha_expr}'"
        f":enable='between(t,0,{_HOOK_ENABLE_SECONDS})'"
    )


_ENDCARD_SECONDS = 3.0

# CTAs de end-card por mood. Antes era uma lista global sorteada
# uniformemente; personalizar por mood aumenta conversao de sessao porque
# o CTA reflete o estado emocional do espectador ao fim do vídeo (diversao
# -> continue jogando; relax -> continue relaxando; anxiety -> conforte
# de novo). Caso o mood nao esteja mapeado, cai na lista legacy/_ENDCARD_CTAS.
_ENDCARD_CTAS_BY_MOOD: dict[str, list[str]] = {
    "diversao": [
        "keep the happy vibe going",
        "play another happy moment",
        "more playful pets coming up",
        "subscribe for daily happy pets",
        "catch the next playful one",
    ],
    "fofura": [
        "more cuteness coming up",
        "subscribe for daily cozy pets",
        "watch another cozy moment",
        "save this for a cozy break",
        "follow for your daily pet fix",
    ],
    "relax": [
        "watch another to keep relaxing",
        "save this for bedtime",
        "keep the calm going",
        "more peaceful pets coming up",
        "subscribe for more calm moments",
    ],
    "sleep": [
        "save this for bedtime",
        "more cozy pet jazz coming up",
        "keep the calm going for your pet",
        "subscribe for more gentle jazz tracks",
        "play another for a cozy pet-and-jazz moment",
    ],
    "anxiety": [
        "calm them again with the next one",
        "more soothing tracks coming up",
        "save this for anxious moments",
        "subscribe for more gentle pet jazz",
        "play another to keep them calm",
    ],
}

# Lista legacy usada como fallback quando o mood nao esta mapeado em
# _ENDCARD_CTAS_BY_MOOD. Mantem os CTAs originais pra backward compat com
# testes que esperam qualquer CTA valido quando nenhum mood e passado.
_ENDCARD_CTAS: list[str] = [
    "subscribe for more cuteness",
    "more pets + jazz coming up",
    "follow for your daily pet fix",
    "catch the next one soon",
    "watch another to keep relaxing",
    "save this for bedtime",
]


def _endcard_cta(mood: str = "") -> str:
    """Sorteia um CTA de end-card apropriado para o mood dado.

    Sem mood (string vazia) ou mood nao mapeado, cai na lista legacy
    _ENDCARD_CTAS para backward compat com callers que nao passam mood.
    """
    pool = _ENDCARD_CTAS_BY_MOOD.get(mood) if mood else None
    if not pool:
        pool = _ENDCARD_CTAS
    return random.choice(pool)


def _build_endcard_filter(height: int, duration: int, mood: str = "") -> str:
    """Constrói filtro drawtext de end-card: um CTA curto no fim do vídeo.

    Session/loop: um chamado à ação no fim incentiva quem ficou até aqui a
    se inscrever ou procurar o próximo vídeo - aumenta sessao e inscritos
    (o CTA funciona porque já houve retenção). Texto ASCII (sem emoji, que
    depende de fonte) rotativo entre vídeos para nao parecer template.

    O CTA agora e personalizado por mood (diversao/fofura/relax/sleep/
    anxiety) para refletir o estado emocional do espectador ao fim do
    vídeo - aumenta conversao de sessao em relacao ao CTA global aleatorio.
    Sem mood passado, cai na lista legacy para backward compat.
    """
    if duration <= _ENDCARD_SECONDS:
        raise ValueError("End-card exige duração maior que o próprio CTA.")
    safe = _endcard_cta(mood).replace("'", "’").replace(":", "\\:")
    start = float(duration) - _ENDCARD_SECONDS
    fade = 0.25
    # Fade-in curto ao entrar; sem fade-out (o vídeo acaba logo depois).
    alpha_expr = f"if(lt(t,{start + fade}),(t-{start})/{fade},1)"
    y_pos = height - 300
    return (
        f"drawtext=text='{safe}'"
        f":fontfile='{font_path()}'"
        f":fontsize=42"
        f":fontcolor=white"
        f":shadowcolor=black:shadowx=2:shadowy=2"
        f":box=1:boxcolor=black@0.35:boxborderw=14"
        f":x=(w-text_w)/2:y={y_pos}"
        f":alpha='{alpha_expr}'"
        f":enable='gte(t,{start})'"
    )


def _prepare_output_paths(stem_prefix: str, output_dir: Path, thumb_dir: Path) -> tuple[Path, Path, str]:
    """Cria diretórios e retorna (video_path, thumb_path, stem).

    Inclui um sufixo aleatorio curto para evitar colisao quando dois
    videos sao gerados no mesmo segundo (batch rapido).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    thumb_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{stem_prefix}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"
    return output_dir / f"{stem}.mp4", thumb_dir / f"{stem}.png", stem


def _validate_source_pools() -> None:
    """Garante que há b-roll e jazz licenciável disponíveis para o vídeo."""
    stats = pool_stats()
    if stats["videos"] == 0:
        raise RuntimeError("Pool de b-roll vazio. Execute scripts/sync_animal_broll.py primeiro.")
    if stats["audio"] == 0:
        raise RuntimeError("Pool de jazz vazio. Execute scripts/sync_jazz_music.py antes de gerar o vídeo.")


def _build_single_clip_video(
    spec: VideoSpec,
    video: Path,
    audio_path: Path | None,
    output: Path,
    hook: str = "",
) -> None:
    """Gera um video com 1 clipe em loop + musica de jazz + overlay de texto."""
    inputs = ["-stream_loop", "-1", "-i", str(video)]
    vf = _build_video_filter(spec)
    if hook:
        vf = f"{vf},{_build_overlay_filter(hook, spec.height)}"
    if spec.duration > _ENDCARD_SECONDS:
        vf = f"{vf},{_build_endcard_filter(spec.height, spec.duration, mood=spec.mood)}"
    output_args: list[str] = [
        "-map",
        "0:v:0",
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "23",
        "-t",
        str(spec.duration),
        "-r",
        "30",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
    ]
    if audio_path:
        inputs += ["-stream_loop", "-1", "-i", str(audio_path)]
        output_args += [
            "-map", "1:a:0",
            "-c:a", "aac", "-b:a", "192k",
            "-af", _audio_master_filter(spec.duration),
        ]
    run_ffmpeg(inputs + output_args + [str(output)])


_XFADE_TRANSITIONS = [
    "fade",
    "dissolve",
    "smoothleft",
    "smoothright",
    "smoothup",
    "smoothdown",
    "circleopen",
    "circleclose",
    "radial",
    "diagtl",
    "diagbr",
]


def _build_multi_clip_short(
    spec: VideoSpec,
    videos: list[Path],
    audio_path: Path | None,
    output: Path,
    hook: str = "",
) -> None:
    """Gera um Short com 2-3 clipes e transicoes crossfade.

    Cada clipe e normalizado para o aspecto-alvo e concatenado com xfade.
    Um estilo de transicao (`_XFADE_TRANSITIONS`) e sorteado por video e
    aplicado a todos os cortes dele - consistente dentro do video, variado
    entre videos, em vez de sempre "fade". A musica de jazz toca por toda a
    duracao total.
    """
    # O conjunto recebido ja foi escolhido e reservado pelo ledger. Nao
    # reamostrar aqui: isso reservaria clipes que nao entram na producao.
    selected = list(videos)
    n_clips = len(selected)
    per_clip = spec.duration // n_clips

    # Valida que cada clipe e longo o suficiente para o xfade cobrir sem
    # produzir frames pretos ou erros do FFmpeg. Se per_clip for muito
    # curto (clipe termina antes do offset do xfade), reduz n_clips.
    xfade_duration = 0.5
    while n_clips > 1 and per_clip <= xfade_duration * (n_clips - 1):
        n_clips -= 1
        selected = selected[:n_clips]
        per_clip = spec.duration // n_clips

    # #9: Cache de segmentos FFmpeg reusaveis. Normaliza o clipe (crop+
    # scale+pad para o aspecto-alvo) UMA VEZ e guarda em _assets/normalized/.
    # Geracoes futuras pulam o crop/scale caro e so cortam o trecho com -t
    # (operacao barata - sem re-encode, so demux+copia). Reduz ~40% do tempo
    # de render porque o crop/scale e a parte mais cara do FFmpeg aqui.
    processed: list[Path] = []
    try:
        for i, v in enumerate(selected):
            proc = output.parent / f"{output.stem}_clip_{i}.mp4"
            cached = _get_or_cache_normalized(v, spec)
            if cached is not None:
                # Clipe ja normalizado - so cortar a duracao necessaria (rapido:
                # stream copy sem re-encode).
                run_ffmpeg(
                    ["-i", str(cached), "-t", str(per_clip), "-c", "copy", "-an", str(proc)]
                )
            else:
                # Fallback: normaliza do zero (sem cache ou cache falhou)
                run_ffmpeg(
                    [
                        "-i",
                        str(v),
                        "-vf",
                        _build_video_filter(spec),
                        "-c:v",
                        "libx264",
                        "-preset",
                        "fast",
                        "-crf",
                        "23",
                        "-t",
                        str(per_clip),
                        "-r",
                        "30",
                        "-pix_fmt",
                        "yuv420p",
                        "-an",
                        str(proc),
                    ]
                )
            processed.append(proc)

        # Monta filter complex com xfade
        if n_clips == 1:
            run_ffmpeg(["-i", str(processed[0]), "-c", "copy", str(output)])
            return

        transition = random.choice(_XFADE_TRANSITIONS)
        filter_parts: list[str] = []
        offsets: list[float] = []

        prev_label = "0:v"
        for i in range(1, n_clips):
            offset = per_clip * i - xfade_duration * i
            offsets.append(offset)
            out_label = f"v{i}"
            filter_parts.append(
                f"[{prev_label}][{i}:v]xfade=transition={transition}:duration={xfade_duration}:offset={offset}[{out_label}]"
            )
            prev_label = out_label

        # Adiciona overlay de texto (hook) no resultado do xfade
        if hook:
            overlay_label = "vtxt"
            filter_parts.append(f"[{prev_label}]{_build_overlay_filter(hook, spec.height)}[{overlay_label}]")
            prev_label = overlay_label

        # End-card CTA no fim do vídeo (session/loop)
        if spec.duration > _ENDCARD_SECONDS:
            endcard_label = "vend"
            filter_parts.append(
            f"[{prev_label}]{_build_endcard_filter(spec.height, spec.duration, mood=spec.mood)}[{endcard_label}]"
        )
            prev_label = endcard_label

        inputs: list[str] = []
        for p in processed:
            inputs += ["-i", str(p)]

        # Input de audio deve vir ANTES das opcoes de output (FFmpeg exige que
        # opcoes de input como -stream_loop precedam -i, e todas as opcoes de
        # input venham antes das de output).
        if audio_path:
            inputs += ["-stream_loop", "-1", "-i", str(audio_path)]

        final_label = prev_label
        cmd_args = inputs + [
            "-filter_complex",
            ";".join(filter_parts),
            "-map",
            f"[{final_label}]",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            "-r",
            "30",
            "-movflags",
            "+faststart",
        ]

        if audio_path:
            # Indice do audio = numero de clipes processados (videos 0..n-1, audio n).
            cmd_args += [
                "-map", f"{n_clips}:a:0", "-c:a", "aac", "-b:a", "192k",
                "-af", _audio_master_filter(spec.duration),
            ]

        # -t sempre aplicado (nao so quando ha audio): sem ele, a duracao do
        # xfade final e sum(per_clip) - (n_clips-1)*xfade_duration, que fica
        # abaixo de spec.duration por causa do truncamento inteiro de per_clip -
        # o suficiente para estourar TOLERANCE_SECONDS na validacao (video_validator).
        cmd_args += ["-t", str(spec.duration)]

        cmd_args += [str(output)]
        log.info("Transicao xfade escolhida: %s (%d clipes)", transition, n_clips)
        run_ffmpeg(cmd_args)
    finally:
        # Limpa arquivos temporarios (sempre, mesmo em falha)
        for p in processed:
            p.unlink(missing_ok=True)


def _build_loop_relax_video(
    spec: VideoSpec,
    videos: list[Path],
    audio_path: Path | None,
    output: Path,
    hook: str = "",
) -> None:
    """Gera long-form horizontal "Loop & Relax": 2-3 clipes em loop com
    crossfade lento + jazz + hook no inicio + end-card no fim.

    Para evitar incompatibilidade entre -stream_loop e xfade no FFmpeg,
    cada segmento e pre-renderizado com loop ate cobrir sua fatia da
    duracao total. Preset ultrafast/CRF 30 nesses segmentos reduz o
    tempo de re-encode; o encode final usa veryfast/CRF 28 para qualidade
    suficiente no YouTube.
    """
    selected = list(videos)
    n_clips = len(selected)
    xfade_duration = 2.0
    per_clip = spec.duration // n_clips
    while n_clips > 1 and per_clip <= xfade_duration * (n_clips - 1):
        n_clips -= 1
        selected = selected[:n_clips]
        per_clip = spec.duration // n_clips

    transition = random.choice(_XFADE_TRANSITIONS)
    base_vf = _build_video_filter(spec)

    processed: list[Path] = []
    try:
        for i, v in enumerate(selected):
            proc = output.parent / f"{output.stem}_clip_{i}.mp4"
            run_ffmpeg(
                [
                    "-stream_loop",
                    "-1",
                    "-i",
                    str(v),
                    "-vf",
                    f"{base_vf},setpts=PTS-STARTPTS",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "ultrafast",
                    "-crf",
                    "30",
                    "-t",
                    str(per_clip),
                    "-r",
                    "30",
                    "-pix_fmt",
                    "yuv420p",
                    "-an",
                    str(proc),
                ]
            )
            processed.append(proc)

        if n_clips == 1:
            run_ffmpeg(["-i", str(processed[0]), "-c", "copy", str(output)])
            return

        filter_parts: list[str] = []
        prev_label = "0:v"
        for i in range(1, n_clips):
            offset = per_clip * i - xfade_duration * i
            out_label = f"v{i}"
            filter_parts.append(
                f"[{prev_label}][{i}:v]xfade=transition={transition}:duration={xfade_duration}:offset={offset}[{out_label}]"
            )
            prev_label = out_label

        if hook:
            overlay_label = "vtxt"
            filter_parts.append(f"[{prev_label}]{_build_overlay_filter(hook, spec.height)}[{overlay_label}]")
            prev_label = overlay_label

        if spec.duration > _ENDCARD_SECONDS:
            endcard_label = "vend"
            filter_parts.append(
            f"[{prev_label}]{_build_endcard_filter(spec.height, spec.duration, mood=spec.mood)}[{endcard_label}]"
        )
            prev_label = endcard_label

        inputs: list[str] = []
        for p in processed:
            inputs += ["-i", str(p)]
        if audio_path:
            inputs += ["-stream_loop", "-1", "-i", str(audio_path)]

        cmd_args = inputs + [
            "-filter_complex",
            ";".join(filter_parts),
            "-map",
            f"[{prev_label}]",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "28",
            "-pix_fmt",
            "yuv420p",
            "-r",
            "30",
            "-movflags",
            "+faststart",
        ]
        if audio_path:
            cmd_args += [
                "-map", f"{n_clips}:a:0", "-c:a", "aac", "-b:a", "192k",
                "-af", _audio_master_filter(spec.duration),
            ]
        cmd_args += ["-t", str(spec.duration), str(output)]

        log.info(
            "Long-form: transicao=%s, clips=%d, per_clip=%ds, duracao=%ds",
            transition,
            n_clips,
            per_clip,
            spec.duration,
        )
        run_ffmpeg(cmd_args)
    finally:
        for p in processed:
            p.unlink(missing_ok=True)


def build_pata_jazz_video(
    spec: VideoSpec,
    output_dir: Path,
    thumb_dir: Path,
    stem_prefix: str,
    dry_run: bool = False,
    *,
    _selected_audio: Path | None = None,
    _selected_videos: list[Path] | None = None,
    _fixed_scene: str = "",
    _fixed_hook: str = "",
    _fixed_emoji: str = "",
    _fixed_output: Path | None = None,
    _fixed_thumb: Path | None = None,
    _reservation: dict | None = None,
) -> Path:
    """Pipeline comum de geração de vídeo Pata Jazz.

    Shorts usam 2-3 clipes com crossfade; long-form (Loop & Relax) usa os
    mesmos clipes em loop cobrindo segmentos longos com crossfade lento.
    Retorna o caminho do vídeo gerado.

    Em modo ``dry_run`` não executa FFmpeg nem gera arquivos: apenas seleciona
    assets, imprime o spec e retorna um path fake (não-existente).
    """
    ensure_dirs()
    _validate_source_pools()

    scene = _fixed_scene or (spec.scene if spec.scene else random_scene())
    # A7: gera 2 candidatos de hook e escolhe o de maior qualidade (tamanho
    # ideal + keywords de alto volume) em vez de sortear 1 so.
    hook, emoji = (
        (_fixed_hook, _fixed_emoji) if _fixed_hook else best_hook_for_scene(scene, mood=spec.mood)
    )
    audio_path = _selected_audio if _selected_audio is not None else pick_audio(mood=spec.mood)
    if audio_path is None:
        raise RuntimeError("Nenhuma faixa de jazz compatível foi encontrada para o mood selecionado.")
    # Deriva o animal do scene para o b-roll bater com o hook/titulo - sem
    # isso pick_videos() escolhia do pool inteiro (gato OU cachorro) sem
    # olhar pra cena, entao um titulo "gatinho dormindo" podia sair com
    # clipes de cachorro no video.
    animal = detect_animal(scene)

    if _fixed_output is not None and _fixed_thumb is not None:
        output, thumb = _fixed_output, _fixed_thumb
    else:
        output, thumb, _ = _prepare_output_paths(stem_prefix, output_dir, thumb_dir)

    if dry_run:
        log.info("[DRY-RUN] kind=%s scene=%s hook=%s emoji=%s audio=%s", spec.kind, scene, hook, emoji, audio_path)
        log.info("[DRY-RUN] seria gravado em %s (thumbnail %s)", output, thumb)
        log.info("[DRY-RUN] resolução=%dx%d duração=%ds", spec.width, spec.height, spec.duration)
        return output

    # A chamada externa escolhe o conjunto exato e o reserva atomicamente.
    # A chamada interna recebe esses assets fixados, executa todo o pipeline e
    # so entao a externa confirma o ledger. Falhas liberam a reserva; falha ao
    # confirmar mantem a reserva pendente e portanto falha de forma segura.
    if _selected_videos is None:
        selected = pick_videos(min_count=2, max_count=3, cuteness_sort=True, animal=animal)
        if len(selected) < 2:
            selected = pick_videos(min_count=1, max_count=1, cuteness_sort=True, animal=animal)
        if not selected:
            raise RuntimeError("Pool de b-roll inedito insuficiente para gerar o video.")
        reservation_id, reservation = reserve_media(audio_path, selected)
        try:
            result = build_pata_jazz_video(
                spec=spec,
                output_dir=output_dir,
                thumb_dir=thumb_dir,
                stem_prefix=stem_prefix,
                dry_run=False,
                _selected_audio=audio_path,
                _selected_videos=selected,
                _fixed_scene=scene,
                _fixed_hook=hook,
                _fixed_emoji=emoji,
                _fixed_output=output,
                _fixed_thumb=thumb,
                _reservation=reservation,
            )
        except Exception:
            release_reservation(reservation_id)
            raise
        committed = commit_reservation(reservation_id, result)
        try:
            meta_path = result.with_suffix(".json")
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta["media_usage"] = {
                "reservation_id": reservation_id,
                "signature": committed["signature"],
                "audio": committed["audio"],
                "video": committed["video"],
            }
            meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        except (OSError, ValueError, TypeError) as exc:
            log.warning("Video validado, mas metadata do ledger nao foi anexada: %s", exc)
        return result

    videos = _selected_videos
    # Multi-clip com crossfade para Shorts / long-form Loop & Relax
    if len(videos) >= 2:
        if spec.kind == "long":
            _build_loop_relax_video(spec, videos, audio_path, output, hook=hook)
        else:
            _build_multi_clip_short(spec, videos, audio_path, output, hook=hook)
    else:
        # Um unico clipe inedito pode ser usado em loop, sem recorrer ao pool
        # novamente (o conjunto exato ja esta coberto pela reserva).
        video = videos[0]
        _build_single_clip_video(spec, video, audio_path, output, hook=hook)

    # A/B/C testing: gera tres variantes de thumbnail. thumb e o caminho base
    # ({stem}.png); as variantes sao {stem}_thumb_a.png, {stem}_thumb_b.png e
    # {stem}_thumb_c.png.
    thumb_a = thumb.with_name(f"{thumb.stem}_thumb_a.png")
    thumb_b = thumb.with_name(f"{thumb.stem}_thumb_b.png")
    thumb_c = thumb.with_name(f"{thumb.stem}_thumb_c.png")
    rendered: dict[str, Path] = {}
    spec.thumbnail_maker(hook, emoji, thumb_a, video_path=output, variant="A")
    rendered["A"] = thumb_a
    for variant, thumb_path in (("B", thumb_b), ("C", thumb_c)):
        try:
            spec.thumbnail_maker(hook, emoji, thumb_path, video_path=output, variant=variant)
            rendered[variant] = thumb_path
        except Exception as exc:
            # Variantes B e C sao opcionais - se falhar, A ainda e suficiente.
            log.warning("Falha ao gerar variante %s de thumbnail: %s", variant, exc)
    generated = [str(p) for p in rendered.values()]

    # Feedback loop: comeca a variante PRIMARIA (a efetivamente enviada ao
    # YouTube) a partir da que historicamente teve mais views
    # (winning_thumbnail_variant, calculado por scripts/collect_analytics.py
    # a partir de video_tags.json + analytics.json), em vez de sempre "A".
    # Fecha o loop entre o sinal de performance e o proximo upload, sem
    # esperar os _THUMBNAIL_ROTATION_DAYS da rotacao reativa
    # (collect_analytics.maybe_rotate_thumbnail). B e C continuam sendo
    # geradas do mesmo jeito - so a que vai pro ar primeiro muda.
    primary_variant = winning_thumbnail_variant()
    if primary_variant not in rendered:
        primary_variant = "A"
    thumb_primary = rendered[primary_variant]

    fallback_title = clean_title(f"{hook} | {active_channel.name}")
    story_card = choose_story_card(scene, spec.mood, hook)
    metadata = generate_metadata(
        hook=hook,
        scene=scene,
        duration=spec.duration,
        kind=spec.kind,  # type: ignore[arg-type]
        emoji=emoji,
        fallback_title=fallback_title,
        fallback_description=spec.fallback_description,
        title_pattern_hint=spec.title_pattern_hint,
        mood=spec.mood,
        lang=spec.lang,
    )
    description = str(metadata.get("description", "")).rstrip()
    community_prompt = story_card["community_prompt"]
    metadata["description"] = f"{description}\n\n{community_prompt}" if description else community_prompt
    attribution = music_attribution(audio_path)
    if attribution:
        description = str(metadata.get("description", "")).rstrip()
        metadata["description"] = f"{description}\n\n{attribution}" if description else attribution
        metadata["music_attribution"] = attribution
    meta = {
        **metadata,
        "scene": scene,
        "hook": hook,
        "kind": spec.kind,
        "mood": spec.mood,
        "lang": spec.lang,
        "duration": spec.duration,
        "resolution": f"{spec.width}x{spec.height}",
        "video": str(output),
        "thumbnail": str(thumb_primary),
        "thumbnail_variant": primary_variant,
        "thumbnails": generated,
        "audio": str(audio_path) if audio_path else None,
        "media_reservation": _reservation or {},
        "editorial_brief": build_editorial_brief(
            scene=scene,
            mood=spec.mood,
            kind=spec.kind,
            duration=spec.duration,
            hook=hook,
        ),
        "format_strategy": format_strategy(kind=spec.kind, duration=spec.duration, mood=spec.mood, scene=scene),
        "story_card": story_card,
    }
    thumbnail_signals = analyze_image(thumb_primary)
    video_signals = analyze_video(output)
    meta["visual_intelligence"] = {
        "thumbnail": thumbnail_signals,
        "video": video_signals,
        "review_flags": creative_quality_flags(thumbnail_signals, video_signals),
    }
    meta["viewer_experience"] = assess_viewer_experience(
        title=str(meta.get("title", "")),
        description=str(meta.get("description", "")),
        story_card=story_card,
        visual=meta["visual_intelligence"],
    )
    output.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    # Gera legenda automatica ASS estilizada (animada palavra-a-palavra).
    try:
        cap_content = generate_ass(hook, scene, spec.duration, emoji)
        cap_path = save_ass(cap_content, output)
        meta["caption"] = str(cap_path)

        # 1.3 - Segunda caption track em PT-BR: multiplica alcance sem
        # regravar o video. YouTube aceita multiplas caption tracks.
        try:
            from utils.caption_engine import generate_srt_pt, save_srt_pt

            pt_content = generate_srt_pt(hook, scene, spec.duration, emoji)
            pt_path = save_srt_pt(pt_content, output)
            meta["caption_pt"] = str(pt_path)
        except Exception as exc:
            log.warning("Falha ao gerar legenda PT: %s", exc)

        # 1.2 - Chapters automaticos na descricao para SEO do YouTube.
        try:
            from utils.caption_engine import generate_chapters

            chapters = generate_chapters(spec.duration)
            if chapters:
                chapter_lines = [f"{ts} {title}" for ts, title in chapters]
                meta["chapters"] = "\n".join(chapter_lines)
                # Prepend chapters na descricao para o YouTube parsear.
                if meta.get("description"):
                    meta["description"] = meta["chapters"] + "\n\n" + meta["description"]
        except Exception as exc:
            log.warning("Falha ao gerar chapters: %s", exc)

        output.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        log.warning("Falha ao gerar legenda: %s", exc)

    # Anti-repeat: registra o titulo no historico assim que o metadata e
    # gravado - impede colisoes dentro do mesmo batch e em geracoes futuras.
    # Tambem serve de fonte para o gerador de longform nao repetir shorts.
    try:
        from utils.seo_keywords import record_used_title

        record_used_title(meta["title"])
    except Exception as exc:
        log.warning("Falha ao registrar titulo usado: %s", exc)
    validation = validate_generated_video(
        output, meta["resolution"], spec.duration, expect_audio=True
    )
    if not validation.ok:
        raise RuntimeError(f"Vídeo gerado não passou na validação: {'; '.join(validation.errors)}")
    record_story_card(story_card)
    log.info("%s gerado e validado: %s", spec.kind.capitalize(), output)
    return output


def short_spec(
    duration: int = 35, scene: str = "", mood: str = "", title_pattern_hint: str = "", lang: str = "en"
) -> VideoSpec:
    """Especificação padrão para Shorts verticais 1080x1920."""
    return VideoSpec(
        kind="short",
        width=1080,
        height=1920,
        duration=duration,
        default_duration=35,
        crop_filter="crop='ih*9/16:ih:(iw-ih*9/16)/2:0'",
        thumbnail_maker=make_short_thumbnail,
        fallback_description=f"{hook_for_scene(scene or random_scene())[0]} with jazz playing. 🐾🎷 #PataJazz",
        scene=scene,
        mood=mood,
        title_pattern_hint=title_pattern_hint,
        lang=lang,
    )


def long_spec(
    duration: int = 600, scene: str = "", mood: str = "", title_pattern_hint: str = "", lang: str = "en"
) -> VideoSpec:
    """Especificação padrão para long-form horizontal 16:9 (Loop & Relax).

    Default de 10 minutos (600s) - longos demais encarecem o render do
    FFmpeg em CI; o intervalo aceito vai de 600s a 2700s (45min).
    """
    if not 600 <= duration <= 2700:
        raise ValueError("Duracao de long-form deve estar entre 600s (10min) e 2700s (45min).")
    return VideoSpec(
        kind="long",
        width=1920,
        height=1080,
        duration=duration,
        default_duration=600,
        crop_filter="crop='ih*16/9:ih:(iw-ih*16/9)/2:0'",
        thumbnail_maker=make_long_thumbnail,
        fallback_description=f"{hook_for_scene(scene or random_scene())[0]} relaxing with jazz. 🐾🎷 #PataJazz",
        scene=scene,
        mood=mood,
        title_pattern_hint=title_pattern_hint,
        lang=lang,
    )


def inspect_video(path: Path) -> dict:
    """Retorna informações básicas de um vídeo via ffprobe.

    Inclui duração, largura, altura, bitrate, codec de vídeo e de áudio.
    """
    info: dict = {"path": str(path), "duration": get_video_duration(str(path))}
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "stream=codec_name,codec_type,width,height,bit_rate",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        data = json.loads(result.stdout)
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video":
                info["video_codec"] = stream.get("codec_name")
                info["width"] = stream.get("width")
                info["height"] = stream.get("height")
                info["video_bit_rate"] = stream.get("bit_rate")
            elif stream.get("codec_type") == "audio":
                info["audio_codec"] = stream.get("codec_name")
                info["audio_bit_rate"] = stream.get("bit_rate")
    except Exception as exc:
        log.warning("Não foi possível inspecionar %s: %s", path, exc)
    return info
