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


def test_publish_window_still_requires_candidate_when_adaptive_cadence_is_disabled(tmp_path):
    _write_json(tmp_path / "_data" / "publish_schedule.json", {"recommended_slots": ["05:23"]})
    _write_json(tmp_path / "_data" / "stories_queue.json", {"stories": []})

    decision = publish_window.evaluate_publish_window(
        root=tmp_path,
        now=datetime(2026, 6, 11, 5, 23, tzinfo=timezone.utc),
        env={"ADAPTIVE_CADENCE_ENABLED": "0"},
        decisions_path=tmp_path / "decisions.jsonl",
    )

    assert decision["decision"] == "skip_no_eligible_story"
    assert decision["reasons"] == ["adaptive_cadence_disabled", "no_eligible_story"]


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


def test_publish_window_ignores_queue_prune_rewrite_candidate(monkeypatch, tmp_path):
    _write_json(tmp_path / "_data" / "publish_schedule.json", {"recommended_slots": ["05:23"]})
    _write_json(
        tmp_path / "_data" / "stories_queue.json",
        {
            "stories": [
                {
                    "id": "rewrite",
                    "title": "Rewrite candidate",
                    "queue_prune": {"state": "rewrite"},
                    "publish_score": {"approved": True, "state": "publish_ready"},
                },
                {
                    "id": "ready",
                    "title": "Ready candidate",
                    "queue_prune": {"state": "publish_ready"},
                    "publish_score": {"approved": True, "state": "publish_ready"},
                },
            ]
        },
    )
    monkeypatch.setattr(
        publish_window,
        "score_story",
        lambda story: {"score": 90 if story["id"] == "rewrite" else 80, "opportunity": {"score": 80}, "approved": True},
    )

    decision = publish_window.evaluate_publish_window(
        root=tmp_path,
        now=datetime(2026, 6, 11, 5, 23, tzinfo=timezone.utc),
        env={"ADAPTIVE_CADENCE_ENABLED": "1", "MIN_SLOT_PUBLISH_SCORE": "72", "MIN_QUEUE_OPPORTUNITY_SCORE": "50"},
        decisions_path=tmp_path / "decisions.jsonl",
    )

    assert decision["decision"] == "publish"
    assert decision["top_candidate_id"] == "ready"


def test_publish_window_ignores_editor_rejected_candidate(monkeypatch, tmp_path):
    _write_json(tmp_path / "_data" / "publish_schedule.json", {"recommended_slots": ["05:23"]})
    _write_json(
        tmp_path / "_data" / "stories_queue.json",
        {
            "stories": [
                {
                    "id": "cooldown",
                    "title": "Bees show the wing beat before the payoff",
                    "queue_prune": {"state": "publish_ready"},
                    "editorial": {"approved": False, "state": "cooldown_subject"},
                    "publish_score": {"approved": True, "state": "publish_ready"},
                },
                {
                    "id": "ready",
                    "title": "Octopuses vanish against coral in seconds",
                    "queue_prune": {"state": "publish_ready"},
                    "editorial": {"approved": True, "state": "publish_now"},
                    "publish_score": {"approved": True, "state": "publish_ready"},
                },
            ]
        },
    )
    monkeypatch.setattr(
        publish_window,
        "score_story",
        lambda story: {
            "score": 95 if story["id"] == "cooldown" else 80,
            "opportunity": {"score": 80},
            "approved": True,
        },
    )

    decision = publish_window.evaluate_publish_window(
        root=tmp_path,
        now=datetime(2026, 6, 11, 5, 23, tzinfo=timezone.utc),
        env={"ADAPTIVE_CADENCE_ENABLED": "1", "MIN_SLOT_PUBLISH_SCORE": "72", "MIN_QUEUE_OPPORTUNITY_SCORE": "50"},
        decisions_path=tmp_path / "decisions.jsonl",
    )

    assert decision["decision"] == "publish"
    assert decision["top_candidate_id"] == "ready"


def test_publish_window_skips_when_only_rewrite_candidates_exist(tmp_path):
    _write_json(tmp_path / "_data" / "publish_schedule.json", {"recommended_slots": ["05:23"]})
    _write_json(
        tmp_path / "_data" / "stories_queue.json",
        {"stories": [{"id": "rewrite", "title": "Rewrite candidate", "queue_prune": {"state": "rewrite"}}]},
    )

    decision = publish_window.evaluate_publish_window(
        root=tmp_path,
        now=datetime(2026, 6, 11, 5, 23, tzinfo=timezone.utc),
        env={"ADAPTIVE_CADENCE_ENABLED": "1"},
        decisions_path=tmp_path / "decisions.jsonl",
    )

    assert decision["decision"] == "skip_no_eligible_story"


