"""Test the YouTube tag packer logic used in upload_youtube.py.

The YouTube Data API caps tags at ~500 characters total across the list,
not 500 items. The packer greedy-fills the budget; this test pins the
behaviour without importing the full Google-API stack (the production
function lives inline in upload_youtube.upload_video()).

If you change the packing rule in upload_youtube.py, mirror the change
here so the test stays meaningful.
"""
from __future__ import annotations


def _pack(tags):
    """Same algorithm as upload_youtube.upload_video()."""
    packed, total = [], 0
    for raw_tag in tags or []:
        tag = str(raw_tag).strip()
        if not tag:
            continue
        cost = len(tag) + (1 if packed else 0)
        if total + cost > 480:
            break
        packed.append(tag)
        total += cost
    return packed


def test_pack_respects_char_budget():
    # 50 tags of 12 chars each = 600 chars + 49 commas → over 480.
    big = ["categoryAB12"] * 50
    packed = _pack(big)
    joined = ",".join(packed)
    assert len(joined) <= 480
    # We expect ~36 tags to fit (12 + 13 per subsequent), not 50.
    assert len(packed) < 50


def test_pack_skips_empty_and_whitespace():
    out = _pack(["foo", "", "   ", "bar"])
    assert out == ["foo", "bar"]


def test_pack_handles_none_input():
    assert _pack(None) == []
    assert _pack([]) == []


def test_pack_stops_at_first_oversize():
    huge = "x" * 481
    out = _pack(["small", huge, "tiny"])
    # `small` fits, then `huge` would exceed 480 → stop. `tiny` is not
    # appended because the packer breaks rather than skipping.
    assert out == ["small"]


def test_pack_preserves_order():
    out = _pack(["one", "two", "three"])
    assert out == ["one", "two", "three"]
