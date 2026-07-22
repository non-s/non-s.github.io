"""
utils/host_persona.py — Single source of truth for the channel's host identity.

Why this exists
---------------
Automated channels that monetize all share one trait: a recognizable
identity. A consistent voice and recurring catchphrases give the impression
that "this channel has a person behind it" — which is the signal YouTube
viewers and discovery reward.

The persona is read by content generators and community-engagement scripts
when an operator wants to inject a host voice into titles, descriptions,
comments or community posts.

Operator override
-----------------
Drop `_data/host_persona.json` to override the defaults. The shipped
defaults are tuned for Amber Hours, a calming ambience channel.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

PERSONA_FILE = Path(os.environ.get("HOST_PERSONA_FILE", "_data/host_persona.json"))


@dataclass
class HostPersona:
    """A channel's host identity. Every field is optional with a
    sensible default — the operator can override piecewise."""

    # Channel identity. The narrator stays invisible: viewers should
    # subscribe to Amber Hours, never feel sent toward a third party.
    name: str = "Amber Hours"

    # The persistent character / point of view the LLM should adopt
    # when writing in first person. Goes verbatim into the system prompt.
    pov: str = (
        "You are the calm, friendly voice of Amber Hours, a channel that "
        "publishes rain, thunder and soothing ambience to help people sleep, "
        "focus and relax. Write warmly and directly, as if speaking to a "
        "friend who needs to unwind. Keep claims humble, avoid hype, and "
        "never promise medical outcomes. NEVER write in third person "
        "('this channel', 'we cover'). NEVER mention a host name, promote a "
        "third party, or drift away from the featured soundscape. NEVER refer "
        "to yourself as an AI, bot, or assistant."
    )

    # Recurring opening line spoken at the very start of every video.
    intro_line: str = ""

    # Closing sign-off — kept short so long-form ambience doesn't lose time
    # to outro chatter.
    outro_line: str = "Rest well with Amber Hours."

    # Signature catchphrases the AI should weave in occasionally.
    # NOT every video — overused they grate.
    catchphrases: list[str] = field(
        default_factory=lambda: [
            "Here's a moment of calm:",
            "Settle in:",
            "Breathe with this one:",
            "Let the sound carry you:",
        ]
    )

    # Pinned-first-comment template. `{name}` interpolates the channel name.
    first_comment_template: str = (
        "New here? Subscribe to {name} for rain, thunder and calming sounds.\n\n"
        "What should we publish next? Drop your idea below."
    )

    # Channel handle (without the @). Used in CTAs and watermarks.
    handle: str = "amberhours"

    # Channel tagline — appears in long-form description, never in Shorts.
    tagline: str = "Rain, thunder and calm sounds for sleep and focus."


_DEFAULT = HostPersona()


def load() -> HostPersona:
    """Return the persona, merging the on-disk override into defaults.

    Missing fields in the JSON file keep the default value, so an
    operator can override just `name` without rewriting the whole
    persona dict.
    """
    if not PERSONA_FILE.exists():
        return _DEFAULT
    try:
        data = json.loads(PERSONA_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return _DEFAULT
    except Exception as exc:
        log.warning("host_persona: %s parse failed: %s", PERSONA_FILE, exc)
        return _DEFAULT

    fields = {f: getattr(_DEFAULT, f) for f in _DEFAULT.__dataclass_fields__}
    for k, v in data.items():
        if k not in fields:
            continue
        # List fields keep the default if the override isn't a list.
        if isinstance(fields[k], list) and not isinstance(v, list):
            continue
        fields[k] = v
    return HostPersona(**fields)


def save(persona: HostPersona, path: Path | None = None) -> None:
    """Write the persona to disk in the canonical JSON shape."""
    target = path or PERSONA_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(asdict(persona), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def system_prompt_overlay(persona: HostPersona | None = None) -> str:
    """Build the text we PREPEND to ai_helper.py's system prompt."""
    persona = persona or load()
    parts = [persona.pov]
    if persona.catchphrases:
        catch = "; ".join(f'"{p}"' for p in persona.catchphrases[:3])
        parts.append(f"Use one of these signature openers occasionally (not every " f"video — feels canned): {catch}")
    return " ".join(parts)


def first_comment_text(persona: HostPersona | None = None) -> str:
    """Render the pinned first-comment text."""
    persona = persona or load()
    return (
        f"New here? Subscribe to {persona.name} for rain, thunder and calming sounds.\n\n"
        "What should we publish next? Drop your idea below."
    )
