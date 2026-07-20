import json
from unittest.mock import MagicMock

import scripts.search_broll_candidates as search_broll_candidates
from utils.broll import BrollClip


def test_main_prints_one_result_list_per_query(monkeypatch, capsys):
    clip = BrollClip(
        source="pixabay",
        url="https://pixabay.com/videos/id-123",
        download_url="https://cdn.pixabay.com/vid/123.mp4",
        width=1920,
        height=1080,
        duration_s=12.0,
        source_metadata={"id": 123, "tags": "anime, rain, window"},
    )
    fetch = MagicMock(return_value=[clip])
    monkeypatch.setattr(search_broll_candidates, "fetch_pixabay", fetch)
    monkeypatch.setattr(search_broll_candidates.sys, "argv", ["search_broll_candidates.py", "anime rain window"])

    assert search_broll_candidates.main() == 0

    out = json.loads(capsys.readouterr().out)
    assert list(out.keys()) == ["anime rain window"]
    hit = out["anime rain window"][0]
    assert hit["id"] == 123
    assert hit["download_url"] == "https://cdn.pixabay.com/vid/123.mp4"
    assert hit["anime_style_tag_match"] is True
    fetch.assert_called_once_with("anime rain window", per_page=8)


def test_main_splits_pipe_delimited_queries(monkeypatch, capsys):
    """Regression: the workflow passes queries as one shell argument (env
    var, not unquoted interpolation) since GitHub Actions substitutes
    ${{ inputs.queries }} as raw text -- an unquoted multi-word query
    would otherwise get word-split by bash into one query per word."""
    fetch = MagicMock(return_value=[])
    monkeypatch.setattr(search_broll_candidates, "fetch_pixabay", fetch)
    monkeypatch.setattr(
        search_broll_candidates.sys,
        "argv",
        ["search_broll_candidates.py", "anime rain window|anime cozy room fireplace"],
    )

    search_broll_candidates.main()

    fetch.assert_any_call("anime rain window", per_page=8)
    fetch.assert_any_call("anime cozy room fireplace", per_page=8)
    assert fetch.call_count == 2


def test_main_flags_hits_that_dont_match_the_anime_style_signals(monkeypatch, capsys):
    clip = BrollClip(
        source="pixabay",
        url="https://pixabay.com/videos/id-456",
        download_url="https://cdn.pixabay.com/vid/456.mp4",
        width=1920,
        height=1080,
        duration_s=8.0,
        source_metadata={"id": 456, "tags": "man, books, library"},
    )
    monkeypatch.setattr(search_broll_candidates, "fetch_pixabay", MagicMock(return_value=[clip]))
    monkeypatch.setattr(search_broll_candidates.sys, "argv", ["search_broll_candidates.py", "anime library reading"])

    search_broll_candidates.main()

    out = json.loads(capsys.readouterr().out)
    assert out["anime library reading"][0]["anime_style_tag_match"] is False
