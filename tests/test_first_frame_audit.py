from utils.first_frame_audit import audit_opening_frames, check_cover_text_budget


def test_opening_audit_rewards_motion_and_short_cover_text(monkeypatch):
    monkeypatch.setenv("OPENING_AUDIT_STRICT", "1")

    audit = audit_opening_frames(
        {"thumbnail_text": "WATCH COLOR", "has_broll": True, "opening_contrast": 85},
        frames=[{"time": 0.5, "motion_score": 88}],
    )

    assert audit["approved"] is True
    assert audit["score"] >= 80


def test_opening_audit_rejects_weak_static_opening_when_strict(monkeypatch):
    monkeypatch.setenv("OPENING_AUDIT_STRICT", "1")

    audit = audit_opening_frames({"thumbnail_text": "THIS IS FAR TOO MANY WORDS FOR COVER TEXT"})

    assert audit["approved"] is False
    assert "cover_text_too_long" in audit["reasons"]


def test_cover_text_budget_prefers_two_to_four_words():
    assert check_cover_text_budget("WATCH THE WING")["score"] == 100
