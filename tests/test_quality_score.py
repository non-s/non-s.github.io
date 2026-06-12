"""Tests for utils.ai_helper.quality_score — the publish gate."""

from utils.ai_helper import quality_score


_RICH_AI = {
    "article_body": "x" * 600,
    "key_points": ["k1", "k2", "k3"],
    "tl_dr": "A sensible one-sentence summary of the animal fact.",
    "faq": [
        {"q": "Q1?", "a": "A1"},
        {"q": "Q2?", "a": "A2"},
        {"q": "Q3?", "a": "A3"},
    ],
}


def test_high_quality_passes():
    score, notes = quality_score(
        title="Octopus camouflage shifts colour and texture in only seconds",
        description="Specialised skin cells and tiny muscles let an octopus blend into coral, rocks, and sand within seconds.",
        ai_payload=_RICH_AI,
        body_chars=900,
    )
    assert score >= 8
    assert "no FAQ" not in " ".join(notes)


def test_thin_title_fails():
    score, _ = quality_score(
        title="animal fact",
        description="A reasonable description that has well over sixty characters of content here.",
        ai_payload=_RICH_AI,
        body_chars=900,
    )
    assert score <= 8  # missing 2 title points


def test_no_description_loses_points():
    # An empty description costs 2 points but rich AI fields still raise
    # the score above 6 — the gate is forgiving when the AI did the work.
    score, notes = quality_score(
        title="A reasonable title with enough length to not be flagged as short",
        description="",
        ai_payload=_RICH_AI,
    )
    assert score < 10
    assert any("description" in n for n in notes)


def test_empty_description_and_thin_ai_fails():
    # Empty description + no rich AI definitely fails the default gate.
    score, _ = quality_score(
        title="A reasonable title with enough length to not be flagged as short",
        description="",
        ai_payload={"article_body": "tiny"},
    )
    assert score < 6


def test_no_ai_body_fails_gate():
    score, _ = quality_score(
        title="A reasonable title with enough length to not be flagged as short",
        description="A reasonable description that has well over sixty characters of content here.",
        ai_payload={},
        body_chars=0,
    )
    assert score < 6  # missing body, key_points, tl_dr, faq


def test_partial_ai_passes_gate_at_6():
    score, _ = quality_score(
        title="A reasonable title with enough length to not be flagged as short",
        description="A reasonable description that has well over sixty characters of content here.",
        ai_payload={
            "article_body": "x" * 500,
            "key_points": ["a", "b", "c"],
            "tl_dr": "A sensible one-sentence summary.",
        },
        body_chars=500,
    )
    assert score >= 6  # title + desc + body + kp + tl_dr = 7


def test_spammy_title_penalised():
    score, notes = quality_score(
        title="Click here for the most shocking animal fact you wont believe",
        description="A reasonable description that has well over sixty characters of content here.",
        ai_payload=_RICH_AI,
    )
    assert any("spammy" in n for n in notes)


def test_max_without_image_is_9():
    # Title 2 + desc 2 + body 2 + kp 1 + tl_dr 1 + faq 1 = 9.
    # The 10th point is reserved for a verified image, injected by the
    # caller — quality_score itself never sees the image.
    score, _ = quality_score(
        title="A perfectly composed animal fact title with verbs and concrete subjects today",
        description="A descriptive paragraph that is clearly longer than 120 chars, contains a period, and clearly explains the story in plain prose so readers can understand the gist before clicking through to the full piece.",
        ai_payload=_RICH_AI,
        body_chars=1200,
    )
    assert score == 9
