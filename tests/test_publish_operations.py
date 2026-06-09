from utils.local_rewriter import rescue_story
from utils.post24_review import build_review, classify_video
from utils.publish_schedule import recommend_schedule
from utils.publish_score import score_story
from utils.rejected_queue import load_rejections, record_rejection
from utils.rights_audit import audit_rights
from utils.sequence_factory import build_sequence_plan
from scripts.backfill_done_markers import backfill_marker
from scripts.dry_run_publish import build_dry_run


def _strong_story(**overrides):
    story = {
        "id": "ducks-1",
        "title": "Mallard ducks fake injuries to pull predators away",
        "seo_title": "Mallard ducks fake injuries to pull predators away",
        "hook": "Mallard ducks fake injuries to protect their young.",
        "script": (
            "Mallard ducks fake injuries when danger gets too close. "
            "The limp pulls attention away from the nest, then the duck escapes "
            "once the threat follows. It is a simple trick with a clear payoff."
        ),
        "category": "birds",
        "story_format": "animal_intelligence",
        "score": 9,
    }
    story.update(overrides)
    return story


def test_score_story_approves_specific_winning_candidate():
    score = score_story(_strong_story())

    assert score["state"] == "publish_ready"
    assert score["approved"] is True
    assert score["score"] >= 72


def test_score_story_sends_repetitive_template_to_rewrite_or_reject():
    story = _strong_story(
        title="Cows have another signal hiding in plain sight",
        seo_title="Cows have another signal hiding in plain sight",
        hook="Cows have another signal hiding in plain sight.",
        script="Another signal hiding in plain sight. Another signal hiding in plain sight.",
        story_format="animal_memory",
    )

    score = score_story(story)

    assert score["approved"] is False
    assert score["state"] in {"rewrite", "reject"}
    assert score["phrase_risk"]["hits"]


def test_rescue_story_rewrites_editorial_template_but_not_visual_mismatch():
    story = _strong_story(
        title="Cows have another signal hiding in plain sight",
        hook="Another signal hiding in plain sight.",
    )

    rescued, applied = rescue_story(story, ["repetitive_title_template"])
    unchanged, blocked = rescue_story(story, ["off_topic_visual"])

    assert applied is True
    assert rescued["local_rewrite"]["applied"] is True
    assert "hiding in plain sight" not in rescued["seo_title"].lower()
    assert blocked is False
    assert unchanged is story


def test_rejected_queue_records_and_replaces_same_story_stage(tmp_path):
    path = tmp_path / "rejected_queue.json"
    story = {"id": "abc", "title": "Weak story"}

    record_rejection(story, ["generic_script_template"], path=path, stage="queue_quality")
    record_rejection(story, ["duplicate_script"], path=path, stage="queue_quality")

    items = load_rejections(path)
    assert len(items) == 1
    assert items[0]["reasons"] == ["duplicate_script"]


def test_rejected_queue_jsonl_default_format_records_deduped_items(tmp_path):
    path = tmp_path / "rejected_queue.jsonl"
    story = {"id": "abc", "title": "Weak story"}

    record_rejection(story, ["weak_packaging"], path=path, stage="youtube_brain")
    record_rejection(story, ["generic_packaging"], path=path, stage="youtube_brain")

    items = load_rejections(path)
    assert len(items) == 1
    assert items[0]["reasons"] == ["generic_packaging"]


def test_rights_audit_requires_known_source_license_and_url():
    approved = audit_rights({
        "source": "Pexels",
        "source_license": "Pexels License",
        "source_url": "https://www.pexels.com/video/1/",
    })
    rejected = audit_rights({"source": "mystery archive"})

    assert approved["approved"] is True
    assert rejected["approved"] is False
    assert "unknown_source" in rejected["reasons"]
    assert "missing_source_url" in rejected["reasons"]


