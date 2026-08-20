from __future__ import annotations

import json
from datetime import UTC, datetime

from utils.rollback_policy import assess_rollback


def test_upload_spike_and_duplicate_content_block_publication(tmp_path):
    now = datetime(2026, 1, 1, 12, tzinfo=UTC)
    metrics = [
        {"at": now.isoformat(), "stage": "upload", "success": False},
        {"at": now.isoformat(), "stage": "upload", "success": False},
        {"at": now.isoformat(), "stage": "upload", "success": False},
    ]
    (tmp_path / "pipeline_metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
    (tmp_path / "video_tags.json").write_text(
        json.dumps({"yt1": {"content_id": "lw_x"}, "yt2": {"content_id": "lw_x"}}), encoding="utf-8"
    )
    decision = assess_rollback(tmp_path, now=now)
    assert decision.required is True
    assert decision.block_publication is True
    assert "upload failure spike" in decision.reasons
    assert "duplicate content publication detected" in decision.reasons


def test_old_failures_do_not_trigger_rollback_and_corruption_does(tmp_path):
    now = datetime(2026, 1, 3, 12, tzinfo=UTC)
    old = [{"at": "2026-01-01T00:00:00+00:00", "stage": "generate_short", "success": False}] * 5
    (tmp_path / "pipeline_metrics.json").write_text(json.dumps(old), encoding="utf-8")
    assert assess_rollback(tmp_path, now=now).required is False
    (tmp_path / "catalog_memory.json").write_text("{broken", encoding="utf-8")
    decision = assess_rollback(tmp_path, now=now)
    assert decision.required is True
    assert decision.block_publication is True
