"""Tests for generate_liquid_wire_video._record_dead_letter (Frente F)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import generate_liquid_wire_video as liquid


def test_record_dead_letter_writes_to_queue(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(liquid, "data_dir", lambda: tmp_path)
    with patch("utils.notifier.send_alert") as mock_alert:
        liquid._record_dead_letter("slot-3", 12345, "score_below_threshold", {"family": "orb", "genre": "lofi_ambient"})
    queue = json.loads((tmp_path / "dead_letter_queue.json").read_text(encoding="utf-8"))
    assert len(queue) == 1
    entry = queue[0]
    assert entry["slot"] == "slot-3"
    assert entry["seed"] == 12345
    assert entry["error"] == "score_below_threshold"
    assert entry["family"] == "orb"
    assert entry["genre"] == "lofi_ambient"
    assert entry["timestamp"].endswith("+00:00")
    mock_alert.assert_called_once()
    assert "slot=slot-3" in mock_alert.call_args.args[0]
    assert mock_alert.call_args.kwargs.get("level") == "error"


def test_record_dead_letter_appends_to_existing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(liquid, "data_dir", lambda: tmp_path)
    existing = [
        {
            "slot": "old", "seed": 1, "error": "x",
            "family": "", "genre": "",
            "timestamp": "2026-01-01T00:00:00+00:00",
        }
    ]
    (tmp_path / "dead_letter_queue.json").write_text(json.dumps(existing), encoding="utf-8")
    with patch("utils.notifier.send_alert"):
        liquid._record_dead_letter("slot-4", 2, "y", {"family": "torus", "genre": "cinematic"})
    queue = json.loads((tmp_path / "dead_letter_queue.json").read_text(encoding="utf-8"))
    assert len(queue) == 2
    assert queue[-1]["slot"] == "slot-4"
    assert queue[0]["slot"] == "old"


def test_record_dead_letter_bounded_to_100(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(liquid, "data_dir", lambda: tmp_path)
    pre = [
        {
            "slot": f"slot-{i}", "seed": i, "error": "e",
            "family": "", "genre": "",
            "timestamp": "2026-01-01T00:00:00+00:00",
        }
        for i in range(100)
    ]
    (tmp_path / "dead_letter_queue.json").write_text(json.dumps(pre), encoding="utf-8")
    with patch("utils.notifier.send_alert"):
        liquid._record_dead_letter("slot-new", 999, "overflow", {"family": "ribbon", "genre": "lofi_ambient"})
    queue = json.loads((tmp_path / "dead_letter_queue.json").read_text(encoding="utf-8"))
    assert len(queue) == 100
    # The oldest entry was evicted, the newest is last.
    assert queue[-1]["slot"] == "slot-new"
    assert queue[0]["slot"] == "slot-1"


def test_record_dead_letter_corrupt_file_is_replaced(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(liquid, "data_dir", lambda: tmp_path)
    (tmp_path / "dead_letter_queue.json").write_text("not valid json", encoding="utf-8")
    with patch("utils.notifier.send_alert"):
        liquid._record_dead_letter("slot-5", 5, "err", {"family": "knot", "genre": "ambient"})
    queue = json.loads((tmp_path / "dead_letter_queue.json").read_text(encoding="utf-8"))
    assert len(queue) == 1
    assert queue[0]["slot"] == "slot-5"


def test_record_dead_letter_sends_alert(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(liquid, "data_dir", lambda: tmp_path)
    with patch("utils.notifier.send_alert") as mock_alert:
        liquid._record_dead_letter("slot-6", 6, "boom", {"family": "coral", "genre": "drone"})
    mock_alert.assert_called_once_with(
        "Liquid Wire dead-letter: slot=slot-6 seed=6 error=boom",
        level="error",
    )
