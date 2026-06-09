from utils.queue_pruner import prune_queue, quality_issues


def _story(idx="1", **overrides):
    story = {
        "id": f"story-{idx}",
        "title": "Mallard ducks fake injuries to pull predators away",
        "seo_title": "Mallard ducks fake injuries to pull predators away",
        "hook": "Mallard ducks fake injuries to protect their young.",
        "script": (
            "Mallard ducks fake injuries when danger gets too close. "
            "Watch the wing cue first, because the limp pulls predators away "
            "from the nest before the duck escapes."
        ),
        "thumbnail_text": "WATCH THE WING",
        "yt_tags": ["ducks", "animal behavior"],
        "category": "farm",
        "source": "Pexels",
        "source_license": "Pexels License",
        "source_url": f"https://www.pexels.com/video/{idx}/",
        "score": 9,
    }
    story.update(overrides)
    return story


def test_quality_issues_rejects_generic_template_and_duplicate_title():
    seen_titles = set()
    seen_angles = set()
    seen_sources = set()
    first = _story()
    duplicate = _story("2")
    generic = _story(
        "3",
        title="Cows have another signal hiding in plain sight",
        seo_title="Cows have another signal hiding in plain sight",
    )

    assert quality_issues(first, seen_titles=seen_titles, seen_angles=seen_angles, seen_sources=seen_sources) == []

    duplicate_issues = quality_issues(
        duplicate,
        seen_titles=seen_titles,
        seen_angles=seen_angles,
        seen_sources=seen_sources,
    )
    generic_issues = quality_issues(
        generic,
        seen_titles=seen_titles,
        seen_angles=seen_angles,
        seen_sources=seen_sources,
    )

    assert "duplicate_title" in duplicate_issues
    assert "generic_title_template" in generic_issues


def test_quality_issues_rejects_script_subject_mismatch():
    issues = quality_issues(
        _story(
            title="orangutan relaxing outdoors with vegetation",
            seo_title="Primates show the hand cue before they follow",
            script="Monkeys follow hand cues because the body signal tells the group where to move.",
            category="primates",
            source_url="https://www.pexels.com/video/orangutan-relaxing-outdoors-with-vegetation/",
        ),
        seen_titles=set(),
        seen_angles=set(),
        seen_sources=set(),
    )

    assert "script_subject_mismatch" in issues


def test_prune_queue_keeps_strong_traceable_candidates_and_quarantines_rest():
    queue = {
        "stories": [
            _story("1"),
            _story("2", seo_title="Penguins slide on their bellies to save energy", title="Penguins slide on their bellies to save energy", source_url=""),
            _story(
                "3",
                seo_title="Why tigers flick their ears before charging",
                title="tiger walking through grass",
                script=(
                    "Tigers flick their ears before charging. Watch the ear cue first, "
                    "because that movement can signal where their focus is before they move."
                ),
                thumbnail_text="WATCH THE EARS",
                category="wildlife",
                source_url="https://www.pexels.com/video/tiger-walking-through-grass/",
            ),
        ]
    }

    pruned, rejected, summary = prune_queue(queue, max_pending=1)

    kept = [story for story in pruned["stories"] if not story.get("consumed")]
    assert len(kept) == 1
    assert kept[0]["queue_prune"]["state"] in {"publish_ready", "rewrite", "reject"}
    assert kept[0]["packaging"]
    assert kept[0]["youtube_brain"]
    assert summary["pending_before"] == 3
    assert summary["pending_after"] == 1
    assert len(rejected) == 2
    assert any("missing_source_url" in item["reasons"] for item in rejected)
    assert any("queue_pruned_low_priority" in item["reasons"] for item in rejected)
