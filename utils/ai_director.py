"""
utils/ai_director.py — AI Director + Vision Quality Gate.

Parte 1: planeja o arco narrativo do video inteiro via Gemini (texto).
Parte 2: quality gate inteligente que avalia frames via Gemini Vision.

Acoplado a utils.ai_helper (chamadas Gemini), utils.liquid_wire_timeline
(modelo de eventos), e utils.paths (data_dir para persistencia de historico
de qualidade). Todos os prompts sao em ingles para o Gemini.
"""

from __future__ import annotations

import json
import logging
import os
import random
import subprocess
from pathlib import Path

from utils.ai_helper import ai_text, ai_text_with_image
from utils.liquid_wire_timeline import (  # noqa: F401 (imports requested by module spec)
    CreativeEvent,
    build_timeline,
    visual_state,
)
from utils.paths import data_dir

log = logging.getLogger(__name__)

# Limite de frames enviados ao Gemini Vision por quality gate — custa quota,
# entao mantemos baixo. 3-5 e suficiente para uma leitura artistica sem
# estourar o rate limit nem a janela de contexto do modelo multimodal.
_QG_MAX_FRAMES = 5
_QG_MIN_FRAMES = 3
_QG_FRAME_FORMAT = "png"
_QG_FRAME_TIMEOUT = 30

# Janelas de intensidade/direcao validas. Fora disso, recortamos para o
# intervalo [0,1] / [-pi, pi] em vez de descartar o evento — o plano do
# Gemini e uma sugestao, nao uma especificacao rigida.
_INTENSITY_MIN = 0.0
_INTENSITY_MAX = 1.0
_DIRECTION_MIN = -3.141592653589793
_DIRECTION_MAX = 3.141592653589793

# Generos de pacing aceitos pelo plano — qualquer outro valor e normalizado
# para "moderate" no caller (nao aqui; aqui apenas validamos tipos).
_VALID_PACING = ("slow_burn", "moderate", "energetic", "hypnotic")
_VALID_EVENT_KINDS = ("bloom", "compression", "rupture", "tide", "stillness")
_VALID_CAMERA_MOVEMENTS = ("orbit", "dolly", "tilt", "shake")
_VALID_EMPHASIS_ELEMENTS = ("color", "motion", "density")


def _channel_context() -> str:
    """Contexto do canal para o prompt do Director.

    Best-effort: se channel_config nao estiver disponivel (import circular
    raro), usa um contexto generico. Mantemos o import dentro da funcao para
    evitar dependencia circular em testes que monkeypatcheai ai_helper.
    """
    try:
        from utils.channel_config import active_channel

        return (
            f"You are directing a video for the YouTube channel "
            f"'{active_channel.name}'. Channel description: "
            f"{active_channel.default_description} The channel publishes "
            f"slow generative visuals with procedural ambient music — no "
            f"stock footage, no narration, no on-screen text. Visuals are "
            f"abstract wireframe/liquid meshes rendered in real time."
        )
    except Exception:  # pragma: no cover — fallback defensivo
        return (
            "You are directing a slow generative art video for a YouTube "
            "channel that publishes abstract procedural visuals with ambient "
            "music. No narration, no stock footage."
        )


