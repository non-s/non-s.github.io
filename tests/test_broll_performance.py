"""Tests for utils/broll_performance.py."""

from __future__ import annotations

import json

from utils import broll_performance


def _write_metric(metrics_dir_path, video_id, views):
    row = {"video_id": video_id, "metrics": {"views": views}}
    with metrics_dir_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def _write_marker(videos_dir, name, video_id, title):
    (videos_dir / name).write_text(json.dumps({"video_id": video_id, "title": title}), encoding="utf-8")


def test_returns_empty_dict_when_no_metrics_file(tmp_path):
    weights = broll_performance.mood_performance_weights(metrics_path=tmp_path / "missing.jsonl", videos_dir=tmp_path)
    assert weights == {}


def test_returns_empty_dict_when_no_bucket_has_enough_samples(tmp_path):
    metrics_path = tmp_path / "metrics.jsonl"
    videos_dir = tmp_path / "_videos"
    videos_dir.mkdir()
    _write_metric(metrics_path, "V1", 100)
    _write_marker(videos_dir, "short-1.done", "V1", "Trovão ao Longe e Chuva para Aliviar a Insônia -- Amber Hours")

    weights = broll_performance.mood_performance_weights(
        metrics_path=metrics_path, videos_dir=videos_dir, min_samples=3
    )
    assert weights == {}


def test_computes_a_relative_weight_once_a_bucket_has_enough_samples(tmp_path):
    metrics_path = tmp_path / "metrics.jsonl"
    videos_dir = tmp_path / "_videos"
    videos_dir.mkdir()
    # "Som de Trovão" bucket: 3 videos averaging 200 views.
    for i, views in enumerate([100, 200, 300], start=1):
        _write_metric(metrics_path, f"RAIN{i}", views)
        _write_marker(videos_dir, f"short-rain-{i}.done", f"RAIN{i}", "Trovão ao Longe e Chuva -- Amber Hours")
    # "Chuva para Dormir Profundamente" bucket: 3 videos averaging 50 views (worse than channel avg).
    for i, views in enumerate([40, 50, 60], start=1):
        _write_metric(metrics_path, f"CAT{i}", views)
        _write_marker(
            videos_dir, f"short-cat-{i}.done", f"CAT{i}", "Chuva Forte para Dormir Profundamente -- Amber Hours"
        )

    weights = broll_performance.mood_performance_weights(
        metrics_path=metrics_path, videos_dir=videos_dir, min_samples=3
    )

    assert weights["Som de Trovão"] > 1.0
    assert weights["Chuva para Dormir Profundamente"] < 1.0


def test_weights_are_clamped_to_the_configured_bounds(tmp_path):
    metrics_path = tmp_path / "metrics.jsonl"
    videos_dir = tmp_path / "_videos"
    videos_dir.mkdir()
    # A wildly outperforming bucket should still clamp to MAX_WEIGHT/MIN_WEIGHT
    # rather than letting the raw ratio run away unbounded.
    for i, views in enumerate([100000, 100000, 100000], start=1):
        _write_metric(metrics_path, f"RAIN{i}", views)
        _write_marker(videos_dir, f"short-rain-{i}.done", f"RAIN{i}", "Trovão ao Longe e Chuva -- Amber Hours")
    for i, views in enumerate([1, 1, 1], start=1):
        _write_metric(metrics_path, f"CAT{i}", views)
        _write_marker(
            videos_dir, f"short-cat-{i}.done", f"CAT{i}", "Chuva Forte para Dormir Profundamente -- Amber Hours"
        )

    weights = broll_performance.mood_performance_weights(
        metrics_path=metrics_path, videos_dir=videos_dir, min_samples=3
    )

    assert weights["Som de Trovão"] == broll_performance.MAX_WEIGHT
    assert weights["Chuva para Dormir Profundamente"] == broll_performance.MIN_WEIGHT


def test_ignores_markers_whose_video_id_has_no_metrics_row(tmp_path):
    metrics_path = tmp_path / "metrics.jsonl"
    videos_dir = tmp_path / "_videos"
    videos_dir.mkdir()
    # A metrics row exists (for some other video), but this marker's id
    # isn't in it -- unmeasured, so it must never count toward a bucket.
    _write_metric(metrics_path, "SOME_OTHER_VIDEO", 999)
    _write_marker(videos_dir, "short-1.done", "NO_METRICS", "Trovão ao Longe e Chuva -- Amber Hours")

    weights = broll_performance.mood_performance_weights(
        metrics_path=metrics_path, videos_dir=videos_dir, min_samples=1
    )
    assert weights == {}
