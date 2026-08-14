"""Recurring, voluntary community rituals for the Liquid Wire channel."""

from __future__ import annotations

from datetime import date

_RITUALS = (
    {
        "id": "reset-monday",
        "name": "Reset Monday",
        "viewer_intent": "a gentle visual reset for the week",
        "community_prompt": "What small visual would make this week feel lighter?",
    },
    {
        "id": "tiny-ritual-tuesday",
        "name": "Tiny Ritual Tuesday",
        "viewer_intent": "noticing the small generative details that make each piece unique",
        "community_prompt": "Tell us one tiny visual detail you noticed in today's piece.",
    },
    {
        "id": "midweek-pause-wednesday",
        "name": "Midweek Pause Wednesday",
        "viewer_intent": "a quiet midweek ambient break",
        "community_prompt": "Choose the next ambient mood: FLOW, WIRE, or NIGHT.",
    },
    {
        "id": "focus-thursday",
        "name": "Focus Thursday",
        "viewer_intent": "gentle company while studying, reading or working",
        "community_prompt": "What are you focusing on today?",
    },
    {
        "id": "golden-hour-friday",
        "name": "Golden Hour Friday",
        "name_alt": "Glow Friday",
        "viewer_intent": "a warm transition into the weekend with brighter visuals",
        "community_prompt": "Comment GEOMETRIC or ORGANIC to help choose a future Friday piece.",
    },
    {
        "id": "slow-saturday",
        "name": "Slow Saturday",
        "viewer_intent": "a slower, deeper generative drift",
        "community_prompt": "What would your ideal slow Saturday visual feel like?",
    },
    {
        "id": "nest-session-sunday",
        "name": "Nest Session Sunday",
        "viewer_intent": "a calm ambient landing before a new week",
        "community_prompt": "What feeling should next Sunday's ambient piece have?",
    },
)


def ritual_for_date(day: date) -> dict[str, str]:
    """Return the stable weekly ritual for a given calendar day."""
    return dict(_RITUALS[day.weekday()])