def test_backfill_done_marker_preserves_upload_identity_fields():
    marker = {
        "video_id": "yt123",
        "uploaded_at": "2026-01-01T00:00:00Z",
        "url": "https://youtube.com/shorts/yt123",
        "title": "Mallard ducks fake injuries to protect young",
        "seo_title": "Mallard ducks fake injuries to protect young",
        "script": "Mallard ducks fake injuries. Watch the wing cue first because it pulls predators away.",
        "thumbnail_text": "WATCH THE WING",
        "category": "birds",
    }

    updated, changed = backfill_marker(marker)

    assert changed is True
    assert updated["video_id"] == marker["video_id"]
    assert updated["uploaded_at"] == marker["uploaded_at"]
    assert updated["url"] == marker["url"]
    assert updated["packaging"]
    assert updated["publish_score"]
    assert updated["youtube_brain"]


def test_sequence_plan_generates_three_variants_per_winner():
    plan = build_sequence_plan({
        "top_performers": [{
            "video_id": "v1",
            "title": "Mallard ducks fake injuries to protect young",
            "category": "birds",
            "views": 1400,
            "view_pct": 66,
            "growth_score": 220,
        }]
    })

    assert plan["source_winners"] == 1
    assert len(plan["variants"]) == 3
    assert {item["sequence_variant"] for item in plan["variants"]} == {
        "same_format_new_animal",
        "same_animal_new_behavior",
        "same_topic_stronger_hook",
    }


def test_post24_review_classifies_scale_rewrite_pause_and_watch():
    assert classify_video({"views": 1200, "view_pct": 70, "growth_score": 250}) == "scale"
    assert classify_video({"views": 1200, "view_pct": 61, "growth_score": 250}) == "rewrite_hook"
    assert classify_video({"views": 1000, "view_pct": 45, "growth_score": 120}) == "rewrite_hook"
    assert classify_video({"views": 200, "view_pct": 40, "growth_score": 20}) == "pause_topic"
    assert classify_video({"views": 700, "view_pct": 55, "growth_score": 100}) == "watch"

    review = build_review({"top_performers": [{"video_id": "x", "title": "X", "views": 1200, "view_pct": 70, "growth_score": 250}]})
    assert review["counts"]["scale"] == 1
    assert "62" in review["rules"]["scale"]


def test_dry_run_publish_uses_autonomy_priority_before_queue_score():
    base = {
        "seo_title": "Ducks fake injuries to protect young",
        "title": "Ducks fake injuries to protect young",
        "hook": "Ducks fake injuries to protect their young.",
        "script": (
            "Ducks fake injuries when danger gets close. Watch the wing movement first, "
            "because that cue pulls predators away from the nest. That is why the young "
            "get time to hide before the payoff."
        ),
        "thumbnail_text": "DUCK WING",
        "yt_tags": ["ducks", "animal facts"],
        "source": "Pexels",
        "source_url": "https://www.pexels.com/video/duck-1/",
        "source_license": "Pexels License",
        "category": "farm",
        "score": 9,
    }
    payload = build_dry_run({"stories": [
        {**base, "id": "low", "autonomy": {"priority": 10, "lane": "fresh_experiment"}},
        {
            **base,
            "id": "high",
            "source_url": "https://www.pexels.com/video/duck-2/",
            "autonomy": {"priority": 130, "lane": "proven_category"},
        },
    ]})

    assert payload["would_publish"][0]["id"] == "high"
    assert payload["would_publish"][0]["autonomy_lane"] == "proven_category"
    assert payload["selection_rule"].startswith("autonomy_priority")


def test_publish_schedule_adapts_to_retention_health():
    low = recommend_schedule({"avg_view_pct": 45})
    high = recommend_schedule({"avg_view_pct": 75})

    assert low["recommended_shorts_per_day"] == 2
    assert high["recommended_shorts_per_day"] == 4
    assert high["recommended_slots"] == ["05:23", "14:23", "19:23", "23:23"]
    assert high["reason"] == "global_daypart_retention_based_until_country_analytics_available"
    assert len(high["recommended_slots"]) > len(low["recommended_slots"])
