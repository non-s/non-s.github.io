"""AI-assisted studio rewrite for borderline Wild Brief stories.

This is a controlled rescue layer. It only targets stories the local
editor marked as `needs_ai_rewrite`, uses the existing free AI provider
chain/cache, and accepts the rewrite only when the editorial gate
improves enough.
"""

from __future__ import annotations

import json
import os
import re

from utils.ai_helper import ai_text

ENABLED = os.environ.get("WILD_BRIEF_AI_REWRITE_ENABLED", "1") not in ("0", "false", "False")
_AI_ENV_KEYS = ("MISTRAL_API_KEY", "CEREBRAS_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY")


def _ai_available() -> bool:
    return any(os.environ.get(key, "").strip() for key in _AI_ENV_KEYS)


def _extract_json(raw: str) -> dict:
    if not raw:
        return {}
    clean = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()
    match = re.search(r"\{.*\}", clean, re.DOTALL)
    if not match:
        return {}
    try:
        data = json.loads(match.group(0), strict=False)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _prompt(story: dict, review: dict) -> str:
    reasons = "; ".join(str(r) for r in (review.get("reasons") or []))
    return (
        "Rewrite this YouTube Short script for Wild Brief.\n"
        "Return ONLY valid JSON with keys: hook, script, thumbnail_text.\n"
        "Rules:\n"
        "- 42-58 words total in script.\n"
        "- Script must start with hook verbatim.\n"
        "- One animal only; never switch visible subject.\n"
        "- Include one tiny host reaction.\n"
        "- Include two visible body/scene details.\n"
        "- Include one clear because/that's why payoff.\n"
        "- End with a tiny comment question.\n"
        "- No hype, no 'did you know', no generic animal kingdom language.\n\n"
        f"Title: {story.get('title') or story.get('seo_title')}\n"
        f"Category: {story.get('category')}\n"
        f"Description: {story.get('description')}\n"
        f"Current hook: {story.get('hook')}\n"
        f"Current script: {story.get('script')}\n"
        f"Current thumbnail_text: {story.get('thumbnail_text')}\n"
        f"Why it failed: {reasons}\n"
    )


def rewrite_if_needed(story: dict) -> dict:
    """Best-effort AI rewrite for stories that local polish cannot approve."""
    if not ENABLED or not _ai_available():
        return story
    from utils.editorial import review

    current = review(story)
    if current.state != "needs_ai_rewrite":
        return story

    raw = ai_text(
        _prompt(story, current.to_dict()), seed=abs(hash(story.get("id", ""))) % 9999, timeout=25, json_mode=True
    )
    data = _extract_json(raw)
    if not data:
        out = dict(story)
        out["ai_rewrite"] = {"attempted": True, "accepted": False, "reason": "empty_or_invalid_json"}
        return out

    candidate = dict(story)
    for key in ("hook", "script", "thumbnail_text"):
        if str(data.get(key) or "").strip():
            candidate[key] = str(data[key]).strip()
    after = review(candidate)
    if after.approved and after.score > current.score:
        candidate["ai_rewrite"] = {
            "attempted": True,
            "accepted": True,
            "before_state": current.state,
            "after_state": after.state,
            "before_score": current.score,
            "after_score": after.score,
        }
        candidate["editorial"] = after.to_dict()
        candidate["studio_state"] = after.state
        return candidate

    out = dict(story)
    out["ai_rewrite"] = {
        "attempted": True,
        "accepted": False,
        "reason": "rewrite_did_not_clear_gate",
        "before_state": current.state,
        "after_state": after.state,
        "before_score": current.score,
        "after_score": after.score,
    }
    return out
