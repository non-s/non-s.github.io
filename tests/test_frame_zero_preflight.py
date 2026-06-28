import json

from scripts.frame_zero_preflight import build_report


def test_frame_zero_preflight_records_rewrites_before_render(tmp_path):
    data_dir = tmp_path / "_data"
    data_dir.mkdir()
    (data_dir / "stories_queue.json").write_text(
        json.dumps(
            {
                "stories": [
                    {
                        "id": "elephant-low-opening",
                        "title": "Elephants can feel rumbles through the ground",
                        "seo_title": "Elephants can feel rumbles through the ground",
                        "hook": "Elephants can sense low rumbles underfoot.",
                        "script": (
                            "Elephants can sense low rumbles underfoot. Watch the feet and stillness, "
                            "because low elephant calls can travel through ground as vibrations."
                        ),
                        "thumbnail_text": "GROUND SIGNAL",
                        "category": "wildlife",
                    },
                    {
                        "id": "mushroom-ready",
                        "title": "Mushrooms release spores from hidden gills",
                        "seo_title": "Mushrooms release spores from hidden gills",
                        "hook": "Mushrooms release spores from hidden gills.",
                        "script": (
                            "Mushrooms release spores from hidden gills. Watch the gills first, "
                            "because those thin plates drop spores into moving air."
                        ),
                        "thumbnail_text": "HIDDEN GILLS",
                        "category": "fungi",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    report = build_report(tmp_path)
    rows = {item["id"]: item for item in report["items"]}

    assert report["pending"] == 2
    assert report["ready"] == 2
    assert report["held"] == 0
    assert report["rewritten"] == 1
    assert report["render_gate"] == "approved"
    assert rows["elephant-low-opening"]["rewrite_applied"] is True
    assert rows["elephant-low-opening"]["before_score"] < rows["elephant-low-opening"]["after_score"]
    assert rows["elephant-low-opening"]["render_gate"] == "approved"
    assert rows["mushroom-ready"]["rewrite_applied"] is False
