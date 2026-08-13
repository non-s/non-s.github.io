from __future__ import annotations

import json
import re
from pathlib import Path

import generate_liquid_wire_video as liquid


def test_dimensions_match_youtube_format() -> None:
    assert liquid._dimensions_for_preset("short") == (720, 1280)
    assert liquid._dimensions_for_preset("long") == (1280, 720)
    assert liquid._dimensions_for_preset("live-test") == (1280, 720)


def test_profile_is_deterministic_for_seed() -> None:
    assert liquid._profile(123, "short") == liquid._profile(123, "short")


def test_profiles_vary_shape_and_palette() -> None:
    profiles = [liquid._profile(seed, "short") for seed in range(20, 40)]
    families = {profile["family"] for profile in profiles}
    palette_bases = {round(profile["palette"]["base_hue"], 4) for profile in profiles}
    assert len(families) >= 3
    assert len(palette_bases) == len(profiles)
    assert len({profile["music"]["meter"] for profile in profiles}) >= 2


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


def test_reusing_requested_seed_fails(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(liquid, "data_dir", lambda: tmp_path)
    liquid._reserve_profile("short", 333)
    try:
        liquid._reserve_profile("short", 333)
    except ValueError as exc:
        assert "Seed already used" in str(exc)
    else:
        raise AssertionError("Expected duplicate seed to fail")


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
    frame_path = liquid._draw_frame(0, 1, profile, tmp_path)
    with liquid.Image.open(frame_path) as frame:
        assert frame.getpixel((0, 0)) == (0, 0, 0)
        assert frame.getpixel((319, 0)) == (0, 0, 0)
        assert frame.getpixel((0, 179)) == (0, 0, 0)
        assert frame.getpixel((319, 179)) == (0, 0, 0)
