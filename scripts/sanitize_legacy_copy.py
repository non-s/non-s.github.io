#!/usr/bin/env python3
"""Sanitize legacy generated copy that no longer passes editorial guardrails."""
from __future__ import annotations

import json
import re
import sys
from hashlib import sha256
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.editorial_guard import editorial_issues  # noqa: E402
from utils.local_rewriter import rescue_story  # noqa: E402
from utils.packaging import extract_cue, package_story  # noqa: E402

TARGET_SUFFIXES = {".done", ".json", ".jsonl"}
TARGET_DIRS = (ROOT / "_videos", ROOT / "_data")
OUT = ROOT / "_data" / "legacy_copy_sanitize_report.json"


def _json_paths() -> list[Path]:
    paths: list[Path] = []
    for folder in TARGET_DIRS:
        if not folder.exists():
            continue
        for path in folder.rglob("*"):
            if path.is_file() and path.suffix.lower() in TARGET_SUFFIXES:
                paths.append(path)
    return sorted(paths)


def _read_jsonish(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".jsonl":
        rows = []
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                rows.append(line)
        return rows
    return json.loads(text)


def _write_jsonish(path: Path, payload: Any) -> None:
    if path.suffix.lower() == ".jsonl":
        text = "\n".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) if not isinstance(row, str) else row for row in payload
        )
        path.write_text(text + ("\n" if text else ""), encoding="utf-8")
        return
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _story_for(item: dict, title: str) -> dict:
    return {
        **item,
        "title": title,
        "seo_title": title,
        "hook": item.get("hook") or title,
        "script": item.get("script") or item.get("description") or title,
        "thumbnail_text": item.get("thumbnail_text") or "",
        "category": item.get("category") or item.get("topic_hashtag") or "",
    }


def _repair_title(item: dict, title: str) -> dict:
    story = _story_for(item, title)
    issues = editorial_issues(story, include_script=False)
    if not issues:
        return {}
    rescued, applied = rescue_story(story, issues)
    if not applied:
        return {}
    packaged = package_story(rescued)
    new_title = str(packaged.get("seo_title") or packaged.get("title") or rescued.get("seo_title") or "").strip()
    if not new_title or new_title.lower() == title.lower():
        return {}
    if editorial_issues({"title": new_title, "seo_title": new_title}, include_script=False):
        return {}
    return {
        "title": new_title,
        "hook": str(packaged.get("hook") or rescued.get("hook") or new_title).strip(),
        "script": str(packaged.get("script") or rescued.get("script") or "").strip(),
        "thumbnail_text": str(packaged.get("thumbnail_text") or rescued.get("thumbnail_text") or "").strip(),
        "cue": str(packaged.get("cue") or extract_cue(packaged) or "").strip(),
    }


def _add_mapping(mapping: dict[str, str], old: str, new: str) -> None:
    old = str(old or "").strip()
    new = str(new or "").strip()
    if old and new and old.lower() != new.lower():
        mapping[old] = new


def _collect_mappings(value: Any, mapping: dict[str, str]) -> None:
    if isinstance(value, dict):
        title = str(value.get("seo_title") or value.get("title") or "").strip()
        repair = _repair_title(value, title) if title else {}
        if repair:
            _add_mapping(mapping, title, repair["title"])
            _add_mapping(mapping, value.get("seo_title", ""), repair["title"])
            _add_mapping(mapping, value.get("hook", ""), repair["hook"])
            old_prefix = re.sub(
                r"\s+to\s+(?:escape|feed|find|follow|hide|hunt|protect|survive|use)\b.*$",
                "",
                title,
                flags=re.I,
            ).strip()
            _add_mapping(mapping, old_prefix, repair["hook"].rstrip("."))
            old_cue = extract_cue(value)
            _add_mapping(mapping, old_cue, repair.get("cue", ""))
        for child in value.values():
            _collect_mappings(child, mapping)
    elif isinstance(value, list):
        for child in value:
            _collect_mappings(child, mapping)


def _replace_text(text: str, mapping: dict[str, str]) -> str:
    out = text
    for old, new in sorted(mapping.items(), key=lambda row: len(row[0]), reverse=True):
        out = out.replace(old, new)
    return out


def _transform(value: Any, mapping: dict[str, str]) -> Any:
    if isinstance(value, str):
        return _replace_text(value, mapping)
    if isinstance(value, list):
        return [_transform(item, mapping) for item in value]
    if isinstance(value, dict):
        return {key: _transform(item, mapping) for key, item in value.items()}
    return value


def main() -> int:
    payloads: dict[Path, Any] = {}
    mapping: dict[str, str] = {}
    for path in _json_paths():
        try:
            payload = _read_jsonish(path)
        except Exception:
            continue
        payloads[path] = payload
        _collect_mappings(payload, mapping)
    changed: list[str] = []
    for path, payload in payloads.items():
        updated = _transform(payload, mapping)
        if updated != payload:
            _write_jsonish(path, updated)
            changed.append(str(path.relative_to(ROOT)))
    report = {
        "changed_files": changed,
        "replacements": [
            {
                "old_sha256": sha256(old.encode("utf-8", "replace")).hexdigest()[:16],
                "old_length": len(old),
                "new": new,
            }
            for old, new in sorted(mapping.items())
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"sanitize_legacy_copy: {len(changed)} file(s), {len(mapping)} replacement(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