def _director_prompt(seed: int, duration: float, genre_name: str, family: str) -> str:
    """Constroi o prompt do Gemini para planejar o arco narrativo.

    O prompt descreve os 5 tipos de eventos e como cada um afeta visuais e
    audio, para que o plano do Gemini faca sentido com o resto do pipeline.
    Tudo em ingles, pedindo JSON valido.
    """
    return (
        f"{_channel_context()}\n\n"
        f"Plan the narrative arc for a {duration:.1f}-second generative art "
        f"video.\n"
        f"Visual family: {family} (one of 42 procedural object families — "
        f"orb, torus, ribbon, helix, gyroid, mandelbulb, flow_field, "
        f"nebula_cloud, etc.).\n"
        f"Musical genre: {genre_name} (procedural ambient soundtrack).\n"
        f"Seed: {seed} (for reference; the timeline is deterministic given "
        f"this seed, but you should design around it, not encode it).\n\n"
        f"The video is driven by timed 'creative events' that shape both "
        f"visuals and audio in real time. There are exactly 5 event kinds:\n"
        f"- 'bloom': expansion, growth, opening up — visuals scale up and "
        f"audio gets brighter/louder.\n"
        f"- 'compression': contraction, density, pressure — visuals scale "
        f"down and audio gets darker/tenser.\n"
        f"- 'rupture': sudden break, discontinuity — a visual glitch or "
        f"flash and an audio spike or texture change.\n"
        f"- 'tide': slow ebb and flow, continuous motion — sustained visual "
        f"drift and audio swells.\n"
        f"- 'stillness': rest, low motion, near-silence — visuals settle "
        f"and audio drops to a whisper or texture bed.\n\n"
        f"Each event has a start time, duration, intensity (0.0 to 1.0), "
        f"and direction (radians, -pi to pi). Plan 4 to 9 events spread "
        f"across the full duration so the arc feels intentional, not "
        f"random. Avoid clustering every event at the climax — the pacing "
        f"should breathe.\n\n"
        f"Also suggest camera movements and visual emphasis moments that "
        f"complement (not fight) the event timeline.\n\n"
        f"Return ONLY valid JSON (no markdown, no prose before or after) "
        f"with this exact shape:\n"
        f"{{\n"
        f"  \"narrative_arc\": \"<one sentence describing the emotional arc, "
        f"e.g. 'calm opening -> building tension -> dramatic climax -> "
        f"peaceful resolution'>\",\n"
        f"  \"events\": [\n"
        f"    {{\"kind\": \"bloom|compression|rupture|tide|stillness\", "
        f"\"start_fraction\": 0.0, \"duration_fraction\": 0.0, "
        f"\"intensity\": 0.0, \"direction\": 0.0}}\n"
        f"  ],\n"
        f"  \"camera_suggestions\": [\n"
        f"    {{\"start_fraction\": 0.0, \"movement\": \"orbit|dolly|tilt|"
        f"shake\", \"intensity\": 0.0}}\n"
        f"  ],\n"
        f"  \"visual_emphasis\": [\n"
        f"    {{\"start_fraction\": 0.0, \"element\": \"color|motion|density"
        f"\", \"intensity\": 0.0}}\n"
        f"  ],\n"
        f"  \"pacing\": \"slow_burn|moderate|energetic|hypnotic\"\n"
        f"}}\n\n"
        f"start_fraction and duration_fraction are in [0, 1] relative to "
        f"the total video duration. intensity is in [0, 1]. direction is "
        f"in radians [-pi, pi]. Aim for 4-9 events, 2-4 camera suggestions, "
        f"1-3 visual emphasis moments. Make the plan specific to this "
        f"visual family and genre — not a generic template."
    )


def _clamp(value: float, low: float, high: float) -> float:
    """Recorta um valor para [low, high]. Nunca levanta."""
    try:
        return float(max(low, min(high, float(value))))
    except (TypeError, ValueError):
        return low


