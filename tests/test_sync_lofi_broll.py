import json

import scripts.sync_lofi_broll as sync_lofi_broll
from utils.broll import BrollClip


def _clip(clip_id="1", **overrides) -> BrollClip:
    clip = BrollClip(
        source="pixabay",
        url=f"https://pixabay.com/videos/id-{clip_id}/",
        download_url=f"https://cdn.pixabay.com/video/{clip_id}/large.mp4",
        width=3840,
        height=2160,
        duration_s=12.0,
        title="girl",
        license="Pixabay Content License (free for commercial use, no attribution required)",
        license_evidence=f"https://pixabay.com/videos/id-{clip_id}/",
        source_metadata={
            "pixabay_video_id": clip_id,
            "pixabay_query": "anime lofi girl study",
            "photographer": "Some Uploader",
            "photographer_url": "https://pixabay.com/users/someone/",
            "is_ai_generated": True,
        },
    )
    for key, value in overrides.items():
        setattr(clip, key, value)
    return clip


def test_downloadable_requires_clip_id():
    clip = _clip()
    clip.source_metadata = dict(clip.source_metadata)
    clip.source_metadata["pixabay_video_id"] = ""
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

    clip = _clip(clip_id="99", title="anime girl studying")
    assert sync_lofi_broll._download(clip) is True

    video_path = tmp_path / "pixabay_99.mp4"
    meta_path = tmp_path / "pixabay_99.json"
    assert video_path.read_bytes() == b"fake-mp4-bytes"
    meta = json.loads(meta_path.read_text())
    assert meta["title"] == "anime girl studying"
    assert meta["photographer"] == "Some Uploader"
    assert meta["pixabay_video_id"] == "99"
    assert meta["is_ai_generated"] is True


def test_download_returns_false_when_download_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(sync_lofi_broll, "BROLL_DIR", tmp_path)
    monkeypatch.setattr(sync_lofi_broll, "download_clip", lambda clip, dest, max_bytes=None: False)

    clip = _clip(clip_id="7")
    assert sync_lofi_broll._download(clip) is False
    assert not (tmp_path / "pixabay_7.mp4").exists()
    assert not (tmp_path / "pixabay_7.json").exists()


def test_main_downloads_up_to_two_new_clips(tmp_path, monkeypatch):
    monkeypatch.setattr(sync_lofi_broll, "BROLL_DIR", tmp_path)
    candidates = [_clip(clip_id=str(i)) for i in range(1, 6)]
    monkeypatch.setattr(sync_lofi_broll, "fetch_pixabay", lambda query, per_page=8: candidates)

    def fake_download_clip(clip, dest, max_bytes=None):
        dest.write_bytes(b"x")
        return True

    monkeypatch.setattr(sync_lofi_broll, "download_clip", fake_download_clip)

    assert sync_lofi_broll.main() == 0

    downloaded = list(tmp_path.glob("pixabay_*.mp4"))
    assert len(downloaded) == 2
    for video_path in downloaded:
        assert video_path.with_suffix(".json").exists()


def test_main_rotates_out_oldest_clips_when_library_is_full(tmp_path, monkeypatch):
    monkeypatch.setattr(sync_lofi_broll, "BROLL_DIR", tmp_path)
    monkeypatch.setattr(sync_lofi_broll, "MAX_CLIPS", 3)
    for i in range(3):
        (tmp_path / f"pixabay_{i}.mp4").write_bytes(b"x")
        (tmp_path / f"pixabay_{i}.json").write_text("{}")
    monkeypatch.setattr(sync_lofi_broll, "fetch_pixabay", lambda query, per_page=8: [])

    assert sync_lofi_broll.main() == 0

    assert len(list(tmp_path.glob("pixabay_*.mp4"))) == 1
    for video_path in tmp_path.glob("pixabay_*.mp4"):
        assert video_path.with_suffix(".json").exists()


def test_main_skips_clips_already_present(tmp_path, monkeypatch):
    monkeypatch.setattr(sync_lofi_broll, "BROLL_DIR", tmp_path)
    (tmp_path / "pixabay_1.mp4").write_bytes(b"x")
    (tmp_path / "pixabay_1.json").write_text("{}")
    monkeypatch.setattr(sync_lofi_broll, "fetch_pixabay", lambda query, per_page=8: [_clip(clip_id="1")])

    assert sync_lofi_broll.main() == 0

    assert len(list(tmp_path.glob("pixabay_*.mp4"))) == 1


def test_main_returns_zero_when_no_candidates_found(tmp_path, monkeypatch):
    monkeypatch.setattr(sync_lofi_broll, "BROLL_DIR", tmp_path)
    monkeypatch.setattr(sync_lofi_broll, "fetch_pixabay", lambda query, per_page=8: [])

    assert sync_lofi_broll.main() == 0
    assert list(tmp_path.glob("pixabay_*.mp4")) == []
