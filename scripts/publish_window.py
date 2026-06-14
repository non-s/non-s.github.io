#!/usr/bin/env python3
"""Decide whether the current publish slot should produce a Short."""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.upload_intent import duplicate_slot_uploaded  # noqa: E402
from utils.publish_priority import publish_priority_key  # noqa: E402
from utils.publish_schedule import (  # noqa: E402
    DECISIONS_FILE,
    SCHEDULE_FILE,
    active_slot_label,
    feature_flags,
    is_active_slot,
    next_slot,
    recommend_schedule,
    slot_label,
)
from utils.publish_score import score_story  # noqa: E402

QUEUE_FILE = ROOT / "_data" / "stories_queue.json"
UPLOAD_INTENTS_FILE = Path("_data/upload_intents.jsonl")


def _read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _parse_now(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    text = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _eligible_stories(queue: dict) -> list[dict]:
    stories = queue.get("stories") if isinstance(queue, dict) else []
    has_prune_state = any(
        isinstance(story, dict) and not story.get("consumed") and bool(story.get("queue_prune"))
        for story in stories or []
    )
    out = []
    for story in stories or []:
        if not isinstance(story, dict) or story.get("consumed"):
            continue
        if not (story.get("title") or story.get("seo_title")):
            continue
        queue_prune = story.get("queue_prune") or {}
        if has_prune_state and queue_prune.get("state") != "publish_ready":
            continue
        editorial = story.get("editorial") or {}
        if editorial and editorial.get("approved") is not True:
            continue
        publish = story.get("publish_score") or {}
        if publish and (publish.get("approved") is not True or publish.get("state") != "publish_ready"):
            continue
        out.append(story)
    return out


def _candidate_id(story: dict | None) -> str:
    if not story:
        return ""
    return str(story.get("id") or story.get("slug") or story.get("source_clip_id") or story.get("title") or "")


def _best_candidate(stories: list[dict]) -> tuple[dict | None, dict]:
    best_story: dict | None = None
    best_score: dict = {}
    best_key = (-1.0, -1.0, -1.0)
    for story in stories:
        try:
            score = score_story(story)
        except Exception as exc:
            score = {"score": 0.0, "approved": False, "opportunity": {"score": 0.0}, "error": str(exc)}
        key = publish_priority_key(story, score)
        if best_story is None or key > best_key:
            best_story = story
            best_score = score
            best_key = key
    return best_story, best_score


def _append_decision(path: Path, decision: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(decision, sort_keys=True, ensure_ascii=False) + "\n")


def _slot_key(current: datetime, label: str) -> str:
    try:
        hour, minute = [int(part) for part in str(label).split(":", 1)]
    except Exception:
        hour, minute = current.hour, current.minute
    start = datetime.combine(current.date(), datetime.min.time(), tzinfo=timezone.utc).replace(
        hour=hour,
        minute=minute,
    )
    if start > current:
        start -= timedelta(days=1)
    return start.strftime("%Y-%m-%dT%H:%MZ")


def evaluate_publish_window(
    *,
    root: Path = ROOT,
    now: datetime | None = None,
    env: dict | None = None,
    queue_path: Path | None = None,
    schedule_path: Path | None = None,
    decisions_path: Path | None = None,
    write_decision: bool = True,
) -> dict:
    """Return and optionally persist the publish decision for this slot."""
    env = env or os.environ
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    flags = feature_flags(env)
    schedule_file = schedule_path or (root / SCHEDULE_FILE)
    queue_file = queue_path or (root / "_data" / "stories_queue.json")
    decision_file = decisions_path or (root / DECISIONS_FILE)
    schedule = _read_json(schedule_file, {})
    if not schedule:
        schedule = recommend_schedule(_read_json(root / "_data" / "analytics" / "latest.json", {}))

    current_label = slot_label(current)
    active_label = active_slot_label(current, schedule, env) if flags["adaptive_cadence_enabled"] else current_label
    label = active_label or current_label
    slot_key = _slot_key(current, label)
    reasons: list[str] = []
    decision = "publish"
    top_story: dict | None = None
    top_score: dict = {}
    uploaded_for_slot: dict = {}

    dispatch_reason = str(env.get("WORKFLOW_DISPATCH_REASON") or "").strip().lower()
    is_watchdog_recovery = dispatch_reason.startswith("watchdog recovery")
    manual = str(env.get("GITHUB_EVENT_NAME") or "").lower() == "workflow_dispatch" and not is_watchdog_recovery
    if manual:
        reasons.append("manual_dispatch")
    elif not flags["adaptive_cadence_enabled"]:
        reasons.append("adaptive_cadence_disabled")
    elif env.get("PUBLISH_QUOTA_BLOCKED", "").strip().lower() in {"1", "true", "yes", "on"}:
        decision = "skip_quota_guard"
        reasons.append("quota_guard_blocked")
    elif not is_active_slot(current, schedule, env):
        decision = "skip_outside_slot"
        reasons.append("outside_recommended_slot")

    if decision == "publish":
        if not manual and active_label and active_label != current_label:
            reasons.append("delayed_slot_recovery")
        uploaded_for_slot = duplicate_slot_uploaded(slot_key, root / UPLOAD_INTENTS_FILE)
        if uploaded_for_slot:
            decision = "skip_slot_already_uploaded"
            reasons.append("slot_already_uploaded")
    if decision == "publish":
        stories = _eligible_stories(_read_json(queue_file, {}))
        if not stories:
            decision = "skip_no_eligible_story"
            reasons.append("no_eligible_story")
        else:
            top_story, top_score = _best_candidate(stories)
            publish_score = float(top_score.get("score") or 0)
            opportunity_score = float((top_score.get("opportunity") or {}).get("score") or 0)
            quality_reasons: list[str] = []
            if publish_score < flags["min_slot_publish_score"]:
                quality_reasons.append("publish_score_below_threshold")
            if opportunity_score < flags["min_queue_opportunity_score"]:
                quality_reasons.append("opportunity_score_below_threshold")
            if quality_reasons:
                decision = "skip_low_queue_quality"
                reasons.extend(quality_reasons)

    if flags["adaptive_cadence_enabled"] and not top_story and decision == "publish" and not manual:
        stories = _eligible_stories(_read_json(queue_file, {}))
        if stories:
            top_story, top_score = _best_candidate(stories)

    publish_score = None if not top_score else float(top_score.get("score") or 0)
    opportunity_score = None if not top_score else float((top_score.get("opportunity") or {}).get("score") or 0)
    payload = {
        "timestamp_utc": current.isoformat(),
        "slot_label": label,
        "slot_key": slot_key,
        "decision": decision,
        "top_candidate_id": _candidate_id(top_story),
        "publish_score": publish_score,
        "opportunity_score": opportunity_score,
        "reasons": reasons,
        "slot_uploaded_video_id": str(uploaded_for_slot.get("video_id") or ""),
        "feature_flags": flags,
        "recommended_slots": schedule.get("recommended_slots") or [],
        "next_slot": next_slot(current, schedule, env),
        "schedule_source": str(
            schedule_file.relative_to(root) if schedule_file.is_relative_to(root) else schedule_file
        ),
    }
    if write_decision:
        _append_decision(decision_file, payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="Print the structured decision JSON only.")
    parser.add_argument("--now", help="Override the current UTC timestamp for tests/manual checks.")
    parser.add_argument("--queue", default=str(QUEUE_FILE), help="Queue JSON path.")
    parser.add_argument("--decisions-file", default=str(ROOT / DECISIONS_FILE), help="Decision JSONL output path.")
    parser.add_argument("--no-write", action="store_true", help="Evaluate without appending to the decision ledger.")
    args = parser.parse_args()

    decision = evaluate_publish_window(
        now=_parse_now(args.now),
        queue_path=Path(args.queue),
        decisions_path=Path(args.decisions_file),
        write_decision=not args.no_write,
    )
    if args.json:
        print(json.dumps(decision, sort_keys=True, ensure_ascii=False))
    else:
        print(
            "publish window: "
            f"slot={decision['slot_label']} decision={decision['decision']} "
            f"next={decision['next_slot']} reasons={decision['reasons'] or ['ready']}"
        )
    if decision["decision"] != "publish" and os.environ.get("PUBLISH_WINDOW_ENFORCE", "0") in {"1", "true", "True"}:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