def _validate_plan_shape(plan: object) -> dict | None:
    """Garante que o dict retornado pelo Gemini tem a forma esperada.

    Retorna o dict normalizado ou None se a forma for inaceitavel (nao e
    dict, falta narrative_arc, events nao e lista, etc.). Campos opcionais
    (camera_suggestions, visual_emphasis, pacing) ganham defaults seguros.
    """
    if not isinstance(plan, dict):
        return None
    if not isinstance(plan.get("narrative_arc"), str) or not plan["narrative_arc"]:
        return None
    events = plan.get("events")
    if not isinstance(events, list) or not events:
        return None
    normalized: dict = {
        "narrative_arc": str(plan["narrative_arc"]).strip(),
        "events": [],
        "camera_suggestions": [],
        "visual_emphasis": [],
        "pacing": "moderate",
    }
    for event in events:
        if not isinstance(event, dict):
            continue
        kind = str(event.get("kind", "")).strip()
        if kind not in _VALID_EVENT_KINDS:
            continue
        try:
            start_frac = float(event.get("start_fraction", -1.0))
            dur_frac = float(event.get("duration_fraction", -1.0))
        except (TypeError, ValueError):
            continue
        if not (0.0 <= start_frac <= 1.0) or not (0.0 < dur_frac <= 1.0):
            continue
        normalized["events"].append(
            {
                "kind": kind,
                "start_fraction": start_frac,
                "duration_fraction": dur_frac,
                "intensity": _clamp(event.get("intensity", 0.5), _INTENSITY_MIN, _INTENSITY_MAX),
                "direction": _clamp(
                    event.get("direction", 0.0), _DIRECTION_MIN, _DIRECTION_MAX
                ),
            }
        )
    if not normalized["events"]:
        return None
    cameras = plan.get("camera_suggestions")
    if isinstance(cameras, list):
        for cam in cameras:
            if not isinstance(cam, dict):
                continue
            try:
                start_frac = float(cam.get("start_fraction", -1.0))
            except (TypeError, ValueError):
                continue
            if not (0.0 <= start_frac <= 1.0):
                continue
            movement = str(cam.get("movement", "")).strip()
            if movement not in _VALID_CAMERA_MOVEMENTS:
                continue
            normalized["camera_suggestions"].append(
                {
                    "start_fraction": start_frac,
                    "movement": movement,
                    "intensity": _clamp(cam.get("intensity", 0.5), _INTENSITY_MIN, _INTENSITY_MAX),
                }
            )
    emphasis = plan.get("visual_emphasis")
    if isinstance(emphasis, list):
        for emp in emphasis:
            if not isinstance(emp, dict):
                continue
            try:
                start_frac = float(emp.get("start_fraction", -1.0))
            except (TypeError, ValueError):
                continue
            if not (0.0 <= start_frac <= 1.0):
                continue
            element = str(emp.get("element", "")).strip()
            if element not in _VALID_EMPHASIS_ELEMENTS:
                continue
            normalized["visual_emphasis"].append(
                {
                    "start_fraction": start_frac,
                    "element": element,
                    "intensity": _clamp(emp.get("intensity", 0.5), _INTENSITY_MIN, _INTENSITY_MAX),
                }
            )
    pacing = str(plan.get("pacing", "")).strip()
    normalized["pacing"] = pacing if pacing in _VALID_PACING else "moderate"
    return normalized


def ai_plan_narrative(seed: int, duration: float, genre_name: str, family: str) -> dict | None:
    """Pede ao Gemini um plano narrativo para o video inteiro.

    Retorna um dict normalizado (com events validos) ou None se a chamada
    falhar, o JSON for invalido, ou a forma nao bater. Nunca levanta.
    """
    if not os.environ.get("GEMINI_API_KEY"):
        log.info("ai_plan_narrative: GEMINI_API_KEY ausente — pulando Director.")
        return None
    prompt = _director_prompt(seed, duration, genre_name, family)
    raw = ai_text(prompt, json_mode=True, task="ai_director_plan", timeout=45)
    if not raw:
        log.warning("ai_plan_narrative: Gemini retornou vazio — fallback.")
        return None
    try:
        plan = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        log.warning("ai_plan_narrative: JSON invalido (%s) — fallback.", exc)
        return None
    normalized = _validate_plan_shape(plan)
    if normalized is None:
        log.warning("ai_plan_narrative: plano invalido apos normalizacao — fallback.")
        return None
    log.info(
        "ai_plan_narrative: plano ok (%d eventos, pacing=%s)",
        len(normalized["events"]),
        normalized["pacing"],
    )
    return normalized


def build_ai_timeline(duration: float, ai_plan: dict | None) -> list[CreativeEvent]:
    """Converte o plano do Gemini em uma lista de CreativeEvent.

    Se ai_plan for None, retorna [] (o chamador deve cair para build_timeline
    normal). Mapeia start_fraction/duration_fraction para segundos e valida
    intensity/direction. pitch_offset e derivado deterministicamente do
    indice do evento — o plano do Gemini nao o inclui porque e um detalhe
    musical interno, nao algo que o modelo deveria escolher.
    """
    if not ai_plan:
        return []
    events: list[CreativeEvent] = []
    pitch_choices = (-12, -7, -5, 5, 7, 12)
    for index, event in enumerate(ai_plan.get("events", [])):
        try:
            start = float(event["start_fraction"]) * duration
            ev_duration = float(event["duration_fraction"]) * duration
            intensity = _clamp(event.get("intensity", 0.5), _INTENSITY_MIN, _INTENSITY_MAX)
            direction = _clamp(
                event.get("direction", 0.0), _DIRECTION_MIN, _DIRECTION_MAX
            )
        except (KeyError, TypeError, ValueError):
            continue
        start = max(0.25, min(duration - 0.5, start))
        ev_duration = max(0.5, min(duration, ev_duration))
        pitch_offset = pitch_choices[index % len(pitch_choices)]
        events.append(
            CreativeEvent(
                kind=str(event["kind"]),
                start=start,
                duration=ev_duration,
                intensity=intensity,
                direction=direction,
                pitch_offset=pitch_offset,
            )
        )
    return events


