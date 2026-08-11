from __future__ import annotations

import json

from utils import story_engine


def test_story_card_has_proprietary_series_and_community_prompt(tmp_path, monkeypatch):
    monkeypatch.setattr(story_engine, "_memory_file", lambda: tmp_path / "story_memory.json")
    card = story_engine.choose_story_card("cat relaxing", "relax", "A cozy cat")
    assert card["id"]
    assert card["community_prompt"]
    assert card["visual_direction"]


def test_story_rotation_avoids_recent_series(tmp_path, monkeypatch):
    path = tmp_path / "story_memory.json"
    monkeypatch.setattr(story_engine, "_memory_file", lambda: path)
    path.write_text(json.dumps(["window-seat-sessions"]))
    for _ in range(20):
        assert story_engine.choose_story_card("cat relaxing", "relax", "A cozy cat")["id"] != "window-seat-sessions"


def test_record_story_card_keeps_latest_first(tmp_path, monkeypatch):
    path = tmp_path / "story_memory.json"
    monkeypatch.setattr(story_engine, "_memory_file", lambda: path)
    story_engine.record_story_card({"id": "tiny-rituals"})
    story_engine.record_story_card({"id": "golden-hour-paws"})
    assert json.loads(path.read_text())[:2] == ["golden-hour-paws", "tiny-rituals"]
