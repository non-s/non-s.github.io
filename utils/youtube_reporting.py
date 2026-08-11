"""Read-only discovery of YouTube Reporting datasets."""

from __future__ import annotations

from typing import Any


def reporting_inventory(service: Any) -> dict[str, object]:
    """List accessible jobs/reports without creating jobs or downloading data."""
    jobs = service.jobs().list(includeSystemManaged=True).execute().get("jobs", [])
    return {
        "method": "read-only YouTube Reporting inventory; no jobs created",
        "jobs": [
            {
                "id": str(job.get("id") or ""),
                "name": str(job.get("reportTypeId") or ""),
                "system_managed": bool(job.get("systemManaged")),
            }
            for job in jobs
        ],
    }
