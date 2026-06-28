from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("googleapiclient")

from scripts.repair_youtube_metadata import (  # noqa: E402
    collect_repair_plans,
    needs_semantic_title_repair,
    repair_plan,
    write_marker_repair,
)


def _bad_marker() -> dict:
    return {
        "title": "Wasp use trap hairs to count touches before snapping shut",
        "description": "Wasp use trap hairs to count touches before snapping shut. A plant short.",
        "category": "plants",
        "tags": ["wasp", "pollination", "flower", "insects", "plants"],
        "search_intent": {
            "visible_cue": "leaf surface",
            "terms": ["plants", "leaf surface", "plant mechanism"],
        },
        "upload_title_dedupe": {
            "applied": True,
            "reason": "published_title_collision",
            "before": "Plants use trap hairs to count touches before snapping shut",
            "after": "Wasp use trap hairs to count touches before snapping shut",
        },
        "video_id": "uMBHm6tNXkg",
    }


def test_repair_plan_restores_safe_story_subject():
    marker = _bad_marker()

    plan = repair_plan(
        marker,
        Path("_videos/short.done"),
        {"wasp use trap hairs to count touches before snapping shut"},
    )

    assert plan["video_id"] == "uMBHm6tNXkg"
    assert plan["before_title"].startswith("Wasp ")
    assert plan["after_title"] == "Plants use trap hairs to count touches before snapping shut"
    assert plan["after_description"].startswith("Plants use trap hairs")


def test_repair_plan_keeps_title_unique_when_original_is_already_live():
    marker = _bad_marker()

    plan = repair_plan(
        marker,
        Path("_videos/short.done"),
        {
            "wasp use trap hairs to count touches before snapping shut",
            "plants use trap hairs to count touches before snapping shut",
        },
    )

    assert plan["after_title"] == "Plants use trap hairs to count touches before snapping shut | Leaf surface"
    assert not plan["after_title"].lower().startswith("wasp ")


def test_safe_dedupe_marker_does_not_need_semantic_repair():
    marker = _bad_marker()
    marker["title"] = "Flowers use trap hairs to count touches before snapping shut"
    marker["upload_title_dedupe"]["after"] = marker["title"]

    assert needs_semantic_title_repair(marker) is False


def test_collect_repair_plans_can_filter_by_video_id(tmp_path):
    videos = tmp_path / "_videos"
    videos.mkdir()
    (videos / "bad.done").write_text(json.dumps(_bad_marker()), encoding="utf-8")

    assert collect_repair_plans(videos, video_ids={"other"}) == []
    assert len(collect_repair_plans(videos, video_ids={"uMBHm6tNXkg"})) == 1


def test_write_marker_repair_records_applied_state(tmp_path):
    path = tmp_path / "short.done"
    path.write_text(json.dumps(_bad_marker()), encoding="utf-8")
    plan = repair_plan(_bad_marker(), path, set())

    write_marker_repair(plan, applied=True, response={"id": "uMBHm6tNXkg"})

    marker = json.loads(path.read_text(encoding="utf-8"))
    assert marker["title"] == plan["after_title"]
    assert marker["metadata_repair"]["applied"] is True
    assert marker["metadata_repair"]["before_title"].startswith("Wasp ")
