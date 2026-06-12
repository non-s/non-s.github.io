#!/usr/bin/env python3
"""Generate frame-first replacement thumbnails for published Shorts."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image
import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from generate_shorts import create_short_thumbnail
from scripts.published_packaging_repair import build_repairs
from utils.visual_ctr import score_ctr_frame

VIDEOS_DIR = ROOT / "_videos"
OUT_DIR = ROOT / "_data" / "published_thumbnails"
MANIFEST_PATH = ROOT / "_data" / "published_thumbnails_manifest.json"
TIMESTAMPS = (0.45, 1.25, 2.25, 3.5, 5.0)


def _safe_id(video_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", video_id).strip("_") or "video"


def _done_by_video_id() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for path in VIDEOS_DIR.glob("*.done"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        video_id = str(data.get("video_id") or data.get("youtube_video_id") or "").strip()
        if video_id:
            out[video_id] = data
    return out


def _download_video(url: str, dest: Path, max_bytes: int = 90 * 1024 * 1024) -> bool:
    try:
        with requests.get(url, stream=True, timeout=35) as response:
            if response.status_code != 200:
                return False
            total = 0
            chunks: list[bytes] = []
            for chunk in response.iter_content(chunk_size=256 * 1024):
                if not chunk:
                    continue
                total += len(chunk)
                if total > max_bytes:
                    return False
                chunks.append(chunk)
        body = b"".join(chunks)
        if len(body) < 50 * 1024 or b"ftyp" not in body[:64]:
            return False
        dest.write_bytes(body)
        return True
    except Exception:
        return False


def _extract_with_ffmpeg(video_path: Path, dest: Path, timestamp: float) -> bool:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False
    try:
        result = subprocess.run(
            [
                ffmpeg,
                "-y",
                "-ss",
                f"{timestamp:.2f}",
                "-i",
                str(video_path),
                "-frames:v",
                "1",
                "-q:v",
                "2",
                str(dest),
            ],
            capture_output=True,
            timeout=55,
        )
        return result.returncode == 0 and dest.exists() and dest.stat().st_size >= 5 * 1024
    except Exception:
        return False


def _extract_with_cv2(video_path: Path, dest: Path, timestamp: float) -> bool:
    try:
        import cv2

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return False
        cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, timestamp) * 1000)
        ok, frame = cap.read()
        cap.release()
        if not ok or frame is None:
            return False
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        Image.fromarray(rgb).save(dest, "JPEG", quality=92, optimize=True)
        return dest.exists() and dest.stat().st_size >= 5 * 1024
    except Exception:
        return False


def _extract_local_frame(video_path: Path, dest: Path, timestamp: float) -> bool:
    return _extract_with_ffmpeg(video_path, dest, timestamp) or _extract_with_cv2(video_path, dest, timestamp)


def _best_frame_from_url(url: str, tmp_dir: Path, video_id: str) -> tuple[Path | None, dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    video_path = tmp_dir / f"{_safe_id(video_id)}.mp4"
    if not _download_video(url, video_path):
        return None, {"checked": False, "reason": "download_failed", "candidates": []}
    for idx, ts in enumerate(TIMESTAMPS):
        frame = tmp_dir / f"{_safe_id(video_id)}_{idx}.jpg"
        if not _extract_local_frame(video_path, frame, ts):
            continue
        score = score_ctr_frame(frame)
        candidates.append({"path": str(frame), "timestamp": ts, **score})
    if not candidates:
        return None, {"checked": False, "reason": "no_remote_frames", "candidates": []}
    candidates.sort(key=lambda item: (int(item.get("score", 0) or 0), float(item.get("timestamp", 0) or 0)), reverse=True)
    best = candidates[0]
    return Path(str(best["path"])), {
        "checked": True,
        "score": int(best.get("score", 0) or 0),
        "timestamp": best.get("timestamp"),
        "reason": best.get("reason", ""),
        "candidates": [{k: v for k, v in item.items() if k != "path"} for item in candidates],
    }


def generate(limit: int | None = None, high_only: bool = True) -> list[dict[str, Any]]:
    done = _done_by_video_id()
    repairs = build_repairs()
    if high_only:
        repairs = [item for item in repairs if item.get("priority") == "high"]
    if limit:
        repairs = repairs[:limit]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="wildbrief-thumbs-") as tmp:
        tmp_dir = Path(tmp)
        for item in repairs:
            video_id = str(item["video_id"])
            data = done.get(video_id) or {}
            source_url = str(data.get("pexels_download_url") or data.get("source_download_url") or "").strip()
            if not source_url:
                manifest.append({**item, "thumbnail_file": "", "status": "skipped_no_download_url"})
                continue
            frame, score = _best_frame_from_url(source_url, tmp_dir, video_id)
            if not frame:
                manifest.append({**item, "thumbnail_file": "", "status": "failed_frame_extract", "frame_score": score})
                continue
            out_path = OUT_DIR / f"{_safe_id(video_id)}.jpg"
            create_short_thumbnail(
                frame_img=Image.open(frame),
                output=out_path,
                thumbnail_text=item["thumbnail_text"],
                category=str(data.get("category") or "wildlife"),
            )
            manifest.append(
                {
                    **item,
                    "thumbnail_file": out_path.relative_to(ROOT).as_posix(),
                    "status": "generated",
                    "source_download_url": source_url,
                    "frame_score": score,
                }
            )
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(manifest),
        "generated_count": sum(1 for item in manifest if item.get("status") == "generated"),
        "items": manifest,
    }
    MANIFEST_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="Maximum repairs to process; 0 means all selected.")
    parser.add_argument("--all-priorities", action="store_true", help="Include non-high-priority published videos.")
    args = parser.parse_args()
    manifest = generate(limit=args.limit or None, high_only=not args.all_priorities)
    print(
        json.dumps(
            {
                "manifest": MANIFEST_PATH.as_posix(),
                "count": len(manifest),
                "generated": sum(1 for item in manifest if item.get("status") == "generated"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
