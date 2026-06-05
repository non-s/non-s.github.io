"""
utils/experiments.py â€” Lightweight A/B testing for prompts, hooks, voices, etc.

Without an experimentation loop, the channel is permanently capped at
whatever the initial prompt template happens to produce. Real growth
comes from iterating â€” and iteration without measurement is theatre.

How it works
------------
1. fetch_animals.py / generate_shorts.py call `assign_variant(story_id, axis)`
   when they need to pick a variant for an experimentable axis (e.g.
   the hook style for THIS story, or the voice for THIS Short).
2. The assignment is deterministic (hash(story_id + axis) mod n_buckets)
   so a re-run yields the same variant â€” idempotent.
3. The chosen variant is stamped on the queue entry (`experiments` dict)
   and persists into `_videos/*.done` after upload.
4. The nightly analytics workflow correlates variant â†” performance and
   writes `_data/analytics/experiments.json` with the winner per axis.
5. Future runs can `read_winner(axis)` to bias toward the winning
   variant (or stay in experiment mode to keep iterating).

Axes shipped today
------------------
  - hook_style: outcome_first | question | shocking_number | curiosity_gap
  - script_tone: opinionated | analytical | conversational
  - thumbnail_style: dynamic_text | category_color | brand_static
  - cta_style: subscribe_channel

Each axis defines its variants and an `is_significant()` heuristic so
the analyser doesn't crown a winner on 3 data points.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
import os
from collections import defaultdict
from pathlib import Path
from typing import Iterable

log = logging.getLogger(__name__)

EXPERIMENTS_FILE = Path(os.environ.get(
    "EXPERIMENTS_FILE", "_data/analytics/experiments.json",
))
# How many Shorts a variant needs before the analyser will declare a
# winner. 8 is the bare minimum for "more signal than noise" on YT
# Analytics' per-video sample sizes.
MIN_SAMPLES_FOR_WINNER = int(os.environ.get("EXPERIMENT_MIN_SAMPLES", "8"))


@dataclasses.dataclass(frozen=True)
class Axis:
    name: str
    variants: tuple[str, ...]
    description: str


# Axes registry. To add a new experimentable knob:
#   1. Add an Axis here.
#   2. Use `assign_variant("axis_name", story_id)` in the producer.
#   3. Make sure the variant is read where it matters (prompt template,
#      voice picker, etc).
AXES: tuple[Axis, ...] = (
    Axis(
        name="hook_style",
        variants=(
            "outcome_first",     # "This octopus changes colour in seconds."
            "question",          # "Why does this octopus change colour?"
            "shocking_number",   # "Three hearts. One extraordinary animal."
            "curiosity_gap",     # "This bird does one thing nobody expects."
        ),
        description="First-sentence shape â€” the single biggest retention lever.",
    ),
    Axis(
        name="script_tone",
        variants=(
            "opinionated",       # name winner/loser explicitly
            "analytical",        # explain mechanism / context
            "conversational",    # friend-style explainer
        ),
        description="Voice-over register.",
    ),
    Axis(
        name="narrator_voice",
        variants=(
            "aria",
            "jenny",
            "guy",
        ),
        description="Small host-voice panel for measured narrator variety.",
    ),
    Axis(
        name="thumbnail_style",
        variants=(
            "dynamic_text",      # AI-authored thumbnail_text overlay (current default)
            "category_color",    # solid category-color slab + title
            # `brand_static` (the shipped JPEG with no per-Short text) was
            # part of the A/B until the channel had enough volume to
            # learn from it. At <100 subs every Short is a first-
            # impression and the boring brand image hurts CTR. Re-add
            # once the channel passes ~500 subs and the A/B has real
            # statistical power.
        ),
        description="Thumbnail composition strategy.",
    ),
    Axis(
        name="cta_style",
        # Order matters: variants[0] is the production fallback when no
        # A/B winner is declared yet. Channel subscription is the only
        # production close: comments stay inside the script and pinned
        # comment so the end card has one clear action.
        variants=(
            "subscribe_channel",
        ),
        description="End-of-Short call-to-action.",
    ),
)


def _axis_by_name(name: str) -> Axis | None:
    for ax in AXES:
        if ax.name == name:
            return ax
    return None


def assign_variant(axis_name: str, key: str) -> str:
    """Deterministic variant assignment for `key` on `axis_name`.

    Same key â†’ same variant across reruns. Falls back to the first
    variant if `axis_name` isn't registered.
    """
    ax = _axis_by_name(axis_name)
    if not ax or not ax.variants:
        return ""
    h = hashlib.sha1(f"{axis_name}:{key}".encode("utf-8")).digest()
    idx = int.from_bytes(h[:4], "big") % len(ax.variants)
    return ax.variants[idx]


def assign_all(key: str) -> dict[str, str]:
    """Assign one variant per axis. Returns {axis_name: variant}."""
    return {ax.name: assign_variant(ax.name, key) for ax in AXES}


def assign_for_production(axis_name: str, key: str,
                          exploration_percent: int = 20) -> str:
    """Favor a measured winner while reserving deterministic exploration."""
    baseline = assign_variant(axis_name, key)
    winner = read_winner(axis_name)
    if not winner or winner not in variant_choices(axis_name):
        return baseline
    bucket = int.from_bytes(
        hashlib.sha1(f"explore:{axis_name}:{key}".encode("utf-8")).digest()[:2],
        "big",
    ) % 100
    return baseline if bucket < exploration_percent else winner


def assign_all_for_production(key: str) -> dict[str, str]:
    return {ax.name: assign_for_production(ax.name, key) for ax in AXES}


# â”€â”€ Reading winners (set by the analyser) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def read_winners(path: Path | None = None) -> dict[str, str]:
    """Return {axis_name: winning_variant}. Empty when not yet computed.

    `path` defaults to `EXPERIMENTS_FILE` â€” resolved at call time so
    monkeypatch in tests is honoured (a stale default would otherwise
    point at the production path forever).
    """
    p = path or EXPERIMENTS_FILE
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    winners = data.get("winners") or {}
    return {str(k): str(v) for k, v in winners.items() if isinstance(v, str)}


def read_winner(axis_name: str) -> str | None:
    """Returns the winning variant for `axis_name`, or None."""
    return read_winners().get(axis_name) or None


# â”€â”€ Computing winners (called by the analyser) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def compute_winners(observations: Iterable[dict],
                     min_samples: int = MIN_SAMPLES_FOR_WINNER) -> dict:
    """Given a list of {"experiments": {axis: variant}, "score": float},
    return a dict suitable for serialising to `experiments.json`:

      {
        "computed_at": iso,
        "axis_stats":  {axis: {variant: {"n": int, "mean": float}}},
        "winners":     {axis: variant_with_best_mean OR omitted if too few samples}
      }

    `score` is typically the YouTube engagement rate
    (likes+comments+shares)/views from channel analytics. The metric
    must be "higher = better".
    """
    stats: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for obs in observations:
        scores = obs.get("score")
        exps = obs.get("experiments") or {}
        if not isinstance(scores, (int, float)) or not isinstance(exps, dict):
            continue
        for axis, variant in exps.items():
            if not isinstance(variant, str):
                continue
            stats[axis][variant].append(float(scores))

    axis_stats: dict[str, dict[str, dict]] = {}
    winners: dict[str, str] = {}
    runners_up: dict[str, dict] = {}
    for axis, by_variant in stats.items():
        per_variant: dict[str, dict] = {}
        for variant, scores in by_variant.items():
            n = len(scores)
            mean = sum(scores) / n if n else 0.0
            per_variant[variant] = {"n": n, "mean": round(mean, 2)}
        axis_stats[axis] = per_variant
        # Pick the variant with the best mean â€” but ONLY if it has
        # enough samples to be trustworthy. Otherwise skip; the
        # generator stays in exploration mode.
        eligible = {v: d for v, d in per_variant.items() if d["n"] >= min_samples}
        if eligible:
            winning_variant, _ = max(eligible.items(), key=lambda kv: kv[1]["mean"])
            winners[axis] = winning_variant
            # Stash the lift over the runner-up for reporting.
            ranked = sorted(eligible.values(), key=lambda d: d["mean"], reverse=True)
            if len(ranked) >= 2:
                lift = ranked[0]["mean"] - ranked[1]["mean"]
                runners_up[axis] = {
                    "winner_mean":      ranked[0]["mean"],
                    "runner_up_mean":   ranked[1]["mean"],
                    "lift":             round(lift, 2),
                }

    from datetime import datetime, timezone
    return {
        "computed_at":  datetime.now(timezone.utc).isoformat(),
        "min_samples":  min_samples,
        "axis_stats":   axis_stats,
        "winners":      winners,
        "lift":         runners_up,
    }


def write_winners(payload: dict, path: Path | None = None) -> None:
    p = path or EXPERIMENTS_FILE
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                  encoding="utf-8")


# â”€â”€ Helpers for the generator â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def axis_names() -> list[str]:
    return [ax.name for ax in AXES]


def variant_choices(axis_name: str) -> tuple[str, ...]:
    ax = _axis_by_name(axis_name)
    return ax.variants if ax else ()
