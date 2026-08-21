"""Append-only publication receipts and deterministic state reconstruction."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from utils.atomic_state import atomic_write_json, load_versioned, save_versioned
from utils.creative_memory import CATALOG_LIMIT, CATALOG_SCHEMA_VERSION, creation_record
from utils.experiment_engine import RESEARCH_SCHEMA_VERSION

RECEIPT_SCHEMA_VERSION = 1
LEGACY_MATCH_MAX_SECONDS = 6 * 3600
LEGACY_AMBIGUITY_MARGIN_SECONDS = 15 * 60


def _time(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _legacy_receipts(evidence_root: Path, data_root: Path, known_video_ids: set[str]) -> dict[str, dict[str, Any]]:
    """Recover pre-receipt publications only when title/time evidence is decisive."""
    try:
        analytics = json.loads((data_root / "analytics.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    videos = analytics.get("all_videos", []) if isinstance(analytics, dict) else []
    if not isinstance(videos, list):
        return {}

    candidates: list[tuple[Path, dict[str, Any], datetime]] = []
    for path in evidence_root.rglob("*.json"):
        if path.name.startswith("publication_receipt_"):
            continue
        try:
            metadata = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        generated = _time(metadata.get("generated_at")) if isinstance(metadata, dict) else None
        if isinstance(metadata, dict) and metadata.get("content_id") and metadata.get("title") and generated:
            candidates.append((path, metadata, generated))

    recovered: dict[str, dict[str, Any]] = {}
    used_paths: set[Path] = set()
    valid_videos = (row for row in videos if isinstance(row, dict))
    for video in sorted(valid_videos, key=lambda row: str(row.get("published_at", ""))):
        video_id = str(video.get("video_id", ""))
        published = _time(video.get("published_at"))
        title = str(video.get("title", "")).strip()
        if not video_id or video_id in known_video_ids or not published or not title:
            continue
        ranked = sorted(
            (
                (abs((generated - published).total_seconds()), path, metadata)
                for path, metadata, generated in candidates
                if path not in used_paths and str(metadata.get("title", "")).strip() == title
            ),
            key=lambda row: row[0],
        )
        if not ranked or ranked[0][0] > LEGACY_MATCH_MAX_SECONDS:
            continue
        if len(ranked) > 1 and ranked[1][0] - ranked[0][0] < LEGACY_AMBIGUITY_MARGIN_SECONDS:
            continue
        _, path, metadata = ranked[0]
        used_paths.add(path)
        recovered[video_id] = publication_receipt(video_id, metadata, uploaded_at=published.isoformat())
    return recovered


def video_tag_record(metadata: dict[str, Any], uploaded_at: str) -> dict[str, Any]:
    return {
        "content_id": metadata.get("content_id", ""),
        "genome_id": metadata.get("genome_id", ""),
        "engine_version": metadata.get("engine_version", ""),
        "strategy_version": metadata.get("strategy_version", ""),
        "visual_dna_id": metadata.get("visual_dna_id", ""),
        "experiment_id": metadata.get("experiment_id", ""),
        "hypothesis_id": metadata.get("hypothesis_id", ""),
        "experiment_variant": metadata.get("experiment_variant", ""),
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
        "production_slot": metadata.get("production_slot"),
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


def _rebuild_experiment_state(data_root: Path, catalog: list[dict[str, Any]]) -> int:
    """Recover experiment cohorts from self-contained immutable publications."""
    path = data_root / "research_ledger.json"
    ledger = load_versioned(path, RESEARCH_SCHEMA_VERSION, {}, {"hypotheses": {}, "experiments": {}})
    if not isinstance(ledger, dict):
        ledger = {"hypotheses": {}, "experiments": {}}
    hypotheses = ledger.setdefault("hypotheses", {})
    experiments = ledger.setdefault("experiments", {})
    recovered = 0
    for record in catalog:
        assignment = record.get("experiment") if isinstance(record, dict) else None
        if not isinstance(assignment, dict):
            continue
        experiment_id = str(assignment.get("experiment_id", ""))
        hypothesis_id = str(assignment.get("hypothesis_id", ""))
        content_id = str(record.get("content_id", ""))
        variant = str(record.get("experiment_variant") or assignment.get("variant", ""))
        changed = assignment.get("changed_variables")
        if (
            not experiment_id
            or not hypothesis_id
            or not content_id
            or variant not in {"control", "treatment"}
            or not isinstance(changed, dict)
            or len(changed) != 1
        ):
            continue
        snapshot = assignment.get("hypothesis")
        if hypothesis_id not in hypotheses and isinstance(snapshot, dict):
            hypotheses[hypothesis_id] = snapshot
        experiment = experiments.setdefault(
            experiment_id,
            {
                "hypothesis_id": hypothesis_id,
                "control_content_ids": [],
                "treatment_content_ids": [],
                "changed_variables": changed,
                "format": record.get("kind"),
                "target_window": assignment.get("target_window"),
                "status": "running",
            },
        )
        if not isinstance(experiment, dict):
            continue
        cohort = "control_content_ids" if variant == "control" else "treatment_content_ids"
        ids = experiment.setdefault(cohort, [])
        if content_id not in ids:
            ids.append(content_id)
        recovered += 1
        if experiment.get("status") == "planned":
            experiment["status"] = "running"
    save_versioned(path, ledger, RESEARCH_SCHEMA_VERSION)
    return recovered


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
    legacy = _legacy_receipts(evidence_root, data_root, set(receipts))
    receipts.update(legacy)

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
    # Deduplicate by content_id + visual_dna_id: when a recovery/re-render of
    # the same slot publishes a new video_id, keep only the most recent entry
    # so the rollback duplicate guard never sees a stale pair.
    seen_content_visual: dict[tuple[str, str], str] = {}
    for vid, tag in list(ordered_tags.items()):
        if not isinstance(tag, dict):
            continue
        cid = str(tag.get("content_id", "") or "")
        vdid = str(tag.get("visual_dna_id", "") or "")
        if not cid or not vdid:
            continue
        key = (cid, vdid)
        if key in seen_content_visual:
            older_vid = seen_content_visual[key]
            older_tag = ordered_tags.get(older_vid, {})
            older_ts = str(older_tag.get("uploaded_at", "")) if isinstance(older_tag, dict) else ""
            newer_ts = str(tag.get("uploaded_at", ""))
            if newer_ts >= older_ts:
                del ordered_tags[older_vid]
                seen_content_visual[key] = vid
            else:
                del ordered_tags[vid]
        else:
            seen_content_visual[key] = vid
    data_root.mkdir(parents=True, exist_ok=True)
    save_versioned(catalog_path, ordered_catalog, CATALOG_SCHEMA_VERSION)
    experiment_assignments = _rebuild_experiment_state(data_root, ordered_catalog)
    atomic_write_json(tags_path, ordered_tags)
    titles_path = data_root / "used_titles.json"
    try:
        old_titles = json.loads(titles_path.read_text(encoding="utf-8")) if titles_path.exists() else []
    except (OSError, ValueError):
        old_titles = []
    old_titles = old_titles if isinstance(old_titles, list) else []
    merged_titles = list(dict.fromkeys([*reversed(titles), *(str(title) for title in old_titles)]))[:120]
    atomic_write_json(titles_path, merged_titles)
    return {
        "receipts": len(receipts),
        "legacy_matches": len(legacy),
        "catalog_records": len(ordered_catalog),
        "video_tags": len(ordered_tags),
        "experiment_assignments": experiment_assignments,
    }
