import json
from pathlib import Path

from generate_shorts import build_short_metadata
from utils.first_frame_audit import audit_opening_frames


def test_golden_story_fixture_builds_metadata(tmp_path):
    story = json.loads((Path(__file__).parent / "fixtures" / "golden" / "story.json").read_text(encoding="utf-8"))

    meta = build_short_metadata(story, tmp_path / "short.mp4", tmp_path / "thumb.jpg")
    audit = audit_opening_frames({"thumbnail_text": story["thumbnail_text"], "has_broll": True})

    assert meta["title"].startswith("Octopus")
    assert meta["seo_lint"]["score"] > 0
    assert audit["approved"] is True
