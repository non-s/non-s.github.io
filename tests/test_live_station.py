from __future__ import annotations

import json
from pathlib import Path

from utils.live_station import build_station_plan


def _asset(tmp_path: Path, name: str, metadata: dict) -> Path:
    path = tmp_path / name
    path.write_bytes(b"")
    path.with_suffix(".json").write_text(json.dumps(metadata), encoding="utf-8")
    return path


def test_station_requires_verified_rights_and_builds_diverse_sessions(tmp_path: Path) -> None:
    audio = _asset(
        tmp_path,
        "approved.mp3",
        {
            "name": "Dawn",
            "artist_name": "Artist",
            "license_verified_for_youtube": True,
            "license_url": "https://lic",
        },
    )
    video = _asset(
        tmp_path,
        "rabbit.mp4",
        {"user": "Maker", "source_url": "https://source", "license": "Pixabay Content License"},
    )
    plan = build_station_plan([audio], [video], target_tracks=5)
    assert len(plan["segments"]) == 5
    assert plan["ready_for_broadcast"] is False
    assert len(plan["session_mix"]) == 5


def test_station_rejects_assets_without_explicit_live_rights(tmp_path: Path) -> None:
    audio = _asset(tmp_path, "unknown.mp3", {"name": "Unknown"})
    video = _asset(tmp_path, "unknown.mp4", {})
    plan = build_station_plan([audio], [video], target_tracks=1)
    assert plan["segments"] == []
    assert plan["approved_unique_tracks"] == 0
    assert plan["requirements"]["additional_verified_tracks_needed"] == 1
