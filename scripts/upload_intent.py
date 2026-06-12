#!/usr/bin/env python3
"""Durable upload intents for idempotent YouTube publishing."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTENTS_FILE = ROOT / "_data" / "upload_intents.jsonl"


def _stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)


def _hash(value: object) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8", "replace")).hexdigest()


def idempotency_key(meta: dict, slot: str = "") -> str:
    payload = {
        "story_id": meta.get("story_id") or meta.get("story_slug") or meta.get("title"),
        "slot": slot or meta.get("publish_slot") or meta.get("publish_ts_utc", "")[:16],
        "variant_hash": _hash(meta.get("experiments") or {}),
        "script_hash": _hash(meta.get("script") or ""),
    }
    return _hash(payload)[:32]


def build_upload_intent(
    meta: dict,
    *,
    meta_file: str = "",
    slot: str = "",
    status: str = "prepared",
    video_id: str = "",
    now: datetime | None = None,
) -> dict:
    stamp = (now or datetime.now(timezone.utc)).isoformat()
    key = idempotency_key(meta, slot)
    return {
        "idempotency_key": key,
        "status": status,
        "story_id": str(meta.get("story_id") or meta.get("story_slug") or ""),
        "title": str(meta.get("title") or "")[:160],
        "slot": slot or str(meta.get("publish_slot") or ""),
        "video": str(meta.get("video") or ""),
        "meta_file": meta_file,
        "video_id": video_id,
        "created_at": stamp,
    }


def read_intents(path: Path = INTENTS_FILE) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def duplicate_uploaded(intent: dict, path: Path = INTENTS_FILE) -> dict:
    key = str(intent.get("idempotency_key") or "")
    for row in read_intents(path):
        if str(row.get("idempotency_key") or "") == key and row.get("status") == "uploaded" and row.get("video_id"):
            return row
    return {}


def duplicate_slot_uploaded(slot: str, path: Path = INTENTS_FILE) -> dict:
    slot = str(slot or "").strip()
    if not slot:
        return {}
    for row in read_intents(path):
        if str(row.get("slot") or "") == slot and row.get("status") == "uploaded" and row.get("video_id"):
            return row
    return {}


def write_upload_intent(intent: dict, path: Path = INTENTS_FILE) -> dict:
    key = (str(intent.get("idempotency_key") or ""), str(intent.get("status") or ""), str(intent.get("video_id") or ""))
    existing = {
        (str(row.get("idempotency_key") or ""), str(row.get("status") or ""), str(row.get("video_id") or ""))
        for row in read_intents(path)
    }
    written = False
    if key not in existing and key[0]:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(intent, sort_keys=True, ensure_ascii=False) + "\n")
        written = True
    return {"path": str(path), "written": written, "idempotency_key": key[0]}


def duplicate_report(path: Path = INTENTS_FILE) -> dict:
    uploaded: dict[str, list[dict]] = {}
    for row in read_intents(path):
        if row.get("status") == "uploaded":
            uploaded.setdefault(str(row.get("idempotency_key") or ""), []).append(row)
    duplicates = [rows for rows in uploaded.values() if len({r.get("video_id") for r in rows}) > 1]
    return {"uploaded_keys": len(uploaded), "duplicate_uploads": duplicates}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", default=str(INTENTS_FILE))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = duplicate_report(Path(args.path))
    print(
        json.dumps(report, sort_keys=True, ensure_ascii=False)
        if args.json
        else f"upload_intent: {len(report['duplicate_uploads'])} duplicates"
    )
    return 1 if report["duplicate_uploads"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
