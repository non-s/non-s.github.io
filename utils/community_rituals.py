"""Recurring, voluntary community rituals for the single Pata Jazz channel."""

from __future__ import annotations

from datetime import date

_RITUALS = (
    {
        "id": "reset-room-monday",
        "name": "Reset Room Monday",
        "viewer_intent": "a gentle reset for the week",
        "community_prompt": "What small ritual would make this week feel lighter?",
    },
    {
        "id": "tiny-ritual-tuesday",
        "name": "Tiny Ritual Tuesday",
        "viewer_intent": "noticing the small habits that make home feel familiar",
        "community_prompt": "Tell us one tiny ritual your pet never skips.",
    },
    {
        "id": "rainy-window-wednesday",
        "name": "Rainy Window Wednesday",
        "viewer_intent": "a quiet midweek pause",
        "community_prompt": "Choose the next window mood: SUN, RAIN, or NIGHT.",
    },
    {
        "id": "companion-thursday",
        "name": "Companion Thursday",
        "viewer_intent": "gentle company while studying, reading or resting",
        "community_prompt": "What are you keeping company with today?",
    },
    {
        "id": "golden-hour-friday",
        "name": "Golden Hour Friday",
        "viewer_intent": "a warm transition into the weekend",
        "community_prompt": "Comment CAT or DOG to help choose a future Golden Hour session.",
    },
    {
        "id": "slow-saturday",
        "name": "Slow Saturday",
        "viewer_intent": "a slower, playful weekend moment",
        "community_prompt": "What would your ideal slow Saturday sound like?",
    },
    {
        "id": "nest-session-sunday",
        "name": "Nest Session Sunday",
        "viewer_intent": "a calm landing before a new week",
        "community_prompt": "What feeling should next Sunday's nest have?",
    },
)


def ritual_for_date(day: date) -> dict[str, str]:
    """Return the stable weekly ritual for a given calendar day."""
    return dict(_RITUALS[day.weekday()])
