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


def test_import_reach_handles_a_utf8_bom_prefixed_csv(tmp_path):
    source = tmp_path / "reach.csv"
    source.write_bytes(
        "Video ID,Video title,Stayed to watch,Swiped away,Views\nabc,Octopus,70,30,100\n".encode("utf-8-sig")
    )

    report = import_reach(tmp_path, str(source))

    assert report["rows"] == 1
    assert report["summary"]["stayed_to_watch_rate"] == 0.7


def test_import_reach_keeps_going_when_one_of_several_files_is_malformed(tmp_path, monkeypatch):
    """A single bad CSV file must not sink the whole import -- the good
    file's rows should still land, and the bad one is recorded as an
    error row instead of raising."""
    import_dir = tmp_path / "imports"
    import_dir.mkdir()
    (import_dir / "good.csv").write_text(
        "Video ID,Video title,Stayed to watch,Swiped away,Views\nabc,Octopus,70,30,100\n",
        encoding="utf-8",
    )
    bad_path = import_dir / "bad.csv"
    bad_path.write_text("irrelevant", encoding="utf-8")

    from utils import studio_reach_schema

    def fake_read_reach_csv(path, *, imported_at=None):
        if path == bad_path:
            raise ValueError("simulated malformed CSV")
        return studio_reach_schema.read_reach_csv(path, imported_at=imported_at)

    monkeypatch.setattr("scripts.import_studio_reach_export.read_reach_csv", fake_read_reach_csv)

    report = import_reach(tmp_path, str(import_dir))

    assert report["rows"] == 1  # only the good file's row counted
    assert len(report["source_files"]) == 2  # both files were attempted
