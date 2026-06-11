"""Claim extraction and source-risk scoring for fact guardrails."""

from __future__ import annotations

import re

RISK_TERMS = {"only", "always", "never", "first", "largest", "fastest", "smallest", "deadliest", "proves"}
SOURCE_KEYS = ("source_url", "commons_page_url", "gbif", "scientific_name", "source_license")


def extract_claims(text: str) -> list[str]:
    claims: list[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+", str(text or "")):
        clean = " ".join(sentence.split())
        if len(clean) < 18:
            continue
        lower = clean.lower()
        if (
            re.search(r"\d", clean)
            or any(term in lower for term in RISK_TERMS)
            or any(term in lower for term in ("because", "scientists", "research", "species", "can "))
        ):
            claims.append(clean[:260])
    return claims


def has_source(meta: dict) -> bool:
    for key in SOURCE_KEYS:
        value = meta.get(key)
        if isinstance(value, dict) and value:
            return True
        if isinstance(value, str) and value.strip():
            return True
    return False


def evaluate_claim_risk(meta: dict | None = None) -> dict:
    meta = meta or {}
    text = " ".join(str(meta.get(key) or "") for key in ("title", "hook", "script", "description"))
    claims = extract_claims(text)
    sourced = has_source(meta)
    high_risk = [claim for claim in claims if any(term in claim.lower() for term in RISK_TERMS)]
    if not claims:
        level = "safe"
    elif sourced and not high_risk:
        level = "safe"
    elif sourced:
        level = "needs_source"
    else:
        level = "block" if high_risk else "needs_source"
    return {
        "level": level,
        "approved": level != "block",
        "claims": claims,
        "claim_count": len(claims),
        "high_risk_claims": high_risk,
        "has_source": sourced,
        "source_keys": [key for key in SOURCE_KEYS if meta.get(key)],
    }
