"""
utils/host_persona.py — Single source of truth for the channel's host identity.

Why this exists
---------------
Automated channels that monetize all share one trait: a recognizable
identity. Six rotating voices reading stock footage = AI slop. ONE host
with a name, a pair of recurring catchphrases, and consistent POV =
"this channel has a person behind it" — which is exactly the signal
TikTok's classifier and viewers both reward.

The persona is read by:
  * `fetch_animals.py` → injected into the AI prompt so every script
    sounds like the SAME person wrote it
  * `generate_shorts.py` → drives voice selection + sign-off line
  * `utils/comment_replies.py` → reply panel in first-person voice

Operator override
-----------------
Drop `_data/host_persona.json` to override the defaults. The shipped
defaults are tuned for Wild Brief, a daily animal-facts Shorts channel.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

PERSONA_FILE = Path(os.environ.get("HOST_PERSONA_FILE",
                                     "_data/host_persona.json"))


@dataclass
class HostPersona:
    """A channel's host identity. Every field is optional with a
    sensible default — the operator can override piecewise."""

    # Display name. Used in the AI prompt to anchor first-person voice
    # and in sign-offs ("I'm Alex, see you tomorrow"). Keep it short;
    # something that fits "I'm <name>." in 1 second of TTS.
    name: str = "Alex"

    # The persistent character / point of view the LLM should adopt
    # when writing the voice-over. Goes verbatim into the system prompt.
    # Stronger framing here = more consistent voice across stories.
    pov: str = (
        "You are Alex, the single recurring host of Wild Brief — a "
        "daily Shorts channel about animals. Write every script in "
        "FIRST PERSON ('I love this one', 'here's what blew my mind') "
        "as if you, Alex, are speaking directly to a friend who follows "
        "the channel daily. Build on the channel's running tone: "
        "curious, warm, surprising, anti-clickbait, the angle nobody "
        "tells you. NEVER write in third person ('this channel', 'we "
        "cover'). NEVER refer to yourself as an AI, bot, or "
        "assistant — Alex is a person."
    )

    # Recurring opening line spoken at the very start of every Short.
    # Pre-rendered to MP3 once per voice (see utils.intro_outro) and
    # concatenated to every render. Kept short (≤ 1 s of audio) so
    # the hook lands before the TikTok For You feed swipe-away window
    # (~2 s) — a 2-second intro burns half that budget on branding.
    intro_line: str = "Brief."

    # Closing sign-off — kept to ~1 second so a 30 s Short doesn't lose
    # 7% of its airtime to outro chatter. Punchy is the goal.
    outro_line: str = "Follow Alex."

    # Signature catchphrases the AI should weave in occasionally.
    # NOT every Short — overused they grate. Mention in the prompt
    # so the LLM uses them sparingly.
    catchphrases: list[str] = field(default_factory=lambda: [
        "Here's the part nobody tells you:",
        "My favourite part:",
        "Watch this one twice:",
    ])

    # Pinned-first-comment template. `{handle}` interpolates the
    # channel handle from the upload metadata.
    first_comment_template: str = (
        "👋 I'm {name}. New here? Stick around — one weird animal "
        "fact every morning, lunch, and evening UTC.\n\n"
        "Which animal should I cover next? Drop it below 👇"
    )

    # Channel handle (without the @). Used in CTAs and watermarks.
    handle: str = "wildbrief_x"

    # Channel tagline — appears in long-form description, never in Shorts.
    tagline: str = "One weird animal fact a day. Wild Brief."


# ── Loader / saver ────────────────────────────────────────────────

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


# ── Prompt injection helpers ─────────────────────────────────────

def system_prompt_overlay(persona: HostPersona | None = None) -> str:
    """Build the text we PREPEND to ai_helper.py's system prompt.

    fetch_animals.py uses this so every story's script is generated AS
    the host, not as an anonymous narrator.
    """
    persona = persona or load()
    parts = [persona.pov]
    if persona.catchphrases:
        catch = "; ".join(f'"{p}"' for p in persona.catchphrases[:3])
        parts.append(
            f"Use one of these signature openers occasionally (not every "
            f"Short — feels canned): {catch}"
        )
    return " ".join(parts)


def first_comment_text(persona: HostPersona | None = None) -> str:
    """Render the pinned first-comment text."""
    persona = persona or load()
    return persona.first_comment_template.format(
        name=persona.name,
        handle=persona.handle,
    )
