import json

import scripts.sync_lofi_broll as sync_lofi_broll
from utils.broll import BrollClip


def _clip(clip_id="1", **overrides) -> BrollClip:
    clip = BrollClip(
        source="pexels",
        url=f"https://www.pexels.com/video/{clip_id}",
        download_url=f"https://videos.pexels.com/video-files/{clip_id}/download.mp4",
        width=1080,
        height=1920,
        duration_s=12.0,
        title="rain on window cozy",
        license="Pexels License (free for commercial use)",
        license_evidence=f"https://www.pexels.com/video/{clip_id}",
        source_metadata={
            "pexels_video_id": clip_id,
            "pexels_query": "rain window cozy",
            "photographer": "Some Photographer",
            "photographer_url": "https://www.pexels.com/@someone",
        },
    )
    for key, value in overrides.items():
        setattr(clip, key, value)
    return clip


def test_downloadable_requires_clip_id():
    clip = _clip()
    clip.source_metadata = dict(clip.source_metadata)
    clip.source_metadata["pexels_video_id"] = ""
    assert sync_lofi_broll._downloadable(clip, set()) is False


def test_downloadable_rejects_already_downloaded_clip():
    clip = _clip(clip_id="42")
    assert sync_lofi_broll._downloadable(clip, {"42"}) is False


def test_downloadable_accepts_clean_clip():
    clip = _clip()
    assert sync_lofi_broll._downloadable(clip, set()) is True


def test_download_writes_video_and_attribution_sidecar(tmp_path, monkeypatch):
    monkeypatch.setattr(sync_lofi_broll, "BROLL_DIR", tmp_path)

    def fake_download_clip(clip, dest, max_bytes=None):
        dest.write_bytes(b"fake-mp4-bytes")
        return True

    monkeypatch.setattr(sync_lofi_broll, "download_clip", fake_download_clip)

    clip = _clip(clip_id="99", title="fireplace night cozy")
    assert sync_lofi_broll._download(clip) is True

    video_path = tmp_path / "pexels_99.mp4"
    meta_path = tmp_path / "pexels_99.json"
    assert video_path.read_bytes() == b"fake-mp4-bytes"
    meta = json.loads(meta_path.read_text())
    assert meta["title"] == "fireplace night cozy"
    assert meta["photographer"] == "Some Photographer"
    assert meta["pexels_video_id"] == "99"


def test_download_returns_false_when_download_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(sync_lofi_broll, "BROLL_DIR", tmp_path)
    monkeypatch.setattr(sync_lofi_broll, "download_clip", lambda clip, dest, max_bytes=None: False)

    clip = _clip(clip_id="7")
    assert sync_lofi_broll._download(clip) is False
    assert not (tmp_path / "pexels_7.mp4").exists()
    assert not (tmp_path / "pexels_7.json").exists()


def test_main_downloads_up_to_two_new_clips(tmp_path, monkeypatch):
    monkeypatch.setattr(sync_lofi_broll, "BROLL_DIR", tmp_path)
    candidates = [_clip(clip_id=str(i)) for i in range(1, 6)]
    monkeypatch.setattr(
        sync_lofi_broll, "fetch_broll_clips", lambda query, want_n=4, orientation="portrait": candidates
    )

    def fake_download_clip(clip, dest, max_bytes=None):
        dest.write_bytes(b"x")
        return True

    monkeypatch.setattr(sync_lofi_broll, "download_clip", fake_download_clip)

    assert sync_lofi_broll.main() == 0

    downloaded = list(tmp_path.glob("pexels_*.mp4"))
    assert len(downloaded) == 2
    for video_path in downloaded:
        assert video_path.with_suffix(".json").exists()


def test_main_rotates_out_oldest_clips_when_library_is_full(tmp_path, monkeypatch):
    monkeypatch.setattr(sync_lofi_broll, "BROLL_DIR", tmp_path)
    monkeypatch.setattr(sync_lofi_broll, "MAX_CLIPS", 3)
    for i in range(3):
        (tmp_path / f"pexels_{i}.mp4").write_bytes(b"x")
        (tmp_path / f"pexels_{i}.json").write_text("{}")
    monkeypatch.setattr(sync_lofi_broll, "fetch_broll_clips", lambda query, want_n=4, orientation="portrait": [])

    assert sync_lofi_broll.main() == 0

    assert len(list(tmp_path.glob("pexels_*.mp4"))) == 1
    for video_path in tmp_path.glob("pexels_*.mp4"):
        assert video_path.with_suffix(".json").exists()


def test_main_skips_clips_already_present(tmp_path, monkeypatch):
    monkeypatch.setattr(sync_lofi_broll, "BROLL_DIR", tmp_path)
    (tmp_path / "pexels_1.mp4").write_bytes(b"x")
    (tmp_path / "pexels_1.json").write_text("{}")
    monkeypatch.setattr(
        sync_lofi_broll, "fetch_broll_clips", lambda query, want_n=4, orientation="portrait": [_clip(clip_id="1")]
    )

    assert sync_lofi_broll.main() == 0

    assert len(list(tmp_path.glob("pexels_*.mp4"))) == 1


def test_main_returns_zero_when_no_candidates_found(tmp_path, monkeypatch):
    monkeypatch.setattr(sync_lofi_broll, "BROLL_DIR", tmp_path)
    monkeypatch.setattr(sync_lofi_broll, "fetch_broll_clips", lambda query, want_n=4, orientation="portrait": [])

    assert sync_lofi_broll.main() == 0
    assert list(tmp_path.glob("pexels_*.mp4")) == []
