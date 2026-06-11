"""Stable transformation/originality manifests for rendered Shorts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def stable_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8", "replace")).hexdigest()


def build_originality_pack(meta: dict | None = None) -> dict:
    meta = meta or {}
    story_material = {
        "story_id": meta.get("story_id") or meta.get("id") or meta.get("story_slug"),
        "title": meta.get("title"),
        "hook": meta.get("hook"),
        "source_url": meta.get("source_url"),
    }
    script = str(meta.get("script") or "")
    clip_material = {
        "source_clip_id": meta.get("source_clip_id"),
        "pexels_video_id": meta.get("pexels_video_id"),
        "pexels_download_url": meta.get("pexels_download_url"),
        "source_download_url": meta.get("source_download_url"),
    }
    render_manifest = {
        "video": meta.get("video"),
        "thumbnail": meta.get("thumbnail"),
        "has_broll": bool(meta.get("has_broll")),
        "has_captions": bool(meta.get("has_captions")),
        "visual_qa": meta.get("visual_qa") or {},
    }
    caption_manifest = {
        "thumbnail_text": meta.get("thumbnail_text"),
        "caption_style": "burned_ass" if meta.get("has_captions") else "missing",
    }
    tts_manifest = {
        "narrator_voice": meta.get("narrator_voice"),
        "human_voice": meta.get("human_voice") or {},
    }
    return {
        "story_id": str(story_material.get("story_id") or ""),
        "story_hash": stable_hash(story_material),
        "script_hash": stable_hash(script),
        "clip_hash": stable_hash(clip_material),
        "render_manifest": render_manifest,
        "caption_manifest": caption_manifest,
        "tts_manifest": tts_manifest,
        "complete": bool(
            script
            and (
                clip_material.get("source_clip_id")
                or clip_material.get("pexels_video_id")
                or render_manifest.get("has_broll")
            )
        ),
    }


def write_originality_pack(meta: dict, path: Path = Path("_data/originality_pack.jsonl")) -> dict:
    row = build_originality_pack(meta)
    key = (row["story_id"], row["story_hash"], row["script_hash"])
    existing = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                old = json.loads(line)
            except Exception:
                continue
            existing.add(
                (str(old.get("story_id") or ""), str(old.get("story_hash") or ""), str(old.get("script_hash") or ""))
            )
    if key not in existing and any(key):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
    return {"path": str(path), "written": key not in existing and any(key), "pack": row}
