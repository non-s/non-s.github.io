from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from utils.publication_cadence import decide_cadence


def test_manual_dispatch_bypasses_schedule_not_quality(tmp_path):
    decision = decide_cadence(tmp_path, manual=True)
    assert decision.generate is True
    assert decision.reason == "manual dispatch"


def test_cadence_enforces_learning_interval(tmp_path):
    now = datetime(2026, 1, 2, tzinfo=UTC)
    (tmp_path / "video_tags.json").write_text(
        json.dumps({"v": {"uploaded_at": (now - timedelta(hours=2)).isoformat()}}), encoding="utf-8"
    )
    decision = decide_cadence(tmp_path, now=now)
    assert decision.generate is False
    assert "four-hour" in decision.reason


def test_cadence_enforces_daily_limit(tmp_path, monkeypatch):
    monkeypatch.setenv("LIQUID_WIRE_DAILY_PUBLICATION_LIMIT", "2")
    now = datetime(2026, 1, 2, tzinfo=UTC)
    tags = {
        str(index): {"uploaded_at": (now - timedelta(hours=5 + index)).isoformat()}
        for index in range(2)
    }
    (tmp_path / "video_tags.json").write_text(json.dumps(tags), encoding="utf-8")
    decision = decide_cadence(tmp_path, now=now)
    assert decision.generate is False
    assert decision.daily_limit == 2


def test_cadence_allows_when_budget_and_interval_are_clear(tmp_path):
    now = datetime(2026, 1, 2, tzinfo=UTC)
    (tmp_path / "video_tags.json").write_text(
        json.dumps({"v": {"uploaded_at": (now - timedelta(hours=8)).isoformat()}}), encoding="utf-8"
    )
    assert decide_cadence(tmp_path, now=now).generate is True
