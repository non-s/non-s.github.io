from scripts.queue_ready_count import build_payload


def test_queue_ready_count_requires_editorial_and_publish_approval():
    queue = {
        "stories": [
            {
                "id": "ready",
                "category": "dogs",
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
            {
                "id": "dirty-packaging",
                "category": "dogs",
                "queue_prune": {"state": "publish_ready"},
                "publish_score": {"approved": True, "state": "publish_ready"},
                "editorial": {"approved": True, "state": "publish_now"},
                "packaging": {"risks": ["missing_visible_cue"]},
            },
            {
                "id": "dirty-brain",
                "category": "dogs",
                "queue_prune": {"state": "publish_ready"},
                "publish_score": {"approved": True, "state": "publish_ready"},
                "editorial": {"approved": True, "state": "publish_now"},
                "youtube_brain": {"risks": ["subject_not_immediately_clear"]},
            },
        ]
    }

    payload = build_payload(queue)

    assert payload["pending"] == 5
    assert payload["publish_ready"] == 1
    assert payload["publish_ready_ids"] == ["ready"]
    assert payload["held_reasons"]["editor_in_chief:cooldown_subject"] == 1
    assert payload["held_reasons"]["queue_prune:rewrite"] == 1
    assert payload["held_reasons"]["packaging:missing_visible_cue"] == 1
    assert payload["held_reasons"]["youtube_brain:subject_not_immediately_clear"] == 1


def test_queue_ready_count_accepts_editorial_cooldown_supply_fallback():
    queue = {
        "stories": [
            {
                "id": "fallback",
                "category": "reptiles",
                "queue_prune": {
                    "state": "publish_ready",
                    "objective_reasons": ["editorial_cooldown_supply_fallback"],
                },
                "publish_score": {"approved": True, "state": "publish_ready"},
                "editorial": {"approved": False, "state": "cooldown_subject"},
            }
        ]
    }

    payload = build_payload(queue)

    assert payload["publish_ready"] == 1
    assert payload["publish_ready_ids"] == ["fallback"]
    assert "editor_in_chief:cooldown_subject" not in payload["held_reasons"]


def test_queue_ready_count_tracks_final_publish_quality_gate(monkeypatch):
    queue = {
        "stories": [
            {
                "id": "strong",
                "queue_prune": {"state": "publish_ready"},
                "publish_score": {"approved": True, "state": "publish_ready"},
                "editorial": {"approved": True, "state": "publish_now"},
            },
            {
                "id": "weak",
                "queue_prune": {"state": "publish_ready"},
                "publish_score": {"approved": True, "state": "publish_ready"},
                "editorial": {"approved": True, "state": "publish_now"},
            },
        ]
    }
    monkeypatch.setattr(
        "utils.publish_score.score_story",
        lambda story: {
            "score": 90 if story["id"] == "strong" else 60,
            "opportunity": {"score": 80 if story["id"] == "strong" else 20},
        },
    )

    payload = build_payload(
        queue,
        env={"MIN_SLOT_PUBLISH_SCORE": "72", "MIN_QUEUE_OPPORTUNITY_SCORE": "50"},
        include_quality_gate=True,
    )

    assert payload["publish_ready"] == 2
    assert payload["publish_eligible"] == 1
    assert payload["publish_eligible_ids"] == ["strong"]
    assert payload["publish_quality_reasons"]["publish_score_below_threshold"] == 1
    assert payload["publish_quality_reasons"]["opportunity_score_below_threshold"] == 1


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
    monkeypatch.setattr(
        "utils.queue_readiness.paused_categories",
        lambda path=None: {"wildlife": {"category": "wildlife"}},
    )

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
                "category": "dogs",
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
    monkeypatch.setattr("utils.queue_readiness.load_rewrite_ids", lambda path: set())
    monkeypatch.setattr("utils.queue_readiness.load_recovery_plans", lambda path: {})
    monkeypatch.setattr("utils.queue_readiness.load_duplicate_ids", lambda path: set())
    monkeypatch.setattr("utils.queue_readiness.load_success_plan", lambda path: {})
    monkeypatch.setattr(
        "utils.queue_readiness.evaluate_story",
        lambda story, rewrite_ids, recovery, duplicate_ids, success_plan: {
            "approved": False,
            "reasons": ["success_recovery_hook_required"],
        },
    )
    queue = {
        "stories": [
            {
                "id": "fresh-held",
                "category": "dogs",
                "queue_prune": {"state": "publish_ready"},
                "publish_score": {"approved": True, "state": "publish_ready"},
                "editorial": {"approved": True, "state": "publish_now"},
            }
        ]
    }

    payload = build_payload(queue, refresh_agency=True, queue_path=tmp_path / "stories_queue.json")

    assert payload["publish_ready"] == 0
    assert payload["held_reasons"]["agency_gate:success_recovery_hook_required"] == 1