def ai_direct(
    seed: int, duration: float, genre_name: str, family: str
) -> tuple[list[CreativeEvent], dict]:
    """Entry point do AI Director.

    Tenta planejar o arco narrativo via Gemini e converter em CreativeEvents.
    Retorna (events, ai_plan) — events pode ser [] se o Director falhar ou
    retornar um plano invalido; ai_plan pode ser {} se nada deu certo. O
    chamador deve tratar events vazio como sinal para cair em build_timeline.
    """
    plan = ai_plan_narrative(seed, duration, genre_name, family)
    if plan is None:
        log.info("ai_direct: usando build_timeline legado (Gemini indisponivel).")
        return ([], {})
    events = build_ai_timeline(duration, plan)
    if not events:
        log.warning("ai_direct: plano recebido mas sem eventos validos — fallback.")
        return ([], {})
    log.info(
        "ai_direct: arco do Gemini aplicado (%d eventos, pacing=%s).",
        len(events),
        plan.get("pacing", "moderate"),
    )
    return (events, plan)


# ---------------------------------------------------------------------------
# PARTE 2 — Quality Gate inteligente via Gemini Vision
# ---------------------------------------------------------------------------


def _quality_prompt() -> str:
    """Prompt do Gemini Vision para avaliar um frame de arte generativa."""
    return (
        "You are evaluating a single frame from a generative art video "
        "(abstract procedural visuals, wireframe/liquid mesh, ambient "
        "music context). Rate this frame objectively on five dimensions. "
        "Be honest — a blank or muddy frame should score low; a frame with "
        "clear composition, harmonious color, and visual interest should "
        "score high. Do not invent dimensions beyond the five listed.\n\n"
        "Return ONLY valid JSON (no markdown, no prose) with this exact "
        "shape:\n"
        "{\n"
        "  \"visual_interest\": 0.0,\n"
        "  \"composition_quality\": 0.0,\n"
        "  \"color_harmony\": 0.0,\n"
        "  \"motion_potential\": 0.0,\n"
        "  \"overall_appeal\": 0.0\n"
        "}\n\n"
        "Every score is a float in [0, 1]. visual_interest: how much there "
        "is to look at (not busy, but not empty). composition_quality: "
        "balance, focal point, use of frame. color_harmony: whether the "
        "palette feels intentional and pleasant. motion_potential: does the "
        "frame suggest movement or feel frozen/dead. overall_appeal: your "
        " holistic gut rating of the frame as a still image."
    )


def ai_quality_assessment(frame_path: Path, video_path: Path) -> dict | None:
    """Avalia um frame via Gemini Vision.

    Retorna um dict com os 5 scores (visual_interest, composition_quality,
    color_harmony, motion_potential, overall_appeal) ou None se a chamada
    falhar (key ausente, circuit breaker, imagem invalida, JSON invalido).
    Nunca levanta — o quality gate precisa ser best-effort.
    """
    if not os.environ.get("GEMINI_API_KEY"):
        log.info("ai_quality_assessment: GEMINI_API_KEY ausente — fallback.")
        return None
    if not frame_path.exists():
        log.warning("ai_quality_assessment: frame ausente: %s", frame_path)
        return None
    prompt = _quality_prompt()
    raw = ai_text_with_image(
        prompt,
        frame_path,
        task="ai_quality_gate",
        timeout=_QG_FRAME_TIMEOUT,
    )
    if not raw:
        log.warning("ai_quality_assessment: Gemini Vision retornou vazio.")
        return None
    try:
        scores = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        log.warning("ai_quality_assessment: JSON invalido (%s).", exc)
        return None
    if not isinstance(scores, dict):
        return None
    keys = (
        "visual_interest",
        "composition_quality",
        "color_harmony",
        "motion_potential",
        "overall_appeal",
    )
    normalized: dict[str, float] = {}
    for key in keys:
        normalized[key] = _clamp(scores.get(key, 0.0), 0.0, 1.0)
    log.info(
        "ai_quality_assessment: %s overall_appeal=%.2f",
        frame_path.name,
        normalized["overall_appeal"],
    )
    return normalized


