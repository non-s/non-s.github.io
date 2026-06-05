"""Prevent platform-specific legacy code from returning."""
from __future__ import annotations

import json
from pathlib import Path

import fetch_animals


ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", ".pytest_cache", ".venv", ".venv-latest", "__pycache__", "env", "venv"}
BLOCKED = (
    "tik" + "tok",
    "f" + "yp",
    "for" + "you",
    "cat" + "tok",
    "dog" + "tok",
    "bird" + "tok",
    "farm" + "tok",
    "@wildbrief" + "_x",
    "feed" + "parser",
    "feed_" + "cache",
    "feed_" + "health",
    "pol" + "linations",
    "internet " + "archive",
    "na" + "sa",
)


def test_repository_is_focused_on_youtube():
    hits: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in {".py", ".md", ".html", ".yml", ".yaml", ".json", ".jsonl", ".example"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        for term in BLOCKED:
            if term in text:
                hits.append(f"{path.relative_to(ROOT)}: {term}")
    assert hits == [], "legacy platform references found:\n" + "\n".join(hits)


def test_animal_queue_has_unique_visually_aligned_scripts():
    queue = json.loads((ROOT/"_data"/"stories_queue.json").read_text(encoding="utf-8"))
    scripts: set[str] = set()
    for story in queue.get("stories", []):
        clip = type("Clip", (), {"url": story.get("url", ""), "title": story.get("title", "")})()
        subject = fetch_animals._subject_from_clip(clip, story.get("category", ""))
        assert fetch_animals._topic_accepts_subject(
            fetch_animals.ANIMAL_TOPICS[story["category"]], subject
        ), f"off-topic visual: {subject}"
        assert fetch_animals._script_matches_visible_subject(
            subject, story.get("script", "")
        ), f"script does not match visible animal: {subject}"
        key = fetch_animals._script_key(story.get("script", ""))
        assert key and key not in scripts, f"duplicate script: {subject}"
        scripts.add(key)


def test_youtube_workflow_stages_queue_before_optional_files():
    workflow = (ROOT / ".github" / "workflows" / "youtube-bot.yml").read_text(encoding="utf-8")
    assert "git add _data/stories_queue.json" in workflow
    assert "git add _videos/*.done _videos/*.roundup" not in workflow
    assert "YOUTUBE_PRIVACY:" in workflow
    assert "YOUTTUBE_PRIVACY:" not in workflow
    assert 'QUALITY_REQUIRE_MOTION_BROLL: "1"' in workflow
    assert 'QUALITY_REQUIRE_CAPTIONS: "1"' in workflow
    assert 'QUALITY_MIN_VISUAL_QA_SCORE: "6"' in workflow


def test_refresh_workflow_stages_queue_before_optional_files():
    workflow = (ROOT / ".github" / "workflows" / "fetch-content.yml").read_text(encoding="utf-8")
    assert "git add _data/stories_queue.json" in workflow
    assert "git add _data/stories_queue.json _data/ai_cache.jsonl" not in workflow
    assert "_data/provider_stats.jsonl" in workflow


def test_dashboard_workflow_refreshes_analytics_before_build():
    workflow = (ROOT / ".github" / "workflows" / "dashboard.yml").read_text(encoding="utf-8")
    assert "python scripts/analyze_channel.py" in workflow
    assert "python scripts/build_dashboard.py" in workflow
