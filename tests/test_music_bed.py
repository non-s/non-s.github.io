"""Tests for autonomous Internet Archive music-bed selection."""

from __future__ import annotations

from utils import music_bed


def test_mood_breaking_picks_tense():
    story = {"slug": "x", "breaking": True}
    assert music_bed._mood_for_story(story) == "tense"


def test_mood_negative_picks_tense():
    story = {"slug": "x", "sentiment": "negative"}
    assert music_bed._mood_for_story(story) == "tense"


def test_mood_ocean_picks_reflective():
    story = {"slug": "x", "category": "ocean"}
    assert music_bed._mood_for_story(story) == "reflective"


def test_mood_default_upbeat():
    story = {"slug": "x", "category": "cats"}
    assert music_bed._mood_for_story(story) == "upbeat"


def test_archive_audio_is_opt_in_by_default():
    assert music_bed.MUSIC_ENABLED is False
    assert music_bed.ARCHIVE_AUDIO_ENABLED is False


def test_pick_track_is_deterministic(monkeypatch):
    from utils.internet_archive import ArchiveAudioAsset

    monkeypatch.setattr(music_bed, "MUSIC_ENABLED", True)
    monkeypatch.setattr(music_bed, "ARCHIVE_AUDIO_ENABLED", True)
    asset = ArchiveAudioAsset(
        identifier="pd-rain",
        file_name="rain.mp3",
        title="Rain Ambience",
        creator="",
        url="https://archive.org/download/pd-rain/rain.mp3",
        source_url="https://archive.org/details/pd-rain",
        license="https://creativecommons.org/publicdomain/zero/1.0/",
        license_evidence="creativecommons.org/publicdomain/zero",
        mood="upbeat",
    )
    monkeypatch.setattr(music_bed, "discover_public_domain_audio", lambda *args, **kwargs: [asset])
    story = {"slug": "abc-123", "category": "cats"}
    a = music_bed.pick_track(story)
    b = music_bed.pick_track(story)
    assert a is not None
    assert a == b


def test_pick_track_disabled_returns_none(monkeypatch):
    monkeypatch.setattr(music_bed, "MUSIC_ENABLED", False)
    assert music_bed.pick_track({"slug": "x", "category": "cats"}) is None


def test_pick_track_returns_none_without_archive_candidate(monkeypatch):
    monkeypatch.setattr(music_bed, "MUSIC_ENABLED", True)
    monkeypatch.setattr(music_bed, "ARCHIVE_AUDIO_ENABLED", True)
    monkeypatch.setattr(music_bed, "discover_public_domain_audio", lambda *args, **kwargs: [])
    track = music_bed.pick_track({"slug": "x"})
    assert track is None


def test_archive_tracks_disabled_skips_discovery(monkeypatch):
    monkeypatch.setattr(music_bed, "ARCHIVE_AUDIO_ENABLED", False)
    monkeypatch.setattr(
        music_bed,
        "discover_public_domain_audio",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("called")),
    )

    assert music_bed.archive_tracks_for_story({"category": "birds"}) == []


def test_pick_track_can_use_archive_audio_when_enabled(monkeypatch):
    from utils.internet_archive import ArchiveAudioAsset

    monkeypatch.setattr(music_bed, "MUSIC_ENABLED", True)
    monkeypatch.setattr(music_bed, "ARCHIVE_AUDIO_ENABLED", True)
    asset = ArchiveAudioAsset(
        identifier="pd-forest",
        file_name="forest.mp3",
        title="Forest Ambience",
        creator="",
        url="https://archive.org/download/pd-forest/forest.mp3",
        source_url="https://archive.org/details/pd-forest",
        license="https://creativecommons.org/publicdomain/mark/1.0/",
        license_evidence="creativecommons.org/publicdomain/mark",
        mood="reflective",
    )
    monkeypatch.setattr(music_bed, "discover_public_domain_audio", lambda *args, **kwargs: [asset])

    track = music_bed.pick_track({"slug": "archive-story", "category": "birds"})

    assert track is not None
    assert track.name == "Forest Ambience"
    assert track.source == "Internet Archive"
    assert track.license_evidence == "creativecommons.org/publicdomain/mark"


