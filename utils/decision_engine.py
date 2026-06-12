"""Single decision layer for Wild Brief story recommendations."""

from __future__ import annotations

from utils.confidence_engine import combined_confidence
from utils.growth_engine import analyze_retention, detect_weak_content, score_topic
from utils.publish_score import score_story
from utils.subscriber_conversion import score_subscriber_conversion


def _source(name: str, payload: dict) -> dict:
    confidence = payload.get("confidence") or payload.get("decision_confidence") or {}
    return {
        "source": name,
        "score": payload.get("score", payload.get("risk", 0)),
        "state": payload.get("state") or payload.get("verdict"),
        "confidence_score": confidence.get("confidence_score", 0),
        "sample_size": confidence.get("sample_size", 0),
        "data_quality": confidence.get("data_quality", "missing"),
        "reasoning": payload.get("reasoning") or confidence.get("reasoning") or "",
    }


def decide_story(story: dict, *, analytics_strategy: dict | None = None) -> dict:
    """Return one explainable decision built from existing Wild Brief systems."""
    publish = score_story(story, analytics_strategy=analytics_strategy)
    opportunity = publish.get("opportunity") or score_topic(story)
    retention = publish.get("retention") or analyze_retention(story)
    weak = publish.get("weak_content") or detect_weak_content(story)
    subscriber = publish.get("subscriber_conversion") or score_subscriber_conversion(story)
    sources = [
        _source("opportunity", opportunity),
        _source("retention", retention),
        _source("subscriber_conversion", subscriber),
        _source("weak_content", weak),
        _source("publish_score", publish),
    ]
    confidence = combined_confidence(
        [
            opportunity.get("confidence") or {},
            retention.get("confidence") or {},
            subscriber.get("confidence") or {},
            weak.get("confidence") or {},
            publish.get("decision_confidence") or {},
        ]
    )

    blockers = []
    if opportunity.get("verdict") == "discard":
        blockers.append("opportunity_discard")
    if retention.get("verdict") == "discard":
        blockers.append("retention_discard")
    if weak.get("state") == "block":
        blockers.append("weak_content_block")
    robotic = (subscriber.get("robotic_title") or {}).get("state")
    if robotic == "block":
        blockers.append("robotic_title_block")

    if blockers:
        decision = "reject"
    elif publish.get("approved") and confidence.get("recommendation_strength") in {"test", "act"}:
        decision = "publish"
    elif publish.get("score", 0) >= 55:
        decision = "rewrite_or_test"
    else:
        decision = "observe"

    reasoning = [
        f"Publish score {publish.get('score', 0)} with state {publish.get('state')}.",
        confidence.get("reasoning", ""),
    ]
    if blockers:
        reasoning.append("Blocked by: " + ", ".join(blockers) + ".")
    if confidence.get("recommendation_strength") == "observe":
        reasoning.append("Confidence is low, so the system should not make a strong strategy change.")

    return {
        "decision": decision,
        "approved": decision == "publish",
        "confidence": confidence,
        "data_sources": sources,
        "blockers": blockers,
        "reasoning": [line for line in reasoning if line],
        "scores": {
            "publish": publish.get("score", 0),
            "opportunity": opportunity.get("score", 0),
            "retention": retention.get("score", 0),
            "subscriber_conversion": subscriber.get("score", 0),
            "weak_content_risk": weak.get("risk", 0),
        },
    }
