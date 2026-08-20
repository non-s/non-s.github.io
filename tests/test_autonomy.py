from __future__ import annotations

import json
from datetime import UTC, datetime

from utils.autonomy import assess_autonomy


def test_default_autonomy_is_shadow_and_allows_work(tmp_path, monkeypatch):
    for name in (
        "LIQUID_WIRE_KILL_SWITCH",
        "LIQUID_WIRE_PUBLICATION_KILL_SWITCH",
        "LIQUID_WIRE_SAFE_MODE",
        "LIQUID_WIRE_EVOLUTION_MODE",
        "LIQUID_WIRE_DISABLE_UPLOAD",
        "LIQUID_WIRE_DISABLE_GEMINI",
        "LIQUID_WIRE_DISABLE_EVOLUTION",
        "LIQUID_WIRE_DISABLE_PUZZLE",
        "LIQUID_WIRE_PAUSE_SCHEDULES",
        "LIQUID_WIRE_FORCE_PRIVATE",
    ):
        monkeypatch.delenv(name, raising=False)
    state = assess_autonomy(tmp_path)
    assert state.generation_allowed is True
    assert state.publication_allowed is True
    assert state.evolution_mode == "shadow"
    assert state.gemini_allowed is True
    assert state.schedules_allowed is True


def test_global_kill_switch_stops_generation_and_publication(tmp_path, monkeypatch):
    monkeypatch.setenv("LIQUID_WIRE_KILL_SWITCH", "1")
    state = assess_autonomy(tmp_path)
    assert state.generation_allowed is False
    assert state.publication_allowed is False


def test_failure_rate_enters_safe_mode_without_stopping_stable_generation(tmp_path, monkeypatch):
    monkeypatch.delenv("LIQUID_WIRE_KILL_SWITCH", raising=False)
    timestamp = datetime.now(UTC).isoformat()
    (tmp_path / "dead_letter_queue.json").write_text(
        json.dumps([{"timestamp": timestamp}] * 3), encoding="utf-8"
    )
    state = assess_autonomy(tmp_path)
    assert state.safe_mode is True
    assert state.generation_allowed is True
    assert state.evolution_mode == "off"
    assert state.puzzles_allowed is False


def test_publication_kill_switch_preserves_offline_generation(tmp_path, monkeypatch):
    monkeypatch.setenv("LIQUID_WIRE_PUBLICATION_KILL_SWITCH", "1")
    state = assess_autonomy(tmp_path)
    assert state.generation_allowed is True
    assert state.publication_allowed is False


def test_historical_duplicate_forces_private_validation_but_allows_recovery(tmp_path, monkeypatch):
    monkeypatch.delenv("LIQUID_WIRE_PUBLICATION_KILL_SWITCH", raising=False)
    (tmp_path / "video_tags.json").write_text(
        json.dumps({"yt1": {"content_id": "lw-x"}, "yt2": {"content_id": "lw-x"}}),
        encoding="utf-8",
    )

    state = assess_autonomy(tmp_path)

    assert state.safe_mode is True
    assert state.force_private is True
    assert state.publication_allowed is True
    assert state.evolution_mode == "off"


def test_independent_kill_switches_are_explicit(tmp_path, monkeypatch):
    monkeypatch.setenv("LIQUID_WIRE_DISABLE_UPLOAD", "1")
    monkeypatch.setenv("LIQUID_WIRE_DISABLE_GEMINI", "1")
    monkeypatch.setenv("LIQUID_WIRE_DISABLE_EVOLUTION", "1")
    monkeypatch.setenv("LIQUID_WIRE_DISABLE_PUZZLE", "1")
    monkeypatch.setenv("LIQUID_WIRE_PAUSE_SCHEDULES", "1")
    monkeypatch.setenv("LIQUID_WIRE_FORCE_PRIVATE", "1")
    state = assess_autonomy(tmp_path)
    assert state.generation_allowed is True
    assert state.publication_allowed is False
    assert state.gemini_allowed is False
    assert state.evolution_mode == "off"
    assert state.puzzles_allowed is False
    assert state.schedules_allowed is False
    assert state.force_private is True
