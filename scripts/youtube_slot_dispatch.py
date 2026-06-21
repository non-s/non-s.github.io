"""Dispatch YouTube publisher recovery runs for an exact hourly slot.

The important invariant is that a publisher run only covers the slot whose
window contains the run creation time. A delayed 10:42 proxy that starts at
10:55 must not satisfy the 11:00 slot.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.upload_intent import INTENTS_FILE, duplicate_slot_uploaded  # noqa: E402


ACTIVE_STATUSES = {"queued", "in_progress", "waiting", "requested", "pending"}
DEFAULT_PUBLISH_SLOTS = tuple(f"{hour:02d}:00" for hour in range(24))


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)


def parse_slots(value: str | None = None) -> tuple[str, ...]:
    raw = value if value is not None else os.environ.get("PUBLISH_SLOTS_UTC", "")
    slots = tuple(part.strip() for part in str(raw or "").split(",") if part.strip())
    return slots or DEFAULT_PUBLISH_SLOTS


def slot_at(day, label: str) -> datetime:
    hour, minute = [int(part) for part in label.split(":", 1)]
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=timezone.utc)


def current_hour_slot(now: datetime) -> datetime:
    return now.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)


def latest_auditable_slot(now: datetime, *, grace: timedelta, publish_slots: Iterable[str]) -> datetime | None:
    now = now.astimezone(timezone.utc)
    candidates: list[datetime] = []
    for day_offset in (-1, 0):
        day = (now + timedelta(days=day_offset)).date()
        for label in publish_slots:
            slot = slot_at(day, label)
            if now >= slot + grace:
                candidates.append(slot)
    return max(candidates) if candidates else None


def slot_window(slot: datetime, *, minutes: int = 60) -> tuple[datetime, datetime]:
    start = slot.astimezone(timezone.utc)
    return start, start + timedelta(minutes=max(1, minutes))


def slot_key(slot: datetime) -> str:
    return slot.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def run_covers_slot(run: dict, slot: datetime, *, window_minutes: int = 60) -> bool:
    created_raw = str(run.get("created_at") or "")
    if not created_raw:
        return False
    created_at = parse_utc(created_raw)
    start, end = slot_window(slot, minutes=window_minutes)
    return start <= created_at < end


def slot_has_uploaded_intent(slot: datetime, path: Path = INTENTS_FILE) -> dict:
    return duplicate_slot_uploaded(slot_key(slot), path)


def successful_run_satisfies_slot(
    run: dict,
    slot: datetime,
    *,
    window_minutes: int = 60,
    upload_intents_path: Path = INTENTS_FILE,
) -> bool:
    if not run_covers_slot(run, slot, window_minutes=window_minutes):
        return False
    if run.get("status") != "completed" or run.get("conclusion") != "success":
        return False
    return bool(slot_has_uploaded_intent(slot, upload_intents_path))


def request_json(token: str, method: str, url: str, body: dict | None = None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "wildbrief-youtube-slot-dispatch",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        raw = response.read()
        return None if not raw else json.loads(raw.decode("utf-8"))


def dispatch_if_missing(
    *,
    token: str,
    repo: str,
    workflow: str,
    slot: datetime,
    reason: str,
    window_minutes: int = 60,
    upload_intents_path: Path = INTENTS_FILE,
) -> int:
    start, end = slot_window(slot, minutes=window_minutes)
    print(f"Auditing slot {slot.isoformat()} with window [{start.isoformat()}, {end.isoformat()}).")
    runs_url = f"https://api.github.com/repos/{repo}/actions/workflows/{workflow}/runs?per_page=30"
    runs = (request_json(token, "GET", runs_url) or {}).get("workflow_runs", [])
    relevant = [run for run in runs if run_covers_slot(run, slot, window_minutes=window_minutes)]
    for run in relevant:
        status = run.get("status")
        conclusion = run.get("conclusion")
        event = run.get("event")
        url = run.get("html_url")
        created = run.get("created_at")
        print(f"Found run in slot window: {created} status={status} conclusion={conclusion} event={event} {url}")
        if status in ACTIVE_STATUSES:
            print("A publishing run is already active or queued for this slot; no recovery needed.")
            return 0
        if status == "completed" and conclusion == "success":
            upload = slot_has_uploaded_intent(slot, upload_intents_path)
            if upload:
                video_id = upload.get("video_id")
                print(f"This slot already has uploaded video_id={video_id}; no recovery needed.")
                return 0
            print("Successful run found, but no uploaded intent exists for this slot; treating slot as uncovered.")

    dispatch_url = f"https://api.github.com/repos/{repo}/actions/workflows/{workflow}/dispatches"
    try:
        request_json(token, "POST", dispatch_url, {"ref": "main", "inputs": {"reason": reason}})
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        print(f"Failed to dispatch recovery run: HTTP {exc.code} {detail}", file=sys.stderr)
        raise
    print(f"Dispatched {workflow}: {reason}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("heartbeat", "watchdog"))
    args = parser.parse_args(argv)

    token = os.environ["GH_TOKEN"]
    repo = os.environ["GH_REPOSITORY"]
    workflow = os.environ.get("TARGET_WORKFLOW", "youtube-bot.yml")
    window_minutes = int(os.environ.get("PUBLISH_SLOT_WINDOW_MINUTES", "60"))
    now = datetime.now(timezone.utc)

    if args.mode == "heartbeat":
        slot = current_hour_slot(now)
        reason = f"{os.environ.get('RECOVERY_REASON_PREFIX', 'heartbeat recovery for slot')} {slot.isoformat()}"
    else:
        grace = timedelta(minutes=int(os.environ.get("GRACE_MINUTES", "45")))
        slot = latest_auditable_slot(now, grace=grace, publish_slots=parse_slots())
        if slot is None:
            print("No publishing slot is old enough to audit yet.")
            return 0
        reason = f"{os.environ.get('RECOVERY_REASON_PREFIX', 'watchdog recovery for missed slot')} {slot.isoformat()}"

    return dispatch_if_missing(
        token=token,
        repo=repo,
        workflow=workflow,
        slot=slot,
        reason=reason,
        window_minutes=window_minutes,
    )


if __name__ == "__main__":
    raise SystemExit(main())
