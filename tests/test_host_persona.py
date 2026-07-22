"""Tests for utils/host_persona.py."""

from __future__ import annotations

import json

from utils import host_persona
from utils.host_persona import HostPersona


def test_default_persona_has_required_fields():
    p = HostPersona()
    assert p.name
    assert p.pov
    assert p.intro_line == ""
    assert p.outro_line
    assert p.catchphrases
    assert "{name}" in p.first_comment_template


def test_load_returns_defaults_without_file(tmp_path, monkeypatch):
    monkeypatch.setattr(host_persona, "PERSONA_FILE", tmp_path / "x.json")
    p = host_persona.load()
    assert p.name == "Amber Hours"


def test_load_merges_partial_override(tmp_path, monkeypatch):
    f = tmp_path / "p.json"
    f.write_text(json.dumps({"name": "Beatriz", "handle": "amberhours_alt"}), encoding="utf-8")
    monkeypatch.setattr(host_persona, "PERSONA_FILE", f)
    p = host_persona.load()
    assert p.name == "Beatriz"
    assert p.handle == "amberhours_alt"
    # Defaults preserved for fields the file didn't override.
    # The default intro_line is intentionally short (â‰¤ 1 s of audio)
    # so the hook lands inside YouTube's first-2-second engagement
    # window without burning half of it on branding.
    assert p.intro_line == ""


def test_load_handles_malformed_json(tmp_path, monkeypatch):
    f = tmp_path / "p.json"
    f.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(host_persona, "PERSONA_FILE", f)
    p = host_persona.load()
    assert p.name == "Amber Hours"  # default


def test_load_rejects_non_list_catchphrases(tmp_path, monkeypatch):
    f = tmp_path / "p.json"
    f.write_text(json.dumps({"catchphrases": "not a list"}), encoding="utf-8")
    monkeypatch.setattr(host_persona, "PERSONA_FILE", f)
    p = host_persona.load()
    # Type mismatch preserves the default list.
    assert isinstance(p.catchphrases, list)
    assert p.catchphrases  # non-empty default


def test_save_writes_canonical_json(tmp_path, monkeypatch):
    f = tmp_path / "p.json"
    monkeypatch.setattr(host_persona, "PERSONA_FILE", f)
    persona = HostPersona(name="Test", handle="testchan")
    host_persona.save(persona)
    assert f.exists()
    body = json.loads(f.read_text(encoding="utf-8"))
    assert body["name"] == "Test"
    assert body["handle"] == "testchan"


def test_system_prompt_overlay_includes_voice_directive():
    overlay = host_persona.system_prompt_overlay()
    assert "amber hours" in overlay.lower()
    # Must explicitly forbid AI/bot self-reference and third-party promotion.
    assert "ai" in overlay.lower() or "bot" in overlay.lower()
    assert "third party" in overlay.lower() or "third-party" in overlay.lower()


def test_system_prompt_overlay_includes_catchphrases(tmp_path, monkeypatch):
    monkeypatch.setattr(host_persona, "PERSONA_FILE", tmp_path / "p.json")
    overlay = host_persona.system_prompt_overlay()
    # At least one of the default catchphrases should appear.
    p = host_persona.load()
    assert any(c in overlay for c in p.catchphrases)


def test_first_comment_text_substitutes_name():
    text = host_persona.first_comment_text(HostPersona(name="Camila"))
    assert "Camila" in text


def test_first_comment_text_substitutes_handle():
    text = host_persona.first_comment_text(HostPersona(handle="myhandle"))
    # Template doesn't currently emit the handle but exposes it as a
    # format kwarg â€” ensure no KeyError.
    assert isinstance(text, str)
    assert text
