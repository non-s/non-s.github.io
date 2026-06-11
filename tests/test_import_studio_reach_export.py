import json

from scripts.import_studio_reach_export import import_reach
from utils.studio_reach_schema import build_reach_row, summarize_reach


def test_reach_schema_accepts_studio_aliases():
    row = build_reach_row(
        {
            "Video ID": "abc",
            "Video title": "Octopus signal",
            "Stayed to watch": "70",
            "Swiped away": "30",
            "Views": "100",
        }
    )

    assert row["video_id"] == "abc"
    assert row["metrics"]["stayed_to_watch_rate"] == 0.7
    assert row["metrics"]["swipe_away_rate"] == 0.3


def test_import_reach_writes_jsonl_and_latest(tmp_path):
    source = tmp_path / "reach.csv"
    source.write_text(
        "Video ID,Video title,Stayed to watch,Swiped away,Views\nabc,Octopus,70,30,100\n",
        encoding="utf-8",
    )

    report = import_reach(tmp_path, str(source))
    latest = json.loads((tmp_path / "_data" / "analytics" / "studio_reach_latest.json").read_text())
    rows = (tmp_path / "_data" / "analytics" / "studio_reach_daily.jsonl").read_text().splitlines()

    assert report["rows"] == 1
    assert latest["summary"]["stayed_to_watch_rate"] == 0.7
    assert len(rows) == 1


def test_summarize_reach_handles_empty_rows():
    assert summarize_reach([])["rows"] == 0
