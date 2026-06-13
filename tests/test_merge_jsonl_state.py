import json
from pathlib import Path

from scripts.merge_jsonl_state import merge_jsonl_lines, merge_state_dir


def _write(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_merge_jsonl_lines_keeps_latest_main_then_generated_rows():
    assert merge_jsonl_lines(["main-a", "shared"], ["shared", "generated-c"]) == [
        "main-a",
        "shared",
        "generated-c",
    ]


def test_merge_state_dir_preserves_concurrent_ledger_rows(tmp_path):
    root = tmp_path / "repo"
    state = tmp_path / "state"
    path = "_data/analytics/api_quota_ledger.jsonl"
    _write(root / path, ['{"row":"main-upload"}', '{"row":"main-fetch"}'])
    _write(state / path, ['{"row":"main-fetch"}', '{"row":"generated-fetch"}'])

    results = merge_state_dir(root, state, [path])

    assert results == [
        {
            "path": path,
            "current": 2,
            "incoming": 2,
            "merged": 3,
            "changed": True,
            "skipped": False,
        }
    ]
    assert (state / path).read_text(encoding="utf-8").splitlines() == [
        '{"row":"main-upload"}',
        '{"row":"main-fetch"}',
        '{"row":"generated-fetch"}',
    ]


def test_merge_state_dir_copies_latest_main_when_generated_file_is_missing(tmp_path):
    root = tmp_path / "repo"
    state = tmp_path / "state"
    path = "_data/upload_intents.jsonl"
    _write(root / path, ['{"slot":"2026-06-13T08:00Z"}'])

    results = merge_state_dir(root, state, [path])

    assert results[0]["merged"] == 1
    assert results[0]["changed"] is True
    assert (state / path).read_text(encoding="utf-8").splitlines() == ['{"slot":"2026-06-13T08:00Z"}']


def test_merge_state_dir_refreshes_quota_latest_from_newest_timestamp(tmp_path):
    root = tmp_path / "repo"
    state = tmp_path / "state"
    path = "_data/analytics/api_quota_ledger.jsonl"
    _write(
        root / path,
        [
            '{"timestamp_utc":"2026-06-13T08:41:21+00:00","workflow":"youtube-bot"}',
        ],
    )
    _write(
        state / path,
        [
            '{"timestamp_utc":"2026-06-13T08:39:21+00:00","workflow":"fetch-content"}',
        ],
    )

    merge_state_dir(root, state, [path])

    latest = json.loads((state / "_data/analytics/api_quota_latest.json").read_text(encoding="utf-8"))
    assert latest["workflow"] == "youtube-bot"
    assert latest["timestamp_utc"] == "2026-06-13T08:41:21+00:00"
