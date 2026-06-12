import json

from scripts.youtube_auth_doctor import build_report
from utils.youtube_oauth import (
    ANALYTICS_SCOPE,
    COMMENTS_SCOPE,
    FULL_YOUTUBE_SCOPE,
    READONLY_SCOPE,
    TOKEN_ENV,
    UPLOAD_SCOPE,
    load_token_info,
    redacted_token_diagnostics,
    token_capabilities,
)


def _token(scopes):
    return {
        "token": "access-secret",
        "refresh_token": "refresh-secret",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "client-id-12345678",
        "client_secret": "client-secret",
        "scopes": scopes,
    }


def test_loads_token_from_env_when_file_is_missing(monkeypatch, tmp_path):
    token = _token([UPLOAD_SCOPE, READONLY_SCOPE, COMMENTS_SCOPE, ANALYTICS_SCOPE])
    monkeypatch.setenv(TOKEN_ENV, json.dumps(token))

    info = load_token_info(tmp_path / "youtube_token.json")

    assert info.source == "env"
    assert info.data["refresh_token"] == "refresh-secret"
    assert token_capabilities(info.data) == {
        "upload": True,
        "readonly": True,
        "comments": True,
        "analytics": True,
    }


def test_loads_token_file_before_env(monkeypatch, tmp_path):
    token_file = tmp_path / "youtube_token.json"
    token_file.write_text(json.dumps(_token([READONLY_SCOPE])), encoding="utf-8")
    monkeypatch.setenv(TOKEN_ENV, json.dumps(_token([UPLOAD_SCOPE])))

    info = load_token_info(token_file)

    assert info.source == "file"
    assert token_capabilities(info.data)["readonly"] is True
    assert token_capabilities(info.data)["upload"] is False


def test_full_youtube_scope_covers_data_and_comments_but_not_studio_analytics():
    capabilities = token_capabilities(_token([FULL_YOUTUBE_SCOPE]))

    assert capabilities["upload"] is True
    assert capabilities["readonly"] is True
    assert capabilities["comments"] is True
    assert capabilities["analytics"] is False


def test_redacted_diagnostics_hide_token_material(monkeypatch, tmp_path):
    token = _token([UPLOAD_SCOPE, READONLY_SCOPE, COMMENTS_SCOPE, ANALYTICS_SCOPE])
    monkeypatch.setenv(TOKEN_ENV, json.dumps(token))
    info = load_token_info(tmp_path / "missing.json")

    diagnostics = redacted_token_diagnostics(info)
    report = build_report(tmp_path / "missing.json")
    dumped = json.dumps({"diagnostics": diagnostics, "report": report})

    assert "access-secret" not in dumped
    assert "refresh-secret" not in dumped
    assert "client-secret" not in dumped
    assert "client-id-12345678" not in dumped
    assert diagnostics["client_id_suffix"] == "12345678"
    assert report["status"] == "ok"
