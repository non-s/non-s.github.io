import json

import fetch_animals
from scripts.quota_preflight import preflight
from utils.api_quota_budget import (
    estimate_fetch_content_cost,
    estimate_metadata_repair_cost,
    estimate_publish_run_cost,
    quota_ledger_row,
    should_block_run,
    write_quota_ledger_row,
)


def test_quota_estimate_separates_youtube_upload_bucket():
    estimate = estimate_publish_run_cost(videos=1, playlists=0, comments=0, analytics_queries=0)

    assert estimate["estimated_units"] == 50
    assert estimate["calls"]["youtube.videos.insert"] == 1
    assert estimate["calls"]["youtube.thumbnails.set"] == 1


def test_fetch_content_estimate_uses_pexels_by_default():
    estimate = estimate_fetch_content_cost(search_calls=8)

    assert estimate["calls"] == {"pexels.search": 8}
    assert estimate["estimated_units"] == 8


def test_metadata_repair_estimates_video_update_cost():
    estimate = estimate_metadata_repair_cost(updates=2)

    assert estimate["workflow"] == "youtube-metadata-repair"
    assert estimate["calls"] == {"youtube.videos.update": 2}
    assert estimate["estimated_units"] == 100


def test_fetch_content_preflight_uses_dynamic_pexels_budget():
    row = preflight("fetch-content", check_only=True)

    assert row["calls"]["pexels.search"] == min(
        len(fetch_animals.ANIMAL_TOPICS) * fetch_animals.PEXELS_TOPIC_CALL_BUDGET,
        200,
    )


def test_quota_guard_blocks_only_in_block_mode(tmp_path):
    estimate = {"workflow": "youtube-bot", "estimated_units": 8000, "calls": {}}
    env = {"QUOTA_GUARD_ENABLED": "1", "QUOTA_GUARD_MODE": "block", "QUOTA_GUARD_MAX_DAILY_RATIO": "0.70"}

    guard = should_block_run(estimate, path=tmp_path / "ledger.jsonl", env=env, daily_budget=10000)

    assert guard["block"] is True


def test_quota_ledger_writes_latest(tmp_path):
    row = write_quota_ledger_row(
        {"workflow": "fetch-content", "estimated_units": 5, "calls": {"pexels.search": 5}},
        path=tmp_path / "ledger.jsonl",
        latest_path=tmp_path / "latest.json",
    )

    assert row["estimated_units"] == 5
    assert (tmp_path / "ledger.jsonl").exists()
    assert (tmp_path / "latest.json").exists()


def test_quota_check_only_does_not_spend_from_ledger(tmp_path):
    row = quota_ledger_row(
        {"workflow": "youtube-bot", "estimated_units": 1810, "calls": {"youtube.videos.insert": 1}},
        path=tmp_path / "ledger.jsonl",
    )

    assert row["guard"]["spent_today"] == 0
    assert row["guard"]["projected_today"] == 0
    assert row["guard"]["daily_call_buckets"]["youtube.videos.insert"]["projected_today"] == 1
    assert not (tmp_path / "ledger.jsonl").exists()


def test_legacy_upload_rows_are_recomputed_with_current_quota_model(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    row = quota_ledger_row(
        {"workflow": "youtube-bot", "estimated_units": 1810, "calls": {"youtube.videos.insert": 1}},
        path=ledger,
    )
    ledger.write_text(json.dumps(row) + "\n", encoding="utf-8")

    guard = should_block_run(
        {"workflow": "youtube-bot", "estimated_units": 1810, "calls": {"youtube.videos.insert": 1}},
        path=ledger,
        env={"QUOTA_GUARD_ENABLED": "1", "QUOTA_GUARD_MODE": "block", "YOUTUBE_DAILY_UPLOAD_BUDGET": "100"},
    )

    assert guard["projected_today"] == 0
    assert guard["daily_call_buckets"]["youtube.videos.insert"]["projected_today"] == 2
    assert guard["block"] is False


def test_quota_guard_blocks_upload_bucket_near_daily_limit(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    rows = [
        quota_ledger_row(
            {"workflow": "youtube-bot", "calls": {"youtube.videos.insert": 1}, "estimated_units": 0},
            path=ledger,
        )
        for _ in range(95)
    ]
    ledger.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    guard = should_block_run(
        {"workflow": "youtube-bot", "estimated_units": 0, "calls": {"youtube.videos.insert": 1}},
        path=ledger,
        env={
            "QUOTA_GUARD_ENABLED": "1",
            "QUOTA_GUARD_MODE": "block",
            "QUOTA_GUARD_MAX_DAILY_RATIO": "0.95",
            "YOUTUBE_DAILY_UPLOAD_BUDGET": "100",
        },
    )

    assert guard["reason"] == "daily_call_limit_exceeded"
    assert guard["daily_call_buckets"]["youtube.videos.insert"]["projected_today"] == 96
    assert guard["block"] is True
