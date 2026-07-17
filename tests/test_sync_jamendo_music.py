import json

import scripts.sync_jamendo_music as sync_jamendo_music


def _track(track_id="1", **overrides):
    base = {
        "id": track_id,
        "name": "Rainy Study Session",
        "artist_name": "Some Artist",
        "audiodownload": f"https://prod-1.storage.jamendo.com/download/track/{track_id}/mp32/",
        "audiodownload_allowed": True,
        "license_ccurl": "http://creativecommons.org/licenses/by/3.0/",
        "shareurl": f"https://www.jamendo.com/track/{track_id}",
    }
    base.update(overrides)
    return base


def test_downloadable_requires_allowed_flag():
    track = _track(audiodownload_allowed=False)
    assert sync_jamendo_music._downloadable(track, set()) is False


def test_downloadable_requires_download_url():
    track = _track(audiodownload="")
    assert sync_jamendo_music._downloadable(track, set()) is False


def test_downloadable_requires_license_url():
    track = _track(license_ccurl="")
    assert sync_jamendo_music._downloadable(track, set()) is False


def test_downloadable_rejects_already_downloaded_track():
    track = _track(track_id="42")
    assert sync_jamendo_music._downloadable(track, {"42"}) is False


def test_downloadable_accepts_clean_track():
    track = _track()
    assert sync_jamendo_music._downloadable(track, set()) is True


def test_fetch_candidates_returns_empty_on_api_error(monkeypatch):
    def fake_urlopen(*args, **kwargs):
        raise sync_jamendo_music.urllib.error.URLError("no network")

    monkeypatch.setattr(sync_jamendo_music.urllib.request, "urlopen", fake_urlopen)

    assert sync_jamendo_music._fetch_candidates() == []


def test_fetch_candidates_returns_empty_on_api_failure_status(monkeypatch):
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return json.dumps({"headers": {"status": "failed", "error_message": "bad client id"}}).encode()

    monkeypatch.setattr(sync_jamendo_music.urllib.request, "urlopen", lambda *a, **k: FakeResponse())

    assert sync_jamendo_music._fetch_candidates() == []


def test_fetch_candidates_returns_results_on_success(monkeypatch):
    payload = {"headers": {"status": "success"}, "results": [_track()]}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return json.dumps(payload).encode()

    monkeypatch.setattr(sync_jamendo_music.urllib.request, "urlopen", lambda *a, **k: FakeResponse())

    assert sync_jamendo_music._fetch_candidates() == [_track()]


def test_download_track_writes_audio_and_attribution_sidecar(tmp_path, monkeypatch):
    monkeypatch.setattr(sync_jamendo_music, "BGM_DIR", tmp_path)
    captured = {}

    def fake_urlretrieve(url, filename):
        captured["url"] = url
        captured["filename"] = filename
        filename.write_bytes(b"fake-mp3-bytes")

    monkeypatch.setattr(sync_jamendo_music.urllib.request, "urlretrieve", fake_urlretrieve)

    track = _track(track_id="99", name="Horizons", artist_name="Train Room")
    assert sync_jamendo_music._download_track(track) is True

    audio_path = tmp_path / "jamendo_99.mp3"
    meta_path = tmp_path / "jamendo_99.json"
    assert audio_path.read_bytes() == b"fake-mp3-bytes"
    meta = json.loads(meta_path.read_text())
    assert meta["track_name"] == "Horizons"
    assert meta["artist_name"] == "Train Room"
    assert meta["license_ccurl"] == "http://creativecommons.org/licenses/by/3.0/"
    assert meta["track_id"] == "99"


def test_download_track_cleans_up_partial_file_on_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(sync_jamendo_music, "BGM_DIR", tmp_path)

    def failing_urlretrieve(url, filename):
        filename.write_bytes(b"partial")
        raise OSError("connection reset")

    monkeypatch.setattr(sync_jamendo_music.urllib.request, "urlretrieve", failing_urlretrieve)

    track = _track(track_id="7")
    assert sync_jamendo_music._download_track(track) is False
    assert not (tmp_path / "jamendo_7.mp3").exists()
    assert not (tmp_path / "jamendo_7.json").exists()


def test_main_downloads_up_to_two_new_tracks(tmp_path, monkeypatch):
    monkeypatch.setattr(sync_jamendo_music, "BGM_DIR", tmp_path)
    candidates = [_track(track_id=str(i)) for i in range(1, 6)]
    monkeypatch.setattr(sync_jamendo_music, "_fetch_candidates", lambda: candidates)
    monkeypatch.setattr(
        sync_jamendo_music.urllib.request, "urlretrieve", lambda url, filename: filename.write_bytes(b"x")
    )

    assert sync_jamendo_music.main() == 0

    downloaded = list(tmp_path.glob("jamendo_*.mp3"))
    assert len(downloaded) == 2
    for audio_path in downloaded:
        assert audio_path.with_suffix(".json").exists()


def test_main_rotates_out_oldest_tracks_when_library_is_full(tmp_path, monkeypatch):
    monkeypatch.setattr(sync_jamendo_music, "BGM_DIR", tmp_path)
    monkeypatch.setattr(sync_jamendo_music, "MAX_TRACKS", 3)
    for i in range(3):
        (tmp_path / f"jamendo_{i}.mp3").write_bytes(b"x")
        (tmp_path / f"jamendo_{i}.json").write_text("{}")
    monkeypatch.setattr(sync_jamendo_music, "_fetch_candidates", lambda: [])

    assert sync_jamendo_music.main() == 0

    assert len(list(tmp_path.glob("jamendo_*.mp3"))) == 1
    # every remaining audio file keeps a matching sidecar (none orphaned)
    for audio_path in tmp_path.glob("jamendo_*.mp3"):
        assert audio_path.with_suffix(".json").exists()


def test_main_skips_tracks_already_present(tmp_path, monkeypatch):
    monkeypatch.setattr(sync_jamendo_music, "BGM_DIR", tmp_path)
    (tmp_path / "jamendo_1.mp3").write_bytes(b"x")
    (tmp_path / "jamendo_1.json").write_text("{}")
    monkeypatch.setattr(sync_jamendo_music, "_fetch_candidates", lambda: [_track(track_id="1")])

    assert sync_jamendo_music.main() == 0

    assert len(list(tmp_path.glob("jamendo_*.mp3"))) == 1
