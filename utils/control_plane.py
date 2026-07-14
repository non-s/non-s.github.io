"""Control-plane pressure report for live operational state."""

from __future__ import annotations

from pathlib import Path

LIVE_ROOTS = ("_data", "_videos")
STATE_SUFFIXES = {".json", ".jsonl", ".csv", ".md", ".done", ".txt"}


def _safe_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _safe_lines(path: Path, limit_bytes: int = 3_000_000) -> int:
    if not path.exists() or _safe_size(path) > limit_bytes:
        return 0
    try:
        return len(path.read_text(encoding="utf-8", errors="ignore").splitlines())
    except OSError:
        return 0


def _rel(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _live_state_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for name in LIVE_ROOTS:
        base = root / name
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and path.suffix.lower() in STATE_SUFFIXES:
                files.append(path)
    return files


def _workflow_state_refs(root: Path) -> dict:
    refs = 0
    files = 0
    workflow_dir = root / ".github" / "workflows"
    for path in workflow_dir.glob("*.yml") if workflow_dir.exists() else []:
        text = path.read_text(encoding="utf-8", errors="ignore")
        refs += text.count("_data/") + text.count("_videos/")
        files += 1
    return {"workflow_files": files, "state_path_refs": refs}


def build_control_plane_report(root: Path | str = ".") -> dict:
    root = Path(root).resolve()
    live_files = _live_state_files(root)
    total_bytes = sum(_safe_size(path) for path in live_files)
    queue = root / "_data" / "stories_queue.json"
    queue_bytes = _safe_size(queue)
    queue_lines = _safe_lines(queue)
    data_files = [path for path in live_files if "_data" in path.parts]
    video_markers = [path for path in live_files if path.suffix.lower() == ".done"]
    workflow_refs = _workflow_state_refs(root)
    largest = sorted(live_files, key=_safe_size, reverse=True)[:12]

    pressure = 0
    pressure += 25 if len(data_files) >= 80 else (15 if len(data_files) >= 45 else 0)
    pressure += 25 if queue_bytes >= 1_000_000 else (12 if queue_bytes >= 500_000 else 0)
    pressure += 20 if workflow_refs["state_path_refs"] >= 100 else (10 if workflow_refs["state_path_refs"] >= 50 else 0)
    pressure += 15 if len(video_markers) >= 100 else (8 if len(video_markers) >= 30 else 0)
    pressure += 15 if total_bytes >= 12_000_000 else (8 if total_bytes >= 5_000_000 else 0)
    pressure = min(100, pressure)

    if pressure >= 70:
        state = "migration_needed"
    elif pressure >= 35:
        state = "watch"
    else:
        state = "ok"

    return {
        "state": state,
        "pressure_score": pressure,
        "metrics": {
            "live_state_files": len(live_files),
            "data_state_files": len(data_files),
            "video_done_markers": len(video_markers),
            "live_state_bytes": total_bytes,
            "stories_queue_bytes": queue_bytes,
            "stories_queue_lines": queue_lines,
            **workflow_refs,
        },
        "largest_state_files": [
            {"path": _rel(root, path), "bytes": _safe_size(path), "lines": _safe_lines(path)} for path in largest
        ],
        "migration_lanes": [
            {
                "lane": "queue_and_upload_intents",
                "target": "Firebase/Firestore collections keyed by channel, language, state, and publish window",
                "reason": "Queue and upload state change every run and should not be merged through Git.",
                "priority": 1,
            },
            {
                "lane": "raw_analytics_and_ledgers",
                "target": "Object storage plus compacted daily snapshots committed to Git",
                "reason": "Append-heavy JSONL/CSV data creates repository churn and merge pressure.",
                "priority": 2,
            },
            {
                "lane": "workflow_runtime_state",
                "target": "External run ledger with Git storing reports, not live locks",
                "reason": "Operational locks, quota ledgers, and markers are control-plane state.",
                "priority": 3,
            },
        ],
        "commands": [
            "Keep Git for code, dashboards, and reviewed daily/weekly snapshots.",
            "Move queue, upload intents, raw analytics, quota ledgers, and run markers behind a storage adapter.",
            "Block new features that add live-state files without a migration lane.",
        ],
    }
