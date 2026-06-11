import json

from scripts.free_signal_harvester import harvest
from utils.trend_bridge import build_topic_candidates, normalize_rss_items


def test_manual_trends_snapshots_are_reusable_offline(tmp_path):
    manual = tmp_path / "_data" / "trends" / "manual_import"
    manual.mkdir(parents=True)
    (manual / "topics.csv").write_text("topic,score\nOctopus skin,84\nCelebrity news,20\n", encoding="utf-8")

    report = harvest(tmp_path)
    output = json.loads((tmp_path / "_data" / "trends" / "topic_candidates.json").read_text(encoding="utf-8"))

    assert report["rows"] == 2
    assert output["candidates"][0]["topic"] == "Octopus skin"


def test_rss_normalization_does_not_hard_fail_bad_xml():
    assert normalize_rss_items("bad", "<not") == []


def test_topic_candidate_merges_sources():
    rows = [
        {"topic": "Octopus skin", "source": "trends", "score": 80},
        {"topic": "octopus skin", "source": "rss", "score": 70},
    ]

    out = build_topic_candidates(rows)

    assert out[0]["topic"] == "Octopus skin"
    assert set(out[0]["sources"]) == {"trends", "rss"}
