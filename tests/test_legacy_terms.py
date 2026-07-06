"""Tests for the shared legacy-term blocklist and scrubber."""

from __future__ import annotations

import json

from utils import rejected_queue
from utils.legacy_terms import BLOCKED_TERMS, matches_blocked_term, scrub_legacy_terms

_AGENCY = "na" + "sa"


def test_scrub_replaces_agency_term_with_neutral_words():
    cleaned = scrub_legacy_terms(f"that's why {_AGENCY}'s probes dive into flares")
    assert not matches_blocked_term(cleaned.lower(), _AGENCY)
    assert "space agency" in cleaned


def test_scrub_keeps_innocent_words_intact():
    text = "the lionfish casano hides near coral"
    assert scrub_legacy_terms(text) == text


def test_scrub_removes_platform_terms():
    term = "tik" + "tok"
    cleaned = scrub_legacy_terms(f"posted on {term} yesterday")
    assert term not in cleaned.lower()


def test_blocked_terms_never_appear_in_module_source():
    from pathlib import Path

    import utils.legacy_terms as module

    source = Path(module.__file__).read_text(encoding="utf-8").lower()
    for term in BLOCKED_TERMS:
        assert not matches_blocked_term(source, term)


def test_record_rejection_scrubs_legacy_terms(tmp_path):
    path = tmp_path / "rejected.jsonl"
    story = {
        "id": "story-1",
        "title": f"{_AGENCY} probes explained",
        "script": f"watch how {_AGENCY}'s probes dive into the sun",
    }
    rejected_queue.record_rejection(story, ["off_topic_visual"], path=path, stage="queue_prune")
    row = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    payload = json.dumps(row).lower()
    assert not matches_blocked_term(payload, _AGENCY)
