from __future__ import annotations

import json

from utils.autonomy import assess_autonomy


def test_default_autonomy_is_shadow_and_allows_work(tmp_path, monkeypatch):
    for name in (
        "LIQUID_WIRE_KILL_SWITCH",
        "LIQUID_WIRE_PUBLICATION_KILL_SWITCH",
        "LIQUID_WIRE_SAFE_MODE",
        "LIQUID_WIRE_EVOLUTION_MODE",
    ):
        monkeypatch.delenv(name, raising=False)
    state = assess_autonomy(tmp_path)
    assert state.generation_allowed is True
    assert state.publication_allowed is True
    assert state.evolution_mode == "shadow"


def test_global_kill_switch_stops_generation_and_publication(tmp_path, monkeypatch):
    monkeypatch.setenv("LIQUID_WIRE_KILL_SWITCH", "1")
    state = assess_autonomy(tmp_path)
    assert state.generation_allowed is False
    assert state.publication_allowed is False


def test_failure_rate_enters_safe_mode_without_stopping_stable_generation(tmp_path, monkeypatch):
    monkeypatch.delenv("LIQUID_WIRE_KILL_SWITCH", raising=False)
    (tmp_path / "dead_letter_queue.json").write_text(json.dumps([{}] * 3), encoding="utf-8")
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
