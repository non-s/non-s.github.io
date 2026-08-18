from datetime import date

from utils.community_rituals import ritual_for_date


def test_weekly_rituals_are_stable_and_participatory():
    monday = ritual_for_date(date(2026, 8, 10))
    sunday = ritual_for_date(date(2026, 8, 16))
    assert monday["id"] == "reset-monday"
    assert sunday["id"] == "nest-session-sunday"
    assert monday["community_prompt"]


def test_all_days_have_rituals():
    """Every day of the week must map to a ritual with id/name/prompt."""
    seen_ids: set[str] = set()
    for offset in range(7):
        day = date(2026, 8, 10) + __import__("datetime").timedelta(days=offset)
        ritual = ritual_for_date(day)
        assert ritual["id"]
        assert ritual["name"]
        assert ritual["viewer_intent"]
        assert ritual["community_prompt"]
        seen_ids.add(ritual["id"])
    assert len(seen_ids) == 7


def test_ritual_is_deterministic_for_same_weekday():
    """Same weekday always returns the same ritual."""
    d1 = date(2026, 1, 5)  # Monday
    d2 = date(2026, 8, 10)  # Monday
    assert ritual_for_date(d1) == ritual_for_date(d2)
