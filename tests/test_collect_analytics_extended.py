import json

from scripts.collect_analytics_extended import collect


def test_collect_extended_writes_warehouse_files_with_partial_data(tmp_path):
    analytics = tmp_path / "_data" / "analytics"
    analytics.mkdir(parents=True)
    (analytics / "latest.json").write_text(
        json.dumps(
            {
                "pulled_at": "2026-06-10T00:00:00+00:00",
                "top_performers": [
                    {
                        "video_id": "vid1",
                        "title": "Octopus changes skin",
                        "views": 10,
                        "engaged_views": 8,
                        "traffic_sources": {"SHORTS": 7, "YT_SEARCH": 3},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "_data" / "youtube_intelligence.json").write_text(
        json.dumps({"analytics_reports": [{"id": "country", "status": "not_authorized"}]}),
        encoding="utf-8",
    )

    report = collect(tmp_path)

    assert report["rows"] == 1
    assert report["traffic_source_rows"] == 2
    assert (analytics / "video_core_daily.jsonl").exists()
    assert (analytics / "traffic_source_daily.jsonl").read_text(encoding="utf-8").count("\n") == 2
    assert report["missing_analytics_reports"][0]["id"] == "country"
