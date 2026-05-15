"""Tests for the AI-driven extra fields that fetch_news.py.build_frontmatter writes.

We don't try to import the giant fetch_news module here (it pulls in
network deps); instead we re-parse the output through utils.frontmatter
so the contract is exercised end-to-end at the YAML level.
"""
from utils.frontmatter import parse, get_str, get_list


def _build(fm_lines: list[str]) -> dict:
    text = "---\n" + "".join(line + "\n" for line in fm_lines) + "---\n\nbody"
    return parse(text)


def test_tl_dr_round_trip():
    fm = _build([
        'title: "Some Title"',
        'tl_dr: "Scientists confirm new drug cuts dementia risk."',
    ])
    assert get_str(fm, "tl_dr") == "Scientists confirm new drug cuts dementia risk."


def test_lead_round_trip():
    fm = _build([
        'title: "Some Title"',
        'lead: "A 40-word answer to who, what, when, where, why."',
    ])
    assert "40-word answer" in get_str(fm, "lead")


def test_content_type_round_trip():
    fm = _build([
        'title: "Some Title"',
        'content_type: "breaking"',
    ])
    assert get_str(fm, "content_type") == "breaking"


def test_entities_round_trip():
    fm = _build([
        'title: "Some Title"',
        'entities:',
        '  - "Anthropic"',
        '  - "OpenAI"',
        '  - "Sam Altman"',
    ])
    entities = get_list(fm, "entities")
    assert entities == ["Anthropic", "OpenAI", "Sam Altman"]


def test_key_points_round_trip():
    fm = _build([
        'title: "Some Title"',
        'key_points:',
        '  - "First key point sentence"',
        '  - "Second key point sentence"',
    ])
    kp = get_list(fm, "key_points")
    assert kp[0] == "First key point sentence"
    assert kp[1] == "Second key point sentence"
