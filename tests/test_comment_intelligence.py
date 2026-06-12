"""Tests for audience-comment learning."""

from utils.comment_intelligence import analyze_comments, clean_comment


def test_clean_comment_strips_html():
    assert clean_comment("Can you do <b>octopus</b>?") == "Can you do octopus?"


def test_analyze_comments_extracts_questions_animals_and_prompts():
    out = analyze_comments(
        [
            {"text": "Can you do a shark video next?", "likeCount": 4, "video_id": "a"},
            {"text": "What about snakes and crocodiles?", "likeCount": 2, "video_id": "b"},
            {"text": "Love the octopus facts", "likeCount": 1, "video_id": "c"},
        ]
    )
    assert out["comments_sampled"] == 3
    assert out["question_count"] == 2
    assert "shark" in out["requested_animals"]
    assert "snake" in out["requested_animals"]
    assert out["content_prompts"][0].startswith("Answer this viewer question:")
