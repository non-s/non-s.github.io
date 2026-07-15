"""Lifecycle policy for generated media artifacts.

The repo should keep durable learning state: YouTube ids, upload markers,
analytics, packaging decisions and provenance. Rendered video/audio/image
files are temporary and should be deleted after upload.
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Iterable

MEDIA_LIFECYCLE_REPORT = Path("_data/media_lifecycle_report.json")

AUDIO_VIDEO_SUFFIXES = {
    ".aac",
    ".avi",
    ".flac",
    ".m4a",
    ".mkv",
    ".mov",
    ".mp3",
    ".mp4",
    ".oga",
    ".ogg",
    ".wav",
    ".webm",
}
GENERATED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
GENERATED_MEDIA_SUFFIXES = AUDIO_VIDEO_SUFFIXES | GENERATED_IMAGE_SUFFIXES

ARTIFACT_KEYS = (
    "video",
    "thumbnail",
    "audio",
    "audio_path",
    "narration",
    "narration_audio",
    "voiceover",
    "tts_audio",
    "music_bed_path",
    "source_local_path",
    "broll_path",
    "clip_path",
)

LIFECYCLE_ROOTS = (
    "_videos",
    "_data/audio_cache",
    "_data/music_cache",
    "tmp_render",
    "render_tmp",
)


def enabled(env: dict | None = None) -> bool:
    source = env or os.environ
    return str(source.get("MEDIA_LIFECYCLE_CLEANUP", "1")).strip().lower() not in {"0", "false", "no", "off"}


def _as_posix(path: Path) -> str:
    return path.as_posix()


def _relative(path: Path, root: Path) -> str:
    try:
        return _as_posix(path.relative_to(root))
    except ValueError:
        return _as_posix(path)


def _resolve_candidate(value: object, root: Path) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(value.strip())
    if not path.is_absolute():
        path = root / path
    try:
        return path.resolve()
    except OSError:
        return path.absolute()


def _is_inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _is_lifecycle_root(path: Path, root: Path, lifecycle_roots: Iterable[str] = LIFECYCLE_ROOTS) -> bool:
    if not _is_inside(path, root):
        return False
    rel = _relative(path, root)
    parts = rel.split("/")
    if parts and parts[0].startswith("_videos"):
        return True
    for rel_root in lifecycle_roots:
        lifecycle_root = (root / rel_root).resolve()
        if _is_inside(path, lifecycle_root):
            return True
    return False


def _artifact_values(meta: dict, extra_keys: Iterable[str] = ()) -> list[object]:
    values: list[object] = []
    for key in tuple(ARTIFACT_KEYS) + tuple(extra_keys):
        values.append(meta.get(key))
    return values


def _delete_file(path: Path, *, root: Path, dry_run: bool) -> dict:
    rel = _relative(path, root)
    try:
        size = path.stat().st_size
    except OSError:
        size = 0
    if not dry_run:
        try:
            path.unlink()
        except OSError as exc:
            return {"path": rel, "bytes": size, "deleted": False, "reason": f"{type(exc).__name__}: {exc}"}
    return {"path": rel, "bytes": size, "deleted": not dry_run, "dry_run": dry_run}


def cleanup_meta_artifacts(
    meta: dict,
    *,
    root: Path | str = ".",
    dry_run: bool = False,
    extra_keys: Iterable[str] = (),
    env: dict | None = None,
) -> dict:
    """Delete generated artifacts referenced by upload metadata."""

    root_path = Path(root).resolve()
    report = {
        "enabled": enabled(env),
        "dry_run": dry_run,
        "deleted": [],
        "skipped": [],
        "deleted_bytes": 0,
    }
    if not report["enabled"]:
        return report

    seen: set[Path] = set()
    for value in _artifact_values(meta, extra_keys):
        path = _resolve_candidate(value, root_path)
        if path is None or path in seen:
            continue
        seen.add(path)
        rel = _relative(path, root_path)
        suffix = path.suffix.lower()
        if suffix not in GENERATED_MEDIA_SUFFIXES:
            report["skipped"].append({"path": rel, "reason": "not_generated_media_suffix"})
            continue
        if not _is_lifecycle_root(path, root_path):
            report["skipped"].append({"path": rel, "reason": "outside_lifecycle_roots"})
            continue
        if not path.exists():
            report["skipped"].append({"path": rel, "reason": "missing"})
            continue
        if not path.is_file():
            report["skipped"].append({"path": rel, "reason": "not_file"})
            continue
        row = _delete_file(path, root=root_path, dry_run=dry_run)
        if row.get("deleted") or dry_run:
            report["deleted"].append(row)
            report["deleted_bytes"] += int(row.get("bytes") or 0)
        else:
            report["skipped"].append(row)
    return report


def _pending_sidecar_exists(path: Path) -> bool:
    stems = [path.stem]
    for suffix in ("_thumb", "-thumb", ".thumb"):
        if path.stem.endswith(suffix):
            stems.append(path.stem[: -len(suffix)])
    return any((path.parent / f"{stem}.json").exists() for stem in stems if stem)


def cleanup_output_dirs(*, root: Path | str = ".", dry_run: bool = False, env: dict | None = None) -> dict:
    """Delete orphan generated media from _videos* folders.

    Pending renders with a matching .json sidecar are preserved, because they
    may still need to be uploaded. After upload, upload_youtube.py removes the
    .json sidecar and this cleanup can delete any remaining media.
    """

    root_path = Path(root).resolve()
    report = {
        "enabled": enabled(env),
        "dry_run": dry_run,
        "deleted": [],
        "skipped": [],
        "deleted_bytes": 0,
    }
    if not report["enabled"]:
        return report

    for directory in sorted(root_path.glob("_videos*")):
        if not directory.is_dir():
            continue
        for path in sorted(directory.iterdir()):
            if not path.is_file() or path.suffix.lower() not in GENERATED_MEDIA_SUFFIXES:
                continue
            rel = _relative(path, root_path)
            if _pending_sidecar_exists(path):
                report["skipped"].append({"path": rel, "reason": "pending_metadata"})
                continue
            row = _delete_file(path, root=root_path, dry_run=dry_run)
            if row.get("deleted") or dry_run:
                report["deleted"].append(row)
                report["deleted_bytes"] += int(row.get("bytes") or 0)
            else:
                report["skipped"].append(row)
    return report


def _tracked_files(root: Path) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=str(root),
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )
    except OSError:
        return []
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _generated_image_path(rel: str) -> bool:
    path = PurePosixPath(rel)
    first = path.parts[0] if path.parts else ""
    return first.startswith("_videos") or rel.startswith("_data/") or rel.startswith("tmp_render/")


def tracked_media_risks(root: Path | str = ".", paths: Iterable[str] | None = None) -> dict:
    """Return tracked files that violate the generated-media policy."""

    root_path = Path(root).resolve()
    checked = list(paths) if paths is not None else _tracked_files(root_path)
    risks: list[dict] = []
    for rel in checked:
        suffix = PurePosixPath(rel).suffix.lower()
        reason = ""
        if suffix in AUDIO_VIDEO_SUFFIXES:
            if not rel.startswith("_assets/"):
                reason = "audio_video_should_not_be_tracked"
        elif suffix in GENERATED_IMAGE_SUFFIXES and _generated_image_path(rel):
            reason = "generated_image_should_not_be_tracked"
        if not reason:
            continue
        path = root_path / rel
        size = path.stat().st_size if path.exists() and path.is_file() else 0
        risks.append({"path": rel, "suffix": suffix, "bytes": size, "reason": reason})
    return {
        "checked_files": len(checked),
        "risk_count": len(risks),
        "risks": risks,
        "ok": not risks,
    }


def write_lifecycle_report(root: Path | str = ".", **sections: dict) -> dict:
    root_path = Path(root).resolve()
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        **sections,
    }
    out = root_path / MEDIA_LIFECYCLE_REPORT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload
