from scripts import dry_run_publish


def test_dry_run_publish_counts_editorial_cooldown_supply_fallback(monkeypatch):
    monkeypatch.setattr(
        dry_run_publish,
        "prune_queue",
        lambda queue: (queue, [], {"pending_before": 1, "pending_after": 1, "rejected": 0}),
    )
    monkeypatch.setattr(dry_run_publish, "_agency_held_reasons", lambda path=None: {})
    queue = {
        "stories": [
            {
                "id": "fallback",
                "title": "Snakes sample the air with a tongue flick",
                "category": "reptiles",
                "queue_prune": {
                    "state": "publish_ready",
                    "score": 72,
                    "objective_reasons": ["editorial_cooldown_supply_fallback"],
                },
                "publish_score": {
                    "approved": True,
                    "state": "publish_ready",
                    "score": 100,
                    "objective_gate": {"reasons": ["observe_before_scaling"]},
                },
                "editorial": {"approved": False, "state": "cooldown_subject"},
                "rights_audit": {"approved": True, "warnings": []},
            }
        ]
    }

    payload = dry_run_publish.build_dry_run(queue)

    assert payload["eligible_count"] == 1
    assert payload["would_publish"][0]["id"] == "fallback"