def _sample_frames_from_video(
    video_path: Path, count: int, dest_dir: Path
) -> list[Path]:
    """Extrai `count` frames do video para `dest_dir` via ffmpeg.

    Usa seek para timestamps equidistantes (nao frame-perfeito, mas barato e
    sem dependencia de cv2). Retorna os caminhos dos frames gerados. Se
    ffmpeg falhar ou o video estiver ausente, retorna [].
    """
    if not video_path.exists():
        log.warning("_sample_frames_from_video: video ausente: %s", video_path)
        return []
    try:
        probe = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=True,
        )
        duration = float(probe.stdout.strip() or 0.0)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError, OSError) as exc:
        log.warning("_sample_frames_from_video: ffprobe falhou (%s).", exc)
        return []
    if duration <= 0.0:
        return []
    dest_dir.mkdir(parents=True, exist_ok=True)
    timestamps = [
        duration * (i + 1) / (count + 1) for i in range(count)
    ]
    frames: list[Path] = []
    for i, ts in enumerate(timestamps):
        out_path = dest_dir / f"qg_frame_{i:02d}.{_QG_FRAME_FORMAT}"
        cmd = [
            "ffmpeg",
            "-v",
            "error",
            "-ss",
            f"{ts:.3f}",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-y",
            str(out_path),
        ]
        try:
            subprocess.run(cmd, capture_output=True, timeout=20, check=True)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
            log.warning("_sample_frames_from_video: ffmpeg frame %d falhou (%s).", i, exc)
            continue
        if out_path.exists():
            frames.append(out_path)
    return frames


def ai_quality_gate(
    video_path: Path,
    frame_paths: list[Path] | None = None,
    min_score: float = 0.6,
) -> tuple[bool, dict]:
    """Quality gate inteligente via Gemini Vision.

    Amostra 3-5 frames do video (de `frame_paths` se fornecido, ou extraidos
    via ffmpeg), envia cada um ao Gemini Vision, e faz a media dos scores.
    Retorna (passed, report):
    - passed=True se a media de overall_appeal >= min_score.
    - Se o Gemini falhar (None em todos os frames), retorna
      (True, {"fallback": True}) — o gate nunca bloqueia sozinho, ele so
      derruba videos que o Gemini explicitamente avaliou como fracos.
    - report inclui scores por frame, medias, e o min_score usado.
    """
    frames = list(frame_paths) if frame_paths else []
    if not frames:
        frames = _sample_frames_from_video(
            video_path, _QG_MAX_FRAMES, data_dir() / "_qg_frames"
        )
    if not frames:
        log.warning("ai_quality_gate: sem frames para avaliar — fallback.")
        return (True, {"fallback": True})
    # Se vieram mais que o maximo, amostra aleatoriamente (sem reposicao)
    # para evitar enviar 30 frames e estourar a quota.
    if len(frames) > _QG_MAX_FRAMES:
        rng = random.Random(42)
        frames = rng.sample(frames, _QG_MAX_FRAMES)
    # Se vieram menos que o minimo, segue mesmo — melhor avaliar com 1 frame
    # do que abortar, desde que o Gemini esteja respondendo.
    per_frame: list[dict] = []
    assessments: list[dict] = []
    for frame in frames:
        scores = ai_quality_assessment(frame, video_path)
        if scores is None:
            per_frame.append({"frame": str(frame), "failed": True})
            continue
        per_frame.append({"frame": str(frame), "scores": scores})
        assessments.append(scores)
    if not assessments:
        log.warning("ai_quality_gate: Gemini falhou em todos os frames — fallback.")
        return (True, {"fallback": True, "frames": per_frame})
    keys = (
        "visual_interest",
        "composition_quality",
        "color_harmony",
        "motion_potential",
        "overall_appeal",
    )
    averages: dict[str, float] = {}
    for key in keys:
        values = [a[key] for a in assessments if key in a]
        averages[key] = sum(values) / len(values) if values else 0.0
    overall = averages["overall_appeal"]
    passed = overall >= min_score
    report: dict = {
        "min_score": min_score,
        "overall_appeal": overall,
        "averages": averages,
        "frames": per_frame,
        "sampled": len(assessments),
    }
    log.info(
        "ai_quality_gate: overall=%.3f (min=%.3f) -> %s",
        overall,
        min_score,
        "PASS" if passed else "FAIL",
    )
    return (passed, report)
