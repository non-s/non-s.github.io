"""Deterministic A/B selection with conservative winner bias."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import datetime

from utils.experiments import read_winner


def _num(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _date_key(row: dict) -> str:
    value = str(row.get("pulled_at") or row.get("uploaded_at") or row.get("assigned_at") or "")
    return value[:10] if len(value) >= 10 else datetime.utcnow().date().isoformat()


def _bucket(axis: str, key: str, candidates: list[str]) -> str:
    if not candidates:
        return ""
    digest = hashlib.sha256(f"{axis}:{key}".encode("utf-8")).digest()
    return candidates[int.from_bytes(digest[:4], "big") % len(candidates)]


def _objective_score(row: dict) -> float:
    metrics = row.get("metrics") or row
    derived = row.get("derived") or {}
    engaged_quality = _num(derived.get("engaged_view_rate"), _num(metrics.get("average_view_percentage")) / 100)
    replay = _num(derived.get("replay_rate_proxy"))
    minutes = _num(derived.get("minutes_per_engaged_view")) / 30
    sub = _num(derived.get("sub_per_1k_engaged")) / 5
    comments = _num(derived.get("comment_rate_per_1k_engaged")) / 10
    diversity = _num(derived.get("source_diversity"))
    retention = _num(metrics.get("average_view_percentage"))
    penalty = 0.18 if retention and retention < 55 else 0
    score = (
        engaged_quality * 35
        + min(replay, 1.0) * 20
        + min(minutes, 1.0) * 15
        + min(sub, 1.0) * 10
        + min(comments, 1.0) * 10
        + min(diversity, 1.0) * 10
    )
    return round(max(0.0, score * (1 - penalty)), 4)


def _engaged_views(row: dict) -> float:
    metrics = row.get("metrics") or row
    return _num(metrics.get("engaged_views"), _num(metrics.get("views")))


class BayesianABSelector:
    """Simple conservative selector; enough data first, winner bias second."""

    def has_enough_data(self, rows: list[dict], min_samples: int, min_days: int) -> bool:
        if len(rows) < min_samples:
            return False
        return len({_date_key(row) for row in rows}) >= min_days

    def guardrail_status(
        self,
        rows: list[dict],
        *,
        min_samples: int = 12,
        min_days: int = 2,
        min_engaged_views: int = 0,
    ) -> dict:
        days = len({_date_key(row) for row in rows})
        engaged = int(sum(_engaged_views(row) for row in rows))
        reasons = []
        if len(rows) < min_samples:
            reasons.append("below_min_samples")
        if days < min_days:
            reasons.append("below_min_days")
        if engaged < min_engaged_views:
            reasons.append("below_min_engaged_views")
        return {
            "eligible": not reasons,
            "reasons": reasons,
            "samples": len(rows),
            "days": days,
            "engaged_views": engaged,
            "min_samples": min_samples,
            "min_days": min_days,
            "min_engaged_views": min_engaged_views,
        }

    def score_variant(self, rows: list[dict], objective: str = "growth") -> dict:
        if not rows:
            return {"n": 0, "mean": 0.0, "objective": objective}
        scores = [_objective_score(row) for row in rows]
        return {
            "n": len(rows),
            "mean": round(sum(scores) / len(scores), 4),
            "objective": objective,
            "min": round(min(scores), 4),
            "max": round(max(scores), 4),
        }

    def choose_live_variant(self, axis: str, candidates: list[str], context: dict) -> str:
        context = context or {}
        candidates = list(candidates or [])
        key = str(context.get("story_id") or context.get("key") or "wildbrief")
        baseline = _bucket(axis, key, candidates)
        winner = str(context.get("winner") or read_winner(axis) or "")
        enough_data = bool(context.get("enough_data", False))
        exploration_percent = int(context.get("exploration_percent", 15))
        explore_bucket = (
            int.from_bytes(
                hashlib.sha256(f"explore:{axis}:{key}".encode("utf-8")).digest()[:2],
                "big",
            )
            % 100
        )
        if not winner or winner not in candidates or not enough_data:
            return baseline
        if explore_bucket < exploration_percent:
            return baseline
        return winner

    def rank_axis(
        self,
        rows: list[dict],
        axis: str,
        min_samples: int = 12,
        min_days: int = 2,
        min_engaged_views: int = 0,
    ) -> dict:
        grouped: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            variants = row.get("variants") or row.get("experiments") or {}
            variant = variants.get(axis)
            if variant:
                grouped[str(variant)].append(row)
        scored = {variant: self.score_variant(items) for variant, items in grouped.items()}
        eligible = {
            variant: payload
            for variant, payload in scored.items()
            if self.guardrail_status(
                grouped[variant],
                min_samples=min_samples,
                min_days=min_days,
                min_engaged_views=min_engaged_views,
            )["eligible"]
        }
        winner = ""
        if eligible:
            winner = max(eligible.items(), key=lambda kv: kv[1]["mean"])[0]
        guardrails = {
            variant: self.guardrail_status(
                items,
                min_samples=min_samples,
                min_days=min_days,
                min_engaged_views=min_engaged_views,
            )
            for variant, items in grouped.items()
        }
        losers = [
            variant
            for variant, payload in scored.items()
            if winner
            and variant != winner
            and payload.get("n", 0) >= min_samples
            and payload.get("mean", 0) < eligible[winner]["mean"] * 0.82
        ]
        return {"axis": axis, "variants": scored, "winner": winner, "guardrails": guardrails, "paused_losers": losers}
