from __future__ import annotations

from utils.rejection_memory import REJECTION_LIMIT, recent_rejection_counts, record_rejection


def test_rejection_memory_is_versioned_normalized_and_bounded(tmp_path):
    path = tmp_path / "rejections.json"
    for index in range(REJECTION_LIMIT + 3):
        record_rejection(path, "too_similar" if index % 2 else "unknown", seed=index)
    counts = recent_rejection_counts(path, limit=REJECTION_LIMIT + 10)
    assert sum(counts.values()) == REJECTION_LIMIT
    assert set(counts) == {"too_similar", "render_failure"}
