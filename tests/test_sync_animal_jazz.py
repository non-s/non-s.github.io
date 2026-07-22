"""Tests for scripts/sync_animal_jazz.py."""

from __future__ import annotations

import json

import scripts.sync_animal_jazz as sync_animal_jazz


def _track(track_id="1", genres=None, **overrides):
    base = {
        "id": track_id,
        "name": "Late Night Swing",
        "artist_name": "Some Artist",
        "audiodownload": f"https://prod-1.storage.jamendo.com/download/track/{track_id}/mp32/",
        "audiodownload_allowed": True,
        "license_ccurl": "http://creativecommons.org/licenses/by/3.0/",
        "shareurl": f"https://www.jamendo.com/track/{track_id}",
        "musicinfo": {"tags": {"genres": genres if genres is not None else ["jazz"]}},
    }
    base.update(overrides)
    return base


def test_commercially_safe_accepts_plain_attribution():
    assert sync_animal_jazz._commercially_safe("http://creativecommons.org/licenses/by/3.0/") is True


def test_commercially_safe_rejects_noncommercial():
    assert sync_animal_jazz._commercially_safe("http://creativecommons.org/licenses/by-nc/3.0/") is False


def test_commercially_safe_rejects_sharealike():
    assert sync_animal_jazz._commercially_safe("http://creativecommons.org/licenses/by-sa/3.0/") is False


def test_is_jazz_genre_accepts_known_jazz_family_genre():
    assert sync_animal_jazz._is_jazz_genre(_track(genres=["swing"])) is True


def test_is_jazz_genre_rejects_unrelated_genre():
    assert sync_animal_jazz._is_jazz_genre(_track(genres=["housemusic"])) is False


def test_is_jazz_genre_rejects_missing_genre_info():
    track = _track()
    del track["musicinfo"]
    assert sync_animal_jazz._is_jazz_genre(track) is False


def test_downloadable_requires_allowed_flag():
    track = _track(audiodownload_allowed=False)
    assert sync_animal_jazz._downloadable(track, set()) is False


def test_downloadable_rejects_noncommercial_license():
    track = _track(license_ccurl="http://creativecommons.org/licenses/by-nc/3.0/")
    assert sync_animal_jazz._downloadable(track, set()) is False


def test_downloadable_rejects_non_jazz_genre():
    track = _track(genres=["corporate"])
    assert sync_animal_jazz._downloadable(track, set()) is False


def test_downloadable_rejects_already_downloaded_track():
    track = _track(track_id="42")
    assert sync_animal_jazz._downloadable(track, {"42"}) is False


def test_downloadable_accepts_clean_jazz_track():
    assert sync_animal_jazz._downloadable(_track(), set()) is True


def test_fetch_candidates_returns_empty_on_api_error(monkeypatch):
    monkeypatch.setattr(sync_animal_jazz.time, "sleep", lambda s: None)

    def fake_urlopen(*args, **kwargs):
        raise sync_animal_jazz.urllib.error.URLError("no network")

    monkeypatch.setattr(sync_animal_jazz.urllib.request, "urlopen", fake_urlopen)

    results, hard_failure = sync_animal_jazz._fetch_candidates_ex()
    assert results == []
    assert hard_failure is True


def test_fetch_candidates_returns_results_on_success(monkeypatch):
    monkeypatch.setattr(sync_animal_jazz.time, "sleep", lambda s: None)
    payload = {"headers": {"status": "success"}, "results": [_track()]}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return json.dumps(payload).encode()

    monkeypatch.setattr(sync_animal_jazz.urllib.request, "urlopen", lambda *a, **k: FakeResponse())

    results, hard_failure = sync_animal_jazz._fetch_candidates_ex()
    assert results == [_track()]
    assert hard_failure is False


def test_download_track_writes_sidecar_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(sync_animal_jazz, "JAZZ_DIR", tmp_path)
    monkeypatch.setattr(sync_animal_jazz.urllib.request, "urlretrieve", lambda url, dest: dest.write_bytes(b"x"))

    assert sync_animal_jazz._download_track(_track(track_id="55")) is True

    meta_path = tmp_path / "jamendo_55.json"
    assert meta_path.exists()
    assert "Late Night Swing" in meta_path.read_text(encoding="utf-8")


def test_main_skips_gracefully_when_no_candidates_found(tmp_path, monkeypatch):
    monkeypatch.setattr(sync_animal_jazz, "JAZZ_DIR", tmp_path)
    monkeypatch.setattr(sync_animal_jazz, "_fetch_candidates_ex", lambda tags, offset=0, limit=200: ([], False))

    assert sync_animal_jazz.main() == 0
