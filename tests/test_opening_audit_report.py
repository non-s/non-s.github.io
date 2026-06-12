import json

from scripts.opening_audit_report import build_report


def test_opening_audit_report_masks_malformed_titles(tmp_path):
    videos = tmp_path / "_videos"
    videos.mkdir()
    (videos / "bad.done").write_text(json.dumps({
        "video_id": "bad",
        "title": "Horses Sheep remember faces by watching the eyes",
        "opening_audit": {"score": 81.44, "approved": True, "reasons": []},
    }), encoding="utf-8")

    report = build_report(tmp_path)
    row = report["worst_openings"][0]

    assert row["title"].startswith("bad (title needs repair:")
    assert row["source_title"] == "Horses Sheep remember faces by watching the eyes"
    assert "stacked_animal_title" in row["title_issues"]
    assert row["suggested_titles"]
