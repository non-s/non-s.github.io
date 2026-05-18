"""Tests for utils/brand_card.py — render the static brand PNGs."""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PIL")

from utils import brand_card
from utils.host_persona import HostPersona


def test_render_intro_card_produces_png(tmp_path, monkeypatch):
    monkeypatch.setattr(brand_card, "BRAND_CARD_CACHE", tmp_path / "cache")
    out = brand_card.render_intro_card(HostPersona(name="TestHost",
                                                     handle="testchan"))
    assert out.exists()
    # PNG magic bytes.
    assert out.read_bytes().startswith(b"\x89PNG")
    # Above the visual sanity-check size (≥ 5 KB).
    assert out.stat().st_size > 5 * 1024


def test_render_intro_card_caches(tmp_path, monkeypatch):
    monkeypatch.setattr(brand_card, "BRAND_CARD_CACHE", tmp_path / "cache")
    p = HostPersona(name="X", handle="x")
    a = brand_card.render_intro_card(p)
    mtime_a = a.stat().st_mtime
    # Same persona → re-render returns the same file, doesn't rewrite.
    b = brand_card.render_intro_card(p)
    assert a == b
    assert b.stat().st_mtime == mtime_a


def test_different_persona_renders_different_card(tmp_path, monkeypatch):
    monkeypatch.setattr(brand_card, "BRAND_CARD_CACHE", tmp_path / "cache")
    a = brand_card.render_intro_card(HostPersona(name="Alex"))
    b = brand_card.render_intro_card(HostPersona(name="Beatriz"))
    assert a != b
    assert a.exists() and b.exists()


def test_render_outro_card_produces_png(tmp_path, monkeypatch):
    monkeypatch.setattr(brand_card, "BRAND_CARD_CACHE", tmp_path / "cache")
    out = brand_card.render_outro_card(HostPersona(name="TestHost"))
    assert out.exists()
    assert out.read_bytes().startswith(b"\x89PNG")


def test_get_intro_outro_cards_returns_both(tmp_path, monkeypatch):
    monkeypatch.setattr(brand_card, "BRAND_CARD_CACHE", tmp_path / "cache")
    intro, outro = brand_card.get_intro_outro_cards(HostPersona())
    assert intro.exists()
    assert outro.exists()
    assert intro != outro