def test_archive_scoring_prefers_nature_over_abstract_track(monkeypatch):
    from utils.internet_archive import ArchiveAudioAsset

    monkeypatch.setattr(music_bed, "MUSIC_ENABLED", True)
    monkeypatch.setattr(music_bed, "ARCHIVE_AUDIO_ENABLED", True)
    abstract = ArchiveAudioAsset(
        identifier="333OfCourseThePersonalityIsGone",
        file_name="333.mp3",
        title="333: Of Course, the Personality is Gone",
        creator="Bull of Heaven",
        url="https://archive.org/download/333OfCourseThePersonalityIsGone/333.mp3",
        source_url="https://archive.org/details/333OfCourseThePersonalityIsGone",
        license="https://creativecommons.org/publicdomain/mark/1.0/",
        license_evidence="creativecommons.org/publicdomain/mark",
        mood="reflective",
    )
    nature = ArchiveAudioAsset(
        identifier="animalsounds1",
        file_name="09littleblueheronfishes.mp3",
        title="Animal sounds from nature",
        creator="Various",
        url="https://archive.org/download/animalsounds1/09littleblueheronfishes.mp3",
        source_url="https://archive.org/details/animalsounds1",
        license="https://creativecommons.org/publicdomain/mark/1.0/",
        license_evidence="creativecommons.org/publicdomain/mark",
        mood="reflective",
    )
    monkeypatch.setattr(music_bed, "discover_public_domain_audio", lambda *args, **kwargs: [abstract, nature])

    track = music_bed.pick_track({"slug": "archive-story", "category": "birds"})

    assert track is not None
    assert track.name == "Animal sounds from nature"


def test_add_music_bed_returns_original_when_disabled(monkeypatch, tmp_path):
    monkeypatch.setattr(music_bed, "MUSIC_ENABLED", False)
    fake_tts = tmp_path / "tts.mp3"
    fake_tts.write_bytes(b"x")
    out = music_bed.add_music_bed(fake_tts, {"slug": "x"}, tmp_path)
    assert out == fake_tts


def test_add_music_bed_returns_original_when_download_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(music_bed, "MUSIC_ENABLED", True)
    fake_tts = tmp_path / "tts.mp3"
    fake_tts.write_bytes(b"x")
    monkeypatch.setattr(music_bed, "download_track", lambda track: None)
    out = music_bed.add_music_bed(fake_tts, {"slug": "x"}, tmp_path)
    assert out == fake_tts


def test_add_music_bed_returns_mixed_when_pipeline_succeeds(monkeypatch, tmp_path):
    monkeypatch.setattr(music_bed, "MUSIC_ENABLED", True)
    monkeypatch.setattr(music_bed, "ARCHIVE_AUDIO_ENABLED", True)
    fake_tts = tmp_path / "tts.mp3"
    fake_tts.write_bytes(b"x")
    fake_music = tmp_path / "music.mp3"
    fake_music.write_bytes(b"x")
    monkeypatch.setattr(music_bed, "download_track", lambda track: fake_music)

    def fake_mix(tts_path, music_path, output_path, music_volume_db=-26.0):
        output_path.write_bytes(b"mixed")
        return True

    monkeypatch.setattr(music_bed, "mix_tts_with_music", fake_mix)
    story = {"slug": "x"}
    out = music_bed.add_music_bed(fake_tts, story, tmp_path)
    assert out != fake_tts
    assert out.read_bytes() == b"mixed"
    assert story["music_bed_track"]["name"]
    assert story["music_bed_track"]["license"]


def test_download_track_uses_archive_downloader(monkeypatch, tmp_path):
    expected = tmp_path / "archive.mp3"
    expected.write_bytes(b"audio")
    seen = {}

    def fake_download(asset):
        seen["asset"] = asset
        return expected

    monkeypatch.setattr(music_bed, "download_asset", fake_download)
    track = music_bed.MusicTrack(
        name="Forest Ambience",
        url="https://archive.org/download/pd-forest/forest.mp3",
        mood="reflective",
        source="Internet Archive",
        source_url="https://archive.org/details/pd-forest",
        license_evidence="creativecommons.org/publicdomain/mark",
    )

    out = music_bed.download_track(track)

    assert out == expected
    assert seen["asset"].identifier == "pd-forest"
    assert seen["asset"].license_evidence == "creativecommons.org/publicdomain/mark"


def test_download_track_rejects_non_archive_source():
    track = music_bed.MusicTrack(name="x", url="https://e.test/x.mp3", mood="upbeat", source="legacy")
    assert music_bed.download_track(track) is None
