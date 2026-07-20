"""Tests for utils/broll.py discovery + download, with no live HTTP."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from utils import broll


def test_looks_anime_styled_accepts_any_signal_keyword():
    for tag in ["anime", "Cartoon", "manga girl", "kawaii style", "hand-drawn loop"]:
        assert broll.looks_anime_styled(tag) is True


def test_looks_anime_styled_rejects_generic_stock_tags():
    assert broll.looks_anime_styled("man, train, window, business, office") is False


def test_looks_anime_styled_handles_empty_input():
    assert broll.looks_anime_styled("") is False
    assert broll.looks_anime_styled(None) is False


def test_is_on_brand_broll_clip_accepts_anime_tagged_sidecar(tmp_path):
    video_path = tmp_path / "pixabay_1.mp4"
    video_path.write_bytes(b"x")
    video_path.with_suffix(".json").write_text(json.dumps({"tags": "anime, girl, study, lofi"}))
    assert broll.is_on_brand_broll_clip(video_path) is True


def test_is_on_brand_broll_clip_rejects_offbrand_sidecar(tmp_path):
    video_path = tmp_path / "pixabay_1.mp4"
    video_path.write_bytes(b"x")
    video_path.with_suffix(".json").write_text(json.dumps({"tags": "man, library, book"}))
    assert broll.is_on_brand_broll_clip(video_path) is False


def test_is_on_brand_broll_clip_rejects_missing_sidecar(tmp_path):
    video_path = tmp_path / "pixabay_1.mp4"
    video_path.write_bytes(b"x")
    assert broll.is_on_brand_broll_clip(video_path) is False


def test_is_on_brand_broll_clip_rejects_corrupt_sidecar(tmp_path):
    video_path = tmp_path / "pixabay_1.mp4"
    video_path.write_bytes(b"x")
    video_path.with_suffix(".json").write_text("not json")
    assert broll.is_on_brand_broll_clip(video_path) is False


def _write_clip(directory, name, query, tags="anime, cozy"):
    video_path = directory / name
    video_path.write_bytes(b"x")
    video_path.with_suffix(".json").write_text(json.dumps({"query": query, "tags": tags}))
    return video_path


def test_is_preferred_mood_clip_matches_rain_night_snow_queries(tmp_path):
    rain = _write_clip(tmp_path, "pixabay_1.mp4", "anime rain window cozy")
    night = _write_clip(tmp_path, "pixabay_2.mp4", "anime night city window")
    snow = _write_clip(tmp_path, "pixabay_3.mp4", "anime snow window night")
    cat = _write_clip(tmp_path, "pixabay_4.mp4", "anime cat sleeping cozy")
    assert broll.is_preferred_mood_clip(rain) is True
    assert broll.is_preferred_mood_clip(night) is True
    assert broll.is_preferred_mood_clip(snow) is True
    assert broll.is_preferred_mood_clip(cat) is False


def test_pick_weighted_broll_file_returns_none_when_directory_empty(tmp_path):
    assert broll.pick_weighted_broll_file(tmp_path, "pixabay_*.mp4") is None


def test_pick_weighted_broll_file_skips_offbrand_clips(tmp_path):
    _write_clip(tmp_path, "pixabay_1.mp4", "man library book", tags="man, library, book")
    assert broll.pick_weighted_broll_file(tmp_path, "pixabay_*.mp4") is None


def test_pick_weighted_broll_file_favors_preferred_mood_over_many_trials(tmp_path):
    rain = _write_clip(tmp_path, "pixabay_1.mp4", "anime rain window cozy")
    cat = _write_clip(tmp_path, "pixabay_2.mp4", "anime cat sleeping cozy")
    picks = [broll.pick_weighted_broll_file(tmp_path, "pixabay_*.mp4") for _ in range(400)]
    rain_count = picks.count(rain)
    cat_count = picks.count(cat)
    assert rain_count + cat_count == 400
    # weighted 3:1 -- allow a wide margin so this isn't flaky, just checks
    # the preferred clip clearly dominates rather than a coin flip.
    assert rain_count > cat_count * 1.5


def test_pick_weighted_broll_file_applies_real_performance_weight_on_top(tmp_path):
    """A clip in a real-performance-boosted bucket should win far more
    often than the fixed 3:1 editorial bias alone would predict, once a
    performance_weights multiplier is supplied for its bucket."""
    cozy_cat = _write_clip(tmp_path, "pixabay_1.mp4", "anime cat sleeping cozy")  # "Cozy Cat Lofi" bucket, base=1
    rain = _write_clip(tmp_path, "pixabay_2.mp4", "anime rain window cozy")  # "Rainy Night Lofi" bucket, base=3

    # Without any performance data: rain (weight 3) beats cat (weight 1).
    picks = [broll.pick_weighted_broll_file(tmp_path, "pixabay_*.mp4", performance_weights={}) for _ in range(400)]
    assert picks.count(rain) > picks.count(cozy_cat)

    # With cat's bucket boosted 2x and rain's bucket cut to 0.5x, cat should
    # now win instead (1*2=2 vs 3*0.5=1.5).
    boosted = {"Cozy Cat Lofi": 2.0, "Rainy Night Lofi": 0.5}
    picks = [broll.pick_weighted_broll_file(tmp_path, "pixabay_*.mp4", performance_weights=boosted) for _ in range(400)]
    assert picks.count(cozy_cat) > picks.count(rain)


def test_pick_weighted_broll_file_defaults_to_mood_performance_weights(tmp_path, monkeypatch):
    """When performance_weights isn't given, it should be computed via
    utils.broll_performance.mood_performance_weights() rather than always
    behaving as if no performance data exists."""
    clip = _write_clip(tmp_path, "pixabay_1.mp4", "anime rain window cozy")
    monkeypatch.setattr(broll, "mood_performance_weights", lambda: {"Rainy Night Lofi": 5.0})

    # Just needs to not blow up and still return the only candidate --
    # the weight value itself doesn't change the outcome with one clip.
    assert broll.pick_weighted_broll_file(tmp_path, "pixabay_*.mp4") == clip


def _pixabay_payload():
    return {
        "hits": [
            {
                "id": 214500,
                "pageURL": "https://pixabay.com/videos/id-214500/",
                "type": "animation",
                "tags": "girl, study, relaxing, anime, lofi",
                "duration": 63,
                "isAiGenerated": True,
                "user": "Earth_to_Infinity",
                "userURL": "https://pixabay.com/users/42093275/",
                "videos": {
                    "large": {"url": "https://cdn.pixabay.com/video/large.mp4", "width": 3840, "height": 2160},
                    "medium": {"url": "https://cdn.pixabay.com/video/medium.mp4", "width": 2560, "height": 1440},
                },
            },
        ]
    }


def test_pixabay_returns_clips_when_key_set(monkeypatch, tmp_path):
    monkeypatch.setenv("PIXABAY_API_KEY", "x")
    monkeypatch.setattr(broll, "_CACHE_DIR", tmp_path / "c")
    fake = MagicMock(status_code=200)
    fake.json.return_value = _pixabay_payload()
    with patch.object(broll, "_session") as factory:
        session = MagicMock()
        session.get.return_value = fake
        factory.return_value = session
        clips = broll.fetch_pixabay("anime lofi girl study")
    assert len(clips) == 1
    clip = clips[0]
    assert clip.source == "pixabay"
    assert clip.download_url == "https://cdn.pixabay.com/video/medium.mp4"
    assert clip.title == "girl"
    assert clip.license_evidence == "https://pixabay.com/videos/id-214500/"
    assert clip.source_metadata["pixabay_video_id"] == "214500"
    assert clip.source_metadata["is_ai_generated"] is True
    params = session.get.call_args.kwargs["params"]
    assert params["video_type"] == "animation"
    assert str(session.get.call_args.args[0]).endswith("/api/videos/")


def test_pixabay_falls_back_to_large_when_medium_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("PIXABAY_API_KEY", "x")
    monkeypatch.setattr(broll, "_CACHE_DIR", tmp_path / "c")
    payload = _pixabay_payload()
    del payload["hits"][0]["videos"]["medium"]
    fake = MagicMock(status_code=200)
    fake.json.return_value = payload
    with patch.object(broll, "_session") as factory:
        session = MagicMock()
        session.get.return_value = fake
        factory.return_value = session
        clips = broll.fetch_pixabay("anime lofi")
    assert clips[0].download_url == "https://cdn.pixabay.com/video/large.mp4"


def test_pixabay_returns_empty_without_key(monkeypatch):
    monkeypatch.delenv("PIXABAY_API_KEY", raising=False)
    assert broll.fetch_pixabay("anything") == []


def test_pixabay_returns_empty_on_non_200(monkeypatch, tmp_path):
    monkeypatch.setenv("PIXABAY_API_KEY", "x")
    monkeypatch.setattr(broll, "_CACHE_DIR", tmp_path / "c")
    fake = MagicMock(status_code=400)
    fake.json.return_value = {}
    with patch.object(broll, "_session") as factory:
        session = MagicMock()
        session.get.return_value = fake
        factory.return_value = session
        assert broll.fetch_pixabay("x") == []


def test_pixabay_cache_avoids_second_call(monkeypatch, tmp_path):
    monkeypatch.setenv("PIXABAY_API_KEY", "x")
    monkeypatch.setattr(broll, "_CACHE_DIR", tmp_path / "c")
    fake = MagicMock(status_code=200)
    fake.json.return_value = _pixabay_payload()
    calls = {"n": 0}

    def make_session():
        session = MagicMock()

        def _get(*args, **kwargs):
            calls["n"] += 1
            return fake

        session.get.side_effect = _get
        return session

    with patch.object(broll, "_session", side_effect=make_session):
        broll.fetch_pixabay("identical query")
        broll.fetch_pixabay("identical query")
    assert calls["n"] == 1


def test_download_clip_writes_valid_mp4(tmp_path):
    dest = tmp_path / "out.mp4"
    body = b"\x00\x00\x00\x18ftypmp42" + b"x" * 60_000
    fake = MagicMock(status_code=200)
    fake.iter_content.return_value = [body]
    clip = broll.BrollClip(
        source="test",
        url="",
        download_url="https://e/x.mp4",
        width=1080,
        height=1920,
        duration_s=10,
    )
    with patch.object(broll, "_session") as factory:
        session = MagicMock()
        session.get.return_value = fake
        factory.return_value = session
        ok = broll.download_clip(clip, dest)
    assert ok
    assert dest.exists()
    assert dest.read_bytes().startswith(b"\x00\x00\x00\x18ftyp")


def test_download_clip_rejects_non_mp4(tmp_path):
    dest = tmp_path / "out.mp4"
    body = b"<html>not a video</html>" * 1000
    fake = MagicMock(status_code=200)
    fake.iter_content.return_value = [body]
    clip = broll.BrollClip(source="test", url="", download_url="https://e/x.mp4", width=1, height=1, duration_s=10)
    with patch.object(broll, "_session") as factory:
        session = MagicMock()
        session.get.return_value = fake
        factory.return_value = session
        assert not broll.download_clip(clip, dest, max_bytes=30 * 1024 * 1024)


def test_download_clip_aborts_oversized(tmp_path):
    dest = tmp_path / "out.mp4"
    chunks = [b"a" * (1024 * 1024) for _ in range(35)]
    fake = MagicMock(status_code=200)
    fake.iter_content.return_value = chunks
    clip = broll.BrollClip(source="test", url="", download_url="https://e/x.mp4", width=1, height=1, duration_s=10)
    with patch.object(broll, "_session") as factory:
        session = MagicMock()
        session.get.return_value = fake
        factory.return_value = session
        assert not broll.download_clip(clip, dest)
