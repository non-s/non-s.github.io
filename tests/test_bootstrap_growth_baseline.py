import json

from scripts.bootstrap_growth_baseline import build_baseline
from utils.analytics_schema import read_jsonl


def test_bootstrap_growth_baseline_is_safe_with_empty_repo_shape(tmp_path):
    summary = build_baseline(tmp_path)

    analytics = tmp_path / "_data" / "analytics"
    assert summary["video_metric_rows"] == 0
    assert summary["variant_assignment_rows"] == 0
    assert (analytics / "video_metrics.jsonl").exists()
    assert (analytics / "variant_assignments.jsonl").exists()
    assert json.loads((analytics / "weekly_summary.json").read_text(encoding="utf-8"))["shorts_tracked"] == 0


def test_bootstrap_growth_baseline_uses_latest_top_performers(tmp_path):
    analytics = tmp_path / "_data" / "analytics"
    analytics.mkdir(parents=True)
    (analytics / "latest.json").write_text(
        json.dumps(
            {
                "pulled_at": "2026-06-10T00:00:00+00:00",
                "shorts_tracked": 1,
                "total_views": 120,
                "top_performers": [
                    {
                        "video_id": "abc",
                        "title": "Octopus changes skin",
                        "views": 120,
                        "average_view_percentage": 84.2,
                        "category": "ocean",
                        "story_format": "mechanism_reveal",
                        "experiments": {"hook_style": "outcome_first"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    summary = build_baseline(tmp_path)
    rows = read_jsonl(analytics / "video_metrics.jsonl")

    assert summary["video_metric_rows"] == 1
    assert rows[0]["video_id"] == "abc"
    assert rows[0]["metrics"]["views"] == 120
