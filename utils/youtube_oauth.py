"""Shared YouTube OAuth token loading and safe diagnostics."""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

TOKEN_ENV = "YOUTUBE_TOKEN"
UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
READONLY_SCOPE = "https://www.googleapis.com/auth/youtube.readonly"
COMMENTS_SCOPE = "https://www.googleapis.com/auth/youtube.force-ssl"
ANALYTICS_SCOPE = "https://www.googleapis.com/auth/yt-analytics.readonly"
ANALYTICS_MONETARY_SCOPE = "https://www.googleapis.com/auth/yt-analytics-monetary.readonly"
FULL_YOUTUBE_SCOPE = "https://www.googleapis.com/auth/youtube"
DEFAULT_SCOPES = [UPLOAD_SCOPE, READONLY_SCOPE, COMMENTS_SCOPE, ANALYTICS_SCOPE]


@dataclass
class YouTubeTokenInfo:
    data: dict
    source: str
    token_file: Path
    env_var: str = TOKEN_ENV
    errors: list[str] = field(default_factory=list)

    @property
    def present(self) -> bool:
        return bool(self.data)

    @property
    def persistable(self) -> bool:
        return self.source == "file"


def _parse_token_json(raw: str) -> dict:
    value = json.loads(raw)
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, dict):
        raise ValueError("token JSON must be an object")
    return value


def load_token_info(token_file: Path, env_var: str = TOKEN_ENV) -> YouTubeTokenInfo:
    """Load authorized-user JSON from disk first, then from the secret env var."""
    token_file = Path(token_file)
    errors: list[str] = []
    if token_file.exists():
        try:
            return YouTubeTokenInfo(
                data=_parse_token_json(token_file.read_text(encoding="utf-8").strip()),
                source="file",
                token_file=token_file,
                env_var=env_var,
                errors=errors,
            )
        except Exception:
            errors.append("youtube_token_file_invalid")
    raw_env = os.environ.get(env_var, "").strip()
    if raw_env:
        try:
            return YouTubeTokenInfo(
                data=_parse_token_json(raw_env),
                source="env",
                token_file=token_file,
                env_var=env_var,
                errors=errors,
            )
        except Exception:
            errors.append("youtube_token_env_invalid")
    return YouTubeTokenInfo(data={}, source="missing", token_file=token_file, env_var=env_var, errors=errors)


def token_scopes(data: dict) -> set[str]:
    raw = data.get("scopes") if isinstance(data, dict) else None
    if isinstance(raw, str):
        return {part.strip() for part in raw.replace(",", " ").split() if part.strip()}
    if isinstance(raw, dict):
        return set()
    if isinstance(raw, Iterable):
        return {str(part).strip() for part in raw if str(part).strip()}
    return set()


def token_grants(data: dict, *accepted_scopes: str) -> bool:
    return bool(token_scopes(data).intersection(accepted_scopes))


def can_read_youtube(data: dict) -> bool:
    return token_grants(data, READONLY_SCOPE, FULL_YOUTUBE_SCOPE)


def can_upload_youtube(data: dict) -> bool:
    return token_grants(data, UPLOAD_SCOPE, FULL_YOUTUBE_SCOPE)


def can_manage_comments(data: dict) -> bool:
    return token_grants(data, COMMENTS_SCOPE, FULL_YOUTUBE_SCOPE)


def can_read_analytics(data: dict) -> bool:
    analytics_scope = token_grants(data, ANALYTICS_SCOPE, ANALYTICS_MONETARY_SCOPE)
    return analytics_scope and can_read_youtube(data)


def token_capabilities(data: dict) -> dict[str, bool]:
    return {
        "upload": can_upload_youtube(data),
        "readonly": can_read_youtube(data),
        "comments": can_manage_comments(data),
        "analytics": can_read_analytics(data),
    }


def credentials_from_token_info(
    info: YouTubeTokenInfo,
    scopes: list[str],
    *,
    refresh: bool = True,
    persist_refresh: bool = True,
) -> Credentials:
    if not info.present:
        raise FileNotFoundError(token_status_message(info))
    creds = Credentials.from_authorized_user_info(info.data, scopes)
    if not creds.valid:
        if refresh and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            if persist_refresh and info.persistable:
                info.token_file.write_text(creds.to_json(), encoding="utf-8")
                try:
                    info.data = _parse_token_json(creds.to_json())
                except Exception:
                    pass
        else:
            raise RuntimeError("YouTube credentials are invalid. Run auth_youtube.py again and update YOUTUBE_TOKEN.")
    return creds


def token_issue_codes(info: YouTubeTokenInfo) -> list[str]:
    if info.present:
        return []
    return list(info.errors) or ["youtube_token_missing"]


def token_status_message(info: YouTubeTokenInfo) -> str:
    if info.source == "file":
        return f"YouTube token loaded from {info.token_file.name}"
    if info.source == "env":
        return f"YouTube token loaded from {info.env_var}"
    if info.errors:
        return "YouTube token data is invalid: " + ", ".join(info.errors)
    return f"YouTube token missing from {info.token_file.name} and {info.env_var}"


def redacted_token_diagnostics(info: YouTubeTokenInfo) -> dict:
    data = info.data if isinstance(info.data, dict) else {}
    client_id = str(data.get("client_id") or "")
    scopes = sorted(token_scopes(data))
    return {
        "source": info.source,
        "present": info.present,
        "token_file_exists": info.token_file.exists(),
        "env_var": info.env_var,
        "errors": list(info.errors),
        "scopes": scopes,
        "capabilities": token_capabilities(data),
        "has_refresh_token": bool(data.get("refresh_token")),
        "expiry": str(data.get("expiry") or ""),
        "client_id_suffix": client_id[-8:] if client_id else "",
    }
