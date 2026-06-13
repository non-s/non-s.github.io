#!/usr/bin/env python3
"""Merge append-only JSONL workflow state after refreshing from origin/main.

GitHub Actions jobs in this repo generate state, fetch the latest main branch,
then replay the generated files before committing. Plain copy is unsafe for
append-only ledgers: a queue refresh can accidentally overwrite a YouTube
upload row that landed a minute earlier. This helper merges known JSONL files
line-by-line so concurrent workflow commits keep both histories.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

QUOTA_LEDGER_PATH = "_data/analytics/api_quota_ledger.jsonl"
QUOTA_LATEST_PATH = "_data/analytics/api_quota_latest.json"

DEFAULT_JSONL_STATE_PATHS = (
    QUOTA_LEDGER_PATH,
    "_data/analytics/reporting_video_metrics.jsonl",
    "_data/analytics/studio_reach_daily.jsonl",
    "_data/ai_cache.jsonl",
    "_data/channel_memory.jsonl",
    "_data/fact_sources.jsonl",
    "_data/originality_pack.jsonl",
    "_data/provider_stats.jsonl",
    "_data/publish_slot_decisions.jsonl",
    "_data/repair_queue.jsonl",
    "_data/rejected_queue.jsonl",
    "_data/source_provenance.jsonl",
    "_data/trends/trend_signals.jsonl",
    "_data/upload_intents.jsonl",
)

KEY_MERGED_JSONL_PATHS = {
    "_data/fact_sources.jsonl",
}


def read_jsonl_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def merge_jsonl_lines(current_lines: list[str], incoming_lines: list[str]) -> list[str]:
    """Preserve latest-main order first, then append generated unseen rows."""
    merged: list[str] = []
    seen: set[str] = set()
    for line in [*current_lines, *incoming_lines]:
        if not line.strip() or line in seen:
            continue
        merged.append(line)
        seen.add(line)
    return merged


def _fact_source_key(row: dict) -> tuple[str, str]:
    return (str(row.get("story_id") or ""), str(row.get("source_url") or ""))


def merge_fact_source_lines(current_lines: list[str], incoming_lines: list[str]) -> list[str]:
    """Merge source metadata by story/source so corrected titles replace stale rows."""
    rows: list[dict] = []
    raw_lines: list[str] = []
    index: dict[tuple[str, str], int] = {}
    seen_raw: set[str] = set()

    def add(line: str, *, prefer: bool) -> None:
        if not line.strip():
            return
        try:
            row = json.loads(line)
        except Exception:
            if line not in seen_raw:
                raw_lines.append(line)
                seen_raw.add(line)
            return
        if not isinstance(row, dict):
            if line not in seen_raw:
                raw_lines.append(line)
                seen_raw.add(line)
            return
        key = _fact_source_key(row)
        if not any(key):
            if line not in seen_raw:
                raw_lines.append(line)
                seen_raw.add(line)
            return
        if key in index:
            if prefer:
                current = rows[index[key]]
                updated = dict(current)
                for field, value in row.items():
                    if field == "recorded_at" and current.get("recorded_at"):
                        continue
                    updated[field] = value
                rows[index[key]] = updated
            return
        index[key] = len(rows)
        rows.append(row)

    for line in current_lines:
        add(line, prefer=False)
    for line in incoming_lines:
        add(line, prefer=True)
    return [json.dumps(row, sort_keys=True, ensure_ascii=False) for row in rows] + raw_lines


def write_quota_latest(state_dir: Path, merged_lines: list[str]) -> None:
    rows: list[dict] = []
    for line in merged_lines:
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict) and row.get("timestamp_utc"):
            rows.append(row)
    if not rows:
        return
    latest = max(rows, key=lambda row: str(row.get("timestamp_utc") or ""))
    latest_path = state_dir / QUOTA_LATEST_PATH
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    latest_path.write_text(json.dumps(latest, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def merge_state_file(root: Path, state_dir: Path, relative_path: str) -> dict:
    rel = Path(relative_path)
    current_path = root / rel
    incoming_path = state_dir / rel
    current_lines = read_jsonl_lines(current_path)
    incoming_lines = read_jsonl_lines(incoming_path)
    if not current_lines and not incoming_lines:
        return {
            "path": relative_path,
            "current": 0,
            "incoming": 0,
            "merged": 0,
            "changed": False,
            "skipped": True,
        }
    if relative_path in KEY_MERGED_JSONL_PATHS:
        merged = merge_fact_source_lines(current_lines, incoming_lines)
    else:
        merged = merge_jsonl_lines(current_lines, incoming_lines)
    incoming_path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(merged)
    if text:
        text += "\n"
    before = "\n".join(incoming_lines)
    if before:
        before += "\n"
    changed = text != before
    incoming_path.write_text(text, encoding="utf-8")
    if relative_path == QUOTA_LEDGER_PATH:
        write_quota_latest(state_dir, merged)
    return {
        "path": relative_path,
        "current": len(current_lines),
        "incoming": len(incoming_lines),
        "merged": len(merged),
        "changed": changed,
        "skipped": False,
    }


def merge_state_dir(root: Path, state_dir: Path, paths: list[str] | tuple[str, ...]) -> list[dict]:
    return [merge_state_file(root, state_dir, path) for path in paths]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("state_dir", help="Temporary state directory captured before git reset.")
    parser.add_argument("paths", nargs="*", help="Relative JSONL paths to merge.")
    parser.add_argument("--root", default=".", help="Repository root after reset to origin/main.")
    args = parser.parse_args()

    paths = tuple(args.paths) or DEFAULT_JSONL_STATE_PATHS
    results = merge_state_dir(Path(args.root), Path(args.state_dir), paths)
    for result in results:
        if result["skipped"]:
            continue
        changed = "changed" if result["changed"] else "unchanged"
        print(
            "jsonl merge: "
            f"{result['path']} current={result['current']} "
            f"incoming={result['incoming']} merged={result['merged']} {changed}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
