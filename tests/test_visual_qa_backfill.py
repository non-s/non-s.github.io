from utils.visual_qa_backfill import build_backfill_report, infer_marker_visual_qa


def test_visual_qa_backfill_infers_safe_legacy_marker():
    marker = {
        "video_id": "abc",
        "title": "Cats jump like springs",
        "category": "cats",
        "has_broll": True,
        "has_captions": True,
    }
    inferred = infer_marker_visual_qa(marker)
    assert inferred["needs_backfill"] is True
    assert inferred["approved"] is True
    assert inferred["score"] >= 6


def test_visual_qa_backfill_flags_missing_motion():
    report = build_backfill_report(
        [
            {
                "video_id": "abc",
                "title": "Still frame",
                "category": "cats",
                "has_captions": True,
            }
        ]
    )
    assert report["legacy_unchecked"] == 1
    assert report["inferred_rejected"] == 1
