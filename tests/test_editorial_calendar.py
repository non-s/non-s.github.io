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
