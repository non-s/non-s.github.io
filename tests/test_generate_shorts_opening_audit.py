from utils.first_frame_audit import audit_opening_frames


def test_generate_opening_audit_contract_for_metadata(monkeypatch):
    monkeypatch.setenv("OPENING_AUDIT_STRICT", "1")

    audit = audit_opening_frames({"title": "Sharks sense fields", "thumbnail_text": "SHARK SENSE", "has_broll": True})

    assert audit["enabled"] is True
    assert "checks" in audit
    assert audit["approved"] is True
