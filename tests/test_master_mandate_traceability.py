from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRACE = ROOT / "config" / "master_mandate_traceability.json"


def test_every_numbered_mandate_section_is_traced_with_existing_evidence():
    payload = json.loads(TRACE.read_text(encoding="utf-8"))
    sections = payload["sections"]
    assert payload["section_count"] == 178
    assert [row["section"] for row in sections] == list(range(178))
    allowed = set(payload["allowed_statuses"])
    for row in sections:
        assert row["status"] in allowed
        assert len(row["body_sha256"]) == 64
        assert row["evidence"]
        for relative in row["evidence"]:
            assert (ROOT / relative).exists(), f"section {row['section']} has missing evidence: {relative}"


def test_traceability_has_no_unresolved_implementation_status():
    payload = json.loads(TRACE.read_text(encoding="utf-8"))
    forbidden = {"missing", "partial", "todo", "unknown"}
    assert not forbidden.intersection(row["status"] for row in payload["sections"])
