"""Targeted coverage for utils/content_strategy.py uncovered paths."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from utils import content_strategy


def _mock_now(month: int, day: int, hour: int):
    return patch(
        "utils.content_strategy.datetime",
        **{"now.return_value": datetime(2026, month, day, hour, 0, 0, tzinfo=UTC)},
    )


def test_viral_boosted_scenes_with_valid_signals(tmp_path, monkeypatch) -> None:
    viral_file = tmp_path / "viral_signals.json"
    monkeypatch.setattr(content_strategy, "_viral_signals_file", lambda: viral_file)
    now = datetime.now(UTC).isoformat()
    viral_file.write_text(
        json.dumps([{"scene": "dark liquid wire", "detected_at": now}]), encoding="utf-8"
    )
    boosted = content_strategy.viral_boosted_scenes()
    assert boosted == {"dark liquid wire": content_strategy._VIRAL_BOOST}


def test_viral_boosted_scenes_expired_signals_ignored(tmp_path, monkeypatch) -> None:
    viral_file = tmp_path / "viral_signals.json"
    monkeypatch.setattr(content_strategy, "_viral_signals_file", lambda: viral_file)
    old = (datetime.now(UTC) - timedelta(days=20)).isoformat()
    viral_file.write_text(
        json.dumps([{"scene": "dark liquid wire", "detected_at": old}]), encoding="utf-8"
    )
    assert content_strategy.viral_boosted_scenes() == {}


def test_viral_boosted_scenes_ctr_avp_modulation(tmp_path, monkeypatch) -> None:
    viral_file = tmp_path / "viral_signals.json"
    monkeypatch.setattr(content_strategy, "_viral_signals_file", lambda: viral_file)
    now = datetime.now(UTC).isoformat()
    viral_file.write_text(
        json.dumps(
            [
                {"scene": "nebula cloud", "detected_at": now, "ctr": 0.08, "avp": 0.6},
                {"scene": "dark liquid wire", "detected_at": now, "ctr": 0.01, "avp": 0.2},
            ]
        ),
        encoding="utf-8",
    )
    boosted = content_strategy.viral_boosted_scenes()
    assert boosted["nebula cloud"] > boosted["dark liquid wire"]
    assert boosted["nebula cloud"] == content_strategy._VIRAL_BOOST + 0.3 + 0.2


def test_viral_boosted_scenes_non_list_returns_empty(tmp_path, monkeypatch) -> None:
    viral_file = tmp_path / "viral_signals.json"
    monkeypatch.setattr(content_strategy, "_viral_signals_file", lambda: viral_file)
    viral_file.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
    assert content_strategy.viral_boosted_scenes() == {}


def test_viral_boosted_scenes_invalid_detected_at_ignored(tmp_path, monkeypatch) -> None:
    viral_file = tmp_path / "viral_signals.json"
    monkeypatch.setattr(content_strategy, "_viral_signals_file", lambda: viral_file)
    viral_file.write_text(
        json.dumps([{"scene": "dark liquid wire", "detected_at": "not-a-date"}]), encoding="utf-8"
    )
    assert content_strategy.viral_boosted_scenes() == {}


def test_viral_boosted_scenes_z_suffix_parsed(tmp_path, monkeypatch) -> None:
    viral_file = tmp_path / "viral_signals.json"
    monkeypatch.setattr(content_strategy, "_viral_signals_file", lambda: viral_file)
    now_z = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    viral_file.write_text(
        json.dumps([{"scene": "nebula cloud", "detected_at": now_z}]), encoding="utf-8"
    )
    boosted = content_strategy.viral_boosted_scenes()
    assert "nebula cloud" in boosted


def test_scene_for_mood_priority_boost_for_first_uploads(tmp_path, monkeypatch) -> None:
    import random

    random.seed(1)
    perf_file = tmp_path / "scene_performance.json"
    viral_file = tmp_path / "viral_signals.json"
    counter_file = tmp_path / "upload_language_counter.json"
    monkeypatch.setattr(content_strategy, "_scene_performance_file", lambda: perf_file)
    monkeypatch.setattr(content_strategy, "_viral_signals_file", lambda: viral_file)
    counter_file.write_text(json.dumps({"count": 3}), encoding="utf-8")
    results = [content_strategy.scene_for_mood("focus") for _ in range(100)]
    assert all(r in content_strategy.SCENE_CATEGORIES["focus"] for r in results)
    assert results.count("calm wireframe flow") >= 1


def test_seasonal_mood_holiday_relax() -> None:
    with _mock_now(12, 25, 12):
        assert content_strategy._seasonal_mood() == "relax"


def test_seasonal_mood_new_year_relax() -> None:
    with _mock_now(1, 3, 10):
        assert content_strategy._seasonal_mood() == "relax"


def test_seasonal_mood_november_ambient() -> None:
    with _mock_now(11, 25, 12):
        assert content_strategy._seasonal_mood() == "ambient"


def test_seasonal_mood_february_focus() -> None:
    with _mock_now(2, 13, 9):
        assert content_strategy._seasonal_mood() == "focus"


def test_seasonal_mood_october_ambient() -> None:
    with _mock_now(10, 30, 12):
        assert content_strategy._seasonal_mood() == "ambient"


def test_seasonal_mood_none_outside_window() -> None:
    with _mock_now(7, 15, 12):
        assert content_strategy._seasonal_mood() is None


def test_min_quality_score_for_slot_all_ranges() -> None:
    for hour in range(6, 12):
        assert content_strategy.min_quality_score_for_slot(hour) == 0.82
    for hour in [12, 13, 14, 15, 16, 17, 18, 19, 20, 21]:
        assert content_strategy.min_quality_score_for_slot(hour) == 0.78
    for hour in [22, 23, 0, 1, 2, 3, 4, 5]:
        assert content_strategy.min_quality_score_for_slot(hour) == 0.75


def test_mood_for_now_uses_seasonal_when_active() -> None:
    with _mock_now(12, 25, 7):
        assert content_strategy.mood_for_now() == "relax"


def test_mood_for_now_uses_hourly_when_no_seasonal() -> None:
    with _mock_now(7, 15, 15):
        assert content_strategy.mood_for_now() in ("focus", "ambient", "relax")
