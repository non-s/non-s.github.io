from unittest.mock import patch

from utils.gbif_research import species_card
from utils.openverse_catalog import search_open_images


@patch("utils.gbif_research.requests.get")
def test_gbif_card_is_conservative_and_attributable(mock_get):
    mock_get.return_value.json.return_value = {"scientificName": "Felis catus", "rank": "SPECIES", "status": "ACCEPTED"}
    card = species_card("cat")
    assert card["scientific_name"] == "Felis catus"
    assert "verify" in card["editorial_rule"]


@patch("utils.openverse_catalog.requests.get")
def test_openverse_filters_noncommercial_candidates(mock_get):
    mock_get.return_value.json.return_value = {"results": [
        {"title": "Cat", "creator": "A", "license": "by", "foreign_landing_url": "https://source"},
        {"title": "No", "creator": "B", "license": "by-nc", "foreign_landing_url": "https://source2"},
    ]}
    candidates = search_open_images("cat")
    assert [item["title"] for item in candidates] == ["Cat"]
