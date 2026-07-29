"""Testes para scripts/tiktok_cookies_to_state.py — conversao de cookies
exportados (Cookie-Editor) para o storage_state do Playwright."""

from __future__ import annotations

import json

import scripts.tiktok_cookies_to_state as tiktok_cookies_to_state


def _raw_cookie(**overrides) -> dict:
    base = {
        "name": "sessionid",
        "value": "abc123",
        "domain": ".tiktok.com",
        "path": "/",
        "expirationDate": 1999999999.0,
        "httpOnly": True,
        "secure": True,
        "sameSite": "no_restriction",
    }
    base.update(overrides)
    return base


class TestConvertCookie:
    def test_converts_expected_fields(self):
        result = tiktok_cookies_to_state._convert_cookie(_raw_cookie())
        assert result == {
            "name": "sessionid",
            "value": "abc123",
            "domain": ".tiktok.com",
            "path": "/",
            "expires": 1999999999.0,
            "httpOnly": True,
            "secure": True,
            "sameSite": "None",
        }

    def test_maps_lax_and_strict(self):
        assert tiktok_cookies_to_state._convert_cookie(_raw_cookie(sameSite="lax"))["sameSite"] == "Lax"
        assert tiktok_cookies_to_state._convert_cookie(_raw_cookie(sameSite="strict"))["sameSite"] == "Strict"

    def test_unknown_same_site_falls_back_to_lax(self):
        assert tiktok_cookies_to_state._convert_cookie(_raw_cookie(sameSite="unspecified"))["sameSite"] == "Lax"
        assert tiktok_cookies_to_state._convert_cookie(_raw_cookie(sameSite=""))["sameSite"] == "Lax"

    def test_missing_expiration_date_means_session_cookie(self):
        raw = _raw_cookie()
        del raw["expirationDate"]
        assert tiktok_cookies_to_state._convert_cookie(raw)["expires"] == -1

    def test_missing_name_returns_none(self):
        raw = _raw_cookie()
        del raw["name"]
        assert tiktok_cookies_to_state._convert_cookie(raw) is None

    def test_missing_value_returns_none(self):
        raw = _raw_cookie()
        del raw["value"]
        assert tiktok_cookies_to_state._convert_cookie(raw) is None

    def test_missing_domain_returns_none(self):
        raw = _raw_cookie()
        del raw["domain"]
        assert tiktok_cookies_to_state._convert_cookie(raw) is None

    def test_defaults_path_to_root(self):
        raw = _raw_cookie()
        del raw["path"]
        assert tiktok_cookies_to_state._convert_cookie(raw)["path"] == "/"


class TestMain:
    def test_missing_argument_returns_1(self, monkeypatch):
        monkeypatch.setattr(tiktok_cookies_to_state.sys, "argv", ["prog"])
        assert tiktok_cookies_to_state.main() == 1

    def test_nonexistent_file_returns_1(self, monkeypatch, tmp_path):
        monkeypatch.setattr(tiktok_cookies_to_state.sys, "argv", ["prog", str(tmp_path / "missing.json")])
        assert tiktok_cookies_to_state.main() == 1

    def test_invalid_json_returns_1(self, monkeypatch, tmp_path):
        src = tmp_path / "bad.json"
        src.write_text("not valid json", encoding="utf-8")
        monkeypatch.setattr(tiktok_cookies_to_state.sys, "argv", ["prog", str(src)])
        assert tiktok_cookies_to_state.main() == 1

    def test_non_list_json_returns_1(self, monkeypatch, tmp_path):
        src = tmp_path / "obj.json"
        src.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
        monkeypatch.setattr(tiktok_cookies_to_state.sys, "argv", ["prog", str(src)])
        assert tiktok_cookies_to_state.main() == 1

    def test_no_tiktok_cookies_returns_1(self, monkeypatch, tmp_path):
        src = tmp_path / "export.json"
        src.write_text(json.dumps([_raw_cookie(domain=".example.com")]), encoding="utf-8")
        monkeypatch.setattr(tiktok_cookies_to_state.sys, "argv", ["prog", str(src)])
        assert tiktok_cookies_to_state.main() == 1

    def test_success_writes_state_file(self, monkeypatch, tmp_path):
        src = tmp_path / "export.json"
        src.write_text(
            json.dumps([_raw_cookie(), _raw_cookie(name="tt_csrf_token", domain=".example.com")]),
            encoding="utf-8",
        )
        state_path = tmp_path / "tiktok_state.json"
        monkeypatch.setattr(tiktok_cookies_to_state, "DEFAULT_STATE_PATH", state_path)
        monkeypatch.setattr(tiktok_cookies_to_state.sys, "argv", ["prog", str(src)])

        assert tiktok_cookies_to_state.main() == 0

        saved = json.loads(state_path.read_text(encoding="utf-8"))
        assert saved["origins"] == []
        assert len(saved["cookies"]) == 1
        assert saved["cookies"][0]["name"] == "sessionid"

    def test_ignores_non_dict_entries(self, monkeypatch, tmp_path):
        src = tmp_path / "export.json"
        src.write_text(json.dumps([_raw_cookie(), "not-a-dict", 42]), encoding="utf-8")
        state_path = tmp_path / "tiktok_state.json"
        monkeypatch.setattr(tiktok_cookies_to_state, "DEFAULT_STATE_PATH", state_path)
        monkeypatch.setattr(tiktok_cookies_to_state.sys, "argv", ["prog", str(src)])

        assert tiktok_cookies_to_state.main() == 0
        saved = json.loads(state_path.read_text(encoding="utf-8"))
        assert len(saved["cookies"]) == 1
