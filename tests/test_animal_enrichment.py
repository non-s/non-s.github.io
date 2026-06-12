"""Tests for GBIF and Wikimedia Commons enrichment."""

from unittest.mock import MagicMock, patch

from utils import animal_enrichment


def test_gbif_species_context_returns_taxonomy(monkeypatch, tmp_path):
    monkeypatch.setattr(animal_enrichment, "_CACHE_DIR", tmp_path)
    response = MagicMock(status_code=200)
    response.json.return_value = {
        "matchType": "EXACT",
        "usageKey": 2435099,
        "scientificName": "Octopus vulgaris",
        "canonicalName": "Octopus vulgaris",
        "rank": "SPECIES",
        "family": "Octopodidae",
    }
    with patch.object(animal_enrichment, "_session") as factory:
        session = MagicMock()
        session.get.return_value = response
        factory.return_value = session
        value = animal_enrichment.gbif_species_context("Octopus vulgaris")
    assert value["usage_key"] == 2435099
    assert value["family"] == "Octopodidae"


def test_commons_image_rejects_noncommercial_license(monkeypatch, tmp_path):
    monkeypatch.setattr(animal_enrichment, "_CACHE_DIR", tmp_path)
    response = MagicMock(status_code=200)
    response.json.return_value = {
        "query": {
            "pages": {
                "1": {
                    "imageinfo": [
                        {
                            "thumburl": "https://example/image.jpg",
                            "extmetadata": {"LicenseShortName": {"value": "CC BY-NC 4.0"}},
                        }
                    ]
                }
            }
        }
    }
    with patch.object(animal_enrichment, "_session") as factory:
        session = MagicMock()
        session.get.return_value = response
        factory.return_value = session
        assert animal_enrichment.commons_image("octopus") == {}


def test_commons_image_accepts_cc_by(monkeypatch, tmp_path):
    monkeypatch.setattr(animal_enrichment, "_CACHE_DIR", tmp_path)
    response = MagicMock(status_code=200)
    response.json.return_value = {
        "query": {
            "pages": {
                "1": {
                    "title": "File:Octopus.jpg",
                    "imageinfo": [
                        {
                            "thumburl": "https://example/image.jpg",
                            "descriptionurl": "https://commons.wikimedia.org/wiki/File:Octopus.jpg",
                            "extmetadata": {"LicenseShortName": {"value": "CC BY-SA 4.0"}},
                        }
                    ],
                }
            }
        }
    }
    with patch.object(animal_enrichment, "_session") as factory:
        session = MagicMock()
        session.get.return_value = response
        factory.return_value = session
        assert animal_enrichment.commons_image("octopus")["license"] == "CC BY-SA 4.0"
