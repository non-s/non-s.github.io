import json

from scripts import dry_run_publish


def test_dry_run_publish_counts_editorial_cooldown_supply_fallback(monkeypatch):
    monkeypatch.setattr(
        dry_run_publish,
        "prune_queue",
        lambda queue: (queue, [], {"pending_before": 1, "pending_after": 1, "rejected": 0}),
    )
    monkeypatch.setattr(dry_run_publish, "_agency_held_reasons", lambda path=None: {})
    # Isolate from the live ops_guardian paused-category list — this test
    # exercises the editorial cooldown fallback, not category pausing, and
    # "reptiles" may or may not be paused in whatever `_data/ops_guardian.json`
    # currently says.
    monkeypatch.setattr(dry_run_publish, "paused_categories", lambda *a, **k: {})
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


def test_dry_run_publish_main_does_not_mutate_queue(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "_data"
    data_dir.mkdir()
    queue = {"stories": [{"id": "raw", "title": "Raw story"}]}
    queue_path = data_dir / "stories_queue.json"
    queue_path.write_text(json.dumps(queue), encoding="utf-8")
    pruned = {
        "stories": [
            {
                "id": "ready",
                "title": "Wolves leave scent notes for the pack",
                "category": "wildlife",
                "queue_prune": {"state": "publish_ready", "score": 100},
                "publish_score": {"approved": True, "state": "publish_ready", "score": 95},
                "editorial": {"approved": True, "state": "publish_now"},
                "rights_audit": {"approved": True, "warnings": []},
                "youtube_brain": {"risks": []},
                "packaging": {"state": "magnetic", "risks": []},
            }
        ]
    }
    monkeypatch.setattr(dry_run_publish, "prune_queue", lambda data: (pruned, [], {"pending_after": 1}))

    assert dry_run_publish.main() == 0

    assert json.loads(queue_path.read_text(encoding="utf-8")) == queue
    assert json.loads((data_dir / "dry_run_publish.json").read_text(encoding="utf-8"))["eligible_count"] == 1
