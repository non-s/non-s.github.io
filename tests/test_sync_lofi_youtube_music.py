import json

import scripts.sync_lofi_youtube_music as sync_music


def _entry(video_id="abc123", **overrides):
    base = {
        "id": video_id,
        "title": "Chill Lofi Beats Mix",
        "uploader": "Some Channel",
        "channel": "Some Channel",
        "license": sync_music.REQUIRED_LICENSE,
        "is_live": False,
        "duration": 300,
    }
    base.update(overrides)
    return base


def test_eligible_requires_exact_cc_license():
    entry = _entry(license="All Rights Reserved")
    assert sync_music._eligible(entry, set()) is False


def test_eligible_rejects_live_streams():
    entry = _entry(is_live=True)
    assert sync_music._eligible(entry, set()) is False


def test_eligible_rejects_too_short():
    entry = _entry(duration=10)
    assert sync_music._eligible(entry, set()) is False


def test_eligible_rejects_too_long():
    entry = _entry(duration=5000)
    assert sync_music._eligible(entry, set()) is False


def test_eligible_rejects_missing_duration():
    entry = _entry(duration=None)
    assert sync_music._eligible(entry, set()) is False


def test_eligible_rejects_already_downloaded():
    entry = _entry(video_id="42")
    assert sync_music._eligible(entry, {"42"}) is False


def test_eligible_accepts_clean_entry():
    entry = _entry()
    assert sync_music._eligible(entry, set()) is True


def test_search_candidates_returns_empty_on_failure(monkeypatch):
    class FakeYDL:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def extract_info(self, url, download=False):
            raise RuntimeError("network error")

    monkeypatch.setattr(sync_music.yt_dlp, "YoutubeDL", lambda opts: FakeYDL())

    assert sync_music._search_candidates("lofi jazz") == []


def test_search_candidates_returns_entries_on_success(monkeypatch):
    entries = [_entry("1"), None, _entry("2")]

    class FakeYDL:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def extract_info(self, url, download=False):
            return {"entries": entries}

    monkeypatch.setattr(sync_music.yt_dlp, "YoutubeDL", lambda opts: FakeYDL())

    result = sync_music._search_candidates("lofi jazz")

    assert result == [_entry("1"), _entry("2")]


def test_download_track_writes_audio_and_attribution_sidecar(tmp_path, monkeypatch):
    monkeypatch.setattr(sync_music, "BGM_DIR", tmp_path)

    class FakeYDL:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def download(self, urls):
            (tmp_path / "ytcc_99.mp3").write_bytes(b"fake-mp3-bytes")

    monkeypatch.setattr(sync_music.yt_dlp, "YoutubeDL", lambda opts: FakeYDL())

    entry = _entry(video_id="99", title="Horizons", uploader="Train Room")
    assert sync_music._download_track(entry) is True

    audio_path = tmp_path / "ytcc_99.mp3"
    meta_path = tmp_path / "ytcc_99.json"
    assert audio_path.read_bytes() == b"fake-mp3-bytes"
    meta = json.loads(meta_path.read_text())
    assert meta["track_name"] == "Horizons"
    assert meta["artist_name"] == "Train Room"
    assert meta["license_ccurl"] == sync_music.REQUIRED_LICENSE
    assert meta["track_id"] == "99"
    assert meta["shareurl"] == "https://www.youtube.com/watch?v=99"


def test_download_track_cleans_up_on_download_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(sync_music, "BGM_DIR", tmp_path)

    class FakeYDL:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def download(self, urls):
            raise RuntimeError("blocked")

    monkeypatch.setattr(sync_music.yt_dlp, "YoutubeDL", lambda opts: FakeYDL())

    entry = _entry(video_id="7")
    assert sync_music._download_track(entry) is False
    assert not (tmp_path / "ytcc_7.mp3").exists()
    assert not (tmp_path / "ytcc_7.json").exists()


def test_download_track_returns_false_when_file_missing_after_download(tmp_path, monkeypatch):
    monkeypatch.setattr(sync_music, "BGM_DIR", tmp_path)

    class FakeYDL:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def download(self, urls):
            pass  # simulate a silent no-op that never wrote the file

    monkeypatch.setattr(sync_music.yt_dlp, "YoutubeDL", lambda opts: FakeYDL())

    entry = _entry(video_id="8")
    assert sync_music._download_track(entry) is False


def test_main_downloads_up_to_two_new_tracks(tmp_path, monkeypatch):
    monkeypatch.setattr(sync_music, "BGM_DIR", tmp_path)
    candidates = [_entry(str(i)) for i in range(1, 6)]
    monkeypatch.setattr(sync_music, "_search_candidates", lambda query: candidates)

    def fake_download(entry):
        (tmp_path / f"ytcc_{entry['id']}.mp3").write_bytes(b"x")
        (tmp_path / f"ytcc_{entry['id']}.json").write_text("{}")
        return True

    monkeypatch.setattr(sync_music, "_download_track", fake_download)

    assert sync_music.main() == 0

    downloaded = list(tmp_path.glob("ytcc_*.mp3"))
    assert len(downloaded) == 2


def test_main_rotates_out_oldest_tracks_when_library_is_full(tmp_path, monkeypatch):
    monkeypatch.setattr(sync_music, "BGM_DIR", tmp_path)
    monkeypatch.setattr(sync_music, "MAX_TRACKS", 3)
    for i in range(3):
        (tmp_path / f"ytcc_{i}.mp3").write_bytes(b"x")
        (tmp_path / f"ytcc_{i}.json").write_text("{}")
    monkeypatch.setattr(sync_music, "_search_candidates", lambda query: [])

    assert sync_music.main() == 0

    assert len(list(tmp_path.glob("ytcc_*.mp3"))) == 1


def test_main_returns_zero_when_no_eligible_candidates(tmp_path, monkeypatch):
    monkeypatch.setattr(sync_music, "BGM_DIR", tmp_path)
    monkeypatch.setattr(sync_music, "_search_candidates", lambda query: [_entry(license="All Rights Reserved")])

    assert sync_music.main() == 0
    assert list(tmp_path.glob("ytcc_*.mp3")) == []
