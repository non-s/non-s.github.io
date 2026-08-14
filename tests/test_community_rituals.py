from datetime import date

from utils.community_rituals import ritual_for_date


def test_weekly_rituals_are_stable_and_participatory():
    monday = ritual_for_date(date(2026, 8, 10))
    sunday = ritual_for_date(date(2026, 8, 16))
    assert monday["id"] == "reset-monday"
    assert sunday["id"] == "nest-session-sunday"
    assert monday["community_prompt"]
