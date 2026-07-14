"""Rights and license checks for queue items and rendered metadata."""

from __future__ import annotations

ALLOWED_SOURCES = {
    "pexels",
    "wikimedia commons",
    "remake factory",
    "youtube analytics sequel",
    "youtube comment idea",
}


def audit_rights(item: dict) -> dict:
    source = str(item.get("source") or "").strip().lower()
    license_text = str(
        item.get("source_license") or item.get("commons_license") or item.get("source_license_evidence") or ""
    ).lower()
    reasons = []
    warnings = []
    if source and source not in ALLOWED_SOURCES:
        reasons.append("unknown_source")
    if not license_text:
        warnings.append("missing_source_license")
    elif source == "pexels" and "license" not in license_text:
        warnings.append("missing_source_license")
    if source != "remake factory" and not (item.get("source_url") or item.get("url")):
        reasons.append("missing_source_url")
    return {
        "approved": not reasons,
        "source": source,
        "license": license_text,
        "reasons": reasons,
        "warnings": warnings,
    }
