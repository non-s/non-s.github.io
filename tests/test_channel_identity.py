"""Testes para utils/channel_identity.py."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import utils.channel_identity as ci

_NOW = datetime(2026, 8, 3, tzinfo=UTC)
_WEEK = _NOW.isocalendar().week


@pytest.fixture(autouse=True)
def _isolate_state_file(tmp_path: Path, monkeypatch):
    """Isola identity.json em tmp_path para nao poluir o repo."""
    monkeypatch.setattr(ci, "_state_file", lambda: tmp_path / "identity.json")


def _channel(description: str = "", keywords: str = "", country: str | None = None) -> dict:
    channel: dict = {"id": "UC123"}
    bs_channel: dict = {"description": description, "keywords": keywords}
    if country:
        bs_channel["country"] = country
    channel["brandingSettings"] = {"channel": bs_channel}
    return channel


def _service(channel: dict):
    svc = MagicMock()
    svc.channels.return_value.list.return_value.execute.return_value = {"items": [channel]}
    return svc


def _identity_run(**kwargs) -> dict:
    """Roda run_identity_update com retry local e identidade canônica."""
    kwargs.setdefault("retry_call", lambda f: f())
    kwargs.setdefault("now", _NOW)
    return ci.run_identity_update(*[], **kwargs)


class TestIdentityTargets:
    def test_deterministic_by_week(self):
        assert ci.identity_targets(31) == ci.identity_targets(31)

    def test_is_stable_across_weeks(self):
        assert ci.identity_targets(31)["description"] == ci.identity_targets(32)["description"]

    def test_keywords_include_base_tags_and_extras(self):
        target = ci.identity_targets(4)
        keywords = target["keywords"]
        for tag in ("cat", "jazz"):
            assert tag in keywords
        assert "pet relaxation music" in keywords

    def test_keywords_within_limit(self):
        for week in range(1, 54):
            assert len(ci.identity_targets(week)["keywords"]) <= ci._KEYWORDS_LIMIT

    def test_description_within_limit(self):
        assert len(ci.identity_targets(1)["description"]) <= ci._DESCRIPTION_LIMIT


class TestNeedsUpdate:
    def test_identical_is_false(self):
        target = {"description": "  same  ", "keywords": "a, b"}
        current = {"description": "same", "keywords": "a, b"}
        assert ci.needs_update(current, target) is False

    def test_description_change_is_true(self):
        assert ci.needs_update({"description": "a"}, {"description": "b"}) is True

    def test_keywords_change_is_true(self):
        assert ci.needs_update({"keywords": "a"}, {"keywords": "b"}) is True


class TestCurrentBranding:
    def test_extracts_fields(self):
        current = ci._current_branding(_channel(description="d", keywords="k"))
        assert current == {"description": "d", "keywords": "k"}

    def test_missing_branding(self):
        assert ci._current_branding({}) == {"description": "", "keywords": ""}


class TestApplyUpdate:
    def test_preserves_other_branding_fields(self):
        service = _service(_channel(country="US"))
        target = {"description": "novo", "keywords": "novo, jazz"}
        ci.apply_update(service, "UC123", _channel(country="US"), target, retry_call=lambda f: f())

        call = service.channels.return_value.update
        _, kwargs = call.call_args
        assert kwargs["part"] == "brandingSettings"
        body = kwargs["body"]
        assert body["id"] == "UC123"
        assert body["brandingSettings"]["channel"]["description"] == "novo"
        assert body["brandingSettings"]["channel"]["keywords"] == "novo, jazz"
        assert body["brandingSettings"]["channel"]["country"] == "US"

    def test_uses_retry_call(self):
        calls = []

        def retry_call(func):
            calls.append(func)
            return func()

        service = _service(_channel())
        ci.apply_update(service, "UC123", _channel(), {"description": "d", "keywords": "k"}, retry_call=retry_call)
        assert len(calls) == 1


class TestRunIdentityUpdate:
    def test_dry_run_does_not_update(self):
        svc = _service(_channel(description="velha"))
        report = _identity_run(service=svc, channel_id="UC123", dry_run=True)
        assert report["dry_run"] is True
        assert report["changed"] is True
        assert report["updated"] is False
        svc.channels.return_value.update.assert_not_called()

    def test_updates_when_changed_and_new_week(self):
        svc = _service(_channel(description="velha"))
        report = _identity_run(service=svc, channel_id="UC123")
        assert report["updated"] is True
        svc.channels.return_value.update.assert_called_once()

    def test_skips_when_same_week(self):
        svc = _service(_channel(description="velha"))
        _identity_run(service=svc, channel_id="UC123")
        svc.channels.return_value.update.reset_mock()

        second = _identity_run(service=svc, channel_id="UC123")
        assert second["updated"] is False
        svc.channels.return_value.update.assert_not_called()

    def test_skips_when_not_changed(self):
        target = ci.identity_targets(_WEEK)
        svc = _service(_channel(description=target["description"], keywords=target["keywords"]))
        report = _identity_run(service=svc, channel_id="UC123")
        assert report["changed"] is False
        assert report["updated"] is False
        svc.channels.return_value.update.assert_not_called()

    def test_force_updates_even_same_week(self):
        svc = _service(_channel(description="velha"))
        _identity_run(service=svc, channel_id="UC123")
        svc.channels.return_value.update.reset_mock()

        forced = _identity_run(service=svc, channel_id="UC123", force=True)
        assert forced["updated"] is True
        svc.channels.return_value.update.assert_called_once()

    def test_raises_when_no_channel(self):
        svc = MagicMock()
        svc.channels.return_value.list.return_value.execute.return_value = {"items": []}
        with pytest.raises(RuntimeError, match="Nenhum canal"):
            _identity_run(service=svc, channel_id="UC123")

    def test_persists_state(self, tmp_path: Path):
        svc = _service(_channel(description="velha"))
        _identity_run(service=svc, channel_id="UC123")
        state = ci._load_state()
        assert "variant_week" in state
        assert state["description"] == ci.identity_targets(_WEEK)["description"]
