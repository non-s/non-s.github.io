import json

from scripts.compact_analytics import compact


def test_compact_analytics_writes_monthly_partitions(tmp_path):
    analytics = tmp_path / "_data" / "analytics"
    analytics.mkdir(parents=True)
    (analytics / "video_metrics.jsonl").write_text(
        json.dumps({"pulled_at": "2026-06-10T00:00:00+00:00", "metrics": {"views": 10}}) + "\n",
        encoding="utf-8",
    )

    report = compact(tmp_path)

    assert report["datasets"]["video_metrics"]["rows"] == 1
    assert (analytics / "partitions" / "video_metrics" / "2026-06.jsonl").exists()
