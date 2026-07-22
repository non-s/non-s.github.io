import json
from unittest.mock import MagicMock

import scripts.search_storm_broll_candidates as search_storm
from utils.broll import BrollClip


def test_main_prints_one_result_list_per_query_using_film_video_type(monkeypatch, capsys):
    clip = BrollClip(
        source="pixabay",
        url="https://pixabay.com/videos/id-123",
        download_url="https://cdn.pixabay.com/vid/123.mp4",
        width=1920,
        height=1080,
        duration_s=12.0,
        source_metadata={
            "pixabay_video_id": "123",
            "tags": "rain, night, window",
            "photographer": "someartist",
            "photographer_url": "https://pixabay.com/users/someartist-1/",
        },
    )
    fetch = MagicMock(return_value=[clip])
    monkeypatch.setattr(search_storm, "fetch_pixabay", fetch)
    monkeypatch.setattr(search_storm.sys, "argv", ["search_storm_broll_candidates.py", "heavy rain window night"])

    assert search_storm.main() == 0

    out = json.loads(capsys.readouterr().out)
    assert list(out.keys()) == ["heavy rain window night"]
    hit = out["heavy rain window night"][0]
    assert hit["id"] == "123"
    assert hit["storm_relevant_tag_match"] is True
    fetch.assert_called_once_with("heavy rain window night", per_page=8, video_type="film")


def test_main_defaults_to_the_built_in_storm_queries_when_none_given(monkeypatch, capsys):
    fetch = MagicMock(return_value=[])
    monkeypatch.setattr(search_storm, "fetch_pixabay", fetch)
    monkeypatch.setattr(search_storm.sys, "argv", ["search_storm_broll_candidates.py"])

    search_storm.main()

    called_queries = {call.args[0] for call in fetch.call_args_list}
    assert called_queries == set(search_storm.DEFAULT_QUERIES)


def test_main_splits_pipe_delimited_queries(monkeypatch, capsys):
    fetch = MagicMock(return_value=[])
    monkeypatch.setattr(search_storm, "fetch_pixabay", fetch)
    monkeypatch.setattr(
        search_storm.sys,
        "argv",
        ["search_storm_broll_candidates.py", "heavy rain window night|thunderstorm lightning night sky"],
    )

    search_storm.main()

    fetch.assert_any_call("heavy rain window night", per_page=8, video_type="film")
    fetch.assert_any_call("thunderstorm lightning night sky", per_page=8, video_type="film")
    assert fetch.call_count == 2


def test_main_passes_through_a_custom_video_type(monkeypatch, capsys):
    fetch = MagicMock(return_value=[])
    monkeypatch.setattr(search_storm, "fetch_pixabay", fetch)
    monkeypatch.setattr(
        search_storm.sys,
        "argv",
        ["search_storm_broll_candidates.py", "cartoon piano cozy room", "--video-type", "animation"],
    )

    search_storm.main()

    fetch.assert_called_once_with("cartoon piano cozy room", per_page=8, video_type="animation")


def test_looks_storm_relevant_flags_expected_signals():
    assert search_storm.looks_storm_relevant("rain, night, city")
    assert search_storm.looks_storm_relevant("Thunderstorm over the hills")
    assert not search_storm.looks_storm_relevant("man, books, library")
    assert not search_storm.looks_storm_relevant("")
