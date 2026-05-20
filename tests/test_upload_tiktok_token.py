"""Tests for upload_tiktok token refresh + GitHub Secrets persistence."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

import upload_tiktok


# ── _is_token_expired ──────────────────────────────────────────────

def test_fresh_token_without_timestamp_is_trusted():
    """Token straight from auth_tiktok.py (pre-issued_at era, no
    timestamps yet) must NOT trigger a preemptive refresh — that would
    burn the single-use refresh_token before we even need it."""
    token = {
        "access_token":  "a",
        "refresh_token": "r",
        "expires_in":    86400,
    }
    assert upload_tiktok._is_token_expired(token) is False


def test_token_without_expires_in_is_considered_expired():
    """No TTL → can't reason about freshness → refresh to be safe."""
    token = {
        "access_token":  "a",
        "refresh_token": "r",
        "issued_at":     datetime.now(timezone.utc).isoformat(),
    }
    assert upload_tiktok._is_token_expired(token) is True


def test_recent_issued_at_is_not_expired():
    token = {
        "access_token":  "a",
        "refresh_token": "r",
        "expires_in":    86400,
        "issued_at":     datetime.now(timezone.utc).isoformat(),
    }
    assert upload_tiktok._is_token_expired(token) is False


def test_stale_refreshed_at_is_expired():
    long_ago = datetime.now(timezone.utc) - timedelta(hours=25)
    token = {
        "access_token":  "a",
        "refresh_token": "r",
        "expires_in":    86400,   # 24h
        "refreshed_at":  long_ago.isoformat(),
    }
    assert upload_tiktok._is_token_expired(token) is True


def test_refreshed_at_takes_precedence_over_issued_at():
    """If both timestamps exist, the more recent _refresh_access_token
    stamp is authoritative."""
    now = datetime.now(timezone.utc)
    token = {
        "access_token":  "a",
        "refresh_token": "r",
        "expires_in":    86400,
        "issued_at":     (now - timedelta(hours=25)).isoformat(),  # stale
        "refreshed_at":  now.isoformat(),                          # fresh
    }
    assert upload_tiktok._is_token_expired(token) is False


# ── _persist_token_to_github_secret ────────────────────────────────

def test_persist_skips_when_pat_missing(monkeypatch):
    monkeypatch.delenv("TIKTOK_SECRETS_PAT", raising=False)
    monkeypatch.setenv("GH_REPO_FULL", "owner/repo")
    assert upload_tiktok._persist_token_to_github_secret({"x": 1}) is False


def test_persist_skips_when_repo_missing(monkeypatch):
    monkeypatch.setenv("TIKTOK_SECRETS_PAT", "pat")
    monkeypatch.delenv("GH_REPO_FULL", raising=False)
    assert upload_tiktok._persist_token_to_github_secret({"x": 1}) is False


def test_persist_round_trips_through_github_secrets_api(monkeypatch):
    """Happy path: fetch public key, encrypt, PUT — verify both
    requests carry the expected payload shape."""
    pytest.importorskip("nacl")
    monkeypatch.setenv("TIKTOK_SECRETS_PAT", "ghp_fake")
    monkeypatch.setenv("GH_REPO_FULL", "owner/repo")

    # Generate a real libsodium keypair so encryption succeeds end-to-end.
    from nacl import encoding, public
    sk = public.PrivateKey.generate()
    pk_b64 = sk.public_key.encode(encoder=encoding.Base64Encoder).decode()

    calls = {"get": None, "put": None}

    def _fake_get(url, headers=None, timeout=None):
        calls["get"] = (url, headers)
        r = MagicMock(status_code=200)
        r.json.return_value = {"key_id": "kid-123", "key": pk_b64}
        return r

    def _fake_put(url, headers=None, json=None, timeout=None):
        calls["put"] = (url, headers, json)
        return MagicMock(status_code=204)

    monkeypatch.setattr(upload_tiktok.requests, "get", _fake_get)
    monkeypatch.setattr(upload_tiktok.requests, "put", _fake_put)

    ok = upload_tiktok._persist_token_to_github_secret(
        {"access_token": "a", "refresh_token": "r"}
    )
    assert ok is True
    assert calls["get"][0].endswith("/actions/secrets/public-key")
    assert calls["put"][0].endswith("/actions/secrets/TIKTOK_TOKEN")
    body = calls["put"][2]
    assert body["key_id"] == "kid-123"
    assert isinstance(body["encrypted_value"], str)
    assert len(body["encrypted_value"]) > 0


def test_persist_warns_but_returns_false_on_404(monkeypatch):
    pytest.importorskip("nacl")
    monkeypatch.setenv("TIKTOK_SECRETS_PAT", "ghp_fake")
    monkeypatch.setenv("GH_REPO_FULL", "owner/repo")
    r = MagicMock(status_code=404, text="not found")
    monkeypatch.setattr(upload_tiktok.requests, "get", lambda *a, **kw: r)
    assert upload_tiktok._persist_token_to_github_secret({"x": 1}) is False


def test_persist_called_after_successful_refresh(monkeypatch, tmp_path):
    """End-to-end glue: a successful refresh must trigger the secrets
    persist call. This is the guard against the design bug — without
    it the bot would silently lose the rotated refresh_token."""
    pytest.importorskip("nacl")
    token = {
        "access_token":  "old-a",
        "refresh_token": "old-r",
        "client_key":    "ck",
    }
    monkeypatch.setenv("TIKTOK_CLIENT_SECRET", "cs")
    monkeypatch.setattr(upload_tiktok, "TOKEN_FILE", tmp_path / "t.json")

    resp = MagicMock(status_code=200)
    resp.json.return_value = {
        "access_token":  "new-a",
        "refresh_token": "new-r",
        "expires_in":    86400,
        "scope":         "video.publish",
    }
    resp.raise_for_status = lambda: None

    called_with: dict[str, dict] = {}

    def _spy(tok):
        called_with["token"] = tok
        return True

    monkeypatch.setattr(upload_tiktok.requests, "post", lambda *a, **kw: resp)
    monkeypatch.setattr(upload_tiktok, "_persist_token_to_github_secret", _spy)

    new = upload_tiktok._refresh_access_token(token)
    assert new["refresh_token"] == "new-r"
    assert called_with["token"]["refresh_token"] == "new-r"
