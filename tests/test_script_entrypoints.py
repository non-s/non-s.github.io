"""Contract tests for operational command entrypoints.

The domain modules have focused unit tests.  These tests protect the thin CLI
layer as well, because that is the layer GitHub Actions actually invokes.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from scripts import (
    collect_competitive_intelligence,
    collect_open_research,
    generate_editorial_calendar,
    refresh_oauth_token,
    respond_comments,
    run_agency_council,
)


def test_collect_competitive_intelligence_main(monkeypatch, capsys):
    service = object()
    report = {"channels": [{"id": "one"}]}
    save = MagicMock()
    monkeypatch.setattr(collect_competitive_intelligence, "configure_logging", MagicMock())
    monkeypatch.setattr(collect_competitive_intelligence, "get_youtube_service", lambda: service)
    monkeypatch.setattr(
        collect_competitive_intelligence,
        "collect_competitive_intelligence",
        lambda actual: report if actual is service else None,
    )
    monkeypatch.setattr(collect_competitive_intelligence, "save_competitive_intelligence", save)

    assert collect_competitive_intelligence.main() == 0
    save.assert_called_once_with(report)
    assert "1 channels" in capsys.readouterr().out


def test_collect_open_research_tolerates_each_provider_failure(monkeypatch):
    monkeypatch.setattr(collect_open_research, "QUERIES", ("cat", "dog"))
    monkeypatch.setattr(
        collect_open_research,
        "species_card",
        lambda query: {"name": query} if query == "cat" else (_ for _ in ()).throw(RuntimeError("gbif")),
    )
    monkeypatch.setattr(
        collect_open_research,
        "search_open_images",
        lambda query: [{"title": query}] if query == "dog" else (_ for _ in ()).throw(RuntimeError("openverse")),
    )

    report = collect_open_research.collect_open_research()
    assert report["species_research"] == [{"name": "cat"}]
    assert report["media_candidates"] == {"dog": [{"title": "dog"}]}
    assert report["generated_at"].endswith("+00:00")


def test_collect_open_research_main_writes_catalog(tmp_path, monkeypatch):
    monkeypatch.setattr(collect_open_research, "data_dir", lambda: tmp_path)
    monkeypatch.setattr(collect_open_research, "collect_open_research", lambda: {"ok": True})

    assert collect_open_research.main() == 0
    assert json.loads((tmp_path / "open_research_catalog.json").read_text()) == {"ok": True}


def test_generate_editorial_calendar_main(tmp_path, monkeypatch):
    monkeypatch.setattr(generate_editorial_calendar, "data_dir", lambda: tmp_path)
    monkeypatch.setattr(
        generate_editorial_calendar,
        "build_calendar",
        lambda start, days: [{"date": start.isoformat(), "days": days}],
    )

    assert generate_editorial_calendar.main(["--days", "7", "--start", "2026-08-13"]) == 0
    payload = json.loads((tmp_path / "editorial_calendar.json").read_text())
    assert payload == {
        "start": "2026-08-13",
        "days": 7,
        "items": [{"date": "2026-08-13", "days": 7}],
    }


def test_generate_editorial_calendar_rejects_invalid_days():
    try:
        generate_editorial_calendar.main(["--days", "0"])
    except SystemExit as exc:
        assert exc.code == 2
    else:  # pragma: no cover - argparse must terminate
        raise AssertionError("invalid --days was accepted")


def test_run_agency_council_main(monkeypatch, capsys):
    monkeypatch.setattr(run_agency_council, "configure_logging", MagicMock())
    monkeypatch.setattr(run_agency_council, "run_daily_council", lambda: {"consensus": {"decision": "review"}})

    assert run_agency_council.main() == 0
    assert json.loads(capsys.readouterr().out) == {"decision": "review"}


def test_respond_comments_guard_and_channel_lookup(monkeypatch):
    monkeypatch.delenv("LIQUID_WIRE_ENABLED", raising=False)
    monkeypatch.delenv("LIQUID_WIRE_COMMENTS_ENABLED", raising=False)
    monkeypatch.setattr("sys.argv", ["respond-comments"])
    assert respond_comments.main() == 0

    service = MagicMock()
    service.channels().list.return_value.execute.return_value = {"items": [{"id": "UC123"}]}
    assert respond_comments._own_channel_id(service) == "UC123"
    service.channels().list.return_value.execute.return_value = {"items": []}
    try:
        respond_comments._own_channel_id(service)
    except RuntimeError as exc:
        assert "Nenhum canal" in str(exc)
    else:  # pragma: no cover - the empty response must be rejected
        raise AssertionError("empty channel response was accepted")


def test_respond_comments_success_and_failure(monkeypatch):
    service = MagicMock()
    monkeypatch.setattr(respond_comments, "configure_logging", MagicMock())
    monkeypatch.setattr(respond_comments, "get_youtube_service", lambda: service)
    monkeypatch.setattr(respond_comments, "_own_channel_id", lambda _service: "UC123")
    monkeypatch.setattr(respond_comments, "record_pipeline_run", pipeline := MagicMock())
    monkeypatch.setattr("sys.argv", ["respond-comments", "--no-guard", "--dry-run", "--max-replies", "2"])
    monkeypatch.setattr(
        respond_comments,
        "run_comment_engagement",
        lambda *_args, **_kwargs: {"fetched": 4, "candidates": 2, "replied": 2, "failed": 0},
    )
    assert respond_comments.main() == 0
    assert pipeline.call_args.kwargs["success"] is True

    monkeypatch.setattr(respond_comments, "get_youtube_service", MagicMock(side_effect=RuntimeError("oauth")))
    monkeypatch.setattr(respond_comments, "log_exception_to_file", logged := MagicMock())
    assert respond_comments.main() == 1
    logged.assert_called_once()
    assert pipeline.call_args.kwargs["success"] is False


_VALID_TOKEN_JSON = (
    '{"token":"new","refresh_token":"rt","client_id":"cid","client_secret":"cs"}'
)


def _fake_credentials(*, refresh_token: str | None = "refresh") -> MagicMock:
    credentials = MagicMock()
    credentials.refresh_token = refresh_token
    credentials.to_json.return_value = _VALID_TOKEN_JSON
    return credentials


def test_refresh_oauth_success(monkeypatch, tmp_path):
    token = tmp_path / "youtube_token.json"
    token.write_text("{}")
    credentials = _fake_credentials()
    monkeypatch.setattr(refresh_oauth_token, "_load_token", lambda: credentials)
    monkeypatch.setattr(refresh_oauth_token, "_save_token", saved := MagicMock())
    monkeypatch.setattr(refresh_oauth_token, "_gh_secret_set", secret_set := MagicMock(return_value=0))
    monkeypatch.setenv("GH_PAT", "test-pat")

    assert refresh_oauth_token.refresh_and_persist(token, "YOUTUBE_TOKEN", "liquid_wire") == 0
    credentials.refresh.assert_called_once()
    saved.assert_called_once_with(credentials, str(token))
    secret_set.assert_called_once_with("YOUTUBE_TOKEN", _VALID_TOKEN_JSON, "test-pat")


def test_refresh_oauth_failure_paths(monkeypatch, tmp_path):
    token = tmp_path / "youtube_token.json"
    monkeypatch.setattr(refresh_oauth_token, "_load_token", lambda: None)
    assert refresh_oauth_token.refresh_and_persist(token, "YOUTUBE_TOKEN", "liquid_wire") == 2

    monkeypatch.setattr(refresh_oauth_token, "_load_token", lambda: _fake_credentials(refresh_token=None))
    assert refresh_oauth_token.refresh_and_persist(token, "YOUTUBE_TOKEN", "liquid_wire") == 2

    credentials = _fake_credentials()
    credentials.refresh.side_effect = RuntimeError("expired")
    monkeypatch.setattr(refresh_oauth_token, "_load_token", lambda: credentials)
    monkeypatch.setattr(refresh_oauth_token, "_open_issue_token_expired", opened := MagicMock())
    assert refresh_oauth_token.refresh_and_persist(token, "YOUTUBE_TOKEN", "liquid_wire") == 1
    opened.assert_called_once()


def test_refresh_oauth_rejects_invalid_token_json(monkeypatch, tmp_path):
    """to_json() retornando JSON invalido/vazio NAO deve sobrescrever o secret."""
    token = tmp_path / "youtube_token.json"
    token.write_text("{}")
    credentials = _fake_credentials()
    monkeypatch.setattr(refresh_oauth_token, "_load_token", lambda: credentials)
    monkeypatch.setattr(refresh_oauth_token, "_save_token", MagicMock())
    monkeypatch.setattr(refresh_oauth_token, "_open_issue_token_expired", opened := MagicMock())
    monkeypatch.setenv("GH_PAT", "test-pat")

    for bad_json in ("", "   ", "{", "not-json", "{}", '{"token":"x"}'):
        credentials.to_json.return_value = bad_json
        monkeypatch.setattr(
            refresh_oauth_token, "_gh_secret_set", MagicMock(return_value=0)
        )
        assert refresh_oauth_token.refresh_and_persist(token, "YOUTUBE_TOKEN", "liquid_wire") == 1
        opened.assert_called()

    opened.reset_mock()
    for bad_json in ("", "   ", "null", "[]", "123", '{"token":"x"}'):
        assert refresh_oauth_token._validate_token_json(bad_json) is False
    assert refresh_oauth_token._validate_token_json(_VALID_TOKEN_JSON) is True


def test_refresh_oauth_requires_pat_and_handles_cli_failure(monkeypatch, tmp_path):
    token = tmp_path / "youtube_token.json"
    credentials = _fake_credentials()
    monkeypatch.setattr(refresh_oauth_token, "_load_token", lambda: credentials)
    monkeypatch.setattr(refresh_oauth_token, "_save_token", MagicMock())
    monkeypatch.delenv("GH_PAT", raising=False)
    monkeypatch.setattr(refresh_oauth_token, "_open_issue_token_expired", opened := MagicMock())
    assert refresh_oauth_token.refresh_and_persist(token, "YOUTUBE_TOKEN", "liquid_wire") == 1
    opened.assert_called_once()

    monkeypatch.setenv("GH_PAT", "test-pat")
    monkeypatch.setattr(refresh_oauth_token, "_gh_secret_set", MagicMock(return_value=1))
    assert refresh_oauth_token.refresh_and_persist(token, "YOUTUBE_TOKEN", "liquid_wire") == 1


def test_refresh_oauth_main_requires_token(monkeypatch, tmp_path):
    missing = tmp_path / "missing.json"
    monkeypatch.setenv("YOUTUBE_TOKEN_PATH", str(missing))
    assert refresh_oauth_token.main() == 2

    missing.write_text("{}")
    monkeypatch.setattr(refresh_oauth_token, "refresh_and_persist", run := MagicMock(return_value=0))
    assert refresh_oauth_token.main() == 0
    run.assert_called_once_with(missing, "YOUTUBE_TOKEN", "liquid_wire")


def test_gh_secret_set_sends_secret_through_stdin(monkeypatch):
    completed = MagicMock(returncode=0, stderr="")
    monkeypatch.setattr(refresh_oauth_token.subprocess, "run", run := MagicMock(return_value=completed))

    assert refresh_oauth_token._gh_secret_set("YOUTUBE_TOKEN", "sensitive-json", "github-pat") == 0
    cmd = run.call_args.args[0]
    assert cmd[:4] == ["gh", "secret", "set", "YOUTUBE_TOKEN"]
    # The secret value must be piped via stdin, never on argv: the command
    # has no --body flag, so gh reads the value from standard input.
    assert "--body" not in cmd
    assert run.call_args.kwargs["input"] == "sensitive-json"
    assert run.call_args.kwargs["env"]["GH_TOKEN"] == "github-pat"
