import json

from utils.analytics_schema import (
    build_retention_row,
    build_segment_row,
    build_traffic_source_row,
    build_trend_signal_row,
    build_variant_row,
    build_video_metric_row,
    read_jsonl,
    validate_row,
    write_jsonl_row,
)


def test_video_metric_row_derives_safe_rates_without_dividing_by_zero():
    row = build_video_metric_row(
        video_id="abc123",
        title="Octopus changes skin",
        metrics={"views": 0, "engagedViews": 0, "comments": 0, "subscribersGained": 0},
        context={"category": "ocean", "story_format": "mechanism_reveal"},
    )

    assert row["metrics"]["views"] == 0
    assert row["derived"]["engaged_view_rate"] == 0
    assert row["derived"]["sub_per_1k_engaged"] == 0
    assert validate_row(row, "video_metric") is True


def test_jsonl_round_trip_validates_rows(tmp_path):
    path = tmp_path / "metrics.jsonl"
    row = build_variant_row("hook_style", "outcome_first", "story-1", video_id="vid-1")

    write_jsonl_row(path, row)
    rows = read_jsonl(path)

    assert rows == [json.loads(path.read_text(encoding="utf-8").strip())]
    assert rows[0]["axis"] == "hook_style"


def test_retention_and_trend_rows_have_required_shape():
    retention = build_retention_row("vid", 0.25, 0.91)
    trend = build_trend_signal_row("manual_csv", "octopus skin", 81.5, context={"notes": ["operator import"]})

    assert retention["row_type"] == "retention_bucket"
    assert trend["row_type"] == "trend_signal"
    assert trend["notes"] == ["operator import"]
    assert validate_row(retention) is True
    assert validate_row(trend) is True


def test_traffic_and_segment_rows_have_required_shape():
    traffic = build_traffic_source_row(
        "vid",
        "SHORTS",
        {"views": 10, "averageViewPercentage": 82.5},
        context={"insight_traffic_source_detail": "shorts_feed"},
    )
    segment = build_segment_row("deviceType", "MOBILE", {"views": 8})

    assert traffic["row_type"] == "traffic_source_daily"
    assert traffic["metrics"]["views"] == 10
    assert segment["row_type"] == "segment_metric"
    assert segment["segment_value"] == "MOBILE"
    assert validate_row(traffic) is True
    assert validate_row(segment) is True
