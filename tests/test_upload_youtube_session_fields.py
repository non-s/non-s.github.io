import pytest

pytest.importorskip("googleapiclient")

from upload_youtube import _done_marker


def test_done_marker_preserves_session_and_opening_fields():
    marker = _done_marker(
        "abc",
        {
            "title": "Octopus",
            "opening_audit": {"score": 88},
            "session_handoff": {"video_id": "next"},
            "session_action": {"applied": True},
            "seo_lint": {"score": 90},
            "music_bed_variant": "off",
        },
    )

    assert marker["opening_audit"]["score"] == 88
    assert marker["session_action"]["applied"] is True
    assert marker["seo_lint"]["score"] == 90
    assert marker["music_bed_variant"] == "off"
