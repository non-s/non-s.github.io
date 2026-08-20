"""Targeted coverage for generate_liquid_wire_video.py uncovered helpers.

Focuses on the pure-logic helpers (style drift, dead letter, slot seed,
durations, profiles/signatures, composition helpers) rather than the
expensive render/ffmpeg paths.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import numpy as np

import generate_liquid_wire_video as liquid
from utils.liquid_wire_timeline import CreativeEvent, build_timeline


def test_load_style_drift_no_file_returns_subset(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(liquid, "data_dir", lambda: tmp_path)
    data = liquid._load_style_drift()
    assert isinstance(data["current_genres"], list)
    assert len(data["current_genres"]) == liquid._STYLE_DRIFT_SUBSET_SIZE
    assert data["rotation"] == 0
    assert data["week_start"]


def test_load_style_drift_with_valid_file(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(liquid, "data_dir", lambda: tmp_path)
    drift = tmp_path / "style_drift.json"
    drift.write_text(
        json.dumps({"current_genres": ["ambient", "cinematic"], "week_start": "2026-01-01", "rotation": 7}),
        encoding="utf-8",
    )
    data = liquid._load_style_drift()
    assert data["current_genres"] == ["ambient", "cinematic"]
    assert data["rotation"] == 7


def test_load_style_drift_drops_unknown_genres(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(liquid, "data_dir", lambda: tmp_path)
    drift = tmp_path / "style_drift.json"
    drift.write_text(
        json.dumps({"current_genres": ["ambient", "nope"], "week_start": "2026-01-01", "rotation": 1}),
        encoding="utf-8",
    )
    data = liquid._load_style_drift()
    assert data["current_genres"] == ["ambient"]


def test_load_style_drift_corrupt_file_falls_back(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(liquid, "data_dir", lambda: tmp_path)
    (tmp_path / "style_drift.json").write_text("not json", encoding="utf-8")
    data = liquid._load_style_drift()
    assert data["rotation"] == 0
    assert len(data["current_genres"]) == liquid._STYLE_DRIFT_SUBSET_SIZE


def test_load_style_drift_empty_subset_falls_back(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(liquid, "data_dir", lambda: tmp_path)
    drift = tmp_path / "style_drift.json"
    drift.write_text(
        json.dumps({"current_genres": ["totally_unknown"], "week_start": "2026-01-01", "rotation": 3}),
        encoding="utf-8",
    )
    data = liquid._load_style_drift()
    assert data["rotation"] == 0


def test_update_style_drift_rotation_increments(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(liquid, "data_dir", lambda: tmp_path)
    first = liquid._update_style_drift(force=True)
    second = liquid._update_style_drift(force=True)
    assert second["rotation"] == first["rotation"] + 1
    assert set(first["current_genres"]) != set(second["current_genres"])


def test_update_style_drift_no_rotation_when_recent(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(liquid, "data_dir", lambda: tmp_path)
    today = liquid._today_date()
    (tmp_path / "style_drift.json").write_text(
        json.dumps({"current_genres": ["ambient", "cinematic", "blues", "jazz"], "week_start": today, "rotation": 5}),
        encoding="utf-8",
    )
    data = liquid._update_style_drift(force=False)
    assert data["rotation"] == 5
    assert data["current_genres"] == ["ambient", "cinematic", "blues", "jazz"]


def test_pick_genre_for_seed_determinism(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(liquid, "data_dir", lambda: tmp_path)
    liquid._update_style_drift(force=True)
    assert liquid._pick_genre_for_seed(123) == liquid._pick_genre_for_seed(123)


def test_current_genres_with_and_without_file(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(liquid, "data_dir", lambda: tmp_path)
    assert liquid._current_genres()
    drift = tmp_path / "style_drift.json"
    drift.write_text(
        json.dumps({"current_genres": ["ambient", "jazz"], "week_start": liquid._today_date(), "rotation": 1}),
        encoding="utf-8",
    )
    assert liquid._current_genres() == ["ambient", "jazz"]


def test_current_genres_empty_falls_back_to_default(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(liquid, "data_dir", lambda: tmp_path)
    drift = tmp_path / "style_drift.json"
    drift.write_text(
        json.dumps({"current_genres": ["missing"], "week_start": liquid._today_date(), "rotation": 1}),
        encoding="utf-8",
    )
    genres = liquid._current_genres()
    assert genres == sorted(liquid.GENRES.keys())[: liquid._STYLE_DRIFT_SUBSET_SIZE]


def test_short_duration_for_slot_range_and_determinism(monkeypatch) -> None:
    monkeypatch.setenv("LIQUID_WIRE_SLOT", "coverage_slot")
    d1 = liquid._short_duration_for_slot()
    d2 = liquid._short_duration_for_slot()
    assert 27.0 <= d1 <= 60.0
    assert d1 == d2


def test_short_duration_for_slot_without_env_var(monkeypatch) -> None:
    monkeypatch.delenv("LIQUID_WIRE_SLOT", raising=False)
    d = liquid._short_duration_for_slot()
    assert 27.0 <= d <= 60.0


def test_slot_seed_with_env_var(monkeypatch) -> None:
    monkeypatch.setenv("LIQUID_WIRE_SLOT", "abc")
    s1 = liquid._slot_seed()
    s2 = liquid._slot_seed()
    assert s1 == s2
    assert 0 <= s1 < 2**32


def test_slot_seed_without_env_var(monkeypatch) -> None:
    monkeypatch.delenv("LIQUID_WIRE_SLOT", raising=False)
    s = liquid._slot_seed()
    assert 0 <= s < 2**32


def test_dimensions_for_preset_returns_1080p() -> None:
    assert liquid._dimensions_for_preset("short") == (1080, 1920)
    assert liquid._dimensions_for_preset("long") == (1920, 1080)
    assert liquid._dimensions_for_preset("live-test") == (1920, 1080)


def test_profile_includes_genre_field() -> None:
    profile = liquid._profile(42, "short")
    assert "genre" in profile
    assert profile["genre"] in set(liquid.GENRES.keys())
    assert profile["seed"] == 42
    assert profile["preset"] == "short"


def test_signature_is_deterministic() -> None:
    p = liquid._profile(777, "short")
    assert liquid._signature(p) == liquid._signature(p)
    assert len(liquid._signature(p)) == 16


def test_materially_distinct_empty_history_is_true() -> None:
    profile = liquid._profile(11, "short")
    assert liquid._materially_distinct(profile, []) is True


def test_materially_distinct_rejects_recent_same_family() -> None:
    profile = liquid._profile(11, "short")
    history = [{"family": profile["family"], "creative_vector": {}}]
    assert liquid._materially_distinct(profile, history) is False


def test_materially_distinct_rejects_similar_hue_and_topology() -> None:
    profile = liquid._profile(11, "short")
    history = [
        {
            "family": profile["family"],
            "creative_vector": {
                "hue": profile["palette"]["base_hue"],
                "folds_theta": profile["folds_theta"],
                "folds_phi": profile["folds_phi"],
            },
        }
    ]
    assert liquid._materially_distinct(profile, history) is False


def test_materially_distinct_accepts_different_family() -> None:
    profile = liquid._profile(11, "short")
    other = liquid._profile(22, "short")
    if other["family"] == profile["family"]:
        return
    history = [{"family": other["family"], "creative_vector": {"hue": other["palette"]["base_hue"]}}]
    assert liquid._materially_distinct(profile, history) is True


def test_record_dead_letter_writes_to_queue(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(liquid, "data_dir", lambda: tmp_path)
    with patch("utils.notifier.send_alert"):
        liquid._record_dead_letter("slot-x", 1, "err", {"family": "orb", "genre": "ambient"})
    queue = json.loads((tmp_path / "dead_letter_queue.json").read_text(encoding="utf-8"))
    assert queue[0]["slot"] == "slot-x"
    assert queue[0]["family"] == "orb"


def test_bus_for_role_known_and_unknown() -> None:
    assert liquid._bus_for_role("lead") == "lead"
    assert liquid._bus_for_role("pad") == "pads"
    assert liquid._bus_for_role("bass") == "bass"
    assert liquid._bus_for_role("drums") == "drums"
    assert liquid._bus_for_role("weird_unknown_role") == "lead"


def test_bus_for_role_heuristic_fallbacks() -> None:
    assert liquid._bus_for_role("sub_bass_thing") == "bass"
    assert liquid._bus_for_role("snare_drum") == "drums"
    assert liquid._bus_for_role("warm_pad") == "pads"
    assert liquid._bus_for_role("rhythm_guitar") == "guitar"
    assert liquid._bus_for_role("grand_piano") == "keys"


def test_voice_for_role_mapping() -> None:
    assert liquid._voice_for_role("bass") == "bass"
    assert liquid._voice_for_role("drone") == "bass"
    assert liquid._voice_for_role("lead") == "motif"
    assert liquid._voice_for_role("strings") == "motif"
    assert liquid._voice_for_role("pad") == "pad"
    assert liquid._voice_for_role("choir") == "pad"
    assert liquid._voice_for_role("unknown_role") == "motif"


def test_duration_of_buffer() -> None:
    assert liquid.duration_of_buffer(44100, 44100) == 1.0
    assert liquid.duration_of_buffer(88200, 44100) == 2.0


def test_event_dynamics_envelope_shape_and_effects() -> None:
    events = build_timeline(5, 5.0, {"beat_seconds": 1.0, "meter": 4})
    env = liquid._event_dynamics_envelope(5.0, events)
    assert env.shape[0] == int(5.0 * liquid.SAMPLE_RATE)
    assert np.all(env <= 1.2)
    assert np.all(env >= 0.0)


def test_event_dynamics_envelope_stillness_ducks() -> None:
    still = CreativeEvent(
        kind="stillness", start=0.5, duration=1.0, intensity=1.0, direction=0.0, pitch_offset=0
    )
    env = liquid._event_dynamics_envelope(2.0, [still])
    assert env.shape[0] == int(2.0 * liquid.SAMPLE_RATE)
    assert env.min() < 1.0


def test_events_to_dicts_and_from_dicts_roundtrip() -> None:
    events = build_timeline(3, 4.0, {"beat_seconds": 1.0, "meter": 4})
    payload = liquid._events_to_dicts(events)
    assert isinstance(payload, list) and payload
    restored = liquid._events_from_dicts(payload)
    assert len(restored) == len(events)
    assert restored[0].kind == events[0].kind


def test_worker_count_bounded() -> None:
    assert 1 <= liquid._worker_count() <= 8


def test_metadata_json_decode_error_falls_back(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(liquid, "ai_text", lambda *a, **k: "not json{")
    profile = liquid._profile(9, "short")
    meta = liquid._metadata(tmp_path / "v.mp4", tmp_path / "t.jpg", 30.0, "short", profile)
    assert meta["title"]
    assert meta["visual_source"] == "procedural_python"
    assert meta["audio_source"] == "synthetic_python"


def test_metadata_rejects_repeated_gemini_title(monkeypatch, tmp_path: Path) -> None:
    repeated = "A Quiet Current Finds Its Shape #Shorts"
    monkeypatch.setattr(
        liquid,
        "ai_text",
        lambda *a, **k: json.dumps({
            "title": repeated,
            "description": "Original code-generated visuals and music move through darkness.",
        }),
    )
    monkeypatch.setattr(liquid, "title_is_too_repetitive", lambda title: title == repeated)
    profile = liquid._profile(91, "short")

    meta = liquid._metadata(tmp_path / "v.mp4", tmp_path / "t.jpg", 30.0, "short", profile)

    assert meta["title"] != repeated
    assert meta["title"].endswith("#Shorts")


def test_metadata_short_has_shorts_hashtag(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(liquid, "ai_text", lambda *a, **k: None)
    profile = liquid._profile(9, "short")
    meta = liquid._metadata(tmp_path / "v.mp4", tmp_path / "t.jpg", 30.0, "short", profile)
    assert "#Shorts" in meta["hashtags"]


def test_metadata_long_has_no_shorts_hashtag(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(liquid, "ai_text", lambda *a, **k: None)
    profile = liquid._profile(9, "long")
    meta = liquid._metadata(tmp_path / "v.mp4", tmp_path / "t.jpg", 180.0, "long", profile)
    assert "#Shorts" not in meta["hashtags"]
