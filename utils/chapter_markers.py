"""utils/chapter_markers.py — YouTube chapter markers from the creative timeline.

YouTube auto-generates chapter markers from timestamps in the video
description when the first timestamp is ``00:00`` and timestamps are in
ascending order. This module converts the creative-event timeline into a
human-readable chapter list that is prepended to the description.

Rules enforced to stay compatible with YouTube's parser:
- First chapter always starts at ``00:00``.
- Timestamps are ``M:SS`` or ``H:MM:SS``, zero-padded, strictly increasing.
- Minimum 10 seconds between chapters (YouTube ignores shorter gaps).
- Chapter title is short and evocative (derived from the event kind).
"""

from __future__ import annotations

from utils.liquid_wire_timeline import CreativeEvent

_LABELS: dict[str, str] = {
    "bloom": "Bloom",
    "compression": "Compression",
    "rupture": "Rupture",
    "tide": "Tide",
    "stillness": "Stillness",
}


def _format_timestamp(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours > 0:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:d}:{secs:02d}"


def build_chapters(duration: float, events: list[CreativeEvent]) -> list[tuple[float, str]]:
    """Return a list of ``(start_seconds, title)`` chapter tuples.

    The first chapter is always ``00:00 — Opening``. Subsequent chapters
    are derived from the creative events, de-duplicated and spaced at
    least 10 seconds apart. The final chapter (when the last event ends
    well before the video end) is ``Closing``.
    """
    chapters: list[tuple[float, str]] = [(0.0, "Opening")]
    last_start = 0.0
    for event in events:
        start = float(event.start)
        if start - last_start < 10.0:
            continue
        if start >= duration - 5.0:
            break
        label = _LABELS.get(event.kind, event.kind.capitalize())
        chapters.append((start, label))
        last_start = start
    if duration - last_start >= 15.0:
        chapters.append((max(last_start + 10.0, duration - 10.0), "Closing"))
    return chapters


def chapters_to_description_block(chapters: list[tuple[float, str]]) -> str:
    """Render chapters as a YouTube-compatible timestamp block.

    The block is plain text, one chapter per line, ready to be prepended
    to the video description. An empty header line separates the chapters
    from the rest of the description.
    """
    lines = [f"{_format_timestamp(start)} {title}" for start, title in chapters]
    return "\n".join(lines) + "\n"


def prepend_chapters(description: str, duration: float, events: list[CreativeEvent]) -> str:
    """Prepend a chapter-marker block to ``description`` if it has none.

    If the description already contains a line starting with a timestamp
    pattern (``00:00``), it is left untouched to avoid duplicating markers.
    """
    if not description:
        return description
    first_line = description.lstrip().splitlines()[0] if description.lstrip() else ""
    if first_line[:5] in {"00:00", "0:00 "} or first_line.startswith("00:00"):
        return description
    chapters = build_chapters(duration, events)
    block = chapters_to_description_block(chapters)
    return f"{block}\n{description}"
