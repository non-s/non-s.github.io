"""Tests for utils/title_history.py."""

from __future__ import annotations

import json

import pytest

from utils import title_history


@pytest.fixture
def intents_file(tmp_path):
    p = tmp_path / "upload_intents.jsonl"
    rows = [
        {"title": "Chuva Calma para Dormir -- Amber Hours", "status": "uploaded"},
        {"title": "  chuva calma para dormir -- amber hours  ", "status": "prepared"},
        {"title": "Rain Sounds for Sleep -- Amber Hours", "status": "uploaded"},
    ]
    p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    return p


def test_load_titles_normalizes_and_dedupes(intents_file):
    used = title_history.load_titles(intents_file)
    assert "chuva calma para dormir -- amber hours" in used
    assert "rain sounds for sleep -- amber hours" in used
    assert len(used) == 2


def test_select_title_picks_first_unused_variant(intents_file):
    used = title_history.load_titles(intents_file)
    variants = [
        "Chuva Calma para Dormir -- Amber Hours",
        "Chuva Forte para Relaxar -- Amber Hours",
        "Trovão e Chuva para Soneca -- Amber Hours",
    ]
    assert title_history.select_title(variants, used=used) == "Chuva Forte para Relaxar -- Amber Hours"


def test_select_title_falls_back_when_all_used(intents_file):
    used = title_history.load_titles(intents_file)
    variants = [
        "Chuva Calma para Dormir -- Amber Hours",
        "Rain Sounds for Sleep -- Amber Hours",
    ]
    assert title_history.select_title(variants, used=used) == "Rain Sounds for Sleep -- Amber Hours"


def test_select_title_loads_used_when_none_given(intents_file):
    variants = [
        "Chuva Calma para Dormir -- Amber Hours",
        "Chuva Forte para Relaxar -- Amber Hours",
    ]
    assert title_history.select_title(variants, path=intents_file) == "Chuva Forte para Relaxar -- Amber Hours"


def test_is_used_matches_normalized(intents_file):
    assert title_history.is_used("chuva calma para DORMIR -- AMBER HOURS", path=intents_file) is True
    assert title_history.is_used("Novo Título Inédito -- Amber Hours", path=intents_file) is False


def test_load_titles_returns_empty_on_missing_file(tmp_path):
    assert title_history.load_titles(tmp_path / "missing.jsonl") == set()


def test_load_titles_skips_malformed_lines(intents_file):
    intents_file.write_text(
        '{"title": "Good Title -- Amber Hours", "status": "uploaded"}\nbad json\n{"title": "Another -- Amber Hours"}\n',
        encoding="utf-8",
    )
    used = title_history.load_titles(intents_file)
    assert "good title -- amber hours" in used
    assert "another -- amber hours" in used
