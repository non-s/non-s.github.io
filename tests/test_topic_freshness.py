from datetime import datetime, timezone

from utils.topic_freshness import annotate_queue, freshness_report, score_topic_freshness


def test_topic_freshness_uses_matching_signal_and_age():
    story = {
        "title": "Octopus skin changes color",
        "category": "ocean",
        "fetched_at": "2026-06-10T00:00:00+00:00",
    }
    candidates = [{"topic": "Octopus skin", "score": 90, "sources": ["trends"]}]

    out = score_topic_freshness(story, candidates, now=datetime(2026, 6, 11, tzinfo=timezone.utc))

    assert out["freshness_score"] > 70
    assert out["signal_source"] == "trend_signal"


def test_annotate_queue_reports_coverage():
    queue = {"stories": [{"id": "a", "title": "Fresh bird", "fetched_at": "2026-06-11T00:00:00+00:00"}]}

    annotated = annotate_queue(queue, [], now=datetime(2026, 6, 11, tzinfo=timezone.utc))
    report = freshness_report(annotated)

    assert annotated["stories"][0]["freshness_score"] > 0
    assert report["coverage"] == 1.0


def test_freshness_report_masks_non_recommendable_titles():
    queue = {
        "stories": [{
            "id": "bad-title",
            "title": "Cows rely on ear position to signal",
            "fetched_at": "2026-06-11T00:00:00+00:00",
        }]
    }

    annotated = annotate_queue(queue, [], now=datetime(2026, 6, 11, tzinfo=timezone.utc))
    report = freshness_report(annotated)

    assert report["top_fresh"][0]["title"].startswith("bad-title (title needs repair:")
    assert "generic_rely_to_signal_cue" in report["top_fresh"][0]["title_issues"]
