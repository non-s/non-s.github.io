#!/usr/bin/env python3
"""Create weighted operator actions from the session graph."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def build_actions(root: Path = ROOT) -> dict:
    graph = _read_json(root / "_data" / "session_graph.json", {})
    actions = []
    for edge in graph.get("edges") or []:
        weight = float(edge.get("score") or 0)
        if weight < 55:
            continue
        actions.append(
            {
                "source_video_id": edge.get("source_video_id", ""),
                "target_video_id": edge.get("target_video_id", ""),
                "edge_weight": weight,
                "action": "add_related_pin_or_playlist_link",
                "priority": "high" if weight >= 75 else "normal",
            }
        )
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "actions": actions[:40]}
    out = root / "_data" / "session_graph_actions.json"
    out.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = build_actions(Path(args.root).resolve())
    print(
        json.dumps(report, sort_keys=True, ensure_ascii=False)
        if args.json
        else f"session_graph_actioner: {len(report['actions'])} actions"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
