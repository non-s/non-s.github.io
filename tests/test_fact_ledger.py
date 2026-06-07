from utils.fact_ledger import build_fact_ledger, duplicate_angle_ids


def test_fact_ledger_finds_duplicate_angles():
    stories = [
        {"id": "a", "category": "cats", "seo_title": "Why cats purr", "hook": "Cats purr."},
        {"id": "b", "category": "cats", "seo_title": "Why cats really purr", "hook": "Cats purr."},
        {"id": "c", "category": "dogs", "seo_title": "Why dogs wag tails", "hook": "Dogs wag tails."},
    ]
    report = build_fact_ledger(stories)
    assert report["pending_stories"] == 3
    assert report["repeated_phrases"]["purr"] == 2
    assert report["duplicate_clusters"]
    assert "b" in duplicate_angle_ids(stories)
