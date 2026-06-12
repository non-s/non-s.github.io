"""Free visual CTR heuristics for Shorts thumbnails and first frames."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from PIL import Image, ImageFilter, ImageStat

from utils.visual_qa import evaluate_local_frame

log = logging.getLogger(__name__)

DEFAULT_TIMESTAMPS = (0.35, 0.8, 1.4, 2.2)


def _closeness(value: float, target: float, spread: float) -> float:
    if spread <= 0:
        return 0.0
    return max(0.0, 1.0 - abs(value - target) / spread)


def score_ctr_frame(image_path: Path) -> dict:
    """Score one still for click/preview strength using local signals only."""
    local = evaluate_local_frame(image_path)
    try:
        with Image.open(image_path) as im:
            rgb = im.convert("RGB")
            width, height = rgb.size
            gray = rgb.convert("L")
            center = gray.crop(
                (
                    int(width * 0.18),
                    int(height * 0.12),
                    int(width * 0.82),
                    int(height * 0.76),
                )
            )
            edges = center.resize((96, 128)).filter(ImageFilter.FIND_EDGES)
            edge_stat = ImageStat.Stat(edges)
            center_detail = float(edge_stat.mean[0])
            full_stat = ImageStat.Stat(gray)
            brightness = float(full_stat.mean[0])
            contrast = float(full_stat.stddev[0])
            # Visual-weight proxy: detail in the center area, where the
            # animal should live after vertical crop.
            center_strength = min(1.0, center_detail / 18.0)
            brightness_fit = _closeness(brightness, 118.0, 120.0)
            contrast_fit = min(1.0, contrast / 58.0)
    except Exception as exc:
        return {
            "checked": False,
            "approved": True,
            "score": 5,
            "reason": f"ctr frame unavailable: {type(exc).__name__}",
            "local_visual_qa": local,
        }
    score = 10
    reasons: list[str] = []
    score += round(center_strength * 22)
    score += round(brightness_fit * 14)
    score += round(contrast_fit * 14)
    score += int(local.get("score", 5) or 5) * 5
    if center_strength < 0.22:
        reasons.append("weak_center_subject")
        score -= 12
    if brightness_fit < 0.28:
        reasons.append("poor_brightness_for_feed")
        score -= 8
    if contrast_fit < 0.38:
        reasons.append("low_feed_contrast")
        score -= 8
    score = max(0, min(100, int(score)))
    return {
        "checked": True,
        "approved": score >= 58 and bool(local.get("approved", True)),
        "score": score,
        "center_strength": round(center_strength, 3),
        "brightness_fit": round(brightness_fit, 3),
        "contrast_fit": round(contrast_fit, 3),
        "profile": classify_visual_profile(
            center_strength=center_strength,
            brightness_fit=brightness_fit,
            contrast_fit=contrast_fit,
            score=score,
        ),
        "reason": ",".join(reasons) or "strong_preview_frame",
        "local_visual_qa": local,
    }


def classify_visual_profile(*, center_strength: float, brightness_fit: float, contrast_fit: float, score: int) -> dict:
    """Map numeric frame signals into learnable visual buckets."""
    buckets: list[str] = []
    if center_strength >= 0.72:
        buckets.append("close_subject")
    elif center_strength >= 0.42:
        buckets.append("subject_rich")
    else:
        buckets.append("weak_subject")
    if brightness_fit >= 0.72:
        buckets.append("feed_bright")
    elif brightness_fit < 0.32:
        buckets.append("dark_or_washed")
    else:
        buckets.append("usable_light")
    if contrast_fit >= 0.68:
        buckets.append("high_contrast")
    elif contrast_fit < 0.38:
        buckets.append("flat_contrast")
    else:
        buckets.append("medium_contrast")
    if score >= 78:
        quality = "hero_frame"
    elif score >= 58:
        quality = "usable_frame"
    else:
        quality = "weak_frame"
    return {
        "quality": quality,
        "buckets": buckets,
        "primary": "|".join((buckets[0], buckets[1], buckets[2])),
    }


def extract_candidate_frame(video_path: Path, dest: Path, timestamp: float) -> bool:
    """Extract one candidate frame from a clip with ffmpeg."""
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-ss",
                f"{max(0.0, timestamp):.2f}",
                "-i",
                str(video_path),
                "-frames:v",
                "1",
                "-q:v",
                "2",
                str(dest),
            ],
            capture_output=True,
            timeout=30,
        )
        return result.returncode == 0 and dest.exists() and dest.stat().st_size >= 5 * 1024
    except Exception as exc:
        log.debug("candidate frame extraction failed: %s", exc)
        return False


def select_best_frame(video_path: Path, tmp_dir: Path, timestamps: tuple[float, ...] = DEFAULT_TIMESTAMPS) -> dict:
    """Extract several early frames and return the strongest CTR candidate."""
    candidates = []
    tmp_dir.mkdir(parents=True, exist_ok=True)
    for idx, ts in enumerate(timestamps):
        frame_path = tmp_dir / f"{video_path.stem}_ctr_{idx}.jpg"
        if not extract_candidate_frame(video_path, frame_path, ts):
            continue
        score = score_ctr_frame(frame_path)
        candidates.append(
            {
                "path": str(frame_path),
                "timestamp": ts,
                **score,
            }
        )
    if not candidates:
        return {
            "checked": False,
            "approved": True,
            "score": 0,
            "reason": "no_candidate_frames",
            "candidates": [],
        }
    candidates.sort(
        key=lambda item: (int(item.get("score", 0) or 0), float(item.get("timestamp", 0) or 0)), reverse=True
    )
    best = candidates[0]
    return {
        "checked": True,
        "approved": bool(best.get("approved", True)),
        "score": int(best.get("score", 0) or 0),
        "reason": best.get("reason", ""),
        "best_frame": best.get("path", ""),
        "best_timestamp": best.get("timestamp", 0),
        "profile": best.get("profile") or {},
        "candidates": [
            {key: value for key, value in item.items() if key not in {"path", "local_visual_qa"}} for item in candidates
        ],
    }
