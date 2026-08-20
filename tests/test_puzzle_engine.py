from __future__ import annotations

from utils.atomic_state import load_versioned
from utils.canon_memory import record_canon_event
from utils.puzzle_engine import PuzzleState, encode_message, prepare_puzzle, validate_puzzle


def test_glyph_encoding_is_reproducible_and_has_checksum():
    assert encode_message("THE WIRE") == encode_message("the wire!")
    codes, checksum = encode_message("THE WIRE")
    assert codes
    assert len(checksum) == 12


def test_only_a_bounded_fraction_of_seeds_receive_puzzles():
    states = [prepare_puzzle(seed, seed + 1, enabled=True) for seed in range(100)]
    enabled = [state for state in states if state.enabled]
    assert 10 <= len(enabled) <= 30
    assert all(state.validated for state in enabled)
    assert all(state.density <= 0.25 for state in enabled)


def test_disabled_video_still_discloses_fictional_language():
    state = prepare_puzzle(1, 1, enabled=False)
    assert state.enabled is False
    assert state.validated is True
    assert "fictional" in state.disclosure.lower()


def test_validation_rejects_historical_misrepresentation_and_unfair_density():
    state = PuzzleState(
        enabled=True,
        validated=False,
        protocol_version=1,
        language_version=1,
        canon_version=1,
        episode=1,
        message_id="msg_bad",
        glyph_codes=(1, 2),
        checksum="123456789012",
        difficulty="deep",
        density=0.9,
        disclosure="historical cuneiform",
        historical_cuneiform=True,
    )
    issues = validate_puzzle(state)
    assert any("historical" in issue for issue in issues)
    assert any("density" in issue for issue in issues)
    assert any("fictional" in issue for issue in issues)


def test_canon_memory_links_puzzle_to_lineage_without_duplicates(tmp_path):
    path = tmp_path / "canon.json"
    metadata = {
        "content_id": "lw_1",
        "generated_at": "2026-01-01T00:00:00+00:00",
        "genome": {
            "parents": ["lw_parent"],
            "puzzle": {
                "enabled": True,
                "episode": 2,
                "message_id": "msg_abc",
                "checksum": "123456789012",
                "difficulty": "layered",
                "canon_version": 1,
            },
        },
    }
    record_canon_event(path, metadata)
    record_canon_event(path, metadata)
    canon = load_versioned(path, 1, {}, {})
    assert len(canon["events"]) == 1
    assert canon["events"][0]["parents"] == ["lw_parent"]
