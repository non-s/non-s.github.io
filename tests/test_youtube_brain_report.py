import json

from scripts.youtube_brain_report import build_report


def _ready_story(**overrides):
    story = {
        "id": "ready",
        "title": "Ducks fake injuries to protect young",
        "seo_title": "Ducks fake injuries to protect young",
        "hook": "Ducks can act injured to pull danger away.",
        "script": (
            "Ducks can act injured to pull danger away. Watch the low awkward display, "
            "because some ducks use a distraction act near the nest. Predators chase the "
            "easier target while the young stay hidden. The drama is a decoy, not weakness. "
            "Would you fall for the trick?"
        ),
        "thumbnail_text": "FAKE INJURY",
        "category": "birds",
        "story_format": "animal_intelligence",
        "queue_prune": {"state": "publish_ready"},
    }
    story.update(overrides)
    return story


def test_youtube_brain_report_separates_ready_summary_from_rewrite_watchlist(tmp_path):
    queue = tmp_path / "_data" / "stories_queue.json"
    out = tmp_path / "_data" / "youtube_brain_report.json"
    queue.parent.mkdir()
    queue.write_text(
        json.dumps(
            {
                "stories": [
                    _ready_story(),
                    _ready_story(
                        id="rewrite",
                        title="Animals have another amazing secret",
                        seo_title="Animals have another amazing secret",
                        hook="Animals are amazing.",
                        script="Animals are amazing and interesting.",
                        thumbnail_text="AMAZING SECRET TODAY",
                        category="wildlife",
                        queue_prune={"state": "rewrite"},
                    ),
                ],
            }
        ),
        encoding="utf-8",
    )

    report = build_report(queue, out)

    assert report["pending"] == 2
    assert report["publish_ready_summary"]["states"]["publish_minded"] == 1
    assert [item["id"] for item in report["publish_ready_top"]] == ["ready"]
    assert [item["id"] for item in report["risk_watchlist"]] == ["rewrite"]
    assert json.loads(out.read_text(encoding="utf-8"))["risk_watchlist"][0]["queue_state"] == "rewrite"
