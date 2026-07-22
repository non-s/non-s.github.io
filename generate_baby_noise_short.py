#!/usr/bin/env python3
"""Generate one vertical white/pink/brown-noise YouTube Short: a real,
calm Pixabay nursery/night clip looped under procedurally-synthesized
noise-color audio, no narration. Companion to
generate_baby_noise_ambience.py's long-form videos -- see that module's
docstring and utils/noise_audio.py's module docstring for the full
pillar reasoning.

Writes `_videos/noise-*.mp4` + matching `.json` that
upload_youtube.py's `_collect_pending_meta()` picks up (extended to
recognize the "noise-" prefix).
"""

from __future__ import annotations

import json
import logging
import random
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.ai_titling import generate_baby_noise_copy  # noqa: E402
from utils.baby_noise_branding import HOOK_BY_SCENE, branded_title, playlist_bucket_for_title  # noqa: E402
from utils.broll import pick_noise_broll_file  # noqa: E402
from utils.noise_audio import NOISE_COLORS, generate_noise_bed, write_wav  # noqa: E402

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("generate_baby_noise_short")

NOISE_BROLL_DIR = ROOT / "_assets" / "video" / "noise_broll"
VIDEOS_DIR = ROOT / "_videos"
TEMP_DIR = ROOT / "_videos" / "temp_baby_noise_short"

TARGET_W = 2160
TARGET_H = 3840
MIN_DURATION_S = 30.0
MAX_DURATION_S = 58.0
FADE_S = 1.5
LOOP_CROSSFADE_S = 1.0
NOISE_BED_SECONDS = 29.0  # short + non-matching period, same reasoning as generate_storm_short.py's identical constant

CATEGORY = "baby_noise_ambience"
SERIES_SUFFIX = "Shorts"
DEFAULT_TAGS = [
    "ruído branco",
    "ruído branco bebê",
    "ruído marrom",
    "ruído rosa",
    "som para bebê dormir",
    "ruído branco para dormir",
    "ruído branco para estudar",
    "amber hours",
]


def _load_sidecar(media_path: Path) -> dict:
    meta_path = media_path.with_suffix(".json")
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _pick_scene() -> str:
    return random.choice(list(HOOK_BY_SCENE.keys())).title()


def _pick_color() -> str:
    return random.choice(sorted(NOISE_COLORS))


