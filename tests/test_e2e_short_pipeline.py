"""Simulated end-to-end test: generate_lofi_short.py's real output feeds
directly into upload_youtube.py's upload pipeline with no schema drift
between the two.

Both modules have thorough unit tests of their own, but nothing before
this exercised the actual producer -> consumer contract together: a field
upload_youtube.py started expecting (or generate_lofi_short.py stopped
providing) wouldn't be caught by either file's own tests in isolation.
Only ffmpeg/thumbnail extraction and the real YouTube API are faked here
-- everything else (metadata building, title dedupe, marker building) runs
for real.
"""

from __future__ import annotations

import json

import generate_lofi_short as lofi
import upload_youtube


class _Req:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return self.payload


class _UploadReq:
    def next_chunk(self):
        return None, {"id": "E2E_VIDEO_ID"}


class _Playlists:
    def list(self, **kwargs):
        return _Req({"items": []})

    def insert(self, **kwargs):
        return _Req({"id": "PL-NEW"})


class _PlaylistItems:
    def list(self, **kwargs):
        return _Req({"items": []})

    def insert(self, **kwargs):
        return _Req({"id": "PLI-1"})


class _Videos:
    def insert(self, **kwargs):
        return _UploadReq()


class _Thumbnails:
    def set(self, **kwargs):
        return _Req({})


class _YouTube:
    def playlists(self):
        return _Playlists()

    def playlistItems(self):
        return _PlaylistItems()

    def videos(self):
        return _Videos()

    def thumbnails(self):
        return _Thumbnails()


def test_generated_short_metadata_survives_the_full_upload_pipeline(tmp_path, monkeypatch):
    pinned_clip = tmp_path / "pinned_short_clip.mp4"
    bgm_dir = tmp_path / "bgm"
    videos_dir = tmp_path / "_videos"
    bgm_dir.mkdir()

    pinned_clip.write_bytes(b"x")
    pinned_clip.with_suffix(".json").write_text(
        json.dumps(
            {
                "tags": "anime, rain, window",
                "pixabay_video_id": "1",
                "photographer": "Test Photographer",
                "license": "Pixabay Content License",
                "license_evidence": "https://pixabay.com/videos/id-1/",
            }
        ),
        encoding="utf-8",
    )
    (bgm_dir / "jamendo_1.mp3").write_bytes(b"x")
    (bgm_dir / "jamendo_1.json").write_text(
        json.dumps({"track_name": "Test Track", "artist_name": "Test Artist", "track_id": "1", "speed": "low"}),
        encoding="utf-8",
    )

    monkeypatch.setattr(lofi, "VIDEOS_DIR", videos_dir)
    monkeypatch.setattr(lofi, "PINNED_BROLL_CLIP", pinned_clip)
    monkeypatch.setattr(lofi, "BGM_DIR", bgm_dir)

    def fake_compose(broll_path, bgm_path, output_path, duration_s):
        output_path.write_bytes(b"fake-mp4")
        return True

    def fake_thumbnail(video_path, thumb_path, timestamp_s=2.0):
        thumb_path.write_bytes(b"fake-jpg")
        return True

    monkeypatch.setattr(lofi, "_compose_short", fake_compose)
    monkeypatch.setattr(lofi, "_extract_thumbnail", fake_thumbnail)

    assert lofi.main() == 0

    meta_files = list(videos_dir.glob("short-*.json"))
    assert len(meta_files) == 1
    meta = json.loads(meta_files[0].read_text(encoding="utf-8"))

    # Hand this real, on-disk metadata off to upload_youtube.py's own
    # pipeline exactly as its main() loop would.
    assert upload_youtube._is_uploadable_meta(meta) is True

    youtube = _YouTube()
    video_id = upload_youtube.upload_video(youtube, meta)
    assert video_id == "E2E_VIDEO_ID"

    marker = upload_youtube._done_marker(video_id, meta)
    assert marker["title"] == meta["title"]
    assert marker["category"] == "lofi"
    assert marker["series"].endswith(" Shorts")
    assert marker["duration_s"] == meta["duration_s"]
    assert marker["bgm_track_id"] == "1"
    assert marker["source_clip_id"] == "1"
    assert marker["bgm_license_ccurl"] == ""
    assert marker["source_license"] == "Pixabay Content License"

    playlists = upload_youtube._playlist_titles(marker)
    assert len(playlists) >= 3  # Start Here / series / category (+ mood bucket if distinct)
