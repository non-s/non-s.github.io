from utils.publish_priority import autonomy_priority, publish_priority_key, queue_score


def test_publish_priority_prefers_autonomy_before_scores():
    low = {
        "autonomy": {"priority": 10},
        "queue_prune": {"score": 99},
        "publish_score": {"score": 99},
    }
    high = {
        "autonomy": {"priority": 130},
        "queue_prune": {"score": 70},
        "publish_score": {"score": 70},
    }

    assert publish_priority_key(high) > publish_priority_key(low)


def test_publish_priority_falls_back_to_queue_then_publish_score():
    low = {"queue_prune": {"score": 70}, "publish_score": {"score": 99}}
    high = {"queue_prune": {"score": 80}, "publish_score": {"score": 60}}

    assert autonomy_priority(low, queue_score(low)) == 70
    assert publish_priority_key(high) > publish_priority_key(low)
