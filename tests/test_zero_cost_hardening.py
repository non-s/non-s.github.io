from __future__ import annotations

from datetime import datetime, timezone

from scripts.audit_slot_contracts import audit_slot_contracts
from scripts.upload_intent import build_upload_intent, duplicate_report, duplicate_uploaded, write_upload_intent
from utils.analytics_schema import build_video_metric_row
from utils.retention_warehouse import reconcile_studio_api
from utils.time_semantics import (
    CURRENT_VIEWS_REGIME,
    LEGACY_VIEWS_REGIME,
    publish_day_pt,
    temporal_fields,
    views_regime,
)


def test_time_semantics_use_pacific_days_and_views_cutover():
    fields = temporal_fields(now=datetime(2026, 6, 11, 5, 23, tzinfo=timezone.utc))

    assert fields["publish_day_pt"] == "2026-06-10"
    assert fields["quota_day_pt"] == "2026-06-10"
    assert publish_day_pt("2026-12-01T05:23:00+00:00") == "2026-11-30"
    assert views_regime("2025-03-30T20:00:00+00:00") == LEGACY_VIEWS_REGIME
    assert views_regime("2025-04-01T07:00:00+00:00") == CURRENT_VIEWS_REGIME


def test_slot_audit_checks_bot_watchdog_docs_and_temporal_fields(tmp_path):
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / "docs").mkdir()
    slots = " ".join(f"{hour:02d}:00" for hour in range(24))
    (tmp_path / ".github" / "workflows" / "youtube-bot.yml").write_text(
        'on:\n  schedule:\n    - cron: "0 * * * *"\n',
        encoding="utf-8",
    )
    (tmp_path / ".github" / "workflows" / "youtube-watchdog.yml").write_text(slots, encoding="utf-8")
    docs = slots + " publish_ts_utc publish_day_pt quota_day_pt views_regime"
    (tmp_path / "README.md").write_text(docs, encoding="utf-8")
    (tmp_path / "docs" / "ENVIRONMENT.md").write_text(docs, encoding="utf-8")

    assert audit_slot_contracts(tmp_path)["ok"] is True
    (tmp_path / ".github" / "workflows" / "youtube-watchdog.yml").write_text("14:00 19:00 23:00", encoding="utf-8")

    errors = audit_slot_contracts(tmp_path)["errors"]
    assert any("05:00" in error and "watchdog" in error for error in errors)


def test_retention_warehouse_and_analytics_row_include_new_fields():
    row = build_video_metric_row(
        "vid1",
        "Title",
        {"views": 100, "engaged_views": 76, "average_view_percentage": 64},
        context={"publish_ts_utc": "2026-06-11T05:23:00+00:00"},
    )
    rec = reconcile_studio_api({"plays": 100, "engaged_views": 76}, row["metrics"])

    assert row["publish_day_pt"] == "2026-06-10"
    assert row["metrics"]["plays"] == 100
    assert "continued_watch_rate" in row["metrics"]
    assert rec["within_2pct"] is True


def test_upload_intent_records_prepared_and_detects_uploaded_duplicates(tmp_path):
    path = tmp_path / "upload_intents.jsonl"
    meta = {"story_id": "story-1", "script": "A tight script", "experiments": {"hook_style": "question"}}
    prepared = build_upload_intent(meta, slot="05:23", status="prepared")
    uploaded = {**prepared, "status": "uploaded", "video_id": "yt123"}

    assert write_upload_intent(prepared, path)["written"] is True
    assert write_upload_intent(uploaded, path)["written"] is True
    assert write_upload_intent(uploaded, path)["written"] is False
    assert duplicate_uploaded(prepared, path)["video_id"] == "yt123"


def test_upload_intent_report_flags_duplicate_titles_and_slots(tmp_path):
    import json

    path = tmp_path / "upload_intents.jsonl"
    rows = [
        {
            "idempotency_key": "one",
            "status": "uploaded",
            "title": "Plants turn sunlight into stored sugar",
            "slot": "2026-06-28T14:00Z",
            "video_id": "video-a",
        },
        {
            "idempotency_key": "two",
            "status": "uploaded",
            "title": "Plants turn sunlight into stored sugar",
            "slot": "2026-06-28T14:00Z",
            "video_id": "video-b",
        },
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    report = duplicate_report(path)

    assert report["uploaded_rows"] == 2
    assert len(report["duplicate_uploads"]) == 0
    assert len(report["duplicate_titles"]) == 1
    assert len(report["duplicate_slots"]) == 1
