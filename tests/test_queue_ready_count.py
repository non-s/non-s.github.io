from scripts.queue_ready_count import build_payload


def test_queue_ready_count_requires_editorial_and_publish_approval():
    queue = {
        "stories": [
            {
                "id": "ready",
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
