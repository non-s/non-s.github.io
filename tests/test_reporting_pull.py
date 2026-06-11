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
