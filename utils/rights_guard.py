"""Source provenance and rights-risk guard for media inputs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

PROVENANCE_FILE = Path("_data/source_provenance.jsonl")
BRAND_TERMS = {"disney", "netflix", "nike", "coca-cola", "national geographic", "nat geo", "bbc"}
PERSON_TERMS = {"person", "people", "human", "celebrity", "interview"}


def _text(value: object) -> str:
    return " ".join(str(value or "").split())


def _risk_terms(text: str, terms: set[str]) -> list[str]:
    lower = text.lower()
    return sorted(term for term in terms if term in lower)


def source_provenance(meta: dict | None = None) -> dict:
    meta = meta or {}
    return {
        "story_id": _text(meta.get("story_id") or meta.get("id") or meta.get("story_slug")),
        "source": _text(meta.get("source")),
        "source_url": _text(meta.get("source_url") or meta.get("url")),
        "source_license": _text(meta.get("source_license") or meta.get("commons_license")),
        "author": _text(meta.get("author") or meta.get("commons_artist")),
        "downloaded_at": _text(
            meta.get("downloaded_at") or meta.get("created_at") or datetime.now(timezone.utc).isoformat()
        ),
        "source_clip_id": _text(meta.get("source_clip_id") or meta.get("pexels_video_id")),
    }


def evaluate_rights_guard(meta: dict | None = None) -> dict:
    meta = meta or {}
    provenance = source_provenance(meta)
    text = " ".join(_text(meta.get(key)) for key in ("title", "description", "source_url", "source"))
    brand_hits = _risk_terms(text, BRAND_TERMS)
    person_hits = _risk_terms(text, PERSON_TERMS)
    license_text = provenance["source_license"].lower()
    source_url = provenance["source_url"]
    reasons: list[str] = []
    if not source_url:
        reasons.append("missing_source_url")
    if not license_text:
        reasons.append("missing_source_license")
    if brand_hits:
        reasons.append("brand_manual_review")
    if person_hits:
        reasons.append("person_manual_review")
    state = "approved"
    if brand_hits or person_hits:
        state = "manual_review"
    if "missing_source_url" in reasons:
        state = "block"
    return {
        "state": state,
        "approved": state != "block",
        "provenance": provenance,
        "brand_risk": {"risk": bool(brand_hits), "terms": brand_hits},
        "person_risk": {"risk": bool(person_hits), "terms": person_hits},
        "reasons": reasons,
    }


def write_source_provenance(meta: dict, path: Path = PROVENANCE_FILE) -> dict:
    row = source_provenance(meta)
    key = (row["story_id"], row["source_clip_id"], row["source_url"])
    existing = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                old = json.loads(line)
            except Exception:
                continue
            existing.add((_text(old.get("story_id")), _text(old.get("source_clip_id")), _text(old.get("source_url"))))
    if key not in existing and any(key):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
    return {"path": str(path), "written": key not in existing and any(key)}
