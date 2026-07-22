"""Tests for scripts/sync_noise_broll.py."""

from __future__ import annotations

import scripts.sync_noise_broll as sync_noise_broll
from utils.broll import BrollClip


def _clip(clip_id="1", tags="nursery, night, soft light", **overrides):
    defaults = dict(
        source="pixabay",
        url="https://pixabay.com/videos/id-1/",
        download_url="https://cdn.pixabay.com/video/large.mp4",
        width=3840,
        height=2160,
        duration_s=12.0,
        title="nursery night",
        license="Pixabay Content License (free for commercial use, no attribution required)",
        license_evidence="https://pixabay.com/videos/id-1/",
        source_metadata={"pixabay_video_id": clip_id, "tags": tags},
    )
    defaults.update(overrides)
    return BrollClip(**defaults)


def test_downloadable_accepts_on_topic_new_clip():
    assert sync_noise_broll._downloadable(_clip(), set()) is True


def test_downloadable_rejects_offtopic_clip():
    clip = _clip(tags="office, business, laptop")
    assert sync_noise_broll._downloadable(clip, set()) is False


def test_downloadable_rejects_missing_clip_id():
    clip = _clip()
    clip.source_metadata["pixabay_video_id"] = ""
    assert sync_noise_broll._downloadable(clip, set()) is False


def test_downloadable_rejects_already_owned_clip():
    assert sync_noise_broll._downloadable(_clip(clip_id="42"), {"42"}) is False


def test_download_writes_sidecar_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(sync_noise_broll, "BROLL_DIR", tmp_path)
    monkeypatch.setattr(sync_noise_broll, "download_clip", lambda clip, dest: dest.write_bytes(b"x") or True)

    clip = _clip(clip_id="99")
    assert sync_noise_broll._download(clip) is True

    meta_path = tmp_path / "pixabay_99.json"
    assert meta_path.exists()
    assert "nursery" in meta_path.read_text(encoding="utf-8")


def test_download_returns_false_when_download_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(sync_noise_broll, "BROLL_DIR", tmp_path)
    monkeypatch.setattr(sync_noise_broll, "download_clip", lambda clip, dest: False)

    assert sync_noise_broll._download(_clip(clip_id="7")) is False
    assert not (tmp_path / "pixabay_7.json").exists()


def test_main_skips_gracefully_when_no_candidates_found(tmp_path, monkeypatch):
    monkeypatch.setattr(sync_noise_broll, "BROLL_DIR", tmp_path)
    monkeypatch.setattr(sync_noise_broll, "search_pixabay", lambda *a, **k: [])

    assert sync_noise_broll.main() == 0


def test_main_rotates_oldest_clips_once_pool_is_full(tmp_path, monkeypatch):
    monkeypatch.setattr(sync_noise_broll, "BROLL_DIR", tmp_path)
    monkeypatch.setattr(sync_noise_broll, "MAX_CLIPS", 2)
    monkeypatch.setattr(sync_noise_broll, "search_pixabay", lambda *a, **k: [])
    for i in range(5):
        video = tmp_path / f"pixabay_{i}.mp4"
        video.write_bytes(b"x")
        video.with_suffix(".json").write_text('{"tags": "night"}', encoding="utf-8")

    sync_noise_broll.main()

    # Pool (5) >= MAX_CLIPS (2) evicts 2 oldest (sync_noise_broll.py's own
    # eviction count, same as the original storm-pillar sync -- not the
    # cute-animal sync's 3) -- see main()'s rotation.
    remaining = list(tmp_path.glob("pixabay_*.mp4"))
    assert len(remaining) == 3
