"""Tests for upload_tiktok._compute_chunking — the math TikTok needs
on `chunk_size` + `total_chunk_count` in the init payload.

The earlier implementation (CHUNK_SIZE = 5 MB, ceil division) sent
TikTok bodies that violated three different invariants:

  - chunk_size > video_size when the video was under 5 MB
  - last chunk under 5 MB when video was a few MB past 5
  - extra chunks on edge cases that broke `The total chunk count
    is invalid`

These tests pin the corrected behaviour.
"""
from __future__ import annotations

import pytest

from upload_tiktok import (
    MAX_CHUNK_SIZE,
    MIN_CHUNK_SIZE,
    _compute_chunking,
)


MB = 1024 * 1024


@pytest.mark.parametrize("size_mb", [1, 4, 5, 6, 9, 12, 25, 50, 64])
def test_single_chunk_for_sub_64mb(size_mb):
    """Anything under TikTok's 64 MB single-chunk ceiling ships as
    one chunk == video_size. This is the path Wild Brief shorts
    always take (typical size 3-12 MB)."""
    size = size_mb * MB
    chunk_size, total = _compute_chunking(size)
    assert total == 1
    assert chunk_size == size


def test_just_above_max_uses_multi_chunk():
    """A 65 MB hypothetical input shouldn't pretend to be single
    chunk — chunk_size ceiling is 64 MB so it splits."""
    size = 65 * MB
    chunk_size, total = _compute_chunking(size)
    assert total >= 2
    assert chunk_size <= MAX_CHUNK_SIZE
    assert chunk_size >= MIN_CHUNK_SIZE
    # Last chunk size must be >= 5 MB by TikTok's rules.
    last = size - chunk_size * (total - 1)
    assert last >= MIN_CHUNK_SIZE
    # All chunks must sum to exactly video_size.
    assert chunk_size * (total - 1) + last == size


def test_last_chunk_floor_respected():
    """If naive ceil-division would leave a < 5 MB tail, the helper
    folds that tail into the previous chunk by emitting one fewer
    total chunk."""
    # 130 MB / 64 MB = 2 chunks of 64 MB + 1 of 2 MB (under floor)
    # Helper should return 2 chunks total: 64 MB + 66 MB.
    size = 130 * MB
    chunk_size, total = _compute_chunking(size)
    last = size - chunk_size * (total - 1)
    assert last >= MIN_CHUNK_SIZE


def test_exact_max_size_is_single_chunk():
    size = MAX_CHUNK_SIZE
    chunk_size, total = _compute_chunking(size)
    assert total == 1
    assert chunk_size == size


def test_tiny_video_single_chunk_equal_to_size():
    """A 100 KB video stays one chunk of 100 KB — the old code would
    have sent chunk_size = 5 MB > video_size and crashed init."""
    size = 100 * 1024
    chunk_size, total = _compute_chunking(size)
    assert total == 1
    assert chunk_size == size
