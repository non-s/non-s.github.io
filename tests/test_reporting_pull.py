from scripts.reporting_pull import pull
from utils.analytics_schema import read_jsonl


def test_reporting_pull_normalizes_csv(tmp_path):
    source = tmp_path / "_data" / "reporting_import"
    source.mkdir(parents=True)
    (source / "report.csv").write_text(
        "Video ID,Video title,Views,Engaged views,Average percentage viewed,Date\nabc,Octopus,100,80,72,2026-06-10\n",
        encoding="utf-8",
    )

    report = pull(tmp_path)
    rows = read_jsonl(tmp_path / "_data" / "analytics" / "reporting_video_metrics.jsonl")

    assert report["rows"] == 1
    assert rows[0]["video_id"] == "abc"


def test_reporting_pull_accepts_the_lowercase_snake_case_header_variant(tmp_path):
    """The Reporting API's own CSV export uses snake_case headers
    (video_id, views, ...), distinct from the "Video ID"/"Views" headers
    a Studio-exported CSV uses -- both must parse."""
    source = tmp_path / "_data" / "reporting_import"
    source.mkdir(parents=True)
    (source / "report.csv").write_text(
        "video_id,title,views,engaged_views\nxyz,Rainy Night,50,40\n",
        encoding="utf-8",
    )

    report = pull(tmp_path)
    rows = read_jsonl(tmp_path / "_data" / "analytics" / "reporting_video_metrics.jsonl")

    assert report["rows"] == 1
    assert rows[0]["video_id"] == "xyz"
    assert rows[0]["metrics"]["views"] == 50


def test_reporting_pull_skips_rows_with_no_video_id(tmp_path):
    """A row missing every id column variant must be dropped, not crash
    the whole import or get written with a blank/garbage id."""
    source = tmp_path / "_data" / "reporting_import"
    source.mkdir(parents=True)
    (source / "report.csv").write_text(
        "Video title,Views\nNo ID Here,100\n",
        encoding="utf-8",
    )

    report = pull(tmp_path)
    rows = read_jsonl(tmp_path / "_data" / "analytics" / "reporting_video_metrics.jsonl")

    assert report["rows"] == 0
    assert rows == []


def test_reporting_pull_handles_a_utf8_bom_prefixed_csv(tmp_path):
    """Exported CSVs commonly carry a UTF-8 BOM; it must not end up glued
    onto the first header name (which would silently break every lookup
    for that column)."""
    source = tmp_path / "_data" / "reporting_import"
    source.mkdir(parents=True)
    (source / "report.csv").write_bytes(
        "Video ID,Views\nabc,10\n".encode("utf-8-sig"),
    )

    report = pull(tmp_path)
    rows = read_jsonl(tmp_path / "_data" / "analytics" / "reporting_video_metrics.jsonl")

    assert report["rows"] == 1
    assert rows[0]["video_id"] == "abc"


def test_reporting_pull_defaults_missing_metric_columns_to_zero(tmp_path):
    source = tmp_path / "_data" / "reporting_import"
    source.mkdir(parents=True)
    (source / "report.csv").write_text("Video ID\nabc\n", encoding="utf-8")

    pull(tmp_path)
    rows = read_jsonl(tmp_path / "_data" / "analytics" / "reporting_video_metrics.jsonl")

    assert rows[0]["metrics"]["views"] == 0
    assert rows[0]["metrics"]["likes"] == 0


def test_reporting_pull_processes_every_csv_file_in_the_import_directory(tmp_path):
    source = tmp_path / "_data" / "reporting_import"
    source.mkdir(parents=True)
    (source / "report_a.csv").write_text("Video ID,Views\naaa,1\n", encoding="utf-8")
    (source / "report_b.csv").write_text("Video ID,Views\nbbb,2\n", encoding="utf-8")

    report = pull(tmp_path)
    rows = read_jsonl(tmp_path / "_data" / "analytics" / "reporting_video_metrics.jsonl")

    assert report["rows"] == 2
    assert {r["video_id"] for r in rows} == {"aaa", "bbb"}


def test_reporting_pull_returns_zero_rows_when_import_directory_is_empty(tmp_path):
    source = tmp_path / "_data" / "reporting_import"
    source.mkdir(parents=True)

    report = pull(tmp_path)

    assert report["rows"] == 0
    assert report["source_files"] == []


def test_reporting_pull_returns_zero_rows_when_import_directory_is_missing(tmp_path):
    report = pull(tmp_path)
    assert report["rows"] == 0
