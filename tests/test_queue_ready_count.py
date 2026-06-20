from scripts.queue_ready_count import build_payload


def test_queue_ready_count_requires_editorial_and_publish_approval():
    queue = {
        "stories": [
            {
                "id": "ready",
                "category": "birds",
                "queue_prune": {"state": "publish_ready"},
                "publish_score": {"approved": True, "state": "publish_ready"},
                "editorial": {"approved": True, "state": "publish_now"},
            },
            {
                "id": "cooldown",
                "queue_prune": {"state": "publish_ready"},
                "publish_score": {"approved": True, "state": "publish_ready"},
                "editorial": {"approved": False, "state": "cooldown_subject"},
            },
            {
                "id": "rewrite",
                "queue_prune": {"state": "rewrite"},
                "publish_score": {"approved": True, "state": "publish_ready"},
                "editorial": {"approved": True, "state": "publish_now"},
            },
        ]
    }

    payload = build_payload(queue)

    assert payload["pending"] == 3
    assert payload["publish_ready"] == 1
    assert payload["publish_ready_ids"] == ["ready"]
    assert payload["held_reasons"]["editor_in_chief:cooldown_subject"] == 1
    assert payload["held_reasons"]["queue_prune:rewrite"] == 1


def test_queue_ready_count_excludes_ops_paused_category(monkeypatch):
    queue = {
        "stories": [
            {
                "id": "paused",
                "category": "wildlife",
                "queue_prune": {"state": "publish_ready"},
                "publish_score": {"approved": True, "state": "publish_ready"},
                "editorial": {"approved": True, "state": "publish_now"},
            }
        ]
    }
    monkeypatch.setattr("scripts.queue_ready_count.paused_categories", lambda: {"wildlife": {"category": "wildlife"}})

    payload = build_payload(queue, env={"OPS_GUARDIAN_ENFORCE": "1"})

    assert payload["publish_ready"] == 0
    assert payload["held_reasons"]["ops_guardian_paused_category:wildlife"] == 1


def test_queue_ready_count_excludes_agency_held_candidate(monkeypatch, tmp_path):
    gate = tmp_path / "agency_gate.json"
    gate.write_text(
        '{"held_items":[{"id":"held","reasons":["category_recovery_rules_not_met"]}]}',
        encoding="utf-8",
    )
    monkeypatch.setattr("scripts.queue_ready_count.AGENCY_GATE", gate)
    queue = {
        "stories": [
            {
                "id": "held",
                "category": "birds",
                "queue_prune": {"state": "publish_ready"},
                "publish_score": {"approved": True, "state": "publish_ready"},
                "editorial": {"approved": True, "state": "publish_now"},
            }
        ]
    }

    payload = build_payload(queue)

    assert payload["publish_ready"] == 0
    assert payload["held_reasons"]["agency_gate:category_recovery_rules_not_met"] == 1


def test_queue_ready_count_refresh_recomputes_agency_gate(monkeypatch, tmp_path):
    monkeypatch.setattr("scripts.queue_ready_count.load_rewrite_ids", lambda path: set())
    monkeypatch.setattr("scripts.queue_ready_count.load_recovery_plans", lambda path: {})
    monkeypatch.setattr("scripts.queue_ready_count.load_duplicate_ids", lambda path: set())
    monkeypatch.setattr("scripts.queue_ready_count.load_success_plan", lambda path: {})
    monkeypatch.setattr(
        "scripts.queue_ready_count.evaluate_story",
        lambda story, rewrite_ids, recovery, duplicate_ids, success_plan: {
            "approved": False,
            "reasons": ["success_recovery_hook_required"],
        },
    )
    queue = {
        "stories": [
            {
                "id": "fresh-held",
                "category": "birds",
                "queue_prune": {"state": "publish_ready"},
                "publish_score": {"approved": True, "state": "publish_ready"},
                "editorial": {"approved": True, "state": "publish_now"},
            }
        ]
    }

    payload = build_payload(queue, refresh_agency=True, queue_path=tmp_path / "stories_queue.json")

    assert payload["publish_ready"] == 0
    assert payload["held_reasons"]["agency_gate:success_recovery_hook_required"] == 1
