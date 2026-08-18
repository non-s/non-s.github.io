from datetime import date

from utils.editorial_calendar import build_calendar


def test_calendar_has_one_short_per_day_and_two_weekly_long_form_slots():
    items = build_calendar(date(2026, 8, 10), days=7)
    shorts = [item for item in items if item["format"] == "short"]
    long_form = [item for item in items if item["format"] == "long"]
    assert len(shorts) == 7
    assert len(long_form) == 2
    assert {item["date"] for item in long_form} == {"2026-08-11", "2026-08-16"}
    assert shorts[0]["ritual"] == "reset-monday"
    assert shorts[2]["ritual"] == "midweek-pause-wednesday"


def test_calendar_is_empty_for_invalid_zero_day_request():
    assert build_calendar(date(2026, 8, 10), days=0) == []


def test_calendar_dates_are_consecutive():
    start = date(2026, 8, 10)
    items = build_calendar(start, days=5)
    expected = ["2026-08-10", "2026-08-11", "2026-08-12", "2026-08-13", "2026-08-14"]
    assert [item["date"] for item in items if item["format"] == "short"] == expected


def test_calendar_long_form_on_tuesday_and_sunday():
    """Long-form slots are always on Tuesday and Sunday."""
    start = date(2026, 1, 5)  # Monday
    items = build_calendar(start, days=14)
    long_form_days = {item["date"] for item in items if item["format"] == "long"}
    for day_str in long_form_days:
        d = date.fromisoformat(day_str)
        assert d.weekday() in (1, 6), f"Long-form on {day_str} ({d.strftime('%A')}) is not Tue/Sun"


def test_calendar_30_days_has_30_shorts():
    items = build_calendar(date(2026, 8, 10), days=30)
    shorts = [item for item in items if item["format"] == "short"]
    assert len(shorts) == 30
