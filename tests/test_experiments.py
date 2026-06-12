"""Tests for utils/experiments.py â€” pure assignment + winner math."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from utils import experiments


# â”€â”€ assignment â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def test_assign_variant_is_deterministic():
    a = experiments.assign_variant("hook_style", "story-abc")
    b = experiments.assign_variant("hook_style", "story-abc")
    assert a == b
    assert a in experiments.variant_choices("hook_style")


def test_assign_variant_distributes_across_panel():
    seen = set()
    for i in range(200):
        seen.add(experiments.assign_variant("hook_style", f"story-{i}"))
    # All 4 variants should appear within 200 random keys.
    assert seen == set(experiments.variant_choices("hook_style"))


def test_assign_variant_unknown_axis_returns_empty():
    assert experiments.assign_variant("not.a.real.axis", "story") == ""


def test_production_assignment_favors_winner(monkeypatch):
    monkeypatch.setattr(experiments, "read_winner", lambda axis: "outcome_first")
    assert (
        experiments.assign_for_production(
            "hook_style",
            "story",
            exploration_percent=0,
        )
        == "outcome_first"
    )


def test_assign_all_returns_one_variant_per_axis():
    out = experiments.assign_all("story-key-123")
    assert set(out.keys()) == set(experiments.axis_names())
    for ax_name, variant in out.items():
        assert variant in experiments.variant_choices(ax_name)


def test_axis_names_matches_registry():
    names = experiments.axis_names()
    assert "hook_style" in names
    assert "script_tone" in names
    assert "narrator_voice" in names
    assert "thumbnail_style" in names
    assert "cta_style" in names


def test_variant_choices_includes_documented_variants():
    assert "outcome_first" in experiments.variant_choices("hook_style")
    assert "question" in experiments.variant_choices("hook_style")
    assert "opinionated" in experiments.variant_choices("script_tone")
    assert "aria" in experiments.variant_choices("narrator_voice")


def test_thumbnail_style_is_locked_to_frame_first_caption():
    assert experiments.variant_choices("thumbnail_style") == ("frame_first_side_caption",)


def test_cta_is_channel_subscription_only():
    """End cards keep one unambiguous growth action."""
    cta_variants = experiments.variant_choices("cta_style")
    assert cta_variants == ("subscribe_channel",)


# â”€â”€ winner computation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def test_compute_winners_picks_highest_mean(monkeypatch):
    monkeypatch.setattr(experiments, "MIN_SAMPLES_FOR_WINNER", 3)
    # 4 outcome_first observations averaging 80; 4 question averaging 60.
    obs = [{"experiments": {"hook_style": "outcome_first"}, "score": 80} for _ in range(4)] + [
        {"experiments": {"hook_style": "question"}, "score": 60} for _ in range(4)
    ]
    out = experiments.compute_winners(obs, min_samples=3)
    assert out["winners"]["hook_style"] == "outcome_first"
    assert out["axis_stats"]["hook_style"]["outcome_first"]["mean"] == 80
    assert out["lift"]["hook_style"]["lift"] == 20


def test_compute_winners_skips_below_min_samples():
    # Only 2 observations per variant â€” below default 8.
    obs = [{"experiments": {"hook_style": "outcome_first"}, "score": 80} for _ in range(2)] + [
        {"experiments": {"hook_style": "question"}, "score": 60} for _ in range(2)
    ]
    out = experiments.compute_winners(obs)
    # No winner emitted â€” needs more data first.
    assert out["winners"] == {}


def test_compute_winners_handles_empty():
    out = experiments.compute_winners([])
    assert out["winners"] == {}
    assert out["axis_stats"] == {}


def test_compute_winners_skips_malformed_observations():
    obs = [
        {"experiments": "not a dict", "score": 80},  # bad experiments
        {"experiments": {"hook_style": 123}, "score": 80},  # bad variant type
        {"experiments": {"hook_style": "x"}, "score": "ten"},  # bad score
        # One valid record so the computation has a tableau.
        {"experiments": {"hook_style": "outcome_first"}, "score": 50.0},
    ]
    out = experiments.compute_winners(obs)
    # Only the one valid record made it in.
    assert out["axis_stats"]["hook_style"]["outcome_first"]["n"] == 1


def test_compute_winners_multi_axis(monkeypatch):
    monkeypatch.setattr(experiments, "MIN_SAMPLES_FOR_WINNER", 3)
    obs = [
        {"experiments": {"hook_style": "outcome_first", "script_tone": "curious"}, "score": 80} for _ in range(5)
    ] + [{"experiments": {"hook_style": "outcome_first", "script_tone": "opinionated"}, "score": 90} for _ in range(5)]
    out = experiments.compute_winners(obs, min_samples=3)
    # hook_style only has one variant in the data, but it still "wins".
    assert out["winners"]["hook_style"] == "outcome_first"
    assert out["winners"]["script_tone"] == "opinionated"


# â”€â”€ read / write â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def test_read_winners_handles_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(experiments, "EXPERIMENTS_FILE", tmp_path / "exp.json")
    assert experiments.read_winners() == {}


def test_read_write_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(experiments, "EXPERIMENTS_FILE", tmp_path / "exp.json")
    payload = {"winners": {"hook_style": "outcome_first"}}
    experiments.write_winners(payload)
    assert experiments.read_winners() == {"hook_style": "outcome_first"}
    assert experiments.read_winner("hook_style") == "outcome_first"
    assert experiments.read_winner("missing_axis") is None


def test_read_winners_handles_malformed(tmp_path, monkeypatch):
    p = tmp_path / "exp.json"
    p.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(experiments, "EXPERIMENTS_FILE", p)
    assert experiments.read_winners() == {}
