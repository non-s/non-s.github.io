from __future__ import annotations

import json

from utils import agency_council


def test_council_records_independent_roles_and_consensus(tmp_path, monkeypatch):
    monkeypatch.setattr(agency_council, "data_dir", lambda: tmp_path)
    monkeypatch.setattr(
        agency_council,
        "ai_grounded_research",
        lambda _prompt: {"text": "Pets and cozy jazz are discussed.", "sources": [{"url": "https://example.test"}]},
    )
    monkeypatch.setattr(
        agency_council,
        "ai_text",
        lambda _prompt, **_kwargs: json.dumps(
            {"observation": "signal", "recommendation": "idea", "risk": "low", "metric": "retention"}
        ),
    )
    brief = agency_council.run_daily_council()
    assert set(brief["roles"]) == {"research", "strategist", "brand_guardian", "growth_lead"}
    assert brief["research"]["web_sources"][0]["url"] == "https://example.test"
    assert brief["research"]["recent_visual_signals"] == []
    assert brief["publication_authority"].startswith("none")
    assert (tmp_path / "agency_daily_brief.json").exists()


def test_council_falls_back_without_model_response(tmp_path, monkeypatch):
    monkeypatch.setattr(agency_council, "data_dir", lambda: tmp_path)
    monkeypatch.setattr(agency_council, "ai_grounded_research", lambda _prompt: {"text": "", "sources": []})
    monkeypatch.setattr(agency_council, "ai_text", lambda _prompt, **_kwargs: "")
    brief = agency_council.run_daily_council()
    assert brief["consensus"]["decision"] == "review before production"
