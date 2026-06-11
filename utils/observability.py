"""Small structured observability helpers for GitHub Actions-safe scripts."""

from __future__ import annotations

import base64
import csv
import json
import logging
import os
from datetime import datetime, timezone
from email.mime.text import MIMEText
from pathlib import Path

SECRET_KEYS = ("token", "secret", "password", "credential", "authorization", "api_key")


def _redact(value):
    if isinstance(value, dict):
        return {
            key: ("***" if any(term in key.lower() for term in SECRET_KEYS) else _redact(val))
            for key, val in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if hasattr(record, "event"):
            payload["event"] = record.event
        if hasattr(record, "fields") and isinstance(record.fields, dict):
            payload.update(_redact(record.fields))
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(os.environ.get("WILD_BRIEF_LOG_LEVEL", "INFO"))
    return logger


def emit_event(logger: logging.Logger, event_name: str, **fields) -> None:
    logger.info(event_name, extra={"event": event_name, "fields": fields})


def append_jsonl_metric(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _redact(dict(row))
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def append_csv_metric(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _redact(dict(row))
    exists = path.exists() and path.stat().st_size > 0
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(payload.keys()))
        if not exists:
            writer.writeheader()
        writer.writerow(payload)


def build_gmail_message(to_addr: str, subject: str, body: str) -> dict:
    mime = MIMEText(body[:4000], "plain", "utf-8")
    mime["to"] = to_addr
    mime["subject"] = subject[:120]
    raw = base64.urlsafe_b64encode(mime.as_bytes()).decode("utf-8")
    return {"raw": raw}


def maybe_send_gmail_alert(subject: str, body: str, enabled: bool = False) -> dict:
    """Build an alert payload unless disabled.

    Sending is intentionally not automatic here. A future Gmail API caller can
    use the returned payload after explicit opt-in.
    """
    enabled = enabled or os.environ.get("WILD_BRIEF_GMAIL_ALERTS", "0").lower() in {"1", "true", "yes"}
    to_addr = os.environ.get("WILD_BRIEF_ALERT_TO", "")
    if not enabled or not to_addr:
        return {"sent": False, "reason": "disabled"}
    return {"sent": False, "reason": "payload_ready", "message": build_gmail_message(to_addr, subject, body)}
