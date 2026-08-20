"""Fictional Liquid Wire glyph protocol embedded as subtle geometry modulation.

This is explicitly not a historical cuneiform transliteration.  Its wedge-like
marks are an original fictional code and metadata always carries that label.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import asdict, dataclass
from typing import Any

PUZZLE_PROTOCOL_VERSION = 1
GLYPH_LANGUAGE_VERSION = 1
CANON_VERSION = 1
_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
_CANON_MESSAGES = (
    "THE WIRE REMEMBERS",
    "MOTION LEAVES A TRACE",
    "THE VOID IS LISTENING",
    "FORM FOLLOWS MEMORY",
    "EVERY RETURN CHANGES US",
)


@dataclass(frozen=True)
class PuzzleState:
    enabled: bool
    validated: bool
    protocol_version: int
    language_version: int
    canon_version: int
    episode: int | None
    message_id: str | None
    glyph_codes: tuple[int, ...]
    checksum: str | None
    difficulty: str
    density: float
    disclosure: str
    historical_cuneiform: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def encode_message(message: str) -> tuple[tuple[int, ...], str]:
    normalized = "".join(character for character in message.upper() if character in _ALPHABET)
    if not normalized:
        raise ValueError("puzzle message has no encodable glyphs")
    codes = tuple(_ALPHABET.index(character) for character in normalized)
    checksum = hashlib.sha256(normalized.encode()).hexdigest()[:12]
    return codes, checksum


def validate_puzzle(state: PuzzleState) -> list[str]:
    issues: list[str] = []
    if not state.enabled:
        return issues
    if state.historical_cuneiform:
        issues.append("fictional glyph protocol must not claim historical cuneiform")
    if not state.glyph_codes or any(code < 0 or code >= len(_ALPHABET) for code in state.glyph_codes):
        issues.append("glyph code outside the versioned alphabet")
    if not state.checksum or len(state.checksum) != 12:
        issues.append("missing or invalid message checksum")
    if not 0.01 <= state.density <= 0.25:
        issues.append("puzzle density outside fair perceptual limits")
    if state.difficulty not in {"discoverable", "layered", "deep"}:
        issues.append("unsupported puzzle difficulty")
    if "fictional" not in state.disclosure.lower():
        issues.append("glyph disclosure must state that the language is fictional")
    return issues


def prepare_puzzle(seed: int, episode: int, *, enabled: bool | None = None) -> PuzzleState:
    configured = os.environ.get("LIQUID_WIRE_PUZZLES_ENABLED", "1") == "1" if enabled is None else enabled
    # At most one in five works carries a puzzle. Identity is consistent,
    # while ordinary videos preserve a humane discovery curve.
    selected = configured and int(hashlib.sha256(f"puzzle:{seed}".encode()).hexdigest(), 16) % 5 == 0
    if not selected:
        return PuzzleState(
            False, True, PUZZLE_PROTOCOL_VERSION, GLYPH_LANGUAGE_VERSION, CANON_VERSION,
            None, None, (), None, "discoverable", 0.0,
            "No puzzle in this work; Liquid Wire glyphs are a fictional visual language.",
        )
    message = _CANON_MESSAGES[(episode - 1) % len(_CANON_MESSAGES)]
    codes, checksum = encode_message(message)
    difficulty = ("discoverable", "layered", "deep")[(episode - 1) % 3]
    density = {"discoverable": 0.08, "layered": 0.12, "deep": 0.16}[difficulty]
    state = PuzzleState(
        True, False, PUZZLE_PROTOCOL_VERSION, GLYPH_LANGUAGE_VERSION, CANON_VERSION,
        episode, f"msg_{checksum}", codes, checksum, difficulty, density,
        "Original fictional wedge-inspired Liquid Wire glyph language; not historical cuneiform.",
    )
    issues = validate_puzzle(state)
    return PuzzleState(**{**state.to_dict(), "validated": not issues})
