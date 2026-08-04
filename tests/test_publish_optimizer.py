"""tests/test_publish_optimizer.py — cobertura para utils/publish_optimizer.py."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from utils import publish_optimizer


@pytest.fixture(autouse=True)
def _reset_env(monkeypatch):
    monkeypatch.setenv("BRT_OFFSET_HOURS", "-3")


def test_best_publish_slots_uses_benchmark_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(publish_optimizer, "data_dir", lambda: tmp_path)
    slots = publish_optimizer.best_publish_slots(count=5)
    assert len(slots) > 0
    for s in slots:
        assert "day_of_week" in s
        assert "hour" in s
        assert s["source"] == "benchmark"


def test_best_publish_slots_uses_data_when_available(tmp_path, monkeypatch):
    monkeypatch.setattr(publish_optimizer, "data_dir", lambda: tmp_path)
    # Força um dia futuro para garantir que o slot nao seja filtrado por delay.
    future = datetime.now(UTC) + timedelta(days=2)
    dow = future.weekday()
    date_int = int(future.strftime("%Y%m%d"))
    publish_slots = {
        str(dow): {
            "19": {"avg_views": 500, "ctr": 0.08, "retention": 25, "samples": 5},
            "21": {"avg_views": 100, "ctr": 0.02, "retention": 10, "samples": 5},
        }
    }
    (tmp_path / "publish_slots.json").write_text(json.dumps(publish_slots), encoding="utf-8")

    slots = publish_optimizer.best_publish_slots(count=5, min_delay_hours=0)
    data_slots = [s for s in slots if s["source"] == "data"]
    assert data_slots
    # 19h deve ter score maior que 21h
    top = data_slots[0]
    assert top["hour"] == 19
    assert top["date_int"] == date_int


def test_pick_publish_time_prefers_data(tmp_path, monkeypatch):
    monkeypatch.setattr(publish_optimizer, "data_dir", lambda: tmp_path)
    future = datetime.now(UTC) + timedelta(days=2)
    dow = future.weekday()
    publish_slots = {
        str(dow): {
            "19": {"avg_views": 1000, "ctr": 0.1, "retention": 30, "samples": 10},
        }
    }
    (tmp_path / "publish_slots.json").write_text(json.dumps(publish_slots), encoding="utf-8")

    chosen = publish_optimizer.pick_publish_time(count=5, min_delay_hours=0)
    assert chosen["source"] == "data"
    assert chosen["hour"] == 19


def test_pick_publish_time_benchmark_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(publish_optimizer, "data_dir", lambda: tmp_path)
    chosen = publish_optimizer.pick_publish_time(count=5)
    assert chosen["source"] == "benchmark"


def test_iso_datetime_from_slot_converts_to_utc():
    slot = {"date_int": 20250115, "hour": 19}
    iso = publish_optimizer.iso_datetime_from_slot(slot)
    assert iso.endswith("Z")
    # BRT 19h -> UTC 22h
    assert "T22:" in iso


def test_iso_datetime_from_slot_custom_offset():
    slot = {"date_int": 20250115, "hour": 19}
    iso = publish_optimizer.iso_datetime_from_slot(slot, offset_hours=-5)
    assert "T00:" in iso
