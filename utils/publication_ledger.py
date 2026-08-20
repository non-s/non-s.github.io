"""Append-only publication receipts and deterministic state reconstruction."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from utils.atomic_state import atomic_write_json, load_versioned, save_versioned
from utils.creative_memory import CATALOG_LIMIT, CATALOG_SCHEMA_VERSION, creation_record

RECEIPT_SCHEMA_VERSION = 1


def video_tag_record(metadata: dict[str, Any], uploaded_at: str) -> dict[str, Any]:
    return {
        "content_id": metadata.get("content_id", ""),
        "genome_id": metadata.get("genome_id", ""),
        "engine_version": metadata.get("engine_version", ""),
        "strategy_version": metadata.get("strategy_version", ""),
        "visual_dna_id": metadata.get("visual_dna_id", ""),
        "experiment_id": metadata.get("experiment_id", ""),
        "hypothesis_id": metadata.get("hypothesis_id", ""),
        "scene": metadata.get("scene", ""),
        "hook": metadata.get("hook", ""),
        "mood": metadata.get("mood", ""),
        "kind": metadata.get("kind", ""),
        "title": metadata.get("title", ""),
        "title_alt": metadata.get("title_alt", ""),
        "title_pattern": metadata.get("title_pattern", ""),
        "lang": metadata.get("lang", "en"),
        "uploaded_at": uploaded_at,
        "thumbnails": metadata.get("thumbnails", []),
        "thumbnail_variant": metadata.get("thumbnail_variant", "A"),
        "editorial_brief": metadata.get("editorial_brief", {}),
        "visual_intelligence": metadata.get("visual_intelligence", {}),
        "story_card": metadata.get("story_card", {}),
        "viewer_experience": metadata.get("viewer_experience", {}),
    }


def publication_receipt(video_id: str, metadata: dict[str, Any], *, uploaded_at: str | None = None) -> dict[str, Any]:
    observed = uploaded_at or datetime.now(UTC).isoformat()
    catalog = creation_record(metadata) if metadata.get("content_id") else None
    return {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "video_id": video_id,
        "content_id": metadata.get("content_id", ""),
        "uploaded_at": observed,
        "title": metadata.get("title", ""),
        "video_tag": video_tag_record(metadata, observed),
        "catalog_record": catalog,
    }


def write_receipt(output_dir: Path, video_id: str, metadata: dict[str, Any]) -> Path:
    path = output_dir / f"publication_receipt_{video_id}.json"
    atomic_write_json(path, publication_receipt(video_id, metadata))
    return path


def rebuild_publication_state(evidence_root: Path, data_root: Path) -> dict[str, int]:
    """Merge immutable receipts; reruns and out-of-order artifacts are idempotent."""
    receipts: dict[str, dict[str, Any]] = {}
    for path in evidence_root.rglob("publication_receipt_*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(payload, dict) and payload.get("schema_version") == RECEIPT_SCHEMA_VERSION:
            video_id = str(payload.get("video_id", ""))
            if video_id:
                current = receipts.get(video_id)
                if current is None or str(payload.get("uploaded_at", "")) >= str(current.get("uploaded_at", "")):
                    receipts[video_id] = payload

    tags_path = data_root / "video_tags.json"
    try:
        tags = json.loads(tags_path.read_text(encoding="utf-8")) if tags_path.exists() else {}
    except (OSError, ValueError):
        tags = {}
    tags = tags if isinstance(tags, dict) else {}

    catalog_path = data_root / "catalog_memory.json"
    catalog = load_versioned(catalog_path, CATALOG_SCHEMA_VERSION, {}, [])
    catalog = catalog if isinstance(catalog, list) else []
    by_content = {str(row.get("content_id")): row for row in catalog if isinstance(row, dict) and row.get("content_id")}
    titles: list[str] = []
    for video_id, receipt in sorted(receipts.items(), key=lambda item: str(item[1].get("uploaded_at", ""))):
        tag = receipt.get("video_tag")
        record = receipt.get("catalog_record")
        if isinstance(tag, dict):
            tags[video_id] = tag
        if isinstance(record, dict) and record.get("content_id"):
            content_id = str(record["content_id"])
            previous = by_content.get(content_id)
            if isinstance(previous, dict):
                record = {
                    **record,
                    "performance_windows": previous.get("performance_windows", {}),
                    "fitness": previous.get("fitness"),
                    "fitness_window": previous.get("fitness_window"),
                    "fitness_observed_at": previous.get("fitness_observed_at"),
                    "youtube_video_id": previous.get("youtube_video_id", video_id),
                }
            by_content[content_id] = record
        title = str(receipt.get("title", "")).strip()
        if title:
            titles.append(title)

    ordered_catalog = sorted(by_content.values(), key=lambda row: str(row.get("generated_at", "")))[-CATALOG_LIMIT:]
    ordered_tags = dict(sorted(tags.items(), key=lambda item: str(item[1].get("uploaded_at", "")))[-500:])
    data_root.mkdir(parents=True, exist_ok=True)
    save_versioned(catalog_path, ordered_catalog, CATALOG_SCHEMA_VERSION)
    atomic_write_json(tags_path, ordered_tags)
    titles_path = data_root / "used_titles.json"
    try:
        old_titles = json.loads(titles_path.read_text(encoding="utf-8")) if titles_path.exists() else []
    except (OSError, ValueError):
        old_titles = []
    old_titles = old_titles if isinstance(old_titles, list) else []
    merged_titles = list(dict.fromkeys([*reversed(titles), *(str(title) for title in old_titles)]))[:120]
    atomic_write_json(titles_path, merged_titles)
    return {"receipts": len(receipts), "catalog_records": len(ordered_catalog), "video_tags": len(ordered_tags)}
