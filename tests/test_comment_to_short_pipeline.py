import json

from scripts.comment_to_short_pipeline import run
from utils.comment_to_short import build_candidates, merge_into_queue
from utils.packaging import package_story


def test_comment_to_short_scores_question():
    candidates = build_candidates(
        {"raw_comments": [{"text": "Can you do sharks next?", "likeCount": 4, "video_id": "v"}]}
    )

    assert candidates[0]["score"] >= 64
    assert candidates[0]["source"] == "YouTube comment idea"
    assert candidates[0]["category"] == "ocean"
    assert candidates[0]["source_license"]
    assert "answer to a viewer question" not in candidates[0]["title"].lower()


def test_comment_to_short_recovers_specific_plural_animal_question():
    candidates = build_candidates(
        {"raw_comments": [{"text": "5 is best number for a clutch of ducklings?", "video_id": "duck1"}]}
    )

    assert candidates[0]["score"] >= 64
    assert candidates[0]["category"] == "farm"
    assert candidates[0]["title"] == "Ducklings compare groups before they swim"
    assert "number sense" in candidates[0]["script"]


def test_comment_to_short_maps_big_cat_question_to_wildlife():
    candidates = build_candidates(
        {"raw_comments": [{"text": "What big cat or predator makes noise when hunting?", "video_id": "lion1"}]}
    )

    assert candidates[0]["category"] == "wildlife"
    assert candidates[0]["title"] == "Lions hunt better when the pride coordinates"
    assert "?comment=" in candidates[0]["source_url"]


def test_comment_to_short_downranks_channel_self_prompt():
    candidates = build_candidates(
        {
            "raw_comments": [
                {
                    "text": "Did you spot the tail before the reveal? Comment the next animal after bird.",
                    "video_id": "bird1",
                    "author": "@wildbrief-e8o",
                }
            ]
        }
    )

    assert candidates[0]["score"] < 64
    assert "channel_self_prompt" in candidates[0]["comment_score"]["reasons"]


def test_comment_to_short_omits_malformed_source_title():
    candidates = build_candidates(
        {"raw_comments": [{"text": "Can you do sharks next?", "likeCount": 4, "video_id": "v"}]},
        [{"video_id": "v", "title": "Lions use their ears to use"}],
    )

    assert candidates[0]["source_title"] == ""


def test_comment_to_short_pipeline_writes_candidates_and_queue(tmp_path, monkeypatch):
    analytics = tmp_path / "_data" / "analytics"
    analytics.mkdir(parents=True)
    (analytics / "comments.json").write_text(
        json.dumps({"raw_comments": [{"text": "Can you do sharks next?", "likeCount": 4, "video_id": "v"}]}),
        encoding="utf-8",
    )
    (tmp_path / "_data" / "stories_queue.json").write_text(json.dumps({"stories": []}), encoding="utf-8")
    monkeypatch.setenv("COMMENT_TO_SHORT_ENABLED", "1")

    payload = run(tmp_path)

    assert payload["queued"] == 1
    assert (tmp_path / "_data" / "comment_to_short_candidates.json").exists()


def test_merge_into_queue_is_idempotent():
    candidate = build_candidates(
        {"raw_comments": [{"text": "Can you do sharks next?", "likeCount": 4, "video_id": "v"}]}
    )[0]

    first = merge_into_queue({"stories": []}, [candidate])
    second = merge_into_queue(first, [candidate])

    assert len(second["stories"]) == 1
    assert second["comment_to_short_updated"] == 1


def test_merge_into_queue_skips_duplicate_comment_angle():
    existing = {
        "id": "lion-existing",
        "title": "Lions hunt better when the pride coordinates",
        "seo_title": "Lions hunt better when the pride coordinates",
        "hook": "Lions turn hunting into a team problem.",
        "script": (
            "Lions keep the hunt quiet for a reason. Watch the ears and body first, because sound can "
            "warn prey before the chase even starts. The payoff lands on replay: the quiet moment is "
            "part of the hunting setup. That makes the first silent second the clue viewers should replay."
        ),
        "thumbnail_text": "PRIDE PLAN",
        "category": "wildlife",
    }
    candidate = build_candidates(
        {"raw_comments": [{"text": "What big cat or predator makes noise when hunting?", "video_id": "lion1"}]}
    )[0]

    merged = merge_into_queue({"stories": [existing]}, [candidate])

    assert len(merged["stories"]) == 1
    assert merged.get("comment_to_short_added") == 0


def test_merge_into_queue_refreshes_existing_comment_idea():
    candidate = build_candidates(
        {"raw_comments": [{"text": "Can you do sharks next?", "likeCount": 4, "video_id": "shark1"}]}
    )[0]
    old = {
        "id": candidate["id"],
        "title": "Old comment title",
        "seo_title": "Old comment title",
        "score": 64,
        "studio_state": "comment_idea",
        "comment_to_short": {"queued_at": "2026-01-01T00:00:00+00:00"},
    }

    merged = merge_into_queue({"stories": [old]}, [candidate])

    assert merged["stories"][0]["title"] == "Sharks sense tiny electric fields"
    assert merged["comment_to_short_added"] == 0
    assert merged["comment_to_short_updated"] == 1
    assert merged["stories"][0]["comment_to_short"]["queued_at"] == "2026-01-01T00:00:00+00:00"


def test_merge_into_queue_keeps_existing_comment_idea_when_angle_passes_directly():
    candidate = build_candidates(
        {"raw_comments": [{"text": "5 is best number for a clutch of ducklings?", "video_id": "duck1"}]}
    )[0]
    old = {
        "id": candidate["id"],
        "title": "Old duckling comment",
        "seo_title": "Old duckling comment",
        "studio_state": "comment_idea",
    }

    merged = merge_into_queue({"stories": [old]}, [candidate])

    assert merged["stories"][0]["title"] == "Ducklings compare groups before they swim"
    assert merged["comment_to_short_updated"] == 1
    assert merged["comment_to_short_removed"] == 0


def test_comment_idea_packaging_preserves_viewer_question_hook():
    candidate = build_candidates(
        {"raw_comments": [{"text": "What big cat or predator makes noise when hunting?", "video_id": "lion1"}]}
    )[0]
    candidate["studio_state"] = "comment_idea"

    packaged = package_story(candidate)

    assert packaged["title"] == "Lions hunt better when the pride coordinates"
    assert packaged["hook"] == "Lions turn hunting into a team problem."
