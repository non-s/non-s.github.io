from __future__ import annotations

import json

from utils.ai_research_advisor import ADVISOR_PROMPT_VERSION, _prompt, advise, build_context
from utils.atomic_state import save_versioned


def _report(samples=8):
    return {
        "generated_at": "2026-01-01T00:00:00+00:00",
        "eligible_creations": samples,
        "family_statistics": {"orb": {"samples": samples}},
        "correlations": [],
    }


def test_advisor_falls_back_without_data_or_key(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    result = advise(tmp_path, _report())
    assert result["status"] == "deterministic_fallback"
    assert result["prompt_version"] == ADVISOR_PROMPT_VERSION


def test_context_is_bounded_and_includes_experiments_and_canon(tmp_path):
    save_versioned(tmp_path / "research_ledger.json", {"hypotheses": {}, "experiments": {"x": {"id": "x"}}}, 1)
    save_versioned(tmp_path / "canon_state.json", {"events": [{"content_id": "lw_1"}]}, 1)
    context = build_context(tmp_path, _report())
    assert context["recent_experiments"] == [{"id": "x"}]
    assert context["canon"] == [{"content_id": "lw_1"}]
    assert "GEMINI_API_KEY" not in json.dumps(context)


def test_prompt_contract_is_versioned_noncausal_and_single_variable():
    prompt = _prompt({"prompt_version": 1})
    assert f"prompt v{ADVISOR_PROMPT_VERSION}" in prompt
    assert "non-causal" in prompt
    assert "exactly one allowed independent variable" in prompt


def test_advisor_rejects_invalid_items_and_caches_valid_result(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    response = {
        "hypotheses": [
            {
                "statement": "Opening may help",
                "independent_variable": "visual_dna.temporal.opening_activity",
                "dependent_metric": "fitness.score",
                "expected_direction": "increase",
                "rationale": "Controlled replication is needed",
            },
            {
                "statement": "Invalid",
                "independent_variable": "publish_every_minute",
                "dependent_metric": "fitness.score",
                "expected_direction": "increase",
                "rationale": "spam",
            },
        ]
    }
    monkeypatch.setattr("utils.ai_research_advisor.ai_text", lambda *args, **kwargs: json.dumps(response))
    first = advise(tmp_path, _report())
    second = advise(tmp_path, _report())
    assert first["status"] == "validated"
    assert len(first["hypothesis_ids"]) == 1
    assert second["cache_hit"] is True
