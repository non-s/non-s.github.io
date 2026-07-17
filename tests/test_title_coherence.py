import utils.title_coherence as title_coherence
from utils.title_coherence import evaluate_title_coherence


def test_empty_title_is_skipped_without_calling_ai(monkeypatch):
    monkeypatch.setattr(
        title_coherence, "ai_text", lambda *a, **k: (_ for _ in ()).throw(AssertionError("ai called"))
    )

    result = evaluate_title_coherence("  ")

    assert result == {"checked": False, "natural": None, "reason": "empty_title", "state": "skipped"}


def test_ai_unavailable_fails_open_as_skipped(monkeypatch):
    monkeypatch.setattr(title_coherence, "ai_text", lambda *a, **k: "")

    result = evaluate_title_coherence("Wolves leave scent notes for the pack")

    assert result["state"] == "skipped"
    assert result["reason"] == "ai_unavailable"


def test_yes_verdict_is_approved(monkeypatch):
    monkeypatch.setattr(title_coherence, "ai_text", lambda *a, **k: "YES - reads naturally")

    result = evaluate_title_coherence("Wolves leave scent notes for the pack")

    assert result == {
        "checked": True,
        "natural": True,
        "reason": "reads naturally",
        "state": "approved",
    }


def test_no_verdict_holds_by_default(monkeypatch):
    monkeypatch.delenv("TITLE_COHERENCE_MODE", raising=False)
    monkeypatch.setattr(
        title_coherence, "ai_text", lambda *a, **k: "NO - subject and verb do not agree"
    )

    result = evaluate_title_coherence("Cows use herd memory before they remember")

    assert result["checked"] is True
    assert result["natural"] is False
    assert result["state"] == "held"
    assert result["reason"] == "subject and verb do not agree"


def test_no_verdict_only_warns_when_mode_is_warn(monkeypatch):
    monkeypatch.setenv("TITLE_COHERENCE_MODE", "warn")
    monkeypatch.setattr(title_coherence, "ai_text", lambda *a, **k: "NO - vague")

    result = evaluate_title_coherence("Crystals use crystal edge before they lock")

    assert result["state"] == "warn"


def test_unparseable_reply_fails_open_as_warn(monkeypatch):
    monkeypatch.setattr(title_coherence, "ai_text", lambda *a, **k: "Sure, happy to help!")

    result = evaluate_title_coherence("Sharks signal through electric sense")

    assert result["checked"] is True
    assert result["natural"] is None
    assert result["state"] == "warn"
    assert result["reason"].startswith("unparseable_response:")
