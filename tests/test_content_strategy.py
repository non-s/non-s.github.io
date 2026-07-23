"""Testes para content_strategy.py."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

from utils import content_strategy


def test_best_slot_for_short():
    slot = content_strategy.best_slot_for("short")
    assert slot in content_strategy.PUBLISH_SLOTS["short"]


def test_best_slot_for_horizontal():
    slot = content_strategy.best_slot_for("horizontal")
    assert slot in content_strategy.PUBLISH_SLOTS["horizontal"]


def test_best_slot_for_live():
    slot = content_strategy.best_slot_for("live")
    assert slot in content_strategy.PUBLISH_SLOTS["live"]


def test_best_slot_weekend():
    # Sabado = 5, Domingo = 6
    slot_sab = content_strategy.best_slot_for("short", weekday=5)
    slot_dom = content_strategy.best_slot_for("short", weekday=6)
    # Finais de semana devem retornar o último slot
    assert slot_sab == content_strategy.PUBLISH_SLOTS["short"][-1]
    assert slot_dom == content_strategy.PUBLISH_SLOTS["short"][-1]


def test_pick_scene_category_fofura():
    category = content_strategy.pick_scene_category("fofura")
    assert category == "fofura"


def test_pick_scene_category_random():
    category = content_strategy.pick_scene_category()
    assert category in content_strategy.SCENE_CATEGORIES


def test_pick_scene_category_invalid():
    category = content_strategy.pick_scene_category("invalido")
    assert category in content_strategy.SCENE_CATEGORIES


def test_weekly_calendar_length():
    calendar = content_strategy.weekly_calendar()
    assert len(calendar) == 7


def test_weekly_calendar_has_required_keys():
    calendar = content_strategy.weekly_calendar()
    for entry in calendar:
        assert "day" in entry
        assert "type" in entry
        assert "slot" in entry
        assert "mood" in entry


def test_weekly_calendar_days():
    calendar = content_strategy.weekly_calendar()
    days = [e["day"] for e in calendar]
    assert days == ["Seg", "Ter", "Qua", "Qui", "Sex", "Sab", "Dom"]
