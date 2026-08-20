from __future__ import annotations

import json
import re
import wave
from pathlib import Path

import numpy as np

import generate_liquid_wire_video as liquid
from utils.liquid_wire_quality import QualityReport
from utils.liquid_wire_timeline import build_timeline


def test_dimensions_match_youtube_format() -> None:
    assert liquid._dimensions_for_preset("short") == (1080, 1920)
    assert liquid._dimensions_for_preset("long") == (1920, 1080)
    assert liquid._dimensions_for_preset("live-test") == (1920, 1080)


def test_profile_is_deterministic_for_seed() -> None:
    assert liquid._profile(123, "short") == liquid._profile(123, "short")


def test_profiles_vary_shape_and_palette() -> None:
    profiles = [liquid._profile(seed, "short") for seed in range(20, 40)]
    families = {profile["family"] for profile in profiles}
    palette_bases = {round(profile["palette"]["base_hue"], 4) for profile in profiles}
    assert len(families) >= 3
    assert len(palette_bases) == len(profiles)
    assert len({profile["music"]["meter"] for profile in profiles}) >= 2
    assert len({profile["material"]["glow_stride"] for profile in profiles}) >= 2


def test_genre_selection_uses_full_catalog() -> None:
    selected = {liquid._pick_genre_for_seed(seed) for seed in range(500)}
    assert len(selected) > liquid._STYLE_DRIFT_SUBSET_SIZE


def test_recent_genre_is_rejected_even_when_visual_family_differs() -> None:
    profile = liquid._profile(321, "short")
    history = [{"family": "different", "genre": profile["genre"], "creative_vector": {}}]
    assert liquid._materially_distinct(profile, history) is False


def test_rupture_opens_real_mesh_gaps() -> None:
    intact = liquid._rupture_visibility(100, {"rupture": 0.0, "direction_x": 1.0, "direction_y": 0.0})
    ruptured = liquid._rupture_visibility(100, {"rupture": 0.9, "direction_x": 1.0, "direction_y": 0.0})
    assert np.all(intact)
    assert 0 < int(np.count_nonzero(~ruptured)) < 30


def test_creative_distance_rejects_near_duplicate() -> None:
    profile = liquid._profile(321, "short")
    history = [
        {
            "family": profile["family"],
            "creative_vector": {
                "hue": profile["palette"]["base_hue"],
                "folds_theta": profile["folds_theta"],
                "folds_phi": profile["folds_phi"],
                "melt_rate": profile["melt_rate"],
            },
        }
    ]
    assert not liquid._materially_distinct(profile, history)


def test_reserve_profile_records_unique_history(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(liquid, "data_dir", lambda: tmp_path)
    first = liquid._reserve_profile("short", 111)
    second_seed = next(seed for seed in range(222, 500) if liquid._profile(seed, "short")["family"] != first["family"])
    second = liquid._reserve_profile("short", second_seed)
    history = json.loads((tmp_path / "generator_history.json").read_text(encoding="utf-8"))
    assert first["signature"] != second["signature"]
    assert [item["seed"] for item in history] == [111, second_seed]


def test_reusing_requested_seed_falls_back_to_random(tmp_path: Path, monkeypatch) -> None:
    """A duplicate requested seed falls back to a fresh random seed.

    Previously _reserve_profile raised ValueError when the requested seed
    was already in the history, which broke scheduled long-form runs
    whose deterministic slot seed collided with an earlier short in the
    same UTC hour, and also broke manual dispatches after any prior
    ad-hoc render. The reservation now continues to the next loop
    iteration with a random seed so the caller still gets a materially
    distinct profile instead of a hard failure.
    """
    monkeypatch.setattr(liquid, "data_dir", lambda: tmp_path)
    first = liquid._reserve_profile("short", 333)
    second = liquid._reserve_profile("short", 333)
    # The second call must not raise; it returns a profile with a
    # different seed/signature drawn at random.
    assert second["signature"] != first["signature"]
    assert second["seed"] != 333


def test_quality_history_is_persisted_and_bounded(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(liquid, "data_dir", lambda: tmp_path)
    report = QualityReport(
        passed=True,
        score=0.95,
        active_ratio=0.1,
        border_activity=0.0,
        motion_signal=2.0,
        color_bins=120,
        sync_signal=0.2,
        audio_channels=2,
        audio_sample_rate=48_000,
        audio_rms_db=-18.0,
        audio_peak=0.8,
        stereo_width=0.12,
        silence_ratio=0.0,
        sampled_frames=16,
        issues=(),
    )
    profile = liquid._profile(555, "short")
    profile.update({"signature": "abc", "engine_version": "2.1"})
    liquid._record_quality(profile, report)
    history = json.loads((tmp_path / "quality_history.json").read_text(encoding="utf-8"))
    assert history[0]["score"] == 0.95
    assert history[0]["engine_version"] == "2.1"


def test_recent_quality_fingerprints_ignore_legacy_entries(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(liquid, "data_dir", lambda: tmp_path)
    (tmp_path / "quality_history.json").write_text(
        json.dumps([{"score": 0.9}, {"fingerprint": [0.1, 0.2, 0.3]}]), encoding="utf-8"
    )
    assert liquid._recent_quality_fingerprints() == [(0.1, 0.2, 0.3)]


def test_metadata_uses_gemini_editorial_result(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        liquid,
        "ai_text",
        lambda *args, **kwargs: json.dumps(
            {
                "title": "A Quiet Current Finds Its Shape #Shorts",
                "description": (
                    "A soft form moves through darkness.\n\n"
                    "Visuals and music are original code-generated work."
                ),
            }
        ),
    )
    profile = liquid._profile(456, "short")
    metadata = liquid._metadata(tmp_path / "video.mp4", tmp_path / "thumb.jpg", 35, "short", profile)
    assert metadata["title"] == "A Quiet Current Finds Its Shape #Shorts"
    assert "original code-generated work" in metadata["description"]


def test_metadata_fallback_has_no_timestamp(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(liquid, "ai_text", lambda *args, **kwargs: None)
    profile = liquid._profile(789, "long")
    metadata = liquid._metadata(tmp_path / "video.mp4", tmp_path / "thumb.jpg", 180, "long", profile)
    assert not re.search(r"\b\d{4}[-/]\d{2}[-/]\d{2}\b|\b\d{1,2}:\d{2}\b", metadata["title"])
    assert metadata["title"] == "A Shape Dreaming in Color | Original Lo-Fi Piano"


def test_frame_background_is_pure_black(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(liquid, "WIDTH", 320)
    monkeypatch.setattr(liquid, "HEIGHT", 180)
    profile = liquid._profile(987, "long")
    events = build_timeline(987, 10.0, profile["music"])
    frame_path = liquid._draw_frame(0, 1, profile, events, tmp_path)
    with liquid.Image.open(frame_path) as frame:
        assert frame.getpixel((0, 0)) == (0, 0, 0)
        assert frame.getpixel((319, 0)) == (0, 0, 0)
        assert frame.getpixel((0, 179)) == (0, 0, 0)
        assert frame.getpixel((319, 179)) == (0, 0, 0)


def test_procedural_score_is_native_stereo(tmp_path: Path) -> None:
    profile = liquid._profile(2468, "short")
    events = build_timeline(2468, 0.25, profile["music"])
    audio = tmp_path / "score.wav"
    liquid._synth_audio(audio, 0.25, 2468, profile, events)
    with wave.open(str(audio), "rb") as score:
        assert score.getnchannels() == 2
        assert score.getframerate() == liquid.SAMPLE_RATE
        assert score.getnframes() == int(0.25 * liquid.SAMPLE_RATE)
