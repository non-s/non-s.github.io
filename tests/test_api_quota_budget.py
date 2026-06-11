from utils.api_quota_budget import estimate_publish_run_cost, should_block_run, write_quota_ledger_row


def test_quota_estimate_uses_youtube_upload_cost():
    estimate = estimate_publish_run_cost(videos=1, playlists=0, comments=0, analytics_queries=0)

    assert estimate["estimated_units"] >= 1600


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
