from utils.topic_freshness import annotate_queue


def test_fetch_queue_freshness_annotation_shape():
    queue = {"stories": [{"id": "a", "title": "Octopus skin", "fetched_at": "2026-06-10T00:00:00+00:00"}]}
    annotated = annotate_queue(queue, [{"topic": "Octopus skin", "score": 90}])

    assert annotated["stories"][0]["freshness"]["matched_signal_score"] == 90
    assert "freshness_score" in annotated["stories"][0]
