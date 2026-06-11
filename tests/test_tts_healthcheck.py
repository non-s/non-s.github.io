from utils.tts_fallback import coqui_healthcheck


def test_tts_healthcheck_reports_unavailable_without_command(monkeypatch):
    monkeypatch.delenv("COQUI_TTS_COMMAND", raising=False)
    monkeypatch.setattr("utils.tts_fallback.shutil.which", lambda name: None)

    payload = coqui_healthcheck(synthesize=False)

    assert payload["status"] == "unavailable"
    assert payload["reason"] == "coqui_command_missing"


def test_tts_healthcheck_accepts_configured_command(monkeypatch):
    monkeypatch.setenv("COQUI_TTS_COMMAND", "tts")

    payload = coqui_healthcheck(synthesize=False)

    assert payload["status"] == "ok"
