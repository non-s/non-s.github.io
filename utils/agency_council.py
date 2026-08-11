"""A small, auditable multi-role editorial council for daily planning."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from utils.ai_helper import ai_grounded_research, ai_text
from utils.paths import data_dir
from utils.state_lock import state_lock

_ROLES = {
    "research": "Identify only verifiable audience and format signals; cite uncertainty.",
    "strategist": "Turn signals into one differentiated, original Pata Jazz series hypothesis.",
    "brand_guardian": "Reject repetitive, copied, unsafe, unsupported, or off-brand ideas.",
    "growth_lead": "Define a measured Short-to-long funnel experiment that favors return viewing.",
}


def _brief_file() -> Path:
    return data_dir() / "agency_daily_brief.json"


def _memory_file() -> Path:
    return data_dir() / "agency_memory.json"


def _load_trending() -> list[str]:
    try:
        data = json.loads((data_dir() / "trending_keywords.json").read_text(encoding="utf-8"))
        return [str(value) for value in data.get("keywords", [])[:20]] if isinstance(data, dict) else []
    except (OSError, json.JSONDecodeError):
        return []


def _load_recent_visual_signals() -> list[dict]:
    """Load a compact visual history from uploaded video metadata."""
    try:
        data = json.loads((data_dir() / "video_tags.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, dict):
        return []
    signals: list[dict] = []
    for video_id, entry in list(data.items())[-12:]:
        if not isinstance(entry, dict):
            continue
        visual = entry.get("visual_intelligence")
        if isinstance(visual, dict):
            signals.append({"video_id": video_id, "visual": visual})
    return signals


def _load_competitive_patterns() -> list[dict]:
    """Load public benchmark metadata collected by the separate research step."""
    try:
        data = json.loads((data_dir() / "competitive_intelligence.json").read_text(encoding="utf-8"))
        return data.get("channels", [])[:8] if isinstance(data, dict) else []
    except (OSError, json.JSONDecodeError):
        return []


def _json_object(text: str) -> dict:
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def run_daily_council() -> dict:
    """Run research, independent roles, and a moderated consensus brief."""
    keywords = _load_trending()
    visual_history = _load_recent_visual_signals()
    competitive_patterns = _load_competitive_patterns()
    research = ai_grounded_research(
        "Research current YouTube audience interests around cozy cat or dog videos and instrumental jazz. "
        "Return concise factual signals, not medical claims and not claims about recommendation algorithms."
    )
    context = json.dumps(
        {
            "youtube_keywords": keywords,
            "web_research": research.get("text", "")[:5000],
            "recent_visual_signals": visual_history,
            "competitive_patterns": competitive_patterns,
        }
    )
    opinions: dict[str, dict] = {}
    for role, instruction in _ROLES.items():
        answer = ai_text(
            f"You are the {role} in a content agency. {instruction}\n"
            f"Use this research context: {context}\n"
            "Return JSON with: observation, recommendation, risk, metric.",
            json_mode=True,
            task=f"agency_{role}",
        )
        opinions[role] = _json_object(answer) or {
            "observation": "No model response; use the existing editorial calendar.",
            "recommendation": "Keep the next asset distinct from recent scenes and titles.",
            "risk": "Insufficient external evidence.",
            "metric": "average view duration",
        }
    synthesis = ai_text(
        "You are the managing editor. Produce a conservative JSON decision from this council. "
        "Optimize for original, authentic viewer value and sustainable monetization eligibility; never copy, "
        "make health/behavior promises, or authorize automatic publication. "
        f"Council: {json.dumps(opinions)}\n"
        "Keys: decision, proposed_series, short_hook_direction, long_form_direction, primary_metric, guardrails.",
        json_mode=True,
        task="agency_managing_editor",
    )
    consensus = _json_object(synthesis) or {
        "decision": "review before production",
        "proposed_series": "cozy pet jazz",
        "short_hook_direction": "show the pet immediately",
        "long_form_direction": "build a distinct 20-45 minute session",
        "primary_metric": "average view duration",
        "guardrails": "no medical or behavioural claims; use distinct assets",
    }
    brief = {
        "generated_at": datetime.now(UTC).isoformat(),
        "research": {
            "youtube_keywords": keywords,
            "web_sources": research.get("sources", []),
            "recent_visual_signals": visual_history,
            "competitive_patterns": competitive_patterns,
        },
        "roles": opinions,
        "consensus": consensus,
        "publication_authority": "none — brief requires the existing production safeguards",
    }
    with state_lock(_brief_file()):
        _brief_file().parent.mkdir(parents=True, exist_ok=True)
        _brief_file().write_text(json.dumps(brief, ensure_ascii=False, indent=2), encoding="utf-8")
    with state_lock(_memory_file()):
        history = []
        try:
            history = json.loads(_memory_file().read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
        if not isinstance(history, list):
            history = []
        history.insert(0, {"generated_at": brief["generated_at"], "consensus": consensus})
        _memory_file().write_text(json.dumps(history[:60], ensure_ascii=False, indent=2), encoding="utf-8")
    return brief
