"""Rights and license checks for queue items and rendered metadata."""

from __future__ import annotations


ALLOWED_SOURCES = {
    "internet archive",
    "pexels",
    "pixabay",
    "wikimedia commons",
    "remake factory",
    "youtube analytics sequel",
    "youtube comment idea",
}

ARCHIVE_SAFE_MARKERS = (
    "creativecommons.org/publicdomain",
    "public domain",
    "publicdomain",
    "cc0",
    "u.s. government",
    "united states government",
    "usgov",
)


def audit_rights(item: dict) -> dict:
    source = str(item.get("source") or "").strip().lower()
    license_text = str(
        item.get("source_license") or item.get("commons_license") or item.get("source_license_evidence") or ""
    ).lower()
    evidence_text = str(item.get("source_license_evidence") or item.get("rights_policy") or "").lower()
    reasons = []
    warnings = []
    if source and source not in ALLOWED_SOURCES:
        reasons.append("unknown_source")
    if not license_text:
        warnings.append("missing_source_license")
    elif source in {"pexels", "pixabay"} and "license" not in license_text:
        warnings.append("missing_source_license")
    elif source == "internet archive" and not any(
        marker in f"{license_text} {evidence_text}" for marker in ARCHIVE_SAFE_MARKERS
    ):
        reasons.append("unsafe_archive_license")
    if source != "remake factory" and not (item.get("source_url") or item.get("url")):
        reasons.append("missing_source_url")
    return {
        "approved": not reasons,
        "source": source,
        "license": license_text,
        "reasons": reasons,
        "warnings": warnings,
    }
