"""Tests for scripts/sync_classical_music.py."""

from __future__ import annotations

import json

import scripts.sync_classical_music as sync_classical


def _track(track_id="1", genres=None, vocalinstrumental="instrumental", **overrides):
    base = {
        "id": track_id,
        "name": "Goldberg Variations, Aria",
        "artist_name": "Some Pianist",
        "audiodownload": f"https://prod-1.storage.jamendo.com/download/track/{track_id}/mp32/",
        "audiodownload_allowed": True,
        "license_ccurl": "http://creativecommons.org/licenses/by/3.0/",
        "shareurl": f"https://www.jamendo.com/track/{track_id}",
        "musicinfo": {
            "vocalinstrumental": vocalinstrumental,
            "tags": {"genres": genres if genres is not None else ["classical"]},
        },
    }
    base.update(overrides)
    return base


def test_commercially_safe_accepts_plain_attribution():
    assert sync_classical._commercially_safe("http://creativecommons.org/licenses/by/3.0/") is True


def test_commercially_safe_rejects_noncommercial():
    assert sync_classical._commercially_safe("http://creativecommons.org/licenses/by-nc/3.0/") is False


def test_commercially_safe_rejects_sharealike():
    assert sync_classical._commercially_safe("http://creativecommons.org/licenses/by-sa/3.0/") is False


def test_is_classical_genre_accepts_known_classical_family_genre():
    assert sync_classical._is_classical_genre(_track(genres=["symphonic"])) is True


def test_is_classical_genre_rejects_unrelated_genre():
    assert sync_classical._is_classical_genre(_track(genres=["housemusic"])) is False


def test_is_classical_genre_rejects_missing_genre_info():
    track = _track()
    del track["musicinfo"]
    assert sync_classical._is_classical_genre(track) is False


def test_is_instrumental_accepts_instrumental_tag():
    assert sync_classical._is_instrumental(_track(vocalinstrumental="instrumental")) is True


def test_is_instrumental_accepts_blank_tag():
    """Checked live: Jamendo leaves this blank on some genuine classical
    tracks rather than omitting it -- blank must mean "allow", not
    "reject"."""
    assert sync_classical._is_instrumental(_track(vocalinstrumental="")) is True


def test_is_instrumental_rejects_explicit_vocal_tag():
    assert sync_classical._is_instrumental(_track(vocalinstrumental="vocal")) is False


def test_downloadable_requires_allowed_flag():
    track = _track(audiodownload_allowed=False)
    assert sync_classical._downloadable(track, set()) is False


def test_downloadable_rejects_noncommercial_license():
    track = _track(license_ccurl="http://creativecommons.org/licenses/by-nc/3.0/")
    assert sync_classical._downloadable(track, set()) is False


def test_downloadable_rejects_non_classical_genre():
    track = _track(genres=["corporate"])
    assert sync_classical._downloadable(track, set()) is False


def test_downloadable_rejects_vocal_track():
    track = _track(vocalinstrumental="vocal")
    assert sync_classical._downloadable(track, set()) is False


def test_downloadable_rejects_already_downloaded_track():
    track = _track(track_id="42")
    assert sync_classical._downloadable(track, {"42"}) is False


def test_downloadable_accepts_clean_classical_track():
    assert sync_classical._downloadable(_track(), set()) is True


def test_fetch_candidates_returns_empty_on_api_error(monkeypatch):
    monkeypatch.setattr(sync_classical.time, "sleep", lambda s: None)

    def fake_urlopen(*args, **kwargs):
        raise sync_classical.urllib.error.URLError("no network")

    monkeypatch.setattr(sync_classical.urllib.request, "urlopen", fake_urlopen)

    results, hard_failure = sync_classical._fetch_candidates_ex()
    assert results == []
    assert hard_failure is True


def test_fetch_candidates_returns_results_on_success(monkeypatch):
    monkeypatch.setattr(sync_classical.time, "sleep", lambda s: None)
    payload = {"headers": {"status": "success"}, "results": [_track()]}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return json.dumps(payload).encode()

    monkeypatch.setattr(sync_classical.urllib.request, "urlopen", lambda *a, **k: FakeResponse())

    results, hard_failure = sync_classical._fetch_candidates_ex()
    assert results == [_track()]
    assert hard_failure is False


def test_download_track_writes_sidecar_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(sync_classical, "CLASSICAL_DIR", tmp_path)
    monkeypatch.setattr(sync_classical.urllib.request, "urlretrieve", lambda url, dest: dest.write_bytes(b"x"))

    assert sync_classical._download_track(_track(track_id="55")) is True

    meta_path = tmp_path / "jamendo_55.json"
    assert meta_path.exists()
    assert "Goldberg Variations, Aria" in meta_path.read_text(encoding="utf-8")


def test_main_skips_gracefully_when_no_candidates_found(tmp_path, monkeypatch):
    monkeypatch.setattr(sync_classical, "CLASSICAL_DIR", tmp_path)
    monkeypatch.setattr(sync_classical, "_fetch_candidates_ex", lambda offset=0: ([], False))

    assert sync_classical.main() == 0


def test_main_rotates_out_oldest_tracks_once_at_max(tmp_path, monkeypatch):
    monkeypatch.setattr(sync_classical, "CLASSICAL_DIR", tmp_path)
    monkeypatch.setattr(sync_classical, "MAX_TRACKS", 2)
    monkeypatch.setattr(sync_classical, "_fetch_candidates_ex", lambda offset=0: ([], False))
    for i in range(3):
        (tmp_path / f"jamendo_{i}.mp3").write_bytes(b"x")
        (tmp_path / f"jamendo_{i}.json").write_text("{}", encoding="utf-8")

    assert sync_classical.main() == 0

    remaining = sorted(p.name for p in tmp_path.glob("jamendo_*.mp3"))
    assert len(remaining) == 0  # MAX_TRACKS=2, rotate 3 oldest away since threshold reached
