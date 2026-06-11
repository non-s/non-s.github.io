"""Render QA and benchmark helpers."""

from __future__ import annotations

from pathlib import Path


def evaluate_render_artifact(path: str | Path, meta: dict | None = None) -> dict:
    meta = meta or {}
    p = Path(path)
    reasons: list[str] = []
    if not p.exists():
        reasons.append("video_missing")
    elif p.stat().st_size < 100_000:
        reasons.append("video_too_small")
    if meta.get("has_captions") is False:
        reasons.append("captions_missing")
    if meta.get("has_broll") is False:
        reasons.append("motion_broll_missing")
    return {"approved": not reasons, "reasons": reasons, "size_bytes": p.stat().st_size if p.exists() else 0}
