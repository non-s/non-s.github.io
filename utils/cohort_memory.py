"""Manual audience cohort memory and slot hints."""

from __future__ import annotations

from collections import Counter


def build_cohort_memory(rows: list[dict] | None = None) -> dict:
    rows = rows or []
    cohorts: Counter[str] = Counter()
    slots: Counter[str] = Counter()
    for row in rows:
        cohorts[str(row.get("cohort") or row.get("viewer_type") or "unknown")] += int(row.get("views") or 1)
        slot = str(row.get("slot_utc") or row.get("publish_slot") or "")
        if slot:
            slots[slot] += int(row.get("engaged_views") or row.get("views") or 1)
    return {
        "cohorts": dict(cohorts),
        "recommended_slots": [slot for slot, _ in slots.most_common(4)],
        "coverage": round(len(rows) / max(len(rows), 1), 4) if rows else 0,
    }
