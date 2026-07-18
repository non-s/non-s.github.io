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


def test_pexels_clip_title_uses_descriptive_url_slug():
    title = broll._pexels_clip_title(
        "https://www.pexels.com/video/sea-turtle-over-coral-reef-12345/",
        "Uploader Name",
    )
    assert title == "sea turtle over coral reef"


def test_build_query_strips_stopwords():
    out = broll._build_query("The octopus just changed colour near coral today")
    assert "the" not in out.lower().split()
    assert "octopus" in out
    assert "colour" in out


def test_build_query_empty_input():
    assert broll._build_query("") == ""
    assert broll._build_query(None) == ""


def test_build_query_caps_tokens():
    out = broll._build_query("Octopus Dolphin Whale Owl Eagle Cat Dog Horse Goat")
    assert len(out.split()) <= 6


def _pexels_payload():
    return {
        "videos": [
            {
                "id": 12345,
                "url": "https://www.pexels.com/video/x/",
                "duration": 12,
                "user": {"name": "Test Author", "url": "https://www.pexels.com/@test"},
                "video_files": [
                    {"link": "https://cdn.pexels.com/big.mp4", "width": 1080, "height": 1920},
                    {"link": "https://cdn.pexels.com/small.mp4", "width": 720, "height": 1280},
                ],
            },
        ]
    }


def test_pexels_returns_clips_when_key_set(monkeypatch, tmp_path):
    monkeypatch.setenv("PEXELS_API_KEY", "x")
    monkeypatch.setattr(broll, "_CACHE_DIR", tmp_path / "c")
    fake = MagicMock(status_code=200)
    fake.json.return_value = _pexels_payload()
    with patch.object(broll, "_session") as factory:
        session = MagicMock()
        session.get.return_value = fake
        factory.return_value = session
        clips = broll.fetch_pexels("octopus animal")
    assert len(clips) == 1
    assert clips[0].source == "pexels"
    assert clips[0].download_url.endswith(".mp4")
    assert clips[0].height >= 1920 or clips[0].width >= 1080
    assert clips[0].license_evidence == "https://www.pexels.com/video/x/"
    assert clips[0].source_metadata["pexels_video_id"] == "12345"
    params = session.get.call_args.kwargs["params"]
    assert params["page"] == 1
    assert str(session.get.call_args.args[0]).endswith("/v1/videos/search")


def test_pexels_returns_empty_without_key(monkeypatch):
    monkeypatch.delenv("PEXELS_API_KEY", raising=False)
    assert broll.fetch_pexels("anything") == []


def test_pexels_returns_empty_on_non_200(monkeypatch, tmp_path):
    monkeypatch.setenv("PEXELS_API_KEY", "x")
    monkeypatch.setattr(broll, "_CACHE_DIR", tmp_path / "c")
    fake = MagicMock(status_code=429)
    fake.json.return_value = {}
    with patch.object(broll, "_session") as factory:
        session = MagicMock()
        session.get.return_value = fake
        factory.return_value = session
        assert broll.fetch_pexels("x") == []


def test_pexels_cache_avoids_second_call(monkeypatch, tmp_path):
    monkeypatch.setenv("PEXELS_API_KEY", "x")
    monkeypatch.setattr(broll, "_CACHE_DIR", tmp_path / "c")
    fake = MagicMock(status_code=200)
    fake.json.return_value = _pexels_payload()
    calls = {"n": 0}

    def make_session():
        session = MagicMock()

        def _get(*args, **kwargs):
            calls["n"] += 1
            return fake

        session.get.side_effect = _get
        return session

    with patch.object(broll, "_session", side_effect=make_session):
        broll.fetch_pexels("identical query")
        broll.fetch_pexels("identical query")
    assert calls["n"] == 1


def test_pexels_cache_keeps_pages_separate(monkeypatch, tmp_path):
    monkeypatch.setenv("PEXELS_API_KEY", "x")
    monkeypatch.setattr(broll, "_CACHE_DIR", tmp_path / "c")
    fake = MagicMock(status_code=200)
    fake.json.return_value = _pexels_payload()
    calls = {"n": 0}

    def make_session():
        session = MagicMock()

        def _get(*args, **kwargs):
            calls["n"] += 1
            return fake

        session.get.side_effect = _get
        return session

    with patch.object(broll, "_session", side_effect=make_session):
        broll.fetch_pexels("identical query", page=1)
        broll.fetch_pexels("identical query", page=2)
        broll.fetch_pexels("identical query", page=2)
    assert calls["n"] == 2


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


def test_enabled_sources_is_pexels_only(monkeypatch):
    monkeypatch.setenv("BROLL_SOURCE_MODE", "legacy,backup,pexels")
    assert broll._enabled_sources() == ["pexels"]


def test_fetch_broll_returns_pexels_clips_by_default(monkeypatch):
    fake_pexels = [
        broll.BrollClip(
            source="pexels",
            url="https://www.pexels.com/video/a/",
            download_url=f"https://cdn.pexels.com/video/{i}.mp4",
            width=1080,
            height=1920,
            duration_s=10,
            license="Pexels License",
        )
        for i in range(2)
    ]
    with patch.object(broll, "fetch_pexels", return_value=fake_pexels):
        out = broll.fetch_broll_clips("octopus underwater animal", want_n=3)
    assert len(out) == 2
    assert {clip.source for clip in out} == {"pexels"}


def test_fetch_broll_deduplicates_by_url(monkeypatch):
    same = broll.BrollClip(
        source="pexels",
        url="",
        download_url="https://dup",
        width=1080,
        height=1920,
        duration_s=10,
    )
    with patch.object(broll, "fetch_pexels", return_value=[same, same]):
        out = broll.fetch_broll_clips("x", want_n=5)
    assert len(out) == 1


def test_fetch_broll_returns_empty_on_total_failure(monkeypatch):
    with patch.object(broll, "fetch_pexels", return_value=[]):
        out = broll.fetch_broll_clips("x", want_n=3)
    assert out == []


def test_fetch_broll_animal_only_uses_pexels(monkeypatch):
    pexels = [
        broll.BrollClip(
            source="pexels",
            url="",
            download_url="https://animal",
            width=1080,
            height=1920,
            duration_s=10,
        ),
    ]
    with patch.object(broll, "fetch_pexels", return_value=pexels):
        out = broll.fetch_broll_clips("octopus underwater animal", want_n=3, animal_only=True)
    assert out == pexels


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
