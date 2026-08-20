from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRACE = ROOT / "config" / "master_mandate_traceability.json"


def _artifact_hash(relative: str) -> str:
    path = ROOT / relative
    digest = hashlib.sha256()
    if path.is_file():
        digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
    else:
        for item in sorted(entry for entry in path.rglob("*.py") if "__pycache__" not in entry.parts):
            digest.update(item.relative_to(path).as_posix().encode())
            digest.update(item.read_bytes().replace(b"\r\n", b"\n"))
    return digest.hexdigest()


def test_every_numbered_mandate_section_is_traced_with_existing_evidence():
    payload = json.loads(TRACE.read_text(encoding="utf-8"))
    sections = payload["sections"]
    assert payload["section_count"] == 178
    assert payload["subrequirement_count"] == 658
    assert [row["section"] for row in sections] == list(range(178))
    allowed = set(payload["allowed_statuses"])
    assert payload["evidence_manifest"]
    for relative, expected_hash in payload["evidence_manifest"].items():
        assert _artifact_hash(relative) == expected_hash, f"stale evidence hash: {relative}"
    for row in sections:
        assert row["status"] in allowed
        assert len(row["body_sha256"]) == 64
        assert row["evidence"]
        for relative in row["evidence"]:
            assert (ROOT / relative).exists(), f"section {row['section']} has missing evidence: {relative}"
        assert len(row["requirements"]) == row["bullet_count"]
        for position, requirement in enumerate(row["requirements"], start=1):
            assert requirement["requirement_id"] == f"{row['section']}.b{position:03d}"
            assert requirement["text"]
            assert requirement["status"] == row["status"]
            assert requirement["evidence"] == row["evidence"]


def test_traceability_has_no_unresolved_implementation_status():
    payload = json.loads(TRACE.read_text(encoding="utf-8"))
    forbidden = {"missing", "partial", "todo", "unknown"}
    assert not forbidden.intersection(row["status"] for row in payload["sections"])


def test_only_declared_external_outcomes_wait_for_real_data():
    payload = json.loads(TRACE.read_text(encoding="utf-8"))
    pending = [
        row["section"]
        for row in payload["sections"]
        if row["status"] == "ready_pending_real_data"
    ]
    assert pending == [13, 44, 55, 116, 119, 121, 132, 138, 147, 148]
