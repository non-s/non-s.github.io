from __future__ import annotations

import json
from datetime import UTC, datetime

from utils.rollback_policy import assess_rollback


def test_upload_spike_and_duplicate_content_block_publication(tmp_path):
    now = datetime(2026, 1, 1, 12, tzinfo=UTC)
    metrics = [
        {"at": now.isoformat(), "stage": "upload", "success": False, "details": {"remote_attempted": True}},
        {"at": now.isoformat(), "stage": "upload", "success": False, "details": {"remote_attempted": True}},
        {"at": now.isoformat(), "stage": "upload", "success": False, "details": {"remote_attempted": True}},
    ]
    (tmp_path / "pipeline_metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
    # Same content_id *and* visual_dna_id re-published within the 6h window to
    # a different video_id: a genuine duplicate. A bare content_id collision
    # without visual_dna_id (legacy/re-render) must NOT trigger the guard.
    tags = {
        "yt1": {
            "content_id": "lw_x",
            "visual_dna_id": "vdna_42",
            "uploaded_at": "2026-01-01T06:30:00+00:00",
        },
        "yt2": {
            "content_id": "lw_x",
            "visual_dna_id": "vdna_42",
            "uploaded_at": "2026-01-01T11:45:00+00:00",
        },
    }
    (tmp_path / "video_tags.json").write_text(json.dumps(tags), encoding="utf-8")
    decision = assess_rollback(tmp_path, now=now)
    assert decision.required is True
    assert decision.block_publication is True
    assert "upload failure spike" in decision.reasons
    assert "duplicate content publication detected" in " ".join(decision.reasons)


def test_content_id_collision_without_visual_dna_is_not_duplicate(tmp_path):
    """Re-renders and legacy receipts share content_id across video_ids.

    That is an idempotent ledger rebuild, not a re-publication, and must not
    arm a self-reinforcing publication kill switch.
    """
    now = datetime(2026, 1, 1, 12, tzinfo=UTC)
    (tmp_path / "video_tags.json").write_text(
        json.dumps({"yt1": {"content_id": "lw_x"}, "yt2": {"content_id": "lw_x"}}),
        encoding="utf-8",
    )
    decision = assess_rollback(tmp_path, now=now)
    assert not any("duplicate" in r for r in decision.reasons)
    assert decision.block_publication is False


def test_duplicate_outside_window_does_not_block(tmp_path):
    """Re-publication after the duplicate window is not a guard signal."""
    now = datetime(2026, 1, 1, 12, tzinfo=UTC)
    tags = {
        "yt1": {
            "content_id": "lw_x",
            "visual_dna_id": "vdna_42",
            "uploaded_at": "2025-12-31T00:00:00+00:00",
        },
        "yt2": {
            "content_id": "lw_x",
            "visual_dna_id": "vdna_42",
            "uploaded_at": "2026-01-01T11:45:00+00:00",
        },
    }
    (tmp_path / "video_tags.json").write_text(json.dumps(tags), encoding="utf-8")
    decision = assess_rollback(tmp_path, now=now)
    assert not any("duplicate" in r for r in decision.reasons)


def test_local_policy_rejections_do_not_self_trigger_upload_rollback(tmp_path):
    now = datetime(2026, 1, 1, 12, tzinfo=UTC)
    metrics = [
        {"at": now.isoformat(), "stage": "upload", "success": False, "details": {"remote_attempted": False}},
        {"at": now.isoformat(), "stage": "upload", "success": False, "details": {"remote_attempted": False}},
        {"at": now.isoformat(), "stage": "upload", "success": False, "details": {"remote_attempted": False}},
    ]
    (tmp_path / "pipeline_metrics.json").write_text(json.dumps(metrics), encoding="utf-8")

    decision = assess_rollback(tmp_path, now=now)

    assert decision.required is False
    assert "upload failure spike" not in decision.reasons


def test_old_failures_do_not_trigger_rollback_and_corruption_does(tmp_path):
    now = datetime(2026, 1, 3, 12, tzinfo=UTC)
    old = [{"at": "2026-01-01T00:00:00+00:00", "stage": "generate_short", "success": False}] * 5
    (tmp_path / "pipeline_metrics.json").write_text(json.dumps(old), encoding="utf-8")
    assert assess_rollback(tmp_path, now=now).required is False
    (tmp_path / "catalog_memory.json").write_text("{broken", encoding="utf-8")
    decision = assess_rollback(tmp_path, now=now)
    assert decision.required is True
    assert decision.block_publication is True
