from __future__ import annotations

import json

from utils import content_funnel


def test_short_is_queued_for_related_long_form(tmp_path, monkeypatch):
    queue = tmp_path / "content_funnel_queue.json"
    monkeypatch.setattr(content_funnel, "_queue_file", lambda: queue)
    content_funnel.record_funnel_candidate("short-1", {"kind": "short", "title": "Pata Jazz | Cat"})
    data = json.loads(queue.read_text(encoding="utf-8"))
    assert data["shorts_needing_link"][0]["video_id"] == "short-1"
    assert data["shorts_needing_link"][0]["status"] == "needs_related_long"


def test_long_form_is_available_as_a_target(tmp_path, monkeypatch):
    queue = tmp_path / "content_funnel_queue.json"
    monkeypatch.setattr(content_funnel, "_queue_file", lambda: queue)
    content_funnel.record_funnel_candidate("long-1", {"kind": "long", "title": "Pata Jazz | 30 minutes"})
    data = json.loads(queue.read_text(encoding="utf-8"))
    assert data["long_form_targets"][0]["video_id"] == "long-1"


def test_short_description_links_to_matching_long_form(tmp_path, monkeypatch):
    queue = tmp_path / "content_funnel_queue.json"
    monkeypatch.setattr(content_funnel, "_queue_file", lambda: queue)
    content_funnel.record_funnel_candidate("long-1", {"kind": "long", "mood": "relax"})
    description, target = content_funnel.append_related_video_cta(
        "A cozy cat and jazz moment.", {"kind": "short", "mood": "relax"}
    )
    assert target == "long-1"
    assert "https://www.youtube.com/watch?v=long-1" in description


def test_short_without_long_form_keeps_original_description(tmp_path, monkeypatch):
    monkeypatch.setattr(content_funnel, "_queue_file", lambda: tmp_path / "missing.json")
    description, target = content_funnel.append_related_video_cta("Original", {"kind": "short"})
    assert description == "Original"
    assert target is None
