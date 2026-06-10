from utils.data_quality import build_data_quality_report


def test_data_quality_report_tracks_metric_origins():
    report = build_data_quality_report([
        {
            "video_id": "abc",
            "analytics": {
                "views": 100,
                "averageViewPercentage": 74,
            },
        },
        {"video_id": "missing"},
    ])

    assert report["metrics"]["views"]["observed"] == 1
    assert report["metrics"]["retention"]["observed"] == 1
    assert report["metrics"]["subscribers"]["missing"] == 2
    assert "origin" in report["metrics"]["views"]