def test_publish_window_ignores_unchecked_candidate_when_queue_has_prune_state(monkeypatch, tmp_path):
    _write_json(tmp_path / "_data" / "publish_schedule.json", {"recommended_slots": ["05:23"]})
    _write_json(
        tmp_path / "_data" / "stories_queue.json",
        {
            "stories": [
                {"id": "unchecked", "title": "Unchecked candidate"},
                {"id": "ready", "title": "Ready candidate", "queue_prune": {"state": "publish_ready"}},
            ]
        },
    )
    monkeypatch.setattr(
        publish_window,
        "score_story",
        lambda story: {
            "score": 100 if story["id"] == "unchecked" else 80,
            "opportunity": {"score": 80},
            "approved": True,
        },
    )

    decision = publish_window.evaluate_publish_window(
        root=tmp_path,
        now=datetime(2026, 6, 11, 5, 23, tzinfo=timezone.utc),
        env={"ADAPTIVE_CADENCE_ENABLED": "1", "MIN_SLOT_PUBLISH_SCORE": "72", "MIN_QUEUE_OPPORTUNITY_SCORE": "50"},
        decisions_path=tmp_path / "decisions.jsonl",
    )

    assert decision["decision"] == "publish"
    assert decision["top_candidate_id"] == "ready"


def test_publish_window_uses_autonomy_priority_before_raw_score(monkeypatch, tmp_path):
    _write_json(tmp_path / "_data" / "publish_schedule.json", {"recommended_slots": ["05:23"]})
    _write_json(
        tmp_path / "_data" / "stories_queue.json",
        {
            "stories": [
                {
                    "id": "raw_score",
                    "title": "Raw score candidate",
                    "queue_prune": {"state": "publish_ready", "score": 95},
                    "autonomy": {"priority": 20},
                },
                {
                    "id": "priority",
                    "title": "Priority candidate",
                    "queue_prune": {"state": "publish_ready", "score": 90},
                    "autonomy": {"priority": 120},
                },
            ]
        },
    )
    monkeypatch.setattr(
        publish_window,
        "score_story",
        lambda story: {
            "score": 100 if story["id"] == "raw_score" else 80,
            "opportunity": {"score": 80},
            "approved": True,
        },
    )

    decision = publish_window.evaluate_publish_window(
        root=tmp_path,
        now=datetime(2026, 6, 11, 5, 23, tzinfo=timezone.utc),
        env={"ADAPTIVE_CADENCE_ENABLED": "1", "MIN_SLOT_PUBLISH_SCORE": "72", "MIN_QUEUE_OPPORTUNITY_SCORE": "50"},
        decisions_path=tmp_path / "decisions.jsonl",
    )

    assert decision["decision"] == "publish"
    assert decision["top_candidate_id"] == "priority"


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


def test_publish_window_skips_slot_already_uploaded(monkeypatch, tmp_path):
    _write_json(tmp_path / "_data" / "publish_schedule.json", {"recommended_slots": ["05:23"]})
    _write_json(
        tmp_path / "_data" / "stories_queue.json",
        {"stories": [{"id": "next", "title": "Strong next story", "script": "A strong story is ready."}]},
    )
    upload_intents = tmp_path / "_data" / "upload_intents.jsonl"
    upload_intents.parent.mkdir(parents=True, exist_ok=True)
    upload_intents.write_text(
        json.dumps(
            {
                "slot": "2026-06-11T05:23Z",
                "status": "uploaded",
                "video_id": "abc123",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        publish_window,
        "score_story",
        lambda story: {"score": 90, "opportunity": {"score": 80}, "approved": True},
    )

    decision = publish_window.evaluate_publish_window(
        root=tmp_path,
        now=datetime(2026, 6, 11, 5, 53, tzinfo=timezone.utc),
        env={
            "ADAPTIVE_CADENCE_ENABLED": "1",
            "PUBLISH_SLOT_GRACE_MINUTES": "90",
            "MIN_SLOT_PUBLISH_SCORE": "72",
            "MIN_QUEUE_OPPORTUNITY_SCORE": "50",
        },
        decisions_path=tmp_path / "decisions.jsonl",
    )

    assert decision["decision"] == "skip_slot_already_uploaded"
    assert decision["slot_key"] == "2026-06-11T05:23Z"
    assert decision["slot_uploaded_video_id"] == "abc123"
    assert decision["top_candidate_id"] == ""


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


def test_publish_window_legacy_mode_still_skips_empty_queue(tmp_path):
    decision = publish_window.evaluate_publish_window(
        root=tmp_path,
        now=datetime(2026, 6, 11, 19, 23, tzinfo=timezone.utc),
        env={"ADAPTIVE_CADENCE_ENABLED": "0"},
        decisions_path=tmp_path / "decisions.jsonl",
    )

    assert decision["decision"] == "skip_no_eligible_story"
    assert decision["reasons"] == ["adaptive_cadence_disabled", "no_eligible_story"]


def test_publish_window_manual_dispatch_bypasses_adaptive_skip_but_not_empty_queue(tmp_path):
    decision = publish_window.evaluate_publish_window(
        root=tmp_path,
        now=datetime(2026, 6, 11, 19, 23, tzinfo=timezone.utc),
        env={"ADAPTIVE_CADENCE_ENABLED": "1", "GITHUB_EVENT_NAME": "workflow_dispatch"},
        decisions_path=tmp_path / "decisions.jsonl",
    )

    assert decision["decision"] == "skip_no_eligible_story"
    assert decision["reasons"] == ["manual_dispatch", "no_eligible_story"]
