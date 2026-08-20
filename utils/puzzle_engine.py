"""Fictional Liquid Wire glyph protocol embedded as subtle geometry modulation.

This is explicitly not a historical cuneiform transliteration.  Its wedge-like
marks are an original fictional code and metadata always carries that label.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import asdict, dataclass
from typing import Any

PUZZLE_PROTOCOL_VERSION = 2
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
    render_validation: dict[str, Any] | None = None

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


def calibrate_difficulty(episode: int, observations: list[dict[str, Any]] | None = None) -> str:
    """Follow a humane discovery curve and move at most one level with evidence."""
    levels = ("discoverable", "layered", "deep")
    baseline = "discoverable" if episode <= 5 else "layered" if episode <= 15 else "deep"
    comparable: list[float] = []
    for item in observations or []:
        puzzle = item.get("puzzle") if isinstance(item, dict) else None
        windows = item.get("performance_windows") if isinstance(item, dict) else None
        if not isinstance(puzzle, dict) or not puzzle.get("enabled") or not isinstance(windows, dict):
            continue
        metrics = next(
            (windows[name] for name in ("mature", "72h", "24h") if isinstance(windows.get(name), dict)),
            None,
        )
        if isinstance(metrics, dict) and isinstance(metrics.get("average_percentage_viewed"), (int, float)):
            comparable.append(float(metrics["average_percentage_viewed"]))
    if len(comparable) < 8:
        return baseline
    index = levels.index(baseline)
    mean_retention = sum(comparable[-20:]) / min(20, len(comparable))
    if mean_retention < 55:
        index = max(0, index - 1)
    elif mean_retention > 95:
        index = min(len(levels) - 1, index + 1)
    return levels[index]


def prepare_puzzle(
    seed: int,
    episode: int,
    *,
    enabled: bool | None = None,
    observations: list[dict[str, Any]] | None = None,
) -> PuzzleState:
    configured = os.environ.get("LIQUID_WIRE_PUZZLES_ENABLED", "1") == "1" if enabled is None else enabled
    # At most one in five works carries a puzzle. Identity is consistent,
    # while ordinary videos preserve a humane discovery curve.
    selected = configured and int(hashlib.sha256(f"puzzle:{seed}".encode()).hexdigest(), 16) % 5 == 0
    if not selected:
        return PuzzleState(
            False, True, PUZZLE_PROTOCOL_VERSION, GLYPH_LANGUAGE_VERSION, CANON_VERSION,
            None, None, (), None, "discoverable", 0.0,
            "No puzzle in this work; Liquid Wire glyphs are a fictional visual language.",
            render_validation={"status": "not_applicable", "passed": True},
        )
    message = _CANON_MESSAGES[(episode - 1) % len(_CANON_MESSAGES)]
    codes, checksum = encode_message(message)
    difficulty = calibrate_difficulty(episode, observations)
    density = {"discoverable": 0.08, "layered": 0.12, "deep": 0.16}[difficulty]
    state = PuzzleState(
        True, False, PUZZLE_PROTOCOL_VERSION, GLYPH_LANGUAGE_VERSION, CANON_VERSION,
        episode, f"msg_{checksum}", codes, checksum, difficulty, density,
        "Original fictional wedge-inspired Liquid Wire glyph language; not historical cuneiform.",
        render_validation={"status": "pending_final_render", "passed": False},
    )
    issues = validate_puzzle(state)
    return PuzzleState(**{**state.to_dict(), "validated": not issues})


def validate_puzzle_carrier(
    puzzle: dict[str, Any], visual_dna: dict[str, Any], quality: dict[str, Any]
) -> dict[str, Any]:
    """Verify that the encoded MP4 retained a usable geometric carrier.

    This does not claim to OCR the secret. It verifies the final compressed
    artifact—not source parameters—has enough decoded samples, edges and
    contrast for the bounded modulation to remain perceptible.
    """
    if not puzzle.get("enabled"):
        return {"status": "not_applicable", "passed": True, "issues": []}
    issues: list[str] = []
    if not quality.get("passed"):
        issues.append("final quality gate failed")
    if int(visual_dna.get("sample_count") or 0) < 3:
        issues.append("insufficient final-render samples")
    edge_density = visual_dna.get("composition", {}).get("edge_density")
    contrast = visual_dna.get("appearance", {}).get("contrast")
    if not isinstance(edge_density, (int, float)) or edge_density < 0.001:
        issues.append("encoded geometric carrier has insufficient edge density")
    if not isinstance(contrast, (int, float)) or contrast < 0.02:
        issues.append("encoded geometric carrier has insufficient contrast")
    return {
        "status": "passed" if not issues else "failed",
        "passed": not issues,
        "issues": issues,
        "edge_density": edge_density,
        "contrast": contrast,
        "sample_count": visual_dna.get("sample_count"),
    }
