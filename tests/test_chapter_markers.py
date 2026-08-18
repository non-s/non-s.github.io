from __future__ import annotations

from utils.chapter_markers import (
    build_chapters,
    chapters_to_description_block,
    prepend_chapters,
)
from utils.liquid_wire_timeline import CreativeEvent, build_timeline

MUSIC = {"beat_seconds": 0.9, "meter": 4}


def _events() -> list[CreativeEvent]:
    return build_timeline(1234, 120.0, MUSIC)


def test_first_chapter_is_opening_at_zero() -> None:
    chapters = build_chapters(120.0, _events())
    assert chapters[0] == (0.0, "Opening")


def test_chapters_are_strictly_increasing_and_spaced() -> None:
    chapters = build_chapters(180.0, _events())
    starts = [start for start, _ in chapters]
    assert starts == sorted(starts)
    for left, right in zip(starts, starts[1:], strict=False):
        assert right - left >= 10.0


def test_description_block_starts_with_zero_timestamp() -> None:
    chapters = build_chapters(60.0, _events())
    block = chapters_to_description_block(chapters)
    first_line = block.splitlines()[0]
    assert first_line.startswith("0:00")


def test_prepend_chapters_adds_block_when_absent() -> None:
    description = "A living wireframe drifts through a black void."
    events = _events()
    out = prepend_chapters(description, 120.0, events)
    assert "0:00 Opening" in out
    assert description in out


def test_prepend_chapters_skips_when_already_present() -> None:
    description = "0:00 Intro\nA living wireframe drifts through a black void."
    events = _events()
    out = prepend_chapters(description, 120.0, events)
    assert out == description


def test_short_video_still_has_opening() -> None:
    chapters = build_chapters(15.0, _events())
    assert chapters[0] == (0.0, "Opening")


def test_hour_formatting() -> None:
    events = [CreativeEvent(kind="bloom", start=3700.0, duration=2.0, intensity=0.5, direction=0.0, pitch_offset=0)]
    chapters = build_chapters(4000.0, events)
    block = chapters_to_description_block(chapters)
    assert "1:01:40 Bloom" in block
