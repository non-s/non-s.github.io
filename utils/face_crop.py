"""
utils/face_crop.py — Smart vertical crop using OpenCV face detection.

Why this exists
---------------
The default FFmpeg vertical crop (`scale + crop` centered) loses
faces that aren't centered in the source footage. Talking-head Pexels
clips often have the speaker on one side. Cutting off the face is the
single worst thing a vertical re-crop can do.

This module probes the FIRST frame of each b-roll clip, runs OpenCV's
haar cascade face detector, and emits a `(x_offset, y_offset)` pair
the FFmpeg crop filter uses to keep the face on-screen.

When OpenCV isn't installed (sandbox / minimal environment), or no
face is found, we silently fall back to center-crop — the existing
behaviour — so this module is purely additive.

The detection runs once per clip and the offset is reused for all
frames in that clip, so the cost is O(clips), not O(frames).
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)


def _try_import_opencv():
    """Import cv2 lazily — keep the module import cheap on sandboxes."""
    try:
        import cv2  # noqa: F401
        return True
    except Exception:
        return False


def _extract_first_frame(clip_path: Path, dest: Path) -> bool:
    """Extract a single PNG of the clip's first frame via FFmpeg."""
    try:
        r = subprocess.run(
            ["ffmpeg", "-y", "-i", str(clip_path),
             "-frames:v", "1", "-q:v", "2", str(dest)],
            capture_output=True, timeout=30,
        )
        return r.returncode == 0 and dest.exists()
    except Exception as exc:
        log.debug("face_crop frame extract failed: %s", exc)
        return False


def detect_face_center(clip_path: Path,
                       tmp_dir: Path) -> tuple[float, float] | None:
    """Probe the first frame for a face. Returns (x_frac, y_frac) in
    [0, 1] coordinates of the source frame's centre-of-largest-face,
    or None when no face is found / OpenCV isn't available.

    Frac coordinates let the caller convert to pixels regardless of
    the actual source resolution.
    """
    if not _try_import_opencv():
        return None
    try:
        import cv2
    except Exception:
        return None

    frame_path = tmp_dir / (clip_path.stem + "_first.png")
    if not _extract_first_frame(clip_path, frame_path):
        return None
    try:
        img = cv2.imread(str(frame_path))
        if img is None:
            return None
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # haarcascades ships with opencv-python-headless under data/.
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        cascade = cv2.CascadeClassifier(cascade_path)
        faces = cascade.detectMultiScale(
            gray, scaleFactor=1.2, minNeighbors=5,
            minSize=(60, 60),
        )
        if len(faces) == 0:
            return None
        # Largest face wins (closest to camera = main subject).
        x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
        cx, cy = x + w / 2.0, y + h / 2.0
        h_img, w_img = gray.shape
        return (cx / w_img, cy / h_img)
    except Exception as exc:
        log.debug("face_crop detect failed for %s: %s", clip_path.name, exc)
        return None
    finally:
        try:
            frame_path.unlink(missing_ok=True)
        except Exception:
            pass


def x_crop_offset_expr(face_x_frac: float | None,
                       source_w: int = 1920,
                       short_w: int = 1080) -> str:
    """Return the FFmpeg crop `x` expression that keeps the face on-screen.

    The Ken Burns pipeline first scales the source to 2× (3840 wide
    for a 1920×1080 source) and crops to 2×Shorts (2160 wide). The
    final downscale brings us to 1080. We want to bias the crop window
    so the face's x-coordinate lands in the middle of the kept region.

    Caller passes the original source's face_x_frac (the fraction
    along the source frame). We return a static integer offset since
    the source size is known at the time we crop.

    When face_x_frac is None, returns "(iw-ow)/2" — the default centred crop.
    """
    if face_x_frac is None:
        return "(iw-ow)/2"
    # We work in the scaled-up space (iw == source_w × 2).
    # crop width ow == short_w × 2.
    # Target x of crop window = face_x × iw - ow/2.
    # Then clamp to [0, iw - ow].
    return (
        f"max(0,min(iw-ow,"
        f"{face_x_frac:.4f}*iw-(ow/2)"
        f"))"
    )
