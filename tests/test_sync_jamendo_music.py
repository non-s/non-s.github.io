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


def test_downloadable_rejects_noncommercial_license():
    track = _track(license_ccurl="http://creativecommons.org/licenses/by-nc/3.0/")
    assert sync_jamendo_music._downloadable(track, set()) is False


def test_downloadable_rejects_noderivatives_license():
    track = _track(license_ccurl="http://creativecommons.org/licenses/by-nd/3.0/")
    assert sync_jamendo_music._downloadable(track, set()) is False


def test_downloadable_rejects_sharealike_license():
    track = _track(license_ccurl="http://creativecommons.org/licenses/by-sa/3.0/")
    assert sync_jamendo_music._downloadable(track, set()) is False


def test_downloadable_rejects_already_downloaded_track():
    track = _track(track_id="42")
    assert sync_jamendo_music._downloadable(track, {"42"}) is False


def test_downloadable_accepts_clean_track():
    track = _track()
    assert sync_jamendo_music._downloadable(track, set()) is True


def test_commercially_safe_accepts_plain_attribution():
    assert sync_jamendo_music._commercially_safe("http://creativecommons.org/licenses/by/3.0/") is True


def test_commercially_safe_rejects_noncommercial_noderivatives():
    assert sync_jamendo_music._commercially_safe("http://creativecommons.org/licenses/by-nc-nd/3.0/") is False


def test_fetch_candidates_returns_empty_on_api_error(monkeypatch):
    monkeypatch.setattr(sync_jamendo_music.time, "sleep", lambda s: None)

    def fake_urlopen(*args, **kwargs):
        raise sync_jamendo_music.urllib.error.URLError("no network")

    monkeypatch.setattr(sync_jamendo_music.urllib.request, "urlopen", fake_urlopen)

    assert sync_jamendo_music._fetch_candidates() == []


def test_fetch_candidates_returns_empty_on_api_failure_status(monkeypatch):
    monkeypatch.setattr(sync_jamendo_music.time, "sleep", lambda s: None)

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


def test_fetch_candidates_retries_when_success_status_has_empty_results(monkeypatch):
    """Checked live against the real API: identical requests intermittently
    return status success with an empty results list. A retry should
    recover once a later attempt returns real results."""
    monkeypatch.setattr(sync_jamendo_music.time, "sleep", lambda s: None)
    responses = [
        {"headers": {"status": "success"}, "results": []},
        {"headers": {"status": "success"}, "results": [_track()]},
    ]

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return json.dumps(self.payload).encode()

    call_count = {"n": 0}

    def fake_urlopen(*args, **kwargs):
        payload = responses[call_count["n"]]
        call_count["n"] += 1
        return FakeResponse(payload)

    monkeypatch.setattr(sync_jamendo_music.urllib.request, "urlopen", fake_urlopen)

    assert sync_jamendo_music._fetch_candidates() == [_track()]
    assert call_count["n"] == 2


def test_fetch_candidates_gives_up_after_all_retries_return_empty(monkeypatch):
    monkeypatch.setattr(sync_jamendo_music.time, "sleep", lambda s: None)
    payload = {"headers": {"status": "success"}, "results": []}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return json.dumps(payload).encode()

    calls = []
    monkeypatch.setattr(
        sync_jamendo_music.urllib.request, "urlopen", lambda *a, **k: (calls.append(1), FakeResponse())[1]
    )

    assert sync_jamendo_music._fetch_candidates() == []
    assert len(calls) == sync_jamendo_music.FETCH_RETRIES


def test_genre_score_prefers_lofi_and_jazz_tags():
    lofi_track = _track(musicinfo={"tags": {"genres": ["lofi", "hiphop"]}})
    corporate_track = _track(musicinfo={"tags": {"genres": ["corporate"]}})
    assert sync_jamendo_music._genre_score(lofi_track) == 1
    assert sync_jamendo_music._genre_score(corporate_track) == 0


def test_genre_score_handles_missing_musicinfo():
    assert sync_jamendo_music._genre_score(_track()) == 0


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


def test_main_downloads_up_to_downloads_per_run_new_tracks(tmp_path, monkeypatch):
    monkeypatch.setattr(sync_jamendo_music, "BGM_DIR", tmp_path)
    candidates = [_track(track_id=str(i)) for i in range(1, 30)]
    monkeypatch.setattr(sync_jamendo_music, "_fetch_candidates", lambda offset=0: candidates)
    monkeypatch.setattr(
        sync_jamendo_music.urllib.request, "urlretrieve", lambda url, filename: filename.write_bytes(b"x")
    )

    assert sync_jamendo_music.main() == 0

    downloaded = list(tmp_path.glob("jamendo_*.mp3"))
    assert len(downloaded) == sync_jamendo_music.DOWNLOADS_PER_RUN
    for audio_path in downloaded:
        assert audio_path.with_suffix(".json").exists()


def test_main_prefers_lofi_jazz_tagged_candidates(tmp_path, monkeypatch):
    monkeypatch.setattr(sync_jamendo_music, "BGM_DIR", tmp_path)
    monkeypatch.setattr(sync_jamendo_music, "DOWNLOADS_PER_RUN", 1)
    corporate = _track(track_id="1", musicinfo={"tags": {"genres": ["corporate"]}})
    lofi = _track(track_id="2", musicinfo={"tags": {"genres": ["lofi"]}})
    monkeypatch.setattr(sync_jamendo_music, "_fetch_candidates", lambda offset=0: [corporate, lofi])
    monkeypatch.setattr(
        sync_jamendo_music.urllib.request, "urlretrieve", lambda url, filename: filename.write_bytes(b"x")
    )

    assert sync_jamendo_music.main() == 0

    downloaded = list(tmp_path.glob("jamendo_*.mp3"))
    assert [p.name for p in downloaded] == ["jamendo_2.mp3"]


def test_main_rotates_out_oldest_tracks_when_library_is_full(tmp_path, monkeypatch):
    monkeypatch.setattr(sync_jamendo_music, "BGM_DIR", tmp_path)
    monkeypatch.setattr(sync_jamendo_music, "MAX_TRACKS", 3)
    for i in range(3):
        (tmp_path / f"jamendo_{i}.mp3").write_bytes(b"x")
        (tmp_path / f"jamendo_{i}.json").write_text("{}")
    monkeypatch.setattr(sync_jamendo_music, "_fetch_candidates", lambda offset=0: [])

    assert sync_jamendo_music.main() == 0

    assert len(list(tmp_path.glob("jamendo_*.mp3"))) == 1
    # every remaining audio file keeps a matching sidecar (none orphaned)
    for audio_path in tmp_path.glob("jamendo_*.mp3"):
        assert audio_path.with_suffix(".json").exists()


def test_main_skips_tracks_already_present(tmp_path, monkeypatch):
    monkeypatch.setattr(sync_jamendo_music, "BGM_DIR", tmp_path)
    (tmp_path / "jamendo_1.mp3").write_bytes(b"x")
    (tmp_path / "jamendo_1.json").write_text("{}")
    monkeypatch.setattr(sync_jamendo_music, "_fetch_candidates", lambda offset=0: [_track(track_id="1")])

    assert sync_jamendo_music.main() == 0

    assert len(list(tmp_path.glob("jamendo_*.mp3"))) == 1