def _media_duration_s(path: Path) -> float:
    cmd = ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def _prepare_seamless_loop_clip(clip_path: Path) -> Path:
    """Same technique as generate_baby_noise_ambience.py's identical helper."""
    out_path = TEMP_DIR / f"seamless_{clip_path.stem}.mp4"
    if out_path.exists() and out_path.stat().st_size > 0:
        return out_path

    duration = _media_duration_s(clip_path)
    fade = min(LOOP_CROSSFADE_S, duration / 6) if duration > 3 else 0.0
    if fade <= 0:
        return clip_path

    filter_complex = (
        f"[0:v]trim=0:{fade:.3f},setpts=PTS-STARTPTS[start];"
        f"[0:v]trim={duration - fade:.3f}:{duration:.3f},setpts=PTS-STARTPTS[end];"
        f"[0:v]trim={fade:.3f}:{duration - fade:.3f},setpts=PTS-STARTPTS[mid];"
        f"[end][start]xfade=transition=fade:duration={fade:.3f}:offset=0[blend];"
        "[mid][blend]concat=n=2:v=1:a=0[out]"
    )
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(clip_path),
        "-filter_complex",
        filter_complex,
        "-map",
        "[out]",
        "-an",
        "-pix_fmt",
        "yuv420p",
        "-preset",
        "veryfast",
        str(out_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except Exception as exc:
        log.warning("Failed to bake seamless loop clip, using raw clip instead: %s", exc)
        return clip_path
    if result.returncode != 0 or not out_path.exists() or out_path.stat().st_size == 0:
        log.warning("ffmpeg seamless-loop bake failed, using raw clip instead: %s", result.stderr[-500:])
        return clip_path
    log.info("Baked seamless loop clip from %s (crossfade=%.2fs).", clip_path.name, fade)
    return out_path


def _prepare_noise_bed(seed: int, color: str) -> Path:
    bed_path = TEMP_DIR / f"noise_bed_short_{color}_{seed}.wav"
    if bed_path.exists() and bed_path.stat().st_size > 0:
        return bed_path
    bed = generate_noise_bed(duration_s=NOISE_BED_SECONDS, seed=seed, color=color)
    write_wav(bed, bed_path)
    return bed_path


def _extract_thumbnail_frame(clip_path: Path, seed: int) -> Path | None:
    out_path = TEMP_DIR / f"thumb_{seed}.jpg"
    duration = _media_duration_s(clip_path)
    offset = min(2.0, max(duration / 3, 0.0))
    cmd = ["ffmpeg", "-y", "-i", str(clip_path), "-ss", f"{offset:.2f}", "-vframes", "1", str(out_path)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except Exception as exc:
        log.warning("Failed to extract thumbnail frame: %s", exc)
        return None
    if result.returncode != 0 or not out_path.exists() or out_path.stat().st_size == 0:
        log.warning("ffmpeg thumbnail-frame extraction failed: %s", result.stderr[-500:])
        return None
    return out_path


def _compose_short(broll_path: Path, noise_bed_path: Path, output_path: Path, duration_s: float) -> bool:
    fade_out_start = max(duration_s - FADE_S, 0.0)
    video_filter = (
        f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=increase,"
        f"crop={TARGET_W}:{TARGET_H},"
        f"setsar=1,fade=t=in:st=0:d={FADE_S},fade=t=out:st={fade_out_start:.3f}:d={FADE_S}[v]"
    )
    audio_filter = f"afade=t=in:st=0:d={FADE_S},afade=t=out:st={fade_out_start:.3f}:d={FADE_S}[a]"
    cmd = [
        "ffmpeg",
        "-y",
        "-stream_loop",
        "-1",
        "-i",
        str(broll_path),
        "-stream_loop",
        "-1",
        "-i",
        str(noise_bed_path),
        "-filter_complex",
        f"[0:v]{video_filter};[1:a]{audio_filter}",
        "-map",
        "[v]",
        "-map",
        "[a]",
        "-t",
        f"{duration_s:.3f}",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        "-ar",
        "44100",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except Exception as exc:
        log.error("ffmpeg failed to run: %s", exc)
        return False
    if result.returncode != 0:
        log.error("ffmpeg exited %d: %s", result.returncode, result.stderr[-2000:])
        return False
    return output_path.exists() and output_path.stat().st_size > 0


def _build_metadata(
    scene: str, color: str, duration_s: float, video_path: Path, slug: str, *, broll_meta: dict
) -> dict:
    template_title = branded_title(scene)
    bucket = playlist_bucket_for_title(template_title)

    color_label = {"white": "branco", "pink": "rosa", "brown": "marrom"}[color]
    disclosure = (
        f"O ruído {color_label} deste vídeo é sintetizado por computador, não uma gravação em loop "
        "-- nenhuma amostra para se esgotar, nenhuma licença para verificar."
    )
    description_lines = [
        f"Ruído {color_label} real -- uma pausa rápida de som constante para relaxar, focar ou acalmar.",
        "",
        f"\U0001f50a Parte da coleção {bucket} no Amber Hours.",
        "",
        f"\U0001f3a7 {disclosure}",
        "",
        "#Shorts",
    ]

    tags = [scene.lower()] if scene.lower() not in {tag.lower() for tag in DEFAULT_TAGS} else []
    tags += DEFAULT_TAGS

    title = template_title
    description = "\n".join(description_lines).strip()

    ai_copy = generate_baby_noise_copy(
        scene=scene,
        color=color,
        duration_s=duration_s,
        fallback_title=template_title,
    )
    if ai_copy:
        title = ai_copy["title"]
        description = f"{ai_copy['description']}\n\n{disclosure}\n\n#Shorts".strip()
        tags = ai_copy["hashtags"]
        if "amber hours" not in tags:
            tags.append("amber hours")

    return {
        "title": title,
        "description": description,
        "category": CATEGORY,
        "series": f"{bucket} {SERIES_SUFFIX}",
        "tags": tags,
        "video": str(video_path),
        "duration_s": duration_s,
        "story_id": slug,
        "packaging": {
            "pinned_comment": "Qual cor de ruído funciona melhor pra você: branco, rosa ou marrom? \U0001f50a"
        },
        "pre_publish_audit": {"approved": True, "reason": "baby_noise_no_claims_to_vet"},
        "source": str(broll_meta.get("source") or ""),
        "source_clip_id": str(broll_meta.get("pixabay_video_id") or ""),
        "source_url": str(broll_meta.get("license_evidence") or ""),
        "source_license": str(broll_meta.get("license") or ""),
        "source_license_evidence": str(broll_meta.get("license_evidence") or ""),
    }


def main() -> int:
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    broll_path = pick_noise_broll_file(NOISE_BROLL_DIR)
    if broll_path is None:
        log.error(
            "No calm nursery/night b-roll available in %s -- run scripts/sync_noise_broll.py first "
            "(needs PIXABAY_API_KEY).",
            NOISE_BROLL_DIR,
        )
        return 1

    broll_meta = _load_sidecar(broll_path)
    scene = _pick_scene()
    color = _pick_color()
    duration_s = round(random.uniform(MIN_DURATION_S, MAX_DURATION_S), 1)
    noise_bed_path = _prepare_noise_bed(seed=random.randint(0, 1_000_000), color=color)
    seamless_clip = _prepare_seamless_loop_clip(broll_path)

    slug = f"noiseshort-{int(time.time())}-{random.randint(1000, 9999)}"
    video_path = VIDEOS_DIR / f"noise-{slug}.mp4"
    meta_path = video_path.with_suffix(".json")

    if not _compose_short(seamless_clip, noise_bed_path, video_path, duration_s):
        log.error("Baby-noise Short composition failed for %s", slug)
        return 1

    metadata = _build_metadata(scene, color, duration_s, video_path, slug, broll_meta=broll_meta)
    thumbnail_path = _extract_thumbnail_frame(broll_path, seed=random.randint(0, 1_000_000))
    if thumbnail_path is not None:
        metadata["thumbnail"] = str(thumbnail_path)
    else:
        log.warning("Could not extract a real thumbnail frame -- YouTube will auto-pick one.")
    meta_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Generated %s (%.1fs, %s): %s", video_path.name, duration_s, color, metadata["title"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
