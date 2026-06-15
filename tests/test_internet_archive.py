from __future__ import annotations

from unittest.mock import MagicMock

from utils import internet_archive as ia


def _metadata_payload(**metadata):
    base = {
        "identifier": "pd-nature-bed",
        "title": "Public Domain Nature Bed",
        "mediatype": "audio",
        "licenseurl": "https://creativecommons.org/publicdomain/mark/1.0/",
    }
    base.update(metadata)
    return {
        "metadata": base,
        "files": [
            {"name": "cover.jpg", "format": "JPEG", "size": "1000"},
            {"name": "nature-bed.mp3", "format": "VBR MP3", "size": "123456"},
        ],
    }


def _video_payload(**metadata):
    base = {
        "identifier": "pd-wildlife-film",
        "title": "Public Domain Wildlife Film",
        "mediatype": "movies",
        "licenseurl": "https://creativecommons.org/publicdomain/mark/1.0/",
        "collection": ["prelinger", "publicdomain"],
        "creator": "Archive Curator",
        "description": "A public-domain wildlife clip with birds in a wetland.",
    }
    base.update(metadata)
    return {
        "metadata": base,
        "files": [
            {"name": "__ia_thumb.jpg", "format": "JPEG Thumb", "size": "1000"},
            {
                "name": "wildlife.mp4",
                "format": "MPEG4",
                "size": "1234567",
                "width": "1080",
                "height": "1920",
                "length": "13.5",
            },
        ],
    }


def test_public_domain_evidence_accepts_pd_mark():
    payload = _metadata_payload()
    assert ia.public_domain_evidence(payload["metadata"]) == "creativecommons.org/publicdomain/mark"
    assert ia.is_public_domain_item(payload["metadata"])


def test_asset_from_metadata_rejects_missing_public_domain_evidence():
    payload = _metadata_payload(licenseurl="https://creativecommons.org/licenses/by-nc/4.0/")
    assert ia.asset_from_metadata(payload) is None


def test_public_domain_evidence_rejects_blocked_rights_terms():
    payload = _metadata_payload(
        licenseurl="https://creativecommons.org/publicdomain/mark/1.0/",
        rights="All rights reserved",
    )
    assert ia.public_domain_evidence(payload["metadata"]) == ""
    assert not ia.is_public_domain_item(payload["metadata"])


def test_asset_from_metadata_picks_audio_file_and_provenance():
    asset = ia.asset_from_metadata(_metadata_payload(), mood="reflective")

    assert asset is not None
    assert asset.identifier == "pd-nature-bed"
    assert asset.file_name == "nature-bed.mp3"
    assert asset.url == "https://archive.org/download/pd-nature-bed/nature-bed.mp3"
    assert asset.source_url == "https://archive.org/details/pd-nature-bed"
    assert asset.mood == "reflective"


def test_advanced_search_returns_identifiers():
    fake = MagicMock()
    fake.get.return_value.json.return_value = {"response": {"docs": [{"identifier": "one"}, {"identifier": "two"}]}}
    fake.get.return_value.raise_for_status.return_value = None

    out = ia.advanced_search_audio('"nature sounds"', session=fake)

    assert out == ["one", "two"]
    params = fake.get.call_args.kwargs["params"]
    assert "mediatype:audio" in params["q"]
    assert "publicdomain" in params["q"]


def test_video_asset_from_metadata_picks_mp4_and_provenance():
    asset = ia.video_asset_from_metadata(_video_payload())

    assert asset is not None
    assert asset.identifier == "pd-wildlife-film"
    assert asset.file_name == "wildlife.mp4"
    assert asset.url == "https://archive.org/download/pd-wildlife-film/wildlife.mp4"
    assert asset.source_url == "https://archive.org/details/pd-wildlife-film"
    assert asset.width == 1080
    assert asset.height == 1920
    assert asset.license_evidence == "creativecommons.org/publicdomain/mark"
    assert "birds" in asset.description


def test_archive_video_relevance_prefers_specific_nature_sources():
    strong = ia.video_asset_from_metadata(
        _video_payload(
            identifier="usfw-bird-clip",
            title="Birds feeding in a wetland",
            creator="U.S. Fish and Wildlife Service",
            description="Public domain footage of birds in a wetland habitat.",
        )
    )
    weak = ia.video_asset_from_metadata(
        _video_payload(
            identifier="old-chapter-film",
            title="Chapter 7 trailer",
            creator="",
            description="A public domain serial chapter and trailer.",
        )
    )

    assert strong is not None and weak is not None
    assert ia.archive_video_relevance_score(strong, "birds wildlife") > ia.archive_video_relevance_score(
        weak, "birds wildlife"
    )


def test_video_asset_from_metadata_rejects_missing_public_domain_evidence():
    payload = _video_payload(licenseurl="https://creativecommons.org/licenses/by-nc/4.0/")
    assert ia.video_asset_from_metadata(payload) is None


def test_advanced_search_video_returns_identifiers():
    fake = MagicMock()
    fake.get.return_value.json.return_value = {"response": {"docs": [{"identifier": "film-one"}]}}
    fake.get.return_value.raise_for_status.return_value = None

    out = ia.advanced_search_video('"wildlife film"', session=fake)

    assert out == ["film-one"]
    queries = [call.kwargs["params"]["q"] for call in fake.get.call_args_list]
    assert all("mediatype:movies" in query for query in queries)
    assert any("publicdomain" in query.lower() for query in queries)


def test_download_asset_rejects_too_small(monkeypatch, tmp_path):
    asset = ia.asset_from_metadata(_metadata_payload())
    assert asset is not None
    monkeypatch.setattr(ia, "ARCHIVE_AUDIO_MIN_BYTES", 50)
    fake = MagicMock()
    fake.get.return_value.iter_content.return_value = [b"tiny"]
    fake.get.return_value.raise_for_status.return_value = None

    assert ia.download_asset(asset, cache_dir=tmp_path, session=fake) is None
