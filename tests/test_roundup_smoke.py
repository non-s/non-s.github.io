"""Smoke test for generate_roundup.py — exercises the script with
every external touchpoint mocked. Catches wiring regressions before
CI."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("PIL")
pytest.importorskip("feedparser")


def _seed_queue(tmp_path: Path, n_stories: int = 8) -> None:
    """Write a `_data/stories_queue.json` with N consumed stories that
    each score 8+. The roundup selector pulls these."""
    from datetime import datetime, timezone, timedelta
    base = datetime.now(timezone.utc) - timedelta(days=2)
    stories = []
    for i in range(n_stories):
        stories.append({
            "id":           f"id-{i:02d}",
            "fetched_at":   base.isoformat(),
            "published_at": base.isoformat(),
            "consumed":     True,  # must be already shipped
            "consumed_at":  base.isoformat(),
            "title":        f"Story {i}",
            "seo_title":    f"Major event #{i} hits markets today",
            "hook":         f"The {i}-th major story dropped.",
            "script":       ("The %d-th major story dropped. " % i) +
                            ("This rewrites everything we knew about it. " * 6),
            "thumbnail_text": f"STORY {i}",
            "yt_description": "x",
            "yt_tags":      ["story"],
            "geo_hashtag":  "Global",
            "topic_hashtag": "Markets",
            "url":          f"https://e.test/{i}",
            "source":       "Test Outlet",
            "category":     "world",
            "description":  "Background paragraph.",
            "image_url":    "",
            "breaking":     False,
            "relevance":    7.0,
            "native_lang":  "en",
            "score":        9,
            "experiments":  {},
            "sentiment":    "neutral",
        })
    queue_dir = tmp_path / "_data"
    queue_dir.mkdir(parents=True, exist_ok=True)
    (queue_dir / "stories_queue.json").write_text(
        json.dumps({"stories": stories}), encoding="utf-8",
    )


def test_select_roundup_stories_returns_consumed_recent_high_score(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed_queue(tmp_path)
    import importlib, sys
    if "generate_roundup" in sys.modules:
        del sys.modules["generate_roundup"]
    import generate_roundup as gr
    importlib.reload(gr)
    chosen = gr.select_roundup_stories(n=7)
    assert len(chosen) == 7
    assert all(s["consumed"] for s in chosen)


def test_select_roundup_stories_skips_low_score(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed_queue(tmp_path, n_stories=2)
    # Patch the score of both stories to below threshold.
    queue_path = tmp_path / "_data" / "stories_queue.json"
    data = json.loads(queue_path.read_text())
    for s in data["stories"]:
        s["score"] = 3
    queue_path.write_text(json.dumps(data))
    import importlib, sys
    if "generate_roundup" in sys.modules:
        del sys.modules["generate_roundup"]
    import generate_roundup as gr
    importlib.reload(gr)
    assert gr.select_roundup_stories(n=7) == []


def test_build_roundup_script_concatenates_chapters():
    import generate_roundup as gr
    stories = [
        {"seo_title": "Story A", "hook": "A happened.",  "script": "A happened. Details. " * 30, "source": "Reuters"},
        {"seo_title": "Story B", "hook": "B happened.",  "script": "B happened. Details. " * 30, "source": "BBC"},
        {"seo_title": "Story C", "hook": "C happened.",  "script": "C happened. Details. " * 30, "source": "CNBC"},
    ]
    script = gr.build_roundup_script(stories)
    assert "Number 1" in script
    assert "Number 2" in script
    assert "Number 3" in script
    assert "Reuters" in script
    assert "BBC" in script
    # Intro + outro are present.
    assert "GlobalBR News" in script


def test_build_roundup_metadata_has_chapters(tmp_path):
    import generate_roundup as gr
    stories = [
        {"seo_title": f"Story {i}", "source": "Reuters", "category": "world",
         "hook": "x", "script": "x", "topic_hashtag": "T"}
        for i in range(7)
    ]
    fake_video = tmp_path / "v.mp4"
    fake_thumb = tmp_path / "t.jpg"
    fake_video.write_bytes(b"x")
    fake_thumb.write_bytes(b"x")
    meta = gr.build_roundup_metadata(stories, fake_video, fake_thumb)
    # Required keys upload_youtube.py reads.
    for k in ("title", "description", "tags", "category_id", "privacy",
               "thumbnail", "video", "story_slug", "category"):
        assert k in meta
    # Description carries chapter markers (00:00 / mm:ss prefixes).
    assert "00:00 Intro" in meta["description"]
    # is_short flag tells upload_youtube it's NOT a Short.
    assert meta["is_short"] is False
    # AI disclosure stays set.
    assert meta["altered_content"] is True


def test_main_exits_cleanly_when_too_few_stories(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed_queue(tmp_path, n_stories=1)
    import importlib, sys
    if "generate_roundup" in sys.modules:
        del sys.modules["generate_roundup"]
    import generate_roundup as gr
    importlib.reload(gr)
    # Should NOT raise — just log "too few" and return.
    gr.main()  # main is sync, returns None
