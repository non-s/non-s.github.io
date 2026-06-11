from __future__ import annotations

import json
from datetime import datetime, timezone

from scripts import publish_window


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_publish_window_writes_publish_decision(monkeypatch, tmp_path):
    _write_json(tmp_path / "_data" / "publish_schedule.json", {"recommended_slots": ["05:23"]})
    _write_json(
        tmp_path / "_data" / "stories_queue.json",
        {"stories": [{"id": "top", "title": "Ducks fake injuries", "script": "Ducks fake injuries to protect young."}]},
    )
    monkeypatch.setattr(
        publish_window,
        "score_story",
        lambda story: {"score": 85, "opportunity": {"score": 72}, "approved": True},
    )
    ledger = tmp_path / "_data" / "publish_slot_decisions.jsonl"

    decision = publish_window.evaluate_publish_window(
        root=tmp_path,
        now=datetime(2026, 6, 11, 5, 23, tzinfo=timezone.utc),
        env={"ADAPTIVE_CADENCE_ENABLED": "1", "MIN_SLOT_PUBLISH_SCORE": "72", "MIN_QUEUE_OPPORTUNITY_SCORE": "50"},
        decisions_path=ledger,
    )

    assert decision["decision"] == "publish"
    assert decision["top_candidate_id"] == "top"
    assert ledger.exists()
    assert json.loads(ledger.read_text(encoding="utf-8").splitlines()[0])["decision"] == "publish"


def test_publish_window_skips_empty_queue(tmp_path):
    _write_json(tmp_path / "_data" / "publish_schedule.json", {"recommended_slots": ["05:23"]})
    _write_json(tmp_path / "_data" / "stories_queue.json", {"stories": []})

    decision = publish_window.evaluate_publish_window(
        root=tmp_path,
        now=datetime(2026, 6, 11, 5, 23, tzinfo=timezone.utc),
        env={"ADAPTIVE_CADENCE_ENABLED": "1"},
        decisions_path=tmp_path / "decisions.jsonl",
    )

    assert decision["decision"] == "skip_no_eligible_story"
    assert "no_eligible_story" in decision["reasons"]


def test_publish_window_skips_low_quality_candidate(monkeypatch, tmp_path):
    _write_json(tmp_path / "_data" / "publish_schedule.json", {"recommended_slots": ["05:23"]})
    _write_json(tmp_path / "_data" / "stories_queue.json", {"stories": [{"id": "weak", "title": "Weak"}]})
    monkeypatch.setattr(
        publish_window,
        "score_story",
        lambda story: {"score": 41, "opportunity": {"score": 20}, "approved": False},
    )

    decision = publish_window.evaluate_publish_window(
        root=tmp_path,
        now=datetime(2026, 6, 11, 5, 23, tzinfo=timezone.utc),
        env={"ADAPTIVE_CADENCE_ENABLED": "1", "MIN_SLOT_PUBLISH_SCORE": "72", "MIN_QUEUE_OPPORTUNITY_SCORE": "50"},
        decisions_path=tmp_path / "decisions.jsonl",
    )

    assert decision["decision"] == "skip_low_queue_quality"
    assert "publish_score_below_threshold" in decision["reasons"]
    assert "opportunity_score_below_threshold" in decision["reasons"]


def test_publish_window_skips_outside_slot(tmp_path):
    _write_json(tmp_path / "_data" / "publish_schedule.json", {"recommended_slots": ["05:23"]})

    decision = publish_window.evaluate_publish_window(
        root=tmp_path,
        now=datetime(2026, 6, 11, 19, 23, tzinfo=timezone.utc),
        env={"ADAPTIVE_CADENCE_ENABLED": "1"},
        decisions_path=tmp_path / "decisions.jsonl",
    )

    assert decision["decision"] == "skip_outside_slot"


def test_publish_window_publishes_delayed_slot_inside_grace(monkeypatch, tmp_path):
    _write_json(tmp_path / "_data" / "publish_schedule.json", {"recommended_slots": ["14:23"]})
    _write_json(
        tmp_path / "_data" / "stories_queue.json",
        {"stories": [{"id": "late", "title": "Late slot recovery", "script": "A strong story is still valid."}]},
    )
    monkeypatch.setattr(
        publish_window,
        "score_story",
        lambda story: {"score": 90, "opportunity": {"score": 80}, "approved": True},
    )

    decision = publish_window.evaluate_publish_window(
        root=tmp_path,
        now=datetime(2026, 6, 11, 15, 43, tzinfo=timezone.utc),
        env={
            "ADAPTIVE_CADENCE_ENABLED": "1",
            "PUBLISH_SLOT_GRACE_MINUTES": "90",
            "MIN_SLOT_PUBLISH_SCORE": "72",
            "MIN_QUEUE_OPPORTUNITY_SCORE": "50",
        },
        decisions_path=tmp_path / "decisions.jsonl",
    )

    assert decision["decision"] == "publish"
    assert decision["slot_label"] == "14:23"
    assert "delayed_slot_recovery" in decision["reasons"]


def test_watchdog_dispatch_does_not_bypass_cadence(tmp_path):
    _write_json(tmp_path / "_data" / "publish_schedule.json", {"recommended_slots": ["05:23"]})

    decision = publish_window.evaluate_publish_window(
        root=tmp_path,
        now=datetime(2026, 6, 11, 19, 23, tzinfo=timezone.utc),
        env={
            "ADAPTIVE_CADENCE_ENABLED": "1",
            "GITHUB_EVENT_NAME": "workflow_dispatch",
            "WORKFLOW_DISPATCH_REASON": "watchdog recovery for missed slot 2026-06-11T19:23:00+00:00",
        },
        decisions_path=tmp_path / "decisions.jsonl",
    )

    assert decision["decision"] == "skip_outside_slot"


def test_publish_window_legacy_mode_does_not_block_empty_queue(tmp_path):
    decision = publish_window.evaluate_publish_window(
        root=tmp_path,
        now=datetime(2026, 6, 11, 19, 23, tzinfo=timezone.utc),
        env={"ADAPTIVE_CADENCE_ENABLED": "0"},
        decisions_path=tmp_path / "decisions.jsonl",
    )

    assert decision["decision"] == "publish"
    assert "adaptive_cadence_disabled" in decision["reasons"]


def test_publish_window_manual_dispatch_bypasses_adaptive_skip(tmp_path):
    decision = publish_window.evaluate_publish_window(
        root=tmp_path,
        now=datetime(2026, 6, 11, 19, 23, tzinfo=timezone.utc),
        env={"ADAPTIVE_CADENCE_ENABLED": "1", "GITHUB_EVENT_NAME": "workflow_dispatch"},
        decisions_path=tmp_path / "decisions.jsonl",
    )

    assert decision["decision"] == "publish"
    assert "manual_dispatch" in decision["reasons"]
