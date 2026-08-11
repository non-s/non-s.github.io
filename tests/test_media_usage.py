"""Invariantes do ledger permanente de audio e video."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from utils.media_usage import (
    MediaAlreadyUsedError,
    commit_reservation,
    filter_unused,
    release_reservation,
    reserve_media,
)


def _asset(tmp_path: Path, name: str, source_id: int, content: bytes) -> Path:
    path = tmp_path / name
    path.write_bytes(content)
    path.with_suffix(".json").write_text(json.dumps({"id": source_id}), encoding="utf-8")
    return path


def test_committed_source_id_never_becomes_eligible_again(tmp_path):
    audio = _asset(tmp_path, "track.mp3", 1, b"audio")
    clip = _asset(tmp_path, "cat.mp4", 2, b"video")
    reservation_id, _ = reserve_media(audio, [clip])
    commit_reservation(reservation_id, tmp_path / "out.mp4")

    same_track_other_name = _asset(tmp_path, "track-copy.mp3", 1, b"other bytes")
    same_clip_other_name = _asset(tmp_path, "cat-copy.mp4", 2, b"other video bytes")
    assert filter_unused([same_track_other_name], "audio") == []
    assert filter_unused([same_clip_other_name], "video") == []


def test_content_hash_blocks_duplicate_with_different_provider_id(tmp_path):
    audio = _asset(tmp_path, "track.mp3", 1, b"identical audio")
    clip = _asset(tmp_path, "cat.mp4", 2, b"identical video")
    reservation_id, _ = reserve_media(audio, [clip])
    commit_reservation(reservation_id, tmp_path / "out.mp4")

    audio_copy = _asset(tmp_path, "copy.mp3", 999, b"identical audio")
    clip_copy = _asset(tmp_path, "copy.mp4", 999, b"identical video")
    with pytest.raises(MediaAlreadyUsedError):
        reserve_media(audio_copy, [clip_copy])


def test_failed_generation_releases_reservation(tmp_path):
    audio = _asset(tmp_path, "track.mp3", 1, b"audio")
    clip = _asset(tmp_path, "cat.mp4", 2, b"video")
    reservation_id, _ = reserve_media(audio, [clip])
    release_reservation(reservation_id)

    second_id, _ = reserve_media(audio, [clip])
    assert second_id != reservation_id


def test_concurrent_reservations_have_single_winner(tmp_path):
    audio = _asset(tmp_path, "track.mp3", 1, b"audio")
    clip = _asset(tmp_path, "cat.mp4", 2, b"video")

    def attempt() -> bool:
        try:
            reserve_media(audio, [clip])
            return True
        except MediaAlreadyUsedError:
            return False

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: attempt(), range(2)))

    assert sorted(results) == [False, True]
